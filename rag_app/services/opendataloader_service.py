"""
OpenDataLoader Service
======================
Replaces LlamaParserService with local PDF parsing using OpenDataLoader.
- No cloud API calls — 100% local
- Correct reading order (XY-Cut++)
- Table structure via JSON rows/cells/kids extraction
- Bounding boxes for every element
- AI safety filters (prompt injection protection)

Uses JSON format per official RAG Integration Guide:
  "Use JSON output when you need bounding boxes for citations"
  "Tables are exported as structured data with rows, columns, and cell content preserved"

Requires: Java 11+, opendataloader-pdf pip package
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger('rag_pipeline')


class OpenDataLoaderService:
    """
    Parses PDF documents using OpenDataLoader (local, no cloud).
    Uses JSON output for proper page splitting + table extraction.
    Returns structured page data for the RAG pipeline.
    """

    def __init__(self):
        self._check_java()
        self._check_package()

    def _check_java(self):
        try:
            import subprocess
            result = subprocess.run(
                ['java', '-version'], capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                logger.warning("Java not found in PATH. OpenDataLoader requires Java 11+.")
        except FileNotFoundError:
            logger.warning("Java not found. Install Adoptium JDK: winget install EclipseAdoptium.Temurin.21.JDK")
        except Exception as e:
            logger.warning(f"Java check failed: {e}")

    def _check_package(self):
        try:
            import opendataloader_pdf
            logger.info("OpenDataLoader PDF package loaded successfully")
        except ImportError:
            logger.error("opendataloader-pdf not installed. Run: pip install opendataloader-pdf")

    def parse_document_sync(self, file_path: str) -> List[Dict]:
        """
        Parse a PDF and return a list of page data.
        Each dict contains: {"page_number": int, "text": str}.
        """
        try:
            import opendataloader_pdf
        except ImportError:
            logger.error("opendataloader-pdf not installed")
            return []

        file_path = str(file_path)
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            return []

        if not file_path.lower().endswith('.pdf'):
            logger.warning(f"OpenDataLoader only supports PDF. Got: {file_path}")
            return []

        try:
            with tempfile.TemporaryDirectory(prefix="odl_") as tmp_dir:
                opendataloader_pdf.convert(
                    input_path=[file_path],
                    output_dir=tmp_dir,
                    format="json",
                    quiet=True,
                )

                json_files = list(Path(tmp_dir).glob("*.json"))
                if not json_files:
                    logger.warning(f"No JSON output from OpenDataLoader for {file_path}")
                    return []

                return self._parse_odl_json(json_files[0], file_path)

        except Exception as e:
            logger.error(f"OpenDataLoader failed for {file_path}: {e}")
            return []

    def parse_pdf_bytes(self, file_bytes: bytes, filename: str = "uploaded.pdf") -> List[Dict]:
        """Parse PDF from raw bytes (for uploaded files)."""
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            return self.parse_document_sync(tmp_path)
        except Exception as e:
            logger.error(f"OpenDataLoader bytes parse failed: {e}")
            return []
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except:
                    pass

    def _parse_odl_json(self, json_path: Path, source_file: str) -> List[Dict]:
        """
        Parse OpenDataLoader JSON output into page-level text.

        JSON structure per docs:
        - doc["kids"] = list of elements in document order
        - Each element has "type", "page number", "bounding box"
        - paragraph/heading/list/text block: element["content"] has text
        - table: element["rows"][r]["cells"][c]["kids"][0]["content"] has cell text
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                doc = json.load(f)
        except Exception as e:
            logger.error(f"Failed to read OpenDataLoader JSON: {e}")
            return []

        kids = doc.get('kids', [])
        if not kids:
            logger.warning(f"No elements in JSON for {source_file}")
            return []

        # Group elements by page number, extract text per element type
        pages_dict: Dict[int, List[str]] = {}

        for element in kids:
            page_num = element.get('page number', 0) or 1
            elem_type = element.get('type', '')

            text = self._extract_element_text(element, elem_type)
            if not text:
                continue

            if page_num not in pages_dict:
                pages_dict[page_num] = []
            pages_dict[page_num].append(text)

        # Convert to sorted page list
        pages = []
        for page_num in sorted(pages_dict.keys()):
            page_text = '\n\n'.join(pages_dict[page_num])
            if page_text.strip():
                pages.append({
                    "page_number": page_num,
                    "text": page_text,
                })

        logger.info(f"OpenDataLoader parsed: {len(pages)} pages from {source_file}")
        return pages

    def _extract_element_text(self, element: dict, elem_type: str) -> str:
        """Extract text from an element based on its type."""

        if elem_type in ('paragraph', 'text block'):
            content = element.get('content', '')
            return content.strip() if content else ''

        if elem_type == 'heading':
            content = element.get('content', '')
            if not content:
                return ''
            level = element.get('level', '')
            if level and str(level).isdigit():
                hashes = '#' * min(int(level), 6)
                return f"{hashes} {content.strip()}"
            return content.strip()

        if elem_type == 'table':
            return self._extract_table_text(element)

        if elem_type == 'list':
            return self._extract_list_text(element)

        if elem_type == 'caption':
            content = element.get('content', '')
            return f"*{content.strip()}*" if content else ''

        # image, formula, header, footer — skip
        return ''

    def _extract_table_text(self, element: dict) -> str:
        """
        Extract text from table using JSON rows/cells/kids structure.

        Per JSON schema:
        - element["rows"] = list of row objects
        - row["cells"] = list of cell objects
        - cell["kids"] = list of nested elements (paragraphs with content)
        """
        rows = element.get('rows', [])
        if not rows:
            return ''

        num_cols = element.get('number of columns', 0)
        table_lines = []

        for row in rows:
            cells = row.get('cells', [])
            cell_texts = []
            for cell in cells:
                cell_kids = cell.get('kids', [])
                cell_content_parts = []
                for kid in cell_kids:
                    kid_content = kid.get('content', '')
                    if kid_content and str(kid_content).strip():
                        cell_content_parts.append(str(kid_content).strip())
                cell_texts.append(' '.join(cell_content_parts))
            if any(ct for ct in cell_texts):
                table_lines.append(' | '.join(cell_texts))

        if not table_lines:
            return ''

        # Add table marker for downstream chunker
        return '[TABLE]\n' + '\n'.join(table_lines)

    def _extract_list_text(self, element: dict) -> str:
        """Extract text from a list element."""
        list_items = element.get('list items', [])
        if not list_items:
            # Fallback: try content field
            content = element.get('content', '')
            return content.strip() if content else ''

        numbering_style = element.get('numbering style', 'bullet')
        lines = []
        for i, item in enumerate(list_items):
            item_content = item.get('content', '')
            if not item_content:
                # Check nested kids
                kids = item.get('kids', [])
                parts = []
                for kid in kids:
                    kc = kid.get('content', '')
                    if kc:
                        parts.append(str(kc).strip())
                item_content = ' '.join(parts)

            if item_content:
                if numbering_style == 'ordered':
                    lines.append(f"{i+1}. {item_content.strip()}")
                else:
                    lines.append(f"- {item_content.strip()}")

        return '\n'.join(lines) if lines else ''
