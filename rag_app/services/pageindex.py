"""
Simple PageIndex Service - Basic RAG + Web Search

Features:
- Document search using BM25
- Web search fallback with query enhancement
- Simple LLM answer generation
- Basic caching
"""

import logging
import re
from typing import Dict, List, Optional, Tuple
from rag_app.models import Document, DocumentIndex
from rag_app.services.llm_service import NVIDIALLMService
from rag_app.services.search_service import BM25SearchService
from rag_app.services.web_search_service import WebSearchService
from rag_app.services.cache_service import CacheService

logger = logging.getLogger(__name__)


class PageIndexService:
    """Simple RAG service with document search and web fallback."""

    def __init__(self):
        self.llm = NVIDIALLMService()
        self.web_search_service = WebSearchService()
        self.cache = CacheService(ttl_seconds=3600)
        self.search_service = BM25SearchService()
        logger.info("PageIndexService initialized (basic mode)")

    def _ensure_indexes_loaded(self):
        """Load document indexes from database."""
        documents = Document.objects.filter(is_processed=True)
        for doc in documents:
            if doc.text_chunks:
                self.search_service.build_index(doc.id, doc.text_chunks)
        logger.info(f"Loaded indexes for {len(documents)} documents")

    def query(self, query, document_id=None):
        """
        Process a query using documents or web search with intelligent fallback.

        Args:
            query: User query string
            document_id: Optional specific document ID to search

        Returns:
            Dict with answer, sources, source_type, and confidence
        """
        logger.info(f"[QUERY START] '{query}'")

        # 1. Check if Factual
        if self._is_factual_query(query):
            logger.info("🔍 Query Type: Factual -> Web Search")
            return self._web_search_only(query)

        # 2. Try Document Search
        index = DocumentIndex.objects.first()
        all_sections = index.all_sections if index else []

        if not all_sections:
            logger.warning("❌ No documents indexed -> Fallback to Web")
            return self._web_search_only(query)

        # Load indexes
        self._ensure_indexes_loaded()

        # Search documents
        doc_results = self.search_service.search_all(all_sections, query, top_k=10)
        logger.info(f"🔍 Found {len(doc_results)} document sections")

        # Check relevance
        is_relevant, confidence = self._check_relevance(doc_results, query)

        if is_relevant:
            logger.info("✅ Documents found relevant. Generating answer...")
            result = self._generate_doc_answer(query, doc_results)

            # SAFETY NET: Check if LLM actually found the answer
            answer_lower = result['answer'].lower()
            if "cannot find" in answer_lower or "not in the provided documents" in answer_lower:
                logger.warning("❌ Document Answer Failed (LLM said 'Cannot find') -> Fallback to Web")
                return self._web_search_only(query)

            logger.info("✅ Successfully answered from Documents")
            return result

        # 3. Fallback to Web
        logger.info("❌ Documents not relevant -> Fallback to Web Search")
        return self._web_search_only(query)

    def _is_factual_query(self, query):
        """Check if query is factual (needs current info from web)."""
        query_lower = query.lower()

        # Factual query indicators
        factual_patterns = [
            r'^who (is|was)',
            r'^what (is|are|was|were)',
            r'^where (is|are)',
            r'^when (is|are|was)',
            r'^current',
            r'^latest',
            r'^new',
            r'202[5-9]',
            r'203[0-9]',
        ]

        for pattern in factual_patterns:
            if re.search(pattern, query_lower):
                return True

        return False

    def _check_relevance(self, results, query):
        """Check if document results are relevant to query."""
        if not results:
            logger.info(f"🔍 Relevance Check: No results -> FAIL")
            return False, 0.2

        sig_words = [w for w in query.lower().split() if len(w) > 3]
        if len(sig_words) < 2:
            logger.info(f"🔍 Relevance Check: Too few significant words -> FAIL")
            return False, 0.3

        # Check keyword overlap
        total_match = 0
        for r in results:
            match_count = sum(1 for w in sig_words if w in r.get('text', '').lower())
            total_match += match_count

        avg_match = total_match / (len(sig_words) * len(results)) if results else 0
        is_rel = avg_match > 0.5  # Stricter threshold: 50% confidence required
        
        logger.info(f"🔍 Relevance Check: Score {avg_match:.2f} -> {'PASS' if is_rel else 'FAIL'}")
        return is_rel, avg_match

    def _enhance_query_for_web(self, query: str) -> str:
        """
        Enhance user query for better web search results.
        
        Uses LLM to rewrite the query into a more effective search statement
        that will find official documents and authoritative sources.
        
        Args:
            query: Original user query
            
        Returns:
            Enhanced query string optimized for web search
        """
        # Simple queries don't need enhancement
        if len(query.split()) <= 2:
            logger.info(f"⚡ Query too short, using original: '{query}'")
            return query
        
        prompt = f"""You are an expert search assistant for trade compliance.
Rewrite the user's question into a detailed search statement (60-90 words) to find official government documents.
Focus on the user's intent, context, and potential synonyms.
Do not just list keywords; explain what information is needed.

User Question: {query}
Enhanced Search Statement:"""
        
        try:
            enhanced = self.llm.generate(prompt, max_tokens=150, temperature=0.3)
            
            # Clean up the enhanced query
            enhanced = enhanced.strip().strip('"').strip("'")
            
            # Guard: If enhanced query is too long (>300 chars), fall back to original
            if len(enhanced) > 300:
                logger.warning(f"⚡ Enhanced query too long ({len(enhanced)} chars), using original")
                return query
            
            # Guard: If enhanced is empty, use original
            if not enhanced:
                logger.warning(f"⚡ Empty enhancement, using original")
                return query
            
            logger.info(f"⚡ Query Enhanced: '{query}' -> '{enhanced[:50]}...'")
            return enhanced
            
        except Exception as e:
            logger.error(f"⚡ Query Enhancement Error: {str(e)}, using original query")
            return query

    def _generate_doc_answer(self, query, doc_results):
        """Generate answer from document sections."""
        # Use top 5 sections for context
        context_parts = [r.get('text', '')[:800] for r in doc_results[:5]]
        sources = [r.get('doc_title', 'Doc') for r in doc_results[:5]]

        context = "\n\n---\n\n".join(context_parts)

        prompt = f"""You are a helpful assistant answering from DOCUMENTS only.

RULES:
1. Answer ONLY from the provided document sections
2. If documents don't contain the answer, say: "I cannot find this information in the provided documents."
3. Do NOT use your training knowledge
4. Be clear and concise

DOCUMENT SECTIONS:
{context}

QUESTION: {query}

ANSWER:"""

        answer = self.llm.generate(prompt, max_tokens=1200)

        return {
            "answer": answer,
            "sources": sources,
            "source_type": "documents",
            "confidence": 0.8
        }

    def _web_search_only(self, query: str) -> Dict:
        """
        Generate answer from web search with query enhancement.
        
        This method enhances the user's query using LLM, performs web search
        with Jina AI, and generates an answer with dynamic confidence scoring.
        
        Args:
            query: User query string
            
        Returns:
            Dictionary with answer, sources, source_type, and confidence
        """
        logger.info("🌐 Starting Web Search...")
        
        # Step A: Enhance the query for better search results
        enhanced_query = self._enhance_query_for_web(query)
        
        # Step B: Log the query transformation
        if enhanced_query != query:
            logger.info(f"🌐 Using enhanced query: '{enhanced_query}'")
        else:
            logger.info(f"🌐 Using original query: '{query}'")
        
        # Step C: Search web with enhanced query
        web_results = self.web_search_service.search(enhanced_query, num_results=10)
        logger.info(f"🌐 Found {len(web_results)} results")
        
        # Handle no results
        if not web_results:
            logger.warning("❌ No web results found")
            return {
                "answer": f"I couldn't find reliable information for: \"{query}\"\n\nTry:\n• Rephrasing your query\n• Using different keywords\n• Checking official sources directly",
                "sources": ["No results found"],
                "source_type": "none",
                "confidence": 0.0
            }
        
        # Build context from top 5 results
        context_parts = []
        sources = []
        
        for i, r in enumerate(web_results[:5], 1):
            content = r.get('full_content') or r.get('snippet', '')
            url = r.get('url', 'No URL')
            title = r.get('title', 'No title')
            
            context_parts.append(f"""[SOURCE {i}]
Title: {title}
URL: {url}
Content: {content[:1500]}
---""")
            sources.append(f"{title} - {url}")
        
        context = "\n\n".join(context_parts)
        
        prompt = f"""You are answering from WEB SOURCES only.

RULES:
1. Answer ONLY from the provided web sources
2. If sources don't have the answer, say: "I cannot find this information in the provided web sources."
3. Do NOT use your training knowledge
4. Cite sources as [SOURCE X] for each fact
5. Do NOT say "as of my knowledge cutoff"

CURRENT DATE: March 2026

QUESTION: {query}

WEB SOURCES:
{context}

ANSWER (cite sources as [SOURCE X]):"""
        
        answer = self.llm.generate(prompt, max_tokens=2048)
        logger.info(f"✅ Generated web answer ({len(answer)} chars)")
        
        # Step D: Dynamic confidence calculation
        # Base confidence on number of results found
        num_results = len(web_results)
        if num_results == 0:
            confidence = 0.0
        elif num_results <= 2:
            confidence = 0.5
        else:
            # Scale confidence: 0.5 + (results * 0.05), capped at 0.9
            confidence = min(0.9, 0.5 + (num_results * 0.05))
        
        logger.info(f"✅ Web search complete with confidence {confidence:.2f}")
        
        return {
            "answer": answer,
            "sources": sources[:5],
            "source_type": "web",
            "confidence": confidence
        }
