import logging
import time
from typing import List, Dict, Optional, Any
from urllib.parse import quote, urlparse

import requests
from django.conf import settings
from tavily import TavilyClient

from .query_transformer import get_query_transformer

logger = logging.getLogger('rag_pipeline')


class EnhancedWebSearchService:
    """Enhanced web search service with multiple search strategies."""

    def __init__(self):
        self.query_transformer = get_query_transformer()
        # Modern Tavily client (tavily-python renamed TavilySearch -> TavilyClient)
        self.tavily = TavilyClient(api_key=settings.TAVILY_API_KEY)
        self.primary_domains = self._get_primary_domains()
        self.secondary_domains = self._get_secondary_domains()
        self.topic_domains = self._get_topic_domains()

    def _get_primary_domains(self) -> Dict[str, List[str]]:
        """Get primary domain mapping by region."""
        return {
            'india': [
                'dgft.gov.in',
                'cbic.gov.in',
                'icegate.gov.in',
                'mofcom.gov.in',
                'trade.gov.in',
                'commerce.gov.in'
            ],
            'us': [
                'cbp.gov',
                'trade.gov',
                'usitc.gov',
                'hsusitc.gov',
                'fda.gov',
                'epa.gov',
                'nist.gov',
                'commerce.gov'
            ],
            'eu': [
                'access2markets.ec.europa.eu',
                'taxation-customs.ec.europa.eu',
                'ec.europa.eu',
                'eur-lex.europa.eu',
                'trade.ec.europa.eu'
            ]
        }

    def _get_secondary_domains(self) -> Dict[str, List[str]]:
        """Get secondary domain mapping by topic."""
        return {
            'agriculture': ['apeda.gov.in', 'mpeda.gov.in', 'usda.gov', 'fao.org', 'fssai.gov.in'],
            'pharmaceuticals': ['pharmexcil.com', 'fda.gov', 'ema.europa.eu', 'who.int'],
            'chemicals': ['chemexcil.in', 'epa.gov', 'echa.europa.eu', 'pubchem.ncbi.nlm.nih.gov'],
            'food': ['fssai.gov.in', 'fda.gov', 'efsa.europa.eu', 'who.int'],
            'textiles': ['texprocil.org', 'textileindustry.gov.in', 'wto.org'],
            'automotive': ['sae.org', 'oica.net', 'autoindia.gov.in', 'sectorwatch.org'],
            'electronics': ['ieee.org', 'semiconductor.org', 'gsma.com', 'electronicstalk.com'],
            'minerals': ['minerals.gov.in', 'usgs.gov', 'eur-lex.europa.eu']
        }

    def _get_topic_domains(self) -> Dict[str, List[str]]:
        """Get topic-specific domain mapping."""
        return {
            'hs_code': ['usitc.gov', 'trade.gov', 'wto.org', 'comtradeplus.un.org'],
            'duty_rate': ['usitc.gov', 'trade.gov', 'uncomtrade.org', 'worldbank.org'],
            'export_procedure': ['dgft.gov.in', 'mofcom.gov.in', 'trade.gov.in', 'trade.gov'],
            'import_procedure': ['cbic.gov.in', 'icegate.gov.in', 'trade.gov', 'cbp.gov'],
            'regulation': ['europa.eu', 'un.org', 'wto.org', 'iso.org']
        }

    def _get_domain_for_query(self, query_type: str, region: str, topic: str = None) -> List[str]:
        """
        Determine which domains to search based on query type and region.

        Args:
            query_type: Type of query
            region: Region
            topic: Specific topic if known

        Returns:
            List of domains to search
        """
        domains = []

        # Always include primary domains for the region
        primary = self.primary_domains.get(region, [])
        domains.extend(primary)

        # Add topic-specific domains if query type matches
        topic_domains = self.topic_domains.get(query_type, [])
        domains.extend(topic_domains)

        # Add general topic domains
        if topic and topic in self.topic_domains:
            domains.extend(self.topic_domains[topic])

        # Add secondary domains if not already present
        for topic in [query_type, topic]:
            if topic and topic in self.secondary_domains:
                domains.extend([d for d in self.secondary_domains[topic] if d not in domains])

        # Remove duplicates and sort
        domains = list(sorted(set(domains)))

        logger.debug(f"Domains for search: {domains}")
        return domains

    def _search_with_domains(self, query: str, domains: List[str], region: str = None) -> List[Dict[str, Any]]:
        """
        Perform search with specific domain restrictions.

        Args:
            query: Search query
            domains: List of domains to search
            region: Region for logging

        Returns:
            List of search results
        """
        try:
            logger.info(f"Searching with domains: {domains}")
            results = self.tavily.search(
                query=query,
                include_domains=domains,
                max_results=10,
                search_depth="advanced",
                include_raw_content=True,
                include_answer="advanced"
            )
            logger.info(f"Found {len(results.get('results', []))} results from {len(domains)} domains")
            return results.get('results', [])
        except Exception as e:
            logger.error(f"Search failed with domain restriction: {e}")
            # Fallback to unrestricted search
            return self.tavily.search(
                query=query,
                max_results=10,
                search_depth="advanced",
                include_raw_content=True,
                include_answer="advanced"
            ).get('results', [])

    def _search_primary_domains(self, query: str, region: str) -> List[Dict[str, Any]]:
        """
        Search primary domain search (official government sites).

        Args:
            query: Search query
            region: Region

        Returns:
            List of search results
        """
        domains = self.primary_domains.get(region, [])
        logger.info(f"Primary domain search for {region}: {domains}")
        return self._search_with_domains(query, domains, region)

    def _search_secondary_domains(self, query: str, region: str, topic: str = None) -> List[Dict[str, Any]]:
        """
        Search secondary domain search (topic-specific sites).

        Args:
            query: Search query
            region: Region
            topic: Specific topic

        Returns:
            List of search results
        """
        domains = []
        if topic and topic in self.secondary_domains:
            domains.extend(self.secondary_domains[topic])

        if domains:
            logger.info(f"Secondary domain search for topic '{topic}': {domains}")
            return self._search_with_domains(query, domains, region)

        return []

    def _search_topic_domains(self, query: str, query_type: str) -> List[Dict[str, Any]]:
        """
        Search topic-specific domains for query type.

        Args:
            query: Search query
            query_type: Type of query

        Returns:
            List of search results
        """
        domains = self.topic_domains.get(query_type, [])
        if domains:
            logger.info(f"Topic domain search for '{query_type}': {domains}")
            return self._search_with_domains(query, domains, None)

        return []

    def _deduplicate_results(self, results: List[Dict[str, Any]], max_results: int = 10) -> List[Dict[str, Any]]:
        """
        Deduplicate and score search results.

        Args:
            results: List of search results
            max_results: Maximum number of results to return

        Returns:
            Deduplicated and scored results
        """
        seen_urls = set()
        deduped_results = []

        for result in results:
            url = result.get('url', '')
            if url and url in seen_urls:
                continue

            seen_urls.add(url)
            deduped_results.append(result)

            if len(deduped_results) >= max_results:
                break

        return deduped_results

    def _extract_key_info(self, result: Dict[str, Any]) -> Dict[str, str]:
        """
        Extract key information from a search result.

        Args:
            result: Search result dict

        Returns:
            Dictionary of extracted information
        """
        extracted = {
            'title': result.get('title', ''),
            'url': result.get('url', ''),
            'snippet': result.get('snippet', ''),
            'content': result.get('raw_content', ''),
            'score': result.get('score', 0)
        }

        # Extract domain
        try:
            parsed = urlparse(extracted['url'])
            extracted['domain'] = parsed.netloc
        except:
            extracted['domain'] = 'unknown'

        # Clean content
        if extracted['content']:
            extracted['content'] = extracted['content'][:1000]  # Truncate if too long

        return extracted

    def multi_source_search(self, query: str, region: str = None,
                            query_type: str = 'general',
                            max_results: int = 15) -> Dict[str, Any]:
        """
        Perform multi-source web search with enhanced strategies.

        Args:
            query: User's question
            region: Region to focus search on
            query_type: Type of query
            max_results: Maximum total results to return

        Returns:
            Dictionary with search results
        """
        logger.info(f"🚀 ENHANCED WEB SEARCH START | Query: {query}")
        logger.info(f"   Region: {region or 'All regions'}")
        logger.info(f"   Query Type: {query_type}")

        start_time = time.time()

        # Transform query for better search
        best_query, variations = self.query_transformer.enhance_query_for_web_search(
            query, region, max_variations=3
        )

        all_results = []
        sources = []

        # ── STRATEGY 1: Primary Domain Search (Official Government Sites) ──
        primary_results = self._search_primary_domains(best_query, region or 'india')
        for result in primary_results:
            extracted = self._extract_key_info(result)
            extracted['source_type'] = 'primary'
            extracted['region'] = region
            all_results.append(extracted)
            sources.append({
                'type': 'primary',
                'region': region,
                'domains': self.primary_domains.get(region, [])
            })

        # ── STRATEGY 2: Topic Domain Search ──
        topic_results = self._search_topic_domains(best_query, query_type)
        for result in topic_results:
            extracted = self._extract_key_info(result)
            extracted['source_type'] = 'topic'
            extracted['region'] = region
            all_results.append(extracted)

        # ── STRATEGY 3: Secondary Domain Search ──
        secondary_results = []
        if region and region in self.secondary_domains:
            topic = query_type
            if topic not in self.secondary_domains:
                # Use query type directly as topic
                topic = query_type
            secondary_results = self._search_secondary_domains(best_query, region, topic)

        for result in secondary_results:
            extracted = self._extract_key_info(result)
            extracted['source_type'] = 'secondary'
            extracted['region'] = region
            all_results.append(extracted)

        # Deduplicate results
        all_results = self._deduplicate_results(all_results, max_results=max_results)

        # Score results by quality
        scored_results = self._score_results(all_results, query)

        # Prepare response
        response = {
            'success': True,
            'query': best_query,
            'query_variations': variations,
            'total_results': len(scored_results),
            'results': scored_results,
            'sources': sources,
            'region': region,
            'query_type': query_type,
            'search_time': time.time() - start_time,
            'confidence': self._calculate_confidence(scored_results, query_type)
        }

        logger.info(f"✅ ENHANCED WEB SEARCH COMPLETE | Results: {len(scored_results)} | Time: {response['search_time']:.2f}s")
        return response

    def _score_results(self, results: List[Dict[str, Any]], query: str) -> List[Dict[str, Any]]:
        """
        Score results by relevance and quality.

        Args:
            results: List of search results
            query: Original query

        Returns:
            Scored and sorted results
        """
        scored = []

        for result in results:
            score = result.get('score', 0)

            # Boost primary domains
            if result.get('source_type') == 'primary':
                score *= 1.5

            # Boost official domains (gov, edu)
            domain = result.get('domain', '').lower()
            if any(x in domain for x in ['gov', 'edu', 'official']):
                score *= 1.3

            # Boost content matching
            content = result.get('content', '').lower()
            if content and len(content) > 50:
                query_lower = query.lower()
                words = query_lower.split()
                matches = sum(1 for word in words if word in content and len(word) > 2)
                score += matches * 0.1

            result['relevance_score'] = round(score, 3)
            scored.append(result)

        # Sort by relevance score
        scored.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)

        return scored

    def _calculate_confidence(self, results: List[Dict[str, Any]], query_type: str) -> float:
        """
        Calculate overall confidence score for search results.

        Args:
            results: Search results
            query_type: Type of query

        Returns:
            Confidence score (0-1)
        """
        if not results:
            return 0.0

        # Confidence based on result count and sources
        confidence = min(1.0, len(results) * 0.1)

        # Boost for multiple sources
        sources = set(r.get('source_type') for r in results)
        if len(sources) >= 2:
            confidence += 0.1
        if len(sources) >= 3:
            confidence += 0.1

        # Boost for primary domains
        primary_count = sum(1 for r in results if r.get('source_type') == 'primary')
        if primary_count > 0:
            confidence += 0.1

        return min(1.0, confidence)


# Singleton instance
_enhanced_web_search_service = None

def get_enhanced_web_search_service() -> EnhancedWebSearchService:
    """Get or create the enhanced web search service singleton."""
    global _enhanced_web_search_service
    if _enhanced_web_search_service is None:
        _enhanced_web_search_service = EnhancedWebSearchService()
    return _enhanced_web_search_service
