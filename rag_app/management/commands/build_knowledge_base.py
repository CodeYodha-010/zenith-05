"""
Django Management Command: Build Knowledge Base v3
==================================================
Multi-granularity KB with:
- Page-level chunking (RecursiveCharacterTextSplitter, 1200 chars / 200 overlap)
- Document metadata extraction (topics, commodities, regulations, key facts)
- Async fact extraction (15 concurrent pages via asyncio)
- Multi-source index (summaries + chunks + metadata + facts)
- Vector embeddings for semantic search (NVIDIA EmbedQA)
- FAISS vector index for similarity search

Usage:
    python manage.py build_knowledge_base --clear --region india
    python manage.py build_knowledge_base --region eu
    python manage.py build_knowledge_base --clear

"""

import os
import re
import json
import time
import asyncio
import requests
import httpx
from pathlib import Path
from typing import List, Dict, Tuple, Optional
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from tqdm import tqdm

import fitz  # PyMuPDF
from docx import Document as DocxDocument
from langchain.text_splitter import RecursiveCharacterTextSplitter

from rag_app.models import Document, DocumentPage, SearchIndex, DocumentMetadata, FactIndex
from rag_app.services.nvidia_ocr_service import NvidiaOcrService
from rag_app.services.nvidia_embedding_service import NVIDIAEmbeddingService
from rag_app.services.opendataloader_service import OpenDataLoaderService
from rag_app.services.faiss_service import FAISSService
from rag_app.services.llm_service import NVIDIALLMService

# ── LLM API Config ──
# Model: meta/llama-3.3-70b-instruct (used for metadata and fact extraction)
LLM_MODEL = 'meta/llama-3.3-70b-instruct'

# ── Embedding Config ──
EMBEDDING_MODEL = 'nvidia/nemotron-3-embed-1b'

# ── Chunking Config ──
CHUNK_SIZE = 1200        # characters (~200-300 words)
CHUNK_OVERLAP = 200      # characters
MIN_CHUNK_CHARS = 200    # discard chunks smaller than this

# ── Async Pipeline Config ──
MAX_CONCURRENT_PAGES = 10   # Reduced from 15 to prevent loop overload
LLM_SEMAPHORE_LIMIT = 5    # Reduced from 8 to prevent API Rate Limits (429)


class Command(BaseCommand):
    help = 'Build knowledge base v3 with async metadata + fact extraction + page-level chunking + embeddings + FAISS'

    def __init__(self):
        super().__init__()
        self.knowledge_base_root = Path(__file__).resolve().parent.parent.parent.parent / 'Knowlegebase'
        self.knowledge_base_dirs = {
            'eu': self.knowledge_base_root / 'eu_official_documents_2026',
            'india': self.knowledge_base_root / 'rag_documents' / 'rag_documents',
            'us': self.knowledge_base_root / 'rag_us_documents' / 'rag_us_docs',
        }
        self.stats = {
            'processed': 0, 'failed': 0, 'pages': 0,
            'chunks': 0, 'facts': 0, 'metadata_docs': 0, 'ocr_pages': 0,
        }
        
        # Initialize services
        self.embedding_service = NVIDIAEmbeddingService()
        self.parser_service = OpenDataLoaderService()
        self.faiss_service = None  # Will be initialized with dimension after first embedding
        self.llm_service = NVIDIALLMService()

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true', help='Clear existing KB before building')
        parser.add_argument('--region', type=str, choices=['eu', 'india', 'us', 'all'], default='all',
                            help='Build KB for specific region only')

    # =========================================================================
    # MAIN ENTRY POINT
    # =========================================================================
    def handle(self, *args, **options):
        self.stdout.write('=' * 70)
        self.stdout.write('Building Knowledge Base v3')
        self.stdout.write('   - Page-level chunking (RecursiveCharacterTextSplitter)')
        self.stdout.write('   - Document metadata extraction')
        self.stdout.write('   - Async fact extraction (15 concurrent pages)')
        self.stdout.write('   - Vector embeddings for semantic search')
        self.stdout.write('   - FAISS vector index for similarity search')
        self.stdout.write('=' * 70)

        if options['clear']:
            self.stdout.write('\nClearing ALL existing knowledge base data...')
            FactIndex.objects.all().delete()
            SearchIndex.objects.all().delete()
            DocumentMetadata.objects.all().delete()
            DocumentPage.objects.all().delete()
            Document.objects.all().delete()
            self.stdout.write('Knowledge base cleared\n')

        # Collect files
        regions = ['eu', 'india', 'us'] if options['region'] == 'all' else [options['region']]
        all_files = []
        for region in regions:
            region_dir = self.knowledge_base_dirs.get(region)
            if not region_dir or not region_dir.exists():
                self.stdout.write(f'WARNING: Directory not found: {region_dir}')
                continue
            files = (list(region_dir.glob('*.pdf')) +
                     list(region_dir.glob('*.docx')) +
                     list(region_dir.glob('*.md')))
            all_files.extend([(f, region) for f in sorted(files)])
            self.stdout.write(f'[DIR] {region.upper()}: {len(files)} files')

        if not all_files:
            self.stdout.write('WARNING: No files found')
            return

        self.stdout.write(f'Total: {len(all_files)} files\n')

        # Process each file
        for file_path, region in all_files:
            try:
                if Document.objects.filter(file_path=str(file_path)).exists():
                    self.stdout.write(f'SKIP (already processed): {file_path.name}')
                    continue
                self.stdout.write(f'Processing: {file_path.name}')
                self.process_document(file_path, region)
                self.stats['processed'] += 1
            except Exception as e:
                self.stats['failed'] += 1
                self.stdout.write(f'Failed: {file_path.name} -- {e}')
                import traceback
                traceback.print_exc()

        # Summary
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write('BUILD SUMMARY')
        self.stdout.write('=' * 70)
        self.stdout.write(f'Documents processed: {self.stats["processed"]}')
        self.stdout.write(f'Failed:             {self.stats["failed"]}')
        self.stdout.write(f'Total pages:        {self.stats["pages"]}')
        self.stdout.write(f'Total chunks:       {self.stats["chunks"]}')
        self.stdout.write(f'Total facts:        {self.stats["facts"]}')
        self.stdout.write(f'Total metadata:     {self.stats["metadata_docs"]}')
        self.stdout.write(f'Total SearchIndex:  {SearchIndex.objects.count()}')
        self.stdout.write(f'Total FactIndex:   {FactIndex.objects.count()}')
        self.stdout.write('\nKnowledge Base v3 Built Successfully!')

    # =========================================================================
    # DOCUMENT PROCESSING PIPELINE
    # =========================================================================
    def process_document(self, file_path, region):
        """Full pipeline: extract → chunk → metadata → facts"""
        doc = Document.objects.create(
            title=file_path.stem,
            file_path=str(file_path),
            region=region,
        )

        # Step 1: Extract pages using parser service
        pages_data = self._extract_pages(file_path)
        self.stats['pages'] += len(pages_data)

        # Step 2: Create pages + summaries + chunks
        page_objects = []
        for page_num, page_text, is_ocr in pages_data:
            page_obj = DocumentPage.objects.create(
                document=doc,
                page_number=page_num,
                original_text=page_text,
            )
            page_objects.append((page_obj, page_text, is_ocr))

            # Summary (first 80 words — fast, no LLM call needed)
            summary = ' '.join(page_text.split()[:80]) + ('...' if len(page_text.split()) > 80 else '')
            page_obj.summary = summary
            page_obj.save(update_fields=['summary'])

            SearchIndex.objects.create(
                page=page_obj,
                content=summary,
                source_type='summary',
                is_ocr_generated=is_ocr,
            )

            # Page-level chunks
            chunk_count = self._create_chunks(page_text, doc.title, is_ocr, page_obj)
            self.stats['chunks'] += chunk_count

        # Step 3: Document metadata (1 LLM call per document)
        self._extract_document_metadata(doc, page_objects)
        self.stats['metadata_docs'] += 1

        # Step 4: Fact extraction (Skipped for speed/stability)
        fact_count = 0
        """
        all_facts = asyncio.run(self._extract_facts_async(page_objects))
        fact_count = len(all_facts)
        self.stats['facts'] += fact_count

        if all_facts:
            # ... save logic ...
            pass
        """

        # Update doc
        ocr_count = sum(1 for _, _, is_ocr in pages_data if is_ocr)
        if ocr_count > 0:
            doc.is_ocred = True
            doc.save(update_fields=['is_ocred'])
            self.stats['ocr_pages'] += ocr_count

        doc.processed_at = timezone.now()
        doc.save(update_fields=['processed_at'])
        
        # Step 5: Save FAISS index once per document (efficiency)
        if self.faiss_service:
            faiss_path = Path(settings.BASE_DIR) / 'faiss_index.index'
            self.faiss_service.save(str(faiss_path))

        self.stdout.write(f'  {doc.title}: {len(pages_data)} pages, '
                          f'{self.stats["chunks"]} chunks, {fact_count} facts')

    # =========================================================================
    # PAGE EXTRACTION USING PARSER SERVICE
    # =========================================================================
    def _extract_pages(self, file_path):
        """Extract pages from document using OpenDataLoader (primary) or local fallbacks."""
        suffix = file_path.suffix.lower()
        
        # Try OpenDataLoader first for PDF (best quality, local, free)
        if suffix == '.pdf':
            self.stdout.write(f'  [Parsing] Using OpenDataLoader for {file_path.name}...')
            try:
                odl_pages = self.parser_service.parse_document_sync(str(file_path))
                if odl_pages:
                    self.stdout.write(f'  [Parsing] OpenDataLoader success: {len(odl_pages)} pages')
                    return [(p['page_number'], p['text'], False) for p in odl_pages]
                else:
                    self.stdout.write(f'  [Parsing] OpenDataLoader returned no data, falling back...')
            except Exception as e:
                self.stdout.write(f'  [Parsing] OpenDataLoader failed: {e}, falling back...')

        # Local Fallbacks
        if suffix == '.pdf':
            return self._extract_pdf_pages(file_path)
        elif suffix == '.docx':
            return self._extract_docx_pages(file_path)
        elif suffix == '.md':
            return self._extract_markdown_pages(file_path)
        else:
            raise ValueError(f"Unsupported file type: {suffix}")

    def _extract_pdf_pages(self, file_path):
        """Extract text from PDF pages using PyMuPDF (primary) + NVIDIA OCR for scanned pages."""
        pages = []
        pdf_doc = fitz.open(str(file_path))
        ocr_service = None
        try:
            from rag_app.services.nvidia_ocr_service import NvidiaOcrService
            svc = NvidiaOcrService()
            if svc.api_key:
                ocr_service = svc
        except Exception:
            pass

        for page_num, page in enumerate(pdf_doc, 1):
            text = page.get_text().strip()
            is_scanned = len(text) < 50

            if is_scanned and ocr_service:
                self.stdout.write(f'  [OCR] Page {page_num}: Scanned -> OCR...')
                try:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    ocr_text, conf = ocr_service.extract_text_from_image(pix.tobytes("png"))
                    if ocr_text:
                        pages.append((page_num, ocr_text, True))
                        self.stdout.write(f'  [OCR] Page {page_num}: {len(ocr_text)} chars')
                    else:
                        pages.append((page_num, '[OCR FAILED]', True))
                except Exception as e:
                    self.stdout.write(f'  WARNING: OCR Page {page_num} failed: {e}')
                    pages.append((page_num, text if text else '[SCANNED]', False))
            elif is_scanned:
                pages.append((page_num, '[SCANNED - NO OCR]', False))
            else:
                pages.append((page_num, text, False))

        pdf_doc.close()
        return pages

    def _extract_docx_pages(self, file_path):
        """Extract text from DOCX file using python-docx (groups 5 paragraphs per page)."""
        try:
            doc = DocxDocument(str(file_path))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            pages = []
            current = []
            for i, para in enumerate(paragraphs):
                current.append(para)
                if len(current) >= 5 or i == len(paragraphs) - 1:
                    pages.append((len(pages) + 1, '\n\n'.join(current), False))
                    current = []
            return pages if pages else [(1, '', False)]
        except Exception as e:
            self.stdout.write(f'  DOCX extraction failed: {e}')
            return [(1, '', False)]

    def _extract_markdown_pages(self, file_path):
        """Extract text from Markdown file, split by headings into pages."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            sections = re.split(r'\n(?=#{1,2}\s)', content)
            pages = []
            for section in sections:
                if section.strip():
                    pages.append((len(pages) + 1, section.strip(), False))
            return pages if pages else [(1, content, False)]
        except Exception as e:
            self.stdout.write(f'  Markdown extraction failed: {e}')
            return [(1, '', False)]

    # =========================================================================
    # EMBEDDING AND FAISS INTEGRATION
    # =========================================================================
    def _generate_and_store_embeddings(self, chunk_objs):
        """
        Generate embeddings for chunks and store them in SearchIndex.
        Also updates FAISS index.
        """
        # Extract text from chunk objects
        texts = [chunk.content for chunk in chunk_objs]
        
        # Generate embeddings
        embeddings = self.embedding_service.embed_batch(texts)
        
        # Store embeddings in database and update FAISS index
        vectors = []
        for chunk_obj, embedding in zip(chunk_objs, embeddings):
            chunk_obj.embedding = embedding
            chunk_obj.embedding_model = EMBEDDING_MODEL
            vectors.append(embedding)
        
        # Bulk update database for speed
        from rag_app.models import SearchIndex
        SearchIndex.objects.bulk_update(chunk_objs, ['embedding', 'embedding_model'])
        
        # Initialize FAISS service if not already done
        if self.faiss_service is None:
            # Get dimension from first embedding
            dimension = len(vectors[0]) if vectors else 0
            self.faiss_service = FAISSService(dimension)
        
        # Add vectors to FAISS index (Memory only)
        self.faiss_service.add_vectors(vectors)
        # REMOVED: self.faiss_service.save() from per-page loop

    # =========================================================================
    # CHUNKING (Page-level RecursiveCharacterTextSplitter)
    # =========================================================================
    def _create_chunks(self, page_text: str, doc_title: str, is_ocr: bool, page_obj) -> int:
        """
        Split page text into overlapping chunks using RecursiveCharacterTextSplitter.
        Uses Markdown-aware separators for better semantic splitting.
        """
        if not page_text or len(page_text.strip()) < MIN_CHUNK_CHARS:
            return 0

        # Optimized separators for Markdown (LlamaParse output)
        separators = [
            "\n# ", "\n## ", "\n### ", "\n#### ",  # Headings
            "\n\n", "\n",                          # Paragraphs and lines
            "| ",                                  # Table rows
            ". ", "? ", "! ",                      # Sentences
            " ", ""                                # Words
        ]

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            length_function=len,
            separators=separators,
        )
        chunks = splitter.split_text(page_text)

        chunk_objs = []
        for i, chunk_text in enumerate(chunks):
            if len(chunk_text.strip()) < MIN_CHUNK_CHARS:
                continue
            
            # Find start position (approximate)
            try:
                char_start = page_text.find(chunk_text)
            except:
                char_start = 0

            chunk_obj = SearchIndex.objects.create(
                page=page_obj,
                content=chunk_text,
                source_type='chunk',
                chunk_level='child',
                is_ocr_generated=is_ocr,
                char_start=char_start if char_start >= 0 else 0,
            )
            chunk_objs.append(chunk_obj)

        # Generate embeddings for these chunks
        if chunk_objs and self.embedding_service:
            try:
                self._generate_and_store_embeddings(chunk_objs)
            except Exception as e:
                self.stdout.write(f'  WARNING: Embedding failed: {e}')

        return len(chunk_objs)

    # =========================================================================
    # DOCUMENT METADATA EXTRACTION (Phase 3)
    # =========================================================================
    def _extract_document_metadata(self, doc, page_objects):
        """
        Extract rich metadata for a document using a single LLM call.
        Analyzes first 5 pages to identify topics, commodities, regulations, key facts.
        """
        sample_text = '\n\n'.join([text for _, text, _ in page_objects[:5]])[:8000]

        prompt = f"""You are an expert trade compliance analyst. Analyze this document and return ONLY valid JSON.

DOCUMENT TITLE: {doc.title}
REGION: {doc.region}

DOCUMENT TEXT (first pages):
{sample_text}

Return JSON with EXACTLY these keys:
- "topics": ["list", "of", "main", "topics"]
- "commodities": ["list", "of", "products", "commodities", "materials"]
- "regulations": ["list", "of", "laws", "policies", "notices", "acts", "codes"]
- "summary": "A 150-200 word comprehensive overview of what this document covers, its purpose, and key areas"
- "key_facts": {{"fact_name": "fact_value"}} (5-10 most important rules, numbers, dates, requirements)

Example key_facts: {{"minimum_export_quantity": "10,000 MT", "application_deadline": "April 15 2026"}}

Return ONLY JSON. No markdown. No explanation."""

        try:
            result = self._llm_sync(prompt, max_tokens=600, temperature=0.2)
            data = self._parse_json(result)

            DocumentMetadata.objects.create(
                document=doc,
                topics=', '.join(data.get('topics', [])),
                commodities=', '.join(data.get('commodities', [])),
                regulations=', '.join(data.get('regulations', [])),
                summary=data.get('summary', ''),
                key_facts=json.dumps(data.get('key_facts', {})),
            )
            topics = data.get('topics', [])[:3]
            self.stdout.write(f'  Metadata: topics={topics}...')
        except Exception as e:
            self.stdout.write(f'  WARNING: Metadata extraction failed: {e}')
            DocumentMetadata.objects.create(document=doc)

    # =========================================================================
    # ASYNC FACT EXTRACTION (Phase 4) — Using llm_service.generate_async
    # =========================================================================
    async def _extract_facts_async(self, page_objects):
        """
        Extract structured facts from all pages concurrently using llm_service.generate_async.
        Processes MAX_CONCURRENT_PAGES pages simultaneously.
        
        Returns:
            List of tuples: (page_obj, fact_dict) for bulk creation
        """
        semaphore = asyncio.Semaphore(LLM_SEMAPHORE_LIMIT)
        all_facts = []  # Collect all facts for bulk save
        tasks = []

        # Filter eligible pages
        eligible = []
        for page_obj, page_text, is_ocr in page_objects:
            if not page_text or len(page_text.strip()) < 300:
                continue
            if '[SCANNED' in page_text or '[OCR FAILED' in page_text:
                continue
            eligible.append((page_obj, page_text, is_ocr))

        if not eligible:
            self.stdout.write('  No pages eligible for fact extraction')
            return 0

        self.stdout.write(f'  Extracting facts from {len(eligible)} pages (concurrency={LLM_SEMAPHORE_LIMIT})...')

        # Create async tasks for each eligible page
        for page_obj, page_text, is_ocr in eligible:
            task = asyncio.create_task(
                self._extract_page_facts_async(page_obj, page_text, semaphore)
            )
            tasks.append(task)

        completed = 0
        for future in asyncio.as_completed(tasks):
            try:
                page_facts = await future  # Returns (page_obj, facts_list)
                if page_facts:
                    all_facts.extend(page_facts)
                completed += 1
                if completed % 10 == 0 or completed == len(tasks):
                    self.stdout.write(f'    Progress: {completed}/{len(tasks)} pages, {len(all_facts)} facts collected')
            except Exception as e:
                if not hasattr(self, '_fact_error_logged'):
                    self._fact_error_logged = True
                    import traceback
                    traceback.print_exc()
                completed += 1

        # Return all collected facts (no bulk save here)
        self.stdout.write(f'  Fact extraction complete: {len(all_facts)} facts from {len(tasks)} pages')
        return all_facts

    async def _extract_page_facts_async(self, page_obj, page_text, semaphore):
        """
        Extract facts from a single page using llm_service.generate_async.
        Returns list of (page_obj, fact_dict) tuples for bulk creation.
        """
        async with semaphore:
            prompt = f"""Extract ALL quantifiable facts, rules, requirements, deadlines, penalties, exemptions, and procedures from this text.

Return ONLY a valid JSON array. Each fact object MUST have these EXACT keys:
- "fact_type": one of ["quantity_limit", "deadline", "requirement", "penalty", "exemption", "procedure_step", "fee_rate", "eligibility", "document_type", "other"]
- "subject": short lowercase topic (e.g., "wheat_export", "reach_registration", "customs_declaration")
- "value": the fact value (e.g., "10000 MT", "30 days before shipment", "mandatory")
- "condition": conditions or qualifiers (empty string "" if none)
- "raw_text": the EXACT sentence or paragraph from the source text
- "confidence": a number between 0.0 and 1.0

TEXT TO ANALYZE:
{page_text[:4000]}

Return ONLY the JSON array. No markdown blocks. No explanation."""

            try:
                # Use llm_service.generate_async for fact extraction
                result = await self.llm_service.generate_async(prompt, max_tokens=1200)
                
                if not result or not result.strip():
                    return []
                
                try:
                    data = self._parse_json_array(result)
                except:
                    return []
                
                if not data:
                    return []
                
                # Return list of (page_obj, fact_dict) for bulk creation
                page_facts = []
                for fact in data:
                    if not isinstance(fact, dict):
                        continue
                    if not fact.get('value', '').strip():
                        continue
                    page_facts.append((page_obj, {
                        'fact_type': fact.get('fact_type', 'other'),
                        'subject': fact.get('subject', '').lower()[:200],
                        'value': fact.get('value', ''),
                        'condition': fact.get('condition', ''),
                        'raw_text': fact.get('raw_text', '')[:5000],
                        'confidence': min(1.0, max(0.0, float(fact.get('confidence', 0.5)))),
                    }))
                
                return page_facts
                
            except Exception as e:
                self.stdout.write(f'  Fact extraction error: {e}')
                return []

    # =========================================================================
    # LLM API CALLS (Sync — for metadata extraction)
    # =========================================================================
    def _llm_sync(self, prompt, max_tokens=500, temperature=0.2):
        """Synchronous LLM call for metadata extraction (once per document)."""
        return self.llm_service.generate(prompt, temperature=temperature, max_tokens=max_tokens)

    # =========================================================================
    # JSON PARSING HELPERS
    # =========================================================================
    def _parse_json(self, text):
        """Extract JSON from LLM response (handles markdown blocks)."""
        s = text.strip()
        # Try direct parse
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        # Try extracting from markdown code block
        if '```' in s:
            parts = s.split('```')
            for part in parts:
                p = part.strip()
                if p.startswith('json'):
                    p = p[4:]
                try:
                    return json.loads(p)
                except json.JSONDecodeError:
                    continue
        # Try finding JSON object boundaries
        start = s.find('{')
        end = s.rfind('}') + 1
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end])
            except json.JSONDecodeError:
                pass
        raise ValueError(f"Could not parse JSON from: {s[:200]}...")

    def _parse_json_array(self, text):
        """Extract JSON array from LLM response."""
        s = text.strip()
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            pass
        if '```' in s:
            parts = s.split('```')
            for part in parts:
                p = part.strip()
                if p.startswith('json'):
                    p = p[4:]
                try:
                    return json.loads(p)
                except json.JSONDecodeError:
                    continue
        start = s.find('[')
        end = s.rfind(']') + 1
        if start >= 0 and end > start:
            try:
                return json.loads(s[start:end])
            except json.JSONDecodeError:
                pass
        return []