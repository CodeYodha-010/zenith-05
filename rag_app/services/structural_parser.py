"""
Structural Parser - Intelligent document chunking based on legal/trade document structure.

This service splits long legal documents into logical chunks based on structural
headers like chapters, sections, articles, and annexes - rather than arbitrary
token limits.
"""

import re
import logging
from typing import List, Dict, Tuple, Optional

logger = logging.getLogger('rag_pipeline')


class StructuralParser:
    """
    Parser for intelligently splitting trade/legal documents based on their structure.
    
    Identifies headers like "CHAPTER IV", "Section 9", "Article 12", etc.
    and groups content under the appropriate header for context preservation.
    """
    
    # Regex patterns for trade/legal document headers
    HEADER_PATTERNS = [
        # CHAPTER patterns (Roman numerals and digits)
        r'(?i)^CHAPTER\s+([IVXLCDM]+|\d+)\s*[-.:]?\s*(.*)',
        r'(?i)^CHAPTER\s+([IVXLCDM]+|\d+)\s*$',
        
        # Section patterns
        r'(?i)^SECTION\s+(\d+|[IVXLCDM]+)\s*[-.:]?\s*(.*)',
        r'(?i)^SECTION\s+(\d+|[IVXLCDM]+)\s*$',
        
        # Article patterns
        r'(?i)^ARTICLE\s+(\d+|[IVXLCDM]+)\s*[-.:]?\s*(.*)',
        r'(?i)^ARTICLE\s+(\d+|[IVXLCDM]+)\s*$',
        
        # Annex patterns
        r'(?i)^ANNEX\s+([A-Z]|\d+|[IVXLCDM]+)\s*[-.:]?\s*(.*)',
        r'(?i)^ANNEX\s+([A-Z]|\d+|[IVXLCDM]+)\s*$',
        
        # Part patterns
        r'(?i)^PART\s+(\d+|[IVXLCDM]+|[A-Z])\s*[-.:]?\s*(.*)',
        r'(?i)^PART\s+(\d+|[IVXLCDM]+|[A-Z])\s*$',
        
        # Sub-section patterns
        r'(?i)^\d+\.\d+\s+(.*)',  # e.g., "1.1 Definitions"
        r'^\d+\.\d+\.\d+\s+(.*)',  # e.g., "1.1.1 Scope"
        
        # Regulation patterns
        r'(?i)^REGULATION\s+(\d+|[IVXLCDM]+)\s*[-.:]?\s*(.*)',
        r'(?i)^RULE\s+(\d+|[IVXLCDM]+)\s*[-.:]?\s*(.*)',
        
        # Numbered items that look like sections
        r'^(\d+)\.\s+([A-Z][a-z].*)',  # e.g., "1. Definitions"
    ]
    
    # Patterns for sub-items (bullets, numbered lists)
    LIST_PATTERNS = [
        r'^\s*[-•*]\s+',  # Bullet points
        r'^\s*\([a-z]\)\s+',  # Lettered lists (a), (b), (c)
        r'^\s*\(\d+\)\s+',  # Numbered lists (1), (2), (3)
        r'^\s*[a-z]\)\s+',  # a) b) c)
        r'^\s*\d+\)\s+',  # 1) 2) 3)
    ]
    
    def __init__(self):
        """Initialize the structural parser."""
        self.header_regex = [re.compile(pattern) for pattern in self.HEADER_PATTERNS]
        self.list_regex = [re.compile(pattern) for pattern in self.LIST_PATTERNS]
        logger.info("StructuralParser initialized")
    
    def parse_document(self, text: str, doc_title: str = "") -> List[Dict]:
        """
        Parse a document and split it into structural chunks.
        
        Args:
            text: Full document text
            doc_title: Document title for context
            
        Returns:
            List of chunk dictionaries with keys:
            - section_title: The header this chunk belongs to
            - content: The chunk text
            - chunk_type: 'text', 'table', or 'list'
            - section_level: Hierarchy level (1=chapter, 2=section, 3=article, etc.)
        """
        if not text or not text.strip():
            return []
        
        # Normalize line endings
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        
        # Split into lines for processing
        lines = text.split('\n')
        
        chunks = []
        current_section = {
            'title': 'Introduction',
            'content': [],
            'level': 0
        }
        
        for line in lines:
            line_stripped = line.strip()
            
            # Skip empty lines
            if not line_stripped:
                continue
            
            # Check if this line is a header
            header_info = self._detect_header(line_stripped)
            
            if header_info:
                # Save current section if it has content
                if current_section['content']:
                    chunk = self._create_chunk(current_section)
                    if chunk:
                        chunks.append(chunk)
                
                # Start new section
                current_section = {
                    'title': header_info['title'],
                    'content': [line_stripped],
                    'level': header_info['level']
                }
            else:
                # Add line to current section
                current_section['content'].append(line_stripped)
        
        # Don't forget the last section
        if current_section['content']:
            chunk = self._create_chunk(current_section)
            if chunk:
                chunks.append(chunk)
        
        # If no chunks were created, create one from the whole document
        if not chunks:
            chunks.append({
                'section_title': doc_title or 'Document',
                'content': text[:5000],  # Limit to 5000 chars
                'chunk_type': 'text',
                'section_level': 0
            })
        
        logger.info(f"Parsed document into {len(chunks)} structural chunks")
        return chunks
    
    def _detect_header(self, line: str) -> Optional[Dict]:
        """
        Detect if a line is a document header.
        
        Args:
            line: The line to check
            
        Returns:
            Dictionary with 'title' and 'level' if header, None otherwise
        """
        # Check against all header patterns
        for i, regex in enumerate(self.header_regex):
            match = regex.match(line)
            if match:
                # Extract title from the match
                groups = match.groups()
                title = line.strip()
                
                # Determine hierarchy level based on pattern index
                level = self._get_header_level(i)
                
                return {
                    'title': title,
                    'level': level
                }
        
        return None
    
    def _get_header_level(self, pattern_index: int) -> int:
        """
        Determine hierarchy level from pattern index.
        
        Args:
            pattern_index: Index of the matching pattern
            
        Returns:
            Hierarchy level (1=highest, 5=lowest)
        """
        # CHAPTER patterns -> level 1
        if pattern_index < 2:
            return 1
        # SECTION patterns -> level 2
        elif pattern_index < 4:
            return 2
        # ARTICLE patterns -> level 3
        elif pattern_index < 6:
            return 3
        # ANNEX/PART patterns -> level 2
        elif pattern_index < 10:
            return 2
        # Sub-sections -> level 4
        else:
            return 4
    
    def _create_chunk(self, section: Dict) -> Optional[Dict]:
        """
        Create a chunk dictionary from a section.
        
        Args:
            section: Section dictionary with title, content, level
            
        Returns:
            Chunk dictionary or None if content is too short
        """
        content = '\n'.join(section['content'])
        
        # Skip very short sections (less than 20 chars)
        if len(content) < 20:
            return None
        
        # Detect chunk type
        chunk_type = self._detect_chunk_type(content)
        
        return {
            'section_title': section['title'],
            'content': content,
            'chunk_type': chunk_type,
            'section_level': section['level']
        }
    
    def _detect_chunk_type(self, content: str) -> str:
        """
        Detect the type of content in a chunk.
        
        Args:
            content: The chunk content
            
        Returns:
            'table', 'list', or 'text'
        """
        lines = content.split('\n')
        
        # Check for table indicators
        table_indicators = 0
        for line in lines:
            if '\t' in line or '|' in line or re.search(r'\s{3,}', line):
                table_indicators += 1
        
        if table_indicators > len(lines) * 0.3:  # 30% of lines look like table
            return 'table'
        
        # Check for list indicators
        list_count = 0
        for line in lines:
            for list_regex in self.list_regex:
                if list_regex.match(line.strip()):
                    list_count += 1
                    break
        
        if list_count > len(lines) * 0.4:  # 40% of lines are list items
            return 'list'
        
        return 'text'
    
    def split_into_token_chunks(self, text: str, chunk_size: int = 500, overlap: int = 50) -> List[str]:
        """
        Fallback method: Split text into chunks by approximate token count.
        
        This is used when structural parsing doesn't find enough headers.
        
        Args:
            text: Text to split
            chunk_size: Approximate number of words per chunk
            overlap: Number of words to overlap between chunks
            
        Returns:
            List of text chunks
        """
        words = text.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk = ' '.join(chunk_words)
            
            if chunk.strip():
                chunks.append(chunk)
        
        return chunks if chunks else [text[:2000]]
    
    def merge_small_chunks(self, chunks: List[Dict], min_size: int = 200) -> List[Dict]:
        """
        Merge very small chunks with adjacent chunks for better context.
        
        Args:
            chunks: List of chunk dictionaries
            min_size: Minimum chunk size in characters
            
        Returns:
            List of merged chunks
        """
        if not chunks:
            return []
        
        merged = []
        current_chunk = chunks[0].copy()
        
        for next_chunk in chunks[1:]:
            # If current chunk is too small, merge with next
            if len(current_chunk['content']) < min_size:
                current_chunk['content'] += '\n\n' + next_chunk['content']
                # Keep the section title of the larger chunk
                if len(next_chunk['content']) > len(current_chunk['content']):
                    current_chunk['section_title'] = next_chunk['section_title']
            else:
                merged.append(current_chunk)
                current_chunk = next_chunk.copy()
        
        # Don't forget the last chunk
        merged.append(current_chunk)
        
        return merged