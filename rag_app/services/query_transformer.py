import logging
import re
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger('rag_pipeline')

# Query type patterns
QUERY_TYPE_PATTERNS = {
    'hs_code': [
        r'hs[ _]code', r'heading[ _]code', r'chapter[ _]code',
        r'tariff[ _]code', r'code[ _]for', r'identify[ _]the[ _]hs[ _]code',
        r'what[ _]is[ _]the[ _]hs[ _]code[ _]for'
    ],
    'duty_rate': [
        r'duty[ _]rate', r'tariff[ _]rate', r'tax', r'customs[ _]duty',
        r'import[ _]duty', r'export[ _]duty', r'percent'
    ],
    'export_procedure': [
        r'export[ _]procedure', r'how[ _]to[ _]export', r'export[ _]steps',
        r'export[ _]process', r'procedure[ _]for[ _]export', r'step[ _]by[ _]step[ _]export'
    ],
    'import_procedure': [
        r'import[ _]procedure', r'how[ _]to[ _]import', r'import[ _]steps',
        r'import[ _]process', r'procedure[ _]for[ _]import'
    ],
    'regulation': [
        r'regulation', r'law', r'policy', r'guideline',
        r'standard', r'rule', r'legislation', r'act'
    ],
    'quota': [
        r'quota', r'limit', r'export[ _]quota', r'import[ _]limit'
    ],
    'license': [
        r'license', r'licensing', r'permit', r'authorization'
    ],
    'certificate': [
        r'certificate', r'certification', r'certificate[ _]of[ _]origin',
        r'coo', r'certificate[ _]required'
    ],
    'sanitary': [
        r'sanitary[ _]phytosanitary', r'sps', r'phytosanitary',
        r'fssai', r'food[ _]safety', r'hsf'
    ]
}

# Entity extraction patterns
ENTITY_PATTERNS = {
    'commodity': [
        r'\b(wheat|corn|rice|cotton|sugar|coffee|tea|spice|vegetable|fruit|meat|dairy|oil|chemical|pharmaceutical|textile|electronics|automobile|steel|cement|mineral|gem|jewel|jewelry)\b'
    ],
    'region': [
        r'\b(india|usa|united[ _]states|us|eu|european[ _]union|united[ _]kingdom|uk|asia|europe|americas)\b',
        r'\b(import[ _]from|export[ _]to|from|to)\s+(india|usa|eu|united[ _]states)'
    ],
    'hs_prefix': [
        r'hs[ _]code[ _]for[ _]([0-9]{2}|[0-9]{4})',
        r'([0-9]{2}|[0-9]{4})[ _]?-[0-9]+'
    ]
}

# Region context mappings
REGION_DOMAINS = {
    'india': ['dgft.gov.in', 'cbic.gov.in', 'icegate.gov.in', 'mofcom.gov.in', 'ministry.gov.in'],
    'us': ['cbp.gov', 'trade.gov', 'usitc.gov', 'hsusitc.gov', 'fda.gov', 'epa.gov'],
    'eu': ['access2markets.ec.europa.eu', 'taxation-customs.ec.europa.eu', 'ec.europa.eu']
}

# Topic-specific domains
TOPIC_DOMAINS = {
    'agriculture': ['apeda.gov.in', 'mpeda.gov.in', 'usda.gov', 'fao.org'],
    'pharmaceuticals': ['pharmexcil.com', 'fda.gov', 'ema.europa.eu'],
    'chemicals': ['chemexcil.in', 'epa.gov', 'echa.europa.eu'],
    'food': ['fssai.gov.in', 'fda.gov', 'efsa.europa.eu'],
    'textiles': ['texprocil.org', 'textiles.gov.in', 'textileindustry.com'],
    'automotive': ['sae.org', 'oica.net', 'autoindia.gov.in'],
    'electronics': ['ieee.org', 'semiconductor.org', 'gsma.com'],
    'minerals': ['minerals.gov.in', 'usgs.gov', 'eur-lex.europa.eu']
}

class QueryTransformer:
    """Transform vague user queries into specific, search-optimized queries."""

    def __init__(self):
        self.query_types = QUERY_TYPE_PATTERNS
        self.entity_patterns = ENTITY_PATTERNS

    def detect_query_type(self, query: str) -> str:
        """
        Detect the type of query being asked.

        Args:
            query: User's question

        Returns:
            Query type (hs_code, duty_rate, export_procedure, etc.)
        """
        query_lower = query.lower().strip()

        for qtype, patterns in self.query_types.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.info(f"Detected query type: {qtype}")
                    return qtype

        return 'general'

    def extract_entities(self, query: str, query_type: str) -> Dict[str, str]:
        """
        Extract entities from the query.

        Args:
            query: User's question
            query_type: Type of query

        Returns:
            Dictionary of extracted entities
        """
        entities = {}
        query_lower = query.lower()

        # Extract region
        for region in REGION_DOMAINS.keys():
            if region in query_lower:
                entities['region'] = region
                break

        # Extract commodity
        for commodity, patterns in self.entity_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    entities['commodity'] = commodity
                    break
            if 'commodity' in entities:
                break

        # Extract HS code prefix if present
        for pattern in self.entity_patterns['hs_prefix']:
            match = re.search(pattern, query_lower, re.IGNORECASE)
            if match:
                entities['hs_prefix'] = match.group(1)
                break

        logger.debug(f"Extracted entities: {entities}")
        return entities

    def apply_region_context(self, query: str, region: Optional[str] = None) -> str:
        """
        Apply region-specific context to the query.

        Args:
            query: User's question
            region: Region to apply context for

        Returns:
            Query with region context
        """
        if not region:
            return query

        region_map = {
            'india': 'India',
            'us': 'United States',
            'eu': 'European Union'
        }

        region_name = region_map.get(region, region.capitalize())

        # Check if region already mentioned
        if region_name.lower() in query.lower():
            return query

        # Prepend region context for specific query types
        query_type = self.detect_query_type(query)
        query_type_map = {
            'export_procedure': f'{region_name} export procedure for',
            'import_procedure': f'{region_name} import procedure for',
            'duty_rate': f'{region_name} {query.lower()}',
            'hs_code': f'{region_name} HS code for'
        }

        if query_type in query_type_map:
            return f"{query_type_map[query_type]} {query.strip()}"

        return query

    def generate_search_variations(self, query: str, region: Optional[str] = None,
                                   query_type: str = 'general') -> List[str]:
        """
        Generate multiple search variations for better coverage.

        Args:
            query: User's question
            region: Region to apply context for
            query_type: Type of query

        Returns:
            List of search query variations
        """
        variations = []

        # Base query
        base_query = self.apply_region_context(query, region)
        variations.append(base_query)

        # Add specific query type keywords
        if query_type == 'hs_code':
            variations.append(f"{base_query} HS code tariff")
            variations.append(f"{base_query} heading code")
            variations.append(f"{base_query} tariff schedule")

        elif query_type == 'duty_rate':
            variations.append(f"{base_query} import duty rate")
            variations.append(f"{base_query} customs duty")
            variations.append(f"{base_query} tariff rate")

        elif query_type == 'export_procedure':
            variations.append(f"{base_query} export procedure step by step")
            variations.append(f"{base_query} export documentation requirements")
            variations.append(f"{base_query} export licensing requirements")

        elif query_type == 'import_procedure':
            variations.append(f"{base_query} import procedure step by step")
            variations.append(f"{base_query} import documentation requirements")
            variations.append(f"{base_query} import licensing requirements")

        elif query_type == 'regulation':
            variations.append(f"{base_query} latest regulation")
            variations.append(f"{base_query} policy guideline")
            variations.append(f"{base_query} legal framework")

        # Generate acronym variations
        if query_type in ['hs_code', 'duty_rate']:
            variations.append(base_query.upper().replace(' ', '_'))

        # Generate year-specific queries
        variations.append(f"{base_query} 2024")
        variations.append(f"{base_query} 2025")
        variations.append(f"{base_query} recent")

        logger.debug(f"Generated {len(variations)} search variations")
        return variations

    def enhance_query_for_web_search(self, query: str, region: Optional[str] = None,
                                     max_variations: int = 3) -> Tuple[str, List[str]]:
        """
        Main function to enhance query for web search.

        Args:
            query: User's question
            region: Region to apply context for
            max_variations: Maximum number of search variations to generate

        Returns:
            Tuple of (best_query, search_variations)
        """
        # Detect query type
        query_type = self.detect_query_type(query)

        # Extract entities
        entities = self.extract_entities(query, query_type)

        # Generate search variations
        variations = self.generate_search_variations(query, region, query_type)

        # Select best variation as main query
        best_query = variations[0] if variations else query

        logger.info(f"Enhanced query for web search:")
        logger.info(f"  Original: {query}")
        logger.info(f"  Type: {query_type}")
        logger.info(f"  Region: {region or 'Not specified'}")
        logger.info(f"  Entities: {entities}")
        logger.info(f"  Best query: {best_query}")
        logger.info(f"  Variations: {variations[:max_variations]}")

        return best_query, variations[:max_variations]


# Singleton instance
_query_transformer = None

def get_query_transformer() -> QueryTransformer:
    """Get or create the query transformer singleton."""
    global _query_transformer
    if _query_transformer is None:
        _query_transformer = QueryTransformer()
    return _query_transformer
