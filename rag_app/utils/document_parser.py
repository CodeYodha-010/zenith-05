"""
Document Parser - Extract text from uploaded PDF/image files.

Supports:
- PDF with text (via OpenDataLoader — primary, local, free)
- PDF fallback (via PyMuPDF + NVIDIA OCR for scanned pages)
- Images (PNG, JPG, JPEG) via NVIDIA OCR
"""

import logging
import io
import fitz  # PyMuPDF
from typing import Dict, Optional
from django.conf import settings

logger = logging.getLogger('rag_pipeline')


class DocumentParser:
    """Parse uploaded documents and extract text."""
    
    def __init__(self):
        self.ocr_service = None
        self.odl_service = None
    
    def _get_ocr_service(self):
        """Lazy load OCR service."""
        if self.ocr_service is None:
            from ..services.nvidia_ocr_service import NvidiaOcrService
            self.ocr_service = NvidiaOcrService()
        return self.ocr_service
    
    def _get_odl_service(self):
        """Lazy load OpenDataLoader service."""
        if self.odl_service is None:
            try:
                from ..services.opendataloader_service import OpenDataLoaderService
                self.odl_service = OpenDataLoaderService()
            except Exception as e:
                logger.warning(f"OpenDataLoader not available: {e}")
                self.odl_service = False  # Mark as unavailable
        return self.odl_service if self.odl_service is not False else None
    
    def parse_file(self, uploaded_file):
        """
        Extract text from uploaded file.
        
        Args:
            uploaded_file: Django UploadedFile object
            
        Returns:
            Dict with keys: success, text, filename, error
        """
        filename = uploaded_file.name
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # Read file bytes
        file_bytes = uploaded_file.read()
        
        try:
            if file_ext == 'pdf':
                return self._parse_pdf(file_bytes, filename)
            elif file_ext in ['png', 'jpg', 'jpeg']:
                return self._parse_image(file_bytes, filename)
            else:
                return {
                    'success': False,
                    'error': f'Unsupported file type: {file_ext}. Use PDF, PNG, JPG, or JPEG.',
                    'filename': filename,
                    'text': ''
                }
        except Exception as e:
            logger.error(f'Document parsing error: {e}')
            return {
                'success': False,
                'error': f'Failed to parse document: {str(e)}',
                'filename': filename,
                'text': ''
            }
    
    def _parse_pdf(self, file_bytes, filename):
        """Parse PDF — try OpenDataLoader first, then PyMuPDF + OCR fallback."""
        # Try OpenDataLoader first (best quality, local, free)
        odl = self._get_odl_service()
        if odl:
            try:
                pages = odl.parse_pdf_bytes(file_bytes, filename)
                if pages:
                    # Combine all pages into single text
                    text_parts = []
                    for p in pages:
                        t = p.get('text', '')
                        if t:
                            text_parts.append(str(t))
                    text = '\n\n'.join(text_parts)
                    if text and len(text.strip()) > 10:
                        logger.info(f'OpenDataLoader parsed {len(pages)} pages from {filename}')
                        return {
                            'success': True,
                            'text': text,
                            'filename': filename,
                            'error': None
                        }
            except Exception as e:
                logger.warning(f'OpenDataLoader failed for {filename}: {e}, falling back...')
        
        # Fallback: PyMuPDF + NVIDIA OCR
        try:
            text = self._extract_text_pymupdf(file_bytes)
            
            if not text or len(text.strip()) < 50:
                logger.info(f'PyMuPDF extracted minimal text, trying OCR for {filename}')
                text = self._extract_text_ocr(file_bytes, filename)
            
            if not text or len(text.strip()) < 10:
                return {
                    'success': False,
                    'error': 'Could not extract text from PDF. It may be empty or corrupted.',
                    'filename': filename,
                    'text': ''
                }
            
            return {
                'success': True,
                'text': text,
                'filename': filename,
                'error': None
            }
            
        except Exception as e:
            logger.error(f'PDF parsing error: {e}')
            return {
                'success': False,
                'error': f'PDF parsing failed: {str(e)}',
                'filename': filename,
                'text': ''
            }
    
    def _extract_text_pymupdf(self, file_bytes):
        """Extract text using PyMuPDF."""
        try:
            doc = fitz.open(stream=file_bytes, filetype='pdf')
            text_parts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(text)
            
            doc.close()
            return '\n'.join(text_parts)
            
        except Exception as e:
            logger.warning(f'PyMuPDF extraction failed: {e}')
            return ''
    
    def _extract_text_ocr(self, file_bytes, filename):
        """Extract text using NVIDIA OCR."""
        try:
            ocr_service = self._get_ocr_service()
            
            # Check if API key is available
            if not ocr_service.api_key:
                logger.warning('NVIDIA OCR API key not configured')
                return ''
            
            # For PDF, convert each page to image and OCR
            doc = fitz.open(stream=file_bytes, filetype='pdf')
            text_parts = []
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                # Render page as image
                zoom = 2  # 2x for better OCR
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # Convert to PNG bytes
                img_bytes = pix.tobytes('png')
                
                try:
                    # OCR this page
                    text, confidence = ocr_service.extract_text_from_image(img_bytes)
                    if text:
                        text_parts.append(f'[Page {page_num + 1}]\n{text}')
                        logger.info(f'OCR Page {page_num + 1}: confidence={confidence:.2f}')
                except Exception as ocr_err:
                    logger.warning(f'OCR failed for page {page_num + 1}: {ocr_err}')
            
            doc.close()
            return '\n\n'.join(text_parts)
            
        except Exception as e:
            logger.error(f'OCR extraction failed: {e}')
            return ''
    
    def _parse_image(self, file_bytes, filename):
        """Parse image using NVIDIA OCR."""
        try:
            ocr_service = self._get_ocr_service()
            
            # Check if API key is available
            if not ocr_service.api_key:
                return {
                    'success': False,
                    'error': 'NVIDIA OCR API key not configured. Cannot process images.',
                    'filename': filename,
                    'text': ''
                }
            
            text, confidence = ocr_service.extract_text_from_image(file_bytes)
            
            if not text or len(text.strip()) < 10:
                return {
                    'success': False,
                    'error': 'Could not extract text from image.',
                    'filename': filename,
                    'text': ''
                }
            
            return {
                'success': True,
                'text': text,
                'filename': filename,
                'error': None
            }
            
        except Exception as e:
            logger.error(f'Image OCR error: {e}')
            return {
                'success': False,
                'error': f'Image processing failed: {str(e)}',
                'filename': filename,
                'text': ''
            }
