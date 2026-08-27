"""
NVIDIA OCR Service - Extract text from scanned PDF pages using NVIDIA API.

This service handles communication with NVIDIA's OCR API to extract text
from images of scanned documents.
"""

import logging
import os
import base64
import requests
from io import BytesIO
from typing import Tuple, Optional
from django.conf import settings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger('rag_pipeline')


class NvidiaOcrService:
    """
    Service for extracting text from scanned PDF pages using NVIDIA OCR API.
    
    This service converts PDF page images to text using NVIDIA's optical
    character recognition capabilities.
    """
    
    def __init__(self):
        """
        Initialize the NVIDIA OCR service with API configuration.
        """
        self.api_key = getattr(settings, 'NVIDIA_OCR_API_KEY', None) or os.getenv('NVIDIA_OCR_API_KEY')
        # Use NVIDIA's official OCR endpoint (NemoRetriever OCR v1)
        self.ocr_url = 'https://ai.api.nvidia.com/v1/cv/nvidia/nemoretriever-ocr-v1'
        
        if not self.api_key:
            logger.warning("NVIDIA_OCR_API_KEY not configured. OCR functionality will not work.")
        
        logger.info("NvidiaOcrService initialized")
    
    def extract_text_from_image(self, image_data: bytes) -> Tuple[str, float]:
        """
        Extract text from an image using NVIDIA OCR API.
        
        Args:
            image_data: Image bytes (PNG/JPEG format)
            
        Returns:
            Tuple of (extracted_text, confidence_score)
            - extracted_text: The OCR-extracted text string
            - confidence_score: Confidence score from 0.0 to 1.0 (or -1.0 if not available)
            
        Raises:
            Exception: If OCR processing fails
        """
        if not self.api_key:
            raise Exception("NVIDIA_OCR_API_KEY not configured")
        
        try:
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            # Prepare the API request
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            # NVIDIA OCR API payload - official format
            payload = {
                "input": [
                    {
                        "type": "image_url",
                        "url": f"data:image/png;base64,{base64_image}"
                    }
                ]
            }
            
            # Make the API request to NVIDIA OCR endpoint
            logger.info(f"Calling NVIDIA OCR API at: {self.ocr_url}")
            
            response = requests.post(
                self.ocr_url,
                headers=headers,
                json=payload,
                timeout=120
            )
            
            # Handle response
            if response.status_code == 200:
                result = response.json()
                
                # Extract text from NVIDIA OCR response
                extracted_text = ""
                confidence = -1.0
                
                # Parse the official NVIDIA OCR response format
                # Response format: {"data": [{"index": 0, "text_detections": [{"text_prediction": {"text": "...", "confidence": 0.82}}]}]}
                if 'data' in result:
                    text_parts = []
                    confidences = []
                    
                    for page in result['data']:
                        if 'text_detections' in page:
                            for detection in page['text_detections']:
                                if 'text_prediction' in detection:
                                    text = detection['text_prediction'].get('text', '')
                                    if text:
                                        text_parts.append(text)
                                    
                                    # Get confidence
                                    conf = detection['text_prediction'].get('confidence', -1.0)
                                    if conf >= 0:
                                        confidences.append(conf)
                    
                    extracted_text = '\n'.join(text_parts)
                    if confidences:
                        confidence = sum(confidences) / len(confidences)
                
                # Clean up the extracted text
                if extracted_text:
                    extracted_text = extracted_text.strip()
                
                logger.info(f"OCR successful: extracted {len(extracted_text)} characters")
                return extracted_text, confidence
            
            elif response.status_code == 401:
                raise Exception("Invalid NVIDIA API key. Please check NVIDIA_OCR_API_KEY in .env")
            
            elif response.status_code == 429:
                raise Exception("NVIDIA API rate limit exceeded. Please wait and try again.")
            
            else:
                error_detail = response.text
                raise Exception(f"NVIDIA OCR API error ({response.status_code}): {error_detail}")
                
        except requests.exceptions.Timeout:
            raise Exception("NVIDIA OCR API request timed out")
        
        except requests.exceptions.RequestException as e:
            raise Exception(f"NVIDIA OCR API connection error: {str(e)}")
        
        except Exception as e:
            raise Exception(f"OCR processing failed: {str(e)}")
    
    def _extract_confidence(self, api_response: dict) -> float:
        """
        Extract confidence score from API response if available.
        
        Args:
            api_response: The full API response dictionary
            
        Returns:
            Confidence score between 0.0 and 1.0, or -1.0 if not available
        """
        # NVIDIA API may not provide confidence in standard response
        # Return -1.0 to indicate confidence not available
        try:
            # Some APIs include confidence in usage or metadata
            usage = api_response.get('usage', {})
            if 'confidence' in usage:
                return float(usage['confidence'])
        except:
            pass
        
        return -1.0
    
    def extract_text_from_pil_image(self, pil_image) -> Tuple[str, float]:
        """
        Extract text from a PIL Image object.
        
        Args:
            pil_image: PIL Image object
            
        Returns:
            Tuple of (extracted_text, confidence_score)
        """
        # Convert PIL Image to bytes
        buffer = BytesIO()
        pil_image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()
        
        return self.extract_text_from_image(image_bytes)