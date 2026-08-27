"""
Local Stealth Scraper using Scrapling

This module provides local stealth scraping capabilities using Scrapling,
which runs on the user's machine and bypasses Cloudflare/WAF protections.
"""

import logging
from typing import Optional

logger = logging.getLogger('rag_pipeline')


def scrape_gov_site(url: str) -> str:
    """
    Scrape a government website using Scrapling.
    Uses HTTP-based Fetcher with browser impersonation (no Playwright required).
    
    Args:
        url: The URL to scrape
        
    Returns:
        Extracted text content, or empty string if failed
    """
    try:
        from scrapling.fetchers import Fetcher
        
        logger.info(f"[SCRAPLING] Fetching: {url}")
        
        # Fetch using Fetcher with Chrome impersonation
        response = Fetcher.get(
            url,
            impersonate='chrome',
            stealthy_headers=True,
            timeout=30000,
            headers={'Accept-Language': 'en-US,en;q=0.9'}  # Request English content
        )
        
        if not response:
            logger.warning(f"[SCRAPLING] No response from {url}")
            return ""
        
        # Extract text from body (more reliable than response.text)
        if response.body:
            text = response.body.decode('utf-8', errors='ignore')
        else:
            text = str(response.text)
        
        if not text or len(text.strip()) < 200:
            logger.warning(f"[SCRAPLING] Content too short from {url} ({len(text.strip()) if text else 0} chars)")
            return ""

        # Block PDF download pages or binary file links
        pdf_triggers = [".pdf", "application/pdf", "downloadacrobat", "filetype:pdf"]
        if any(trigger in text.lower() for trigger in pdf_triggers):
            logger.info(f"[SKIPPED] {url} - Page is just a PDF download link, not readable text.")
            return ""

        logger.info(f"[SCRAPING] Success: {len(text)} chars from {url}")
        return text
        
    except Exception as e:
        logger.error(f"[SCRAPLING] Failed: {url} - {str(e)}")
        return ""


def scrape_url(url: str, use_fda_api: bool = False) -> str:
    """
    Scrape a URL using Scrapling.
    
    Args:
        url: The URL to scrape
        use_fda_api: Deprecated - FDA now uses normal Scrapling
        
    Returns:
        Extracted text content, or empty string if failed
    """
    return scrape_gov_site(url)