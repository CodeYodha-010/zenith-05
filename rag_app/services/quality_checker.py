"""
Quality Checker for Knowledge Base Answers

This module provides instant (NO LLM) quality checking for KB answers.
It determines if an answer is "weak" and needs web search fallback.
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# ============================================================================
# DEFEAT PHRASES - If LLM says these, answer is weak
# ============================================================================

DEFEAT_PHRASES = [
    "does not contain",
    "insufficient information",
    "cannot determine",
    "text does not specify",
    "not in the provided",
    "cannot find",
    "not available in",
    "could not find",
    "not found in",
]


def is_answer_weak(answer_text: str, max_match_score: int) -> bool:
    """
    Check if a KB answer is weak and needs web search fallback.
    
    This function runs INSTANTLY with NO LLM calls.
    
    Args:
        answer_text: The LLM-generated answer from KB
        max_match_score: The highest keyword match score from SearchIndex
        
    Returns:
        True if answer is weak (needs web fallback)
        False if answer is strong (KB is sufficient)
    """
    if not answer_text:
        logger.info("Quality Check: Empty answer -> WEAK")
        return True
    
    answer_lower = answer_text.lower().strip()
    
    # Check 1: Low match score
    if max_match_score <= 2:
        logger.info(f"Quality Check: Low match score ({max_match_score}) -> WEAK")
        return True
    
    # Check 2: Short answer (less than 30 words)
    word_count = len(answer_text.split())
    if word_count < 30:
        logger.info(f"Quality Check: Short answer ({word_count} words) -> WEAK")
        return True
    
    # Check 3: Defeat phrases
    for phrase in DEFEAT_PHRASES:
        if phrase in answer_lower:
            logger.info(f"Quality Check: Defeat phrase found ('{phrase}') -> WEAK")
            return True
    
    # All checks passed
    logger.info(f"Quality Check: Strong answer ({word_count} words, score={max_match_score}) -> STRONG")
    return False


def get_answer_quality_report(answer_text: str, max_match_score: int) -> dict:
    """
    Get a detailed quality report for an answer.
    
    Args:
        answer_text: The LLM-generated answer
        max_match_score: The highest keyword match score
        
    Returns:
        Dictionary with quality metrics
    """
    if not answer_text:
        return {
            "is_weak": True,
            "reason": "Empty answer",
            "word_count": 0,
            "max_match_score": max_match_score,
            "defeat_phrases_found": []
        }
    
    answer_lower = answer_text.lower().strip()
    word_count = len(answer_text.split())
    
    # Find defeat phrases
    found_phrases = []
    for phrase in DEFEAT_PHRASES:
        if phrase in answer_lower:
            found_phrases.append(phrase)
    
    # Determine weakness
    is_weak = False
    reason = "Strong"
    
    if max_match_score <= 2:
        is_weak = True
        reason = f"Low match score ({max_match_score})"
    elif word_count < 30:
        is_weak = True
        reason = f"Short answer ({word_count} words)"
    elif found_phrases:
        is_weak = True
        reason = f"Defeat phrases found: {found_phrases}"
    
    return {
        "is_weak": is_weak,
        "reason": reason,
        "word_count": word_count,
        "max_match_score": max_match_score,
        "defeat_phrases_found": found_phrases
    }


# ============================================================================
# SCRAPED CONTENT EVALUATOR - Zenith-Aware LLM Filter
# ============================================================================

def evaluate_scraped_content(text: str, expected_topic: str, exclude_keywords: list, llm_service) -> bool:
    """
    Use NVIDIA LLM to evaluate whether scraped content is VALID for Zenith's
    knowledge base. Rejects generic manuals, PDF dumps, and static content
    that Zenith already has in its 41 foundational PDFs.

    Args:
        text: The scraped page text
        expected_topic: What kind of dynamic content we expect from this target
        exclude_keywords: List of phrases that indicate redundant/static content
        llm_service: NVIDIALLMService instance

    Returns:
        True if content is VALID (dynamic, actionable, not redundant)
        False if content is INVALID (static manual, generic overview, PDF dump)
    """
    if not text or len(text.strip()) < 100:
        logger.info("Scraped Content Evaluator: Text too short -> INVALID")
        return False

    exclude_text = ", ".join(exclude_keywords) if exclude_keywords else "none specified"
    text_snippet = text[:800]

    prompt = f"""You are a data quality filter for 'Zenith', an AI assistant for Indian exporters.

CONTEXT: We already have static PDFs in our database (CBIC Manuals, DGFT Handbooks, FDA 21 CFR rules, EU UCC codes). We are scraping the web to find ONLY dynamic, live updates or specific product protocols.

TARGET TOPIC: {expected_topic}
EXCLUDE IF IT CONTAINS: {exclude_text}

SCRAPED TEXT:
{text_snippet}

ANSWERING RULES:
- Answer 'VALID' only if the text contains LIVE updates, specific product lists, current detention alerts, or actionable compliance steps NOT found in standard static manuals.
- Answer 'INVALID' if the text is a generic overview, a table of contents, an introduction to customs, or matches any of the EXCLUDE keywords.
- Answer 'INVALID' if the text looks like a standard PDF manual dump.
- Answer ONLY with the word 'VALID' or 'INVALID'."""

    try:
        response = llm_service.generate(prompt, max_tokens=10, temperature=0.0)
        response_clean = response.strip().upper()

        if "VALID" in response_clean and "INVALID" not in response_clean:
            logger.info(f"Scraped Content Evaluator: VALID")
            return True
        else:
            logger.info(f"Scraped Content Evaluator: INVALID (LLM said: {response_clean})")
            return False

    except Exception as e:
        logger.error(f"Scraped Content Evaluator failed: {str(e)}")
        return False