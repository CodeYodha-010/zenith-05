"""
Tariff disclaimer logic.
Previously was inside TARIFF_PROMPT_TEMPLATE in views.py.
Now separated as a post-processing function.
Import this in views.py and call after LLM generates an answer.
"""


def get_tariff_disclaimer(url: str) -> str:
    """
    Returns an appropriate disclaimer based on the source URL.
    Called after LLM generates an answer for tariff-related queries.

    Args:
        url: The source URL from the search result.

    Returns:
        A disclaimer string, or empty string if no disclaimer needed.
    """
    url_lower = url.lower()

    if 'eximpedia' in url_lower:
        return (
            "⚠️ Source: Eximpedia (Third-party aggregator). "
            "Verify exact country-specific suffixes and duty rates "
            "on the official CBIC/ICEGATE portal."
        )

    if 'trade.gov' in url_lower:
        return "✅ Source: Official US Trade Portal."

    if 'access2markets' in url_lower:
        return "✅ Source: Official EU Access2Markets Portal."

    if 'dgft.gov.in' in url_lower:
        return "✅ Source: Official DGFT Portal."

    if 'cbic.gov.in' in url_lower or 'icegate.gov.in' in url_lower:
        return "✅ Source: Official CBIC/ICEGATE Portal."

    return ""


def is_tariff_query(question: str) -> bool:
    """
    Detects if the user's question is tariff/duty related.
    Used to decide whether to append disclaimers.

    Args:
        question: The user's question.

    Returns:
        True if the question is tariff-related.
    """
    tariff_keywords = [
        'tariff', 'duty', 'rate', 'hs code', 'hscode', 'customs',
        'import duty', 'export duty', 'basic customs duty', 'bcd',
        'igst', 'cess', 'anti-dumping', 'safeguard', 'countervailing',
    ]
    question_lower = question.lower()
    return any(keyword in question_lower for keyword in tariff_keywords)
