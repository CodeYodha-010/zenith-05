"""
Search Configuration for Official Government Domains

This file contains ONLY data structures (dictionaries and lists).
No logic - just configuration for Tavily web search.
"""

# ============================================================================
# SEARCH MODE CONTROL
# ============================================================================

# Set to True to search entire web (no domain filtering)
# Set to False to use official government domains only
SEARCH_FULL_WEB = True

PRIMARY_DOMAINS = {
    "india": [
        "dgft.gov.in",           # Directorate General of Foreign Trade
        "cbic.gov.in",           # Central Board of Indirect Taxes & Customs
        "icegate.gov.in",        # Indian Customs Electronic Gateway
    ],
    "us": [
        "cbp.gov",               # Customs and Border Protection
        "hts.usitc.gov",         # Harmonized Tariff Schedule
        "trade.gov",             # International Trade Administration
    ],
    "eu": [
        "access2markets.trade.ec.europa.eu",  # EU Trade Access
        "taxation-customs.ec.europa.eu",      # EU Taxation & Customs
    ],
}

# ============================================================================
# SECONDARY DOMAINS - Search only if specific keywords detected
# ============================================================================

SECONDARY_DOMAINS = {
    "india": {
        "agri": [
            "apeda.gov.in",      # Agricultural and Processed Food Products
            "mpeda.gov.in",      # Marine Products Export Development
        ],
        "pharma": [
            "pharmexcil.com",    # Pharmaceuticals Export Promotion Council
        ],
        "chemical": [
            "chemexcil.in",      # Chemicals Export Promotion Council
        ],
        "credit": [
            "ecgc.in",           # Export Credit Guarantee Corporation
        ],
    },
    "us": {
        "food": [
            "fda.gov",           # Food and Drug Administration
        ],
        "agri": [
            "usda.gov",          # United States Department of Agriculture
            "aphis.usda.gov",    # Animal and Plant Health Inspection
        ],
        "environmental": [
            "epa.gov",           # Environmental Protection Agency
        ],
        "sanctions": [
            "ofac.treas.gov",    # Office of Foreign Assets Control
        ],
        "dual_use": [
            "bis.gov",           # Bureau of Industry and Security
        ],
    },
    "eu": {
        "regulation": [
            "eur-lex.europa.eu", # EU Legal Database
        ],
        "germany": [
            "zoll.de",           # German Customs
        ],
        "netherlands": [
            "douane.nl",         # Netherlands Customs
        ],
    },
}

# ============================================================================
# TOPIC DETECTION KEYWORDS
# ============================================================================

AGRI_KEYWORDS = [
    "spice", "spices", "rice", "fruit", "fruits", "vegetable", "vegetables",
    "agricultural", "agri", "farm", "farming", "crop", "crops",
    "apeda", "mpeda", "marine", "seafood", "fish", "prawn", "shrimp",
    "grain", "grains", "wheat", "corn", "maize", "cotton", "tea", "coffee",
    "sugar", "jute", "tobacco", "rubber", "cocoa", "nuts", "almond", "cashew",
]

PHARMA_KEYWORDS = [
    "pharma", "pharmaceutical", "drug", "drugs", "medicine", "medicines",
    "medical", "healthcare", "health", "vaccine", "vaccines",
    "pharmexcil", "api", "active pharmaceutical", "generic",
    "biosimilar", "biotech", "biotechnology",
]

CHEMICAL_KEYWORDS = [
    "chemical", "chemicals", "chemexcil", "petrochemical", "polymer",
    "plastic", "plastics", "rubber", "resin", "resins",
    "fertilizer", "fertilizers", "pesticide", "pesticides",
    "dye", "dyes", "paint", "paints", "adhesive",
]

CREDIT_KEYWORDS = [
    "credit", "insurance", "guarantee", "ecgc", "export credit",
    "trade finance", "letter of credit", "lc", "payment guarantee",
]

FOOD_KEYWORDS = [
    "food", "foods", "fda", "food safety", "food import",
    "nutritional", "supplement", "supplements", "organic",
    "additive", "additives", "preservative", "preservatives",
    "labeling", "packaging", "shelf life",
]

AGRI_US_KEYWORDS = [
    "agricultural", "agri", "usda", "aphis", "animal", "plant",
    "livestock", "poultry", "meat", "dairy", "grain",
    "seed", "seeds", "nursery", "quarantine", "inspection",
]

ENVIRONMENTAL_KEYWORDS = [
    "environmental", "epa", "emission", "emissions", "pollution",
    "chemical", "hazardous", "toxic", "waste", "recycling",
    "clean air", "clean water", "endangered", "wildlife",
]

SANCTIONS_KEYWORDS = [
    "sanction", "sanctions", "ofac", "embargo", "embargoes",
    "restricted", "prohibited", "denied", "blocked",
    "terrorist", "terrorism", "proliferation",
]

DUAL_USE_KEYWORDS = [
    "dual-use", "dual use", "bis", "export control", "export controls",
    "technology", "technologies", "encryption", "software",
    "military", "defense", "defence", "nuclear", "missile",
]

REGULATION_KEYWORDS = [
    "regulation", "regulations", "law", "laws", "legal", "legislation",
    "directive", "directives", "eur-lex", "eu law", "eu regulation",
    "compliance", "requirement", "requirements", "standard", "standards",
]

GERMANY_KEYWORDS = [
    "germany", "german", "zoll", "deutschland", "bundesrepublik",
]

NETHERLANDS_KEYWORDS = [
    "netherlands", "dutch", "douane", "holland", "nederland",
]

# ============================================================================
# TOPIC TO KEYWORD MAPPING
# ============================================================================

TOPIC_KEYWORDS = {
    "india": {
        "agri": AGRI_KEYWORDS,
        "pharma": PHARMA_KEYWORDS,
        "chemical": CHEMICAL_KEYWORDS,
        "credit": CREDIT_KEYWORDS,
    },
    "us": {
        "food": FOOD_KEYWORDS,
        "agri": AGRI_US_KEYWORDS,
        "environmental": ENVIRONMENTAL_KEYWORDS,
        "sanctions": SANCTIONS_KEYWORDS,
        "dual_use": DUAL_USE_KEYWORDS,
    },
    "eu": {
        "regulation": REGULATION_KEYWORDS,
        "germany": GERMANY_KEYWORDS,
        "netherlands": NETHERLANDS_KEYWORDS,
    },
}

# ============================================================================
# REGION DISPLAY NAMES
# ============================================================================

REGION_NAMES = {
    "india": "India",
    "us": "United States",
    "eu": "European Union",
}

# ============================================================================
# TARIFF DOMAINS - Specific sites for HS Code and Duty Rate lookups
# ============================================================================

TARIFF_DOMAINS = {
    "india": ["eximpedia.app"],
    "us": ["trade.gov"],
    "eu": ["access2markets.trade.ec.europa.eu"]
}

# ============================================================================
# TARIFF TRIGGER KEYWORDS - Detect HS Code/Duty queries
# ============================================================================

TARIFF_TRIGGER_KEYWORDS = [
    "hs code", "hscode", "hts code", "htscode", "itc code", "itccode",
    "duty rate", "dutyrate", "tariff rate", "tariffrate", "customs duty", "customsduty",
    "tax rate", "taxrate", "gst rate", "gstrate", "import duty", "importduty",
    "export duty", "exportduty", "classification", "duty percentage",
    "how much duty", "what is the duty", "what is duty",
    "how much tax", "what is the tax", "what is tax"
]

# ============================================================================
# TIERED DOMAIN CREDIBILITY SCORING
# ============================================================================

DOMAIN_CREDIBILITY = {
    # Government domains (highest trust)
    ".gov.in": 2.0,
    ".gov": 2.0,
    ".nic.in": 2.0,
    ".ec.europa.eu": 2.0,
    # Education and research
    ".edu": 1.5,
    ".ac.in": 1.5,
    ".iit": 1.5,
    ".iiit": 1.5,
    # Trade and industry bodies
    ".org": 1.2,
    ".com": 1.0,
    # News and media
    ".co.in": 0.9,
    ".in": 0.9,
}

def get_domain_credibility_boost(url: str) -> float:
    """Return credibility boost multiplier for a given URL."""
    if not url:
        return 1.0
    url_lower = url.lower()
    for domain_suffix, score in DOMAIN_CREDIBILITY.items():
        if domain_suffix in url_lower:
            return score
    return 1.0
