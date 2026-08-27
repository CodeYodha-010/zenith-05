"""
Query Router - Smart Query Classification

Classifies user queries to determine search strategy.
No hardcoded responses - the LLM handles all natural language generation.
"""

import logging

logger = logging.getLogger('rag_pipeline')

TRADE_KEYWORDS = [
    "hs code", "hscode", "hts code", "htscode", "itc code",
    "duty", "duties", "tariff", "customs", "export", "import",
    "dgft", "cbp", "cbic", "fda", "usda", "epa", "apeda", "fssai",
    "license", "licence", "certificate", "certification",
    "invoice", "packing list", "bill of lading", "bill of entry",
    "iec code", "iec", "eori", "shipping bill",
    "restriction", "prohibited", "banned", "allowed",
    "regulation", "compliance", "procedure", "documentation",
    "shipping", "freight", "logistics", "clearance",
    "origin", "quota", "gsp", "mfn",
    "epcg", "c-tpat", "ctpat", "aeo", "rex",
    "anti-dumping", "safeguard", "sanitary", "phytosanitary",
    "grapes", "cotton", "t-shirt", "tshirt", "textile",
    "food", "pharmaceutical", "chemical", "machinery",
    "eu", "european union", "germany", "usa", "united states",
    "india", "delhi", "mumbai",
    "import clearance", "port of entry", "noc",
    "air waybill", "certificate of origin",
    "rules of origin", "taric", "access2markets",
]


def route_query(question: str) -> str:
    """
    Route a query - always goes to RAG pipeline.
    The LLM decides how to respond, not this function.
    """
    if not question or not question.strip():
        return "WEB_SEARCH"

    question_lower = question.lower().strip()

    for keyword in TRADE_KEYWORDS:
        if keyword in question_lower:
            logger.info(f"ROUTE: RAG_PIPELINE (matched: '{keyword}')")
            return "RAG_PIPELINE"

    logger.info(f"ROUTE: RAG_PIPELINE (default)")
    return "RAG_PIPELINE"
