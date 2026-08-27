"""
Query Understanding Module

Understands the user query BEFORE searching:
1. Topic detection — maps query words to known topics/commodities
2. Query expansion — adds synonyms and related terms
3. Intent classification — determines what kind of answer is needed
4. Document identification — predicts which documents are relevant

This replaces the naive "split into words and search" approach.
"""

import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger('rag_pipeline')

# ── Commodity/Topic Keyword Mappings ──
# Maps user query words to standardized topics

COMMODITY_MAP = {
    'wheat': ['wheat', 'durum_wheat', 'grain', 'cereal'],
    'rice': ['rice', 'basmati', 'paddy', 'grain'],
    'cotton': ['cotton', 'textile', 'fabric', 'yarn', 'fiber'],
    'steel': ['steel', 'iron', 'metal'],
    'chemical': ['chemical', 'chemexcil', 'petrochemical', 'polymer', 'plastic'],
    'pharma': ['pharma', 'pharmaceutical', 'drug', 'medicine', 'api', 'biosimilar'],
    'food': ['food', 'fssai', 'spice', 'spices', 'fruit', 'vegetable', 'agricultural'],
    'fish': ['fish', 'seafood', 'marine', 'shrimp', 'prawn'],
    'oil': ['oil', 'soya', 'sunflower', 'palm', 'crude_oil'],
    'sugar': ['sugar', 'jaggery'],
    'leather': ['leather', 'hide', 'footwear'],
    'jewelry': ['jewelry', 'gem', 'diamond', 'gold', 'silver'],
    'electronics': ['electronics', 'computer', 'mobile', 'semiconductor'],
}

# ── Query Intent Patterns ──
INTENT_PATTERNS = {
    'find_quantity': [
        r'how much', r'how many', r'quantity', r'minimum', r'maximum',
        r'limit', r'threshold', r'cap', r'quota', r'amount',
        r'\d+\s*(mt|kg|tonne|liter|unit|piece)',
    ],
    'find_procedure': [
        r'how to', r'what paperwork', r'what document', r'what form',
        r'procedure', r'steps? to', r'apply for', r'register',
        r'process for', r'how do i',
    ],
    'find_rule': [
        r'what (is|are|is the)', r'requirement', r'regulation',
        r'rule', r'law', r'compliance', r'must', r'shall',
        r'allowed', r'permitted', r'prohibited', r'banned',
        r'penalty', r'fine', r'punishment',
    ],
    'compare': [
        r'vs\b', r'versus', r'difference between', r'compare',
        r'how does.*differ', r'what.*different',
    ],
    'find_rate': [
        r'duty', r'tariff', r'rate', r'tax', r'fee', r'hs code',
        r'hts', r'customs duty', r'import duty', r'export duty',
    ],
    'find_deadline': [
        r'deadline', r'when', r'date', r'expiry', r'valid until',
        r'validity', r'last date', r'time limit', r'by when',
    ],
    'greeting': [
        r'^hi\b', r'^hello\b', r'^hey\b', r'^good morning',
        r'^good evening', r'^thanks', r'^thank you',
    ],
}

# ── Synonym Expansions ──
SYNONYM_MAP = {
    'minimum': ['minimum', 'floor', 'threshold', 'lowest', 'at least', 'not less than'],
    'maximum': ['maximum', 'cap', 'ceiling', 'highest', 'limit', 'not more than'],
    'quantity': ['quantity', 'amount', 'volume', 'tonnes', 'mt', 'kilogram', 'kg'],
    'paperwork': ['paperwork', 'documentation', 'documents', 'forms', 'certificates'],
    'import': ['import', 'bring into', 'enter', 'incoming', 'inward'],
    'export': ['export', 'ship out', 'send abroad', 'outgoing', 'outward'],
    'requirement': ['requirement', 'needed', 'mandatory', 'must', 'required', 'shall'],
    'penalty': ['penalty', 'fine', 'punishment', 'confiscation', 'disqualification'],
    'procedure': ['procedure', 'process', 'steps', 'how to', 'method'],
    'deadline': ['deadline', 'date', 'expiry', 'valid until', 'last date', 'by when'],
    'duty': ['duty', 'tariff', 'tax', 'rate', 'customs duty', 'import duty'],
    'compliance': ['compliance', 'regulation', 'rule', 'law', 'requirement'],
    'chemical': ['chemical', 'reach', 'substance', 'hazardous', 'toxic'],
}


class QueryUnderstanding:
    """
    Understand a user query and expand it for multi-source retrieval.
    
    Usage:
        qa = QueryUnderstanding()
        result = qa.understand("wheat minimum quantity for export", region='india')
        
        result = {
            'topics': ['wheat_export'],
            'commodities': ['wheat', 'grain'],
            'intent': 'find_quantity',
            'expanded_terms': ['wheat', 'minimum', 'quantity', 'export', 
                               'mt', 'tonnes', 'threshold', 'at least'],
            'likely_documents': ['DGFT_Notification_62', 'DGFT_Public_Notice_49'],
            'fact_types': ['quantity_limit'],
        }
    """

    def understand(self, query: str, region: str = None) -> Dict:
        """Full query understanding pipeline."""
        query_lower = query.lower().strip()
        query_words = set(re.findall(r'\w+', query_lower))

        # Step 1: Intent classification
        intent = self._classify_intent(query_lower)

        # Step 2: Topic detection
        topics = self._detect_topics(query_lower)

        # Step 3: Commodity detection
        commodities = self._detect_commodities(query_lower)

        # Step 4: Query expansion (synonyms)
        expanded_terms = self._expand_query(query_lower, query_words)

        # Step 5: Document identification (which docs are likely relevant)
        likely_docs = self._identify_documents(query_lower, topics, commodities, region)

        # Step 6: Fact type prediction (what kind of facts to look for)
        fact_types = self._predict_fact_types(intent, query_lower)

        result = {
            'original_query': query,
            'region': region,
            'intent': intent,
            'topics': topics,
            'commodities': commodities,
            'expanded_terms': list(set(expanded_terms)),
            'likely_documents': likely_docs,
            'fact_types': fact_types,
        }

        logger.info(f"🧠 QUERY UNDERSTANDING | '{query}' | intent={intent} | "
                    f"topics={topics[:3]} | commodities={commodities[:3]} | "
                    f"expanded={len(expanded_terms)} terms | likely_docs={likely_docs[:3]}")

        return result

    def _classify_intent(self, query_lower: str) -> str:
        """Classify the query intent."""
        scores = {}
        for intent_name, patterns in INTENT_PATTERNS.items():
            score = sum(1 for p in patterns if re.search(p, query_lower))
            if score > 0:
                scores[intent_name] = score

        if not scores:
            return 'general_search'

        return max(scores, key=scores.get)

    def _detect_topics(self, query_lower: str) -> List[str]:
        """Detect topics from the query."""
        topics = []
        for keyword, topic_list in COMMODITY_MAP.items():
            if keyword in query_lower:
                topics.extend([t for t in topic_list if t not in topics])
        return topics[:10]

    def _detect_commodities(self, query_lower: str) -> List[str]:
        """Detect commodities mentioned in the query."""
        commodities = []
        for keyword in COMMODITY_MAP:
            if keyword in query_lower and keyword not in commodities:
                commodities.append(keyword)
        return commodities[:10]

    def _expand_query(self, query_lower: str, query_words: Set[str]) -> List[str]:
        """Expand query with synonyms and related terms."""
        expanded = list(query_words)

        for word in query_words:
            # Check exact match in synonym map
            if word in SYNONYM_MAP:
                expanded.extend(SYNONYM_MAP[word])
            else:
                # Check if any synonym key contains this word
                for key, synonyms in SYNONYM_MAP.items():
                    if word in synonyms:
                        expanded.extend(synonyms)
                        break

        # Add commodity-related terms
        for keyword, topic_list in COMMODITY_MAP.items():
            if keyword in query_lower:
                expanded.extend(topic_list)

        # Remove duplicates, keep order
        seen = set()
        result = []
        for term in expanded:
            if term not in seen and len(term) > 1:
                seen.add(term)
                result.append(term)

        return result

    def _identify_documents(self, query_lower: str, topics: List[str],
                            commodities: List[str], region: str = None) -> List[str]:
        """
        Predict which documents are likely relevant.
        Uses topic/commodity keywords to match against document titles and metadata.
        """
        # Build a relevance score for each known document type
        doc_scores = {}

        # India-specific document patterns
        india_patterns = {
            'DGFT': ['dgft', 'export', 'import', 'ftp', 'foreign trade', 'handbook'],
            'CBIC': ['cbic', 'customs', 'duty', 'tariff', 'icegate'],
            'eSANCHIT': ['esanchit', 'document', 'upload'],
            'RoDTEP': ['rodtep', 'rebate', 'duty'],
            'FTP': ['ftp', 'foreign trade policy'],
            'IEC': ['iec', 'importer exporter code'],
            'Certificate of Origin': ['certificate of origin', 'COO'],
        }

        eu_patterns = {
            'UCC': ['ucc', 'customs code', 'union customs'],
            'REACH': ['reach', 'chemical', 'substance', 'registration'],
            'EORI': ['eori', 'economic operator'],
            'Food Safety': ['food safety', 'food regulation'],
        }

        us_patterns = {
            'CBP': ['cbp', 'customs', 'border protection'],
            'FDA': ['fda', 'food', 'drug', 'pharmaceutical', 'fsvp'],
            'USDA': ['usda', 'agricultural', 'plant', 'animal'],
            'CTPAT': ['ctpat', 'trusted trader'],
        }

        all_patterns = {}
        if region == 'india' or region is None:
            all_patterns.update(india_patterns)
        if region == 'eu' or region is None:
            all_patterns.update(eu_patterns)
        if region == 'us' or region is None:
            all_patterns.update(us_patterns)

        for doc_name, keywords in all_patterns.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            # Boost if topics/commodities match
            for topic in topics:
                if topic in ' '.join(keywords):
                    score += 2
            for commodity in commodities:
                if commodity in ' '.join(keywords):
                    score += 2
            if score > 0:
                doc_scores[doc_name] = score

        # Sort by score descending
        sorted_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)
        return [doc for doc, score in sorted_docs[:5]]

    def _predict_fact_types(self, intent: str, query_lower: str) -> List[str]:
        """Predict what fact types to search for based on query intent."""
        intent_to_facts = {
            'find_quantity': ['quantity_limit', 'fee_rate'],
            'find_procedure': ['procedure_step', 'requirement', 'document_type'],
            'find_rule': ['requirement', 'eligibility', 'exemption'],
            'compare': ['requirement', 'procedure_step', 'quantity_limit'],
            'find_rate': ['fee_rate', 'quantity_limit'],
            'find_deadline': ['deadline'],
            'find_penalty': ['penalty', 'eligibility'],
        }
        return intent_to_facts.get(intent, ['requirement', 'procedure_step'])
