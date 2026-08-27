import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger('rag_pipeline')


class WebSearchMetrics:
    """Track and calculate web search performance metrics."""

    def __init__(self):
        self.metrics = {
            'total_queries': 0,
            'successful_queries': 0,
            'failed_queries': 0,
            'total_results': 0,
            'total_search_time': 0,
            'avg_search_time': 0.0,
            'avg_results_per_query': 0.0,
            'confidence_scores': [],
            'region_usage': {},
            'query_type_distribution': {},
            'sources_used': {}
        }

    def record_query(self, success: bool, num_results: int, search_time: float,
                     region: str = None, query_type: str = 'general'):
        """
        Record a query for metrics tracking.

        Args:
            success: Whether query was successful
            num_results: Number of results returned
            search_time: Time taken to search (seconds)
            region: Region searched
            query_type: Type of query
        """
        self.metrics['total_queries'] += 1

        if success:
            self.metrics['successful_queries'] += 1
            self.metrics['total_results'] += num_results
            self.metrics['total_search_time'] += search_time

            # Calculate averages
            if self.metrics['successful_queries'] > 0:
                self.metrics['avg_search_time'] = (
                    self.metrics['total_search_time'] / self.metrics['successful_queries']
                )
                self.metrics['avg_results_per_query'] = (
                    self.metrics['total_results'] / self.metrics['successful_queries']
                )

            # Track region usage
            if region:
                self.metrics['region_usage'][region] = (
                    self.metrics['region_usage'].get(region, 0) + 1
                )

            # Track query type distribution
            self.metrics['query_type_distribution'][query_type] = (
                self.metrics['query_type_distribution'].get(query_type, 0) + 1
            )
        else:
            self.metrics['failed_queries'] += 1

    def record_confidence(self, confidence: float):
        """Record a confidence score."""
        self.metrics['confidence_scores'].append(confidence)

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of all metrics."""
        return {
            'timestamp': datetime.now().isoformat(),
            'total_queries': self.metrics['total_queries'],
            'successful_queries': self.metrics['successful_queries'],
            'failed_queries': self.metrics['failed_queries'],
            'success_rate': (
                self.metrics['successful_queries'] / self.metrics['total_queries']
                if self.metrics['total_queries'] > 0 else 0
            ),
            'total_results': self.metrics['total_results'],
            'avg_results_per_query': self.metrics['avg_results_per_query'],
            'avg_search_time': round(self.metrics['avg_search_time'], 2),
            'avg_confidence': (
                sum(self.metrics['confidence_scores']) / len(self.metrics['confidence_scores'])
                if self.metrics['confidence_scores'] else 0
            ),
            'region_usage': self.metrics['region_usage'],
            'query_type_distribution': self.metrics['query_type_distribution']
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get detailed statistics."""
        return {
            'metrics': self.get_summary(),
            'average_metrics': {
                'avg_results': round(self.metrics['avg_results_per_query'], 2),
                'avg_time': round(self.metrics['avg_search_time'], 2),
                'avg_confidence': round(
                    sum(self.metrics['confidence_scores']) / len(self.metrics['confidence_scores'])
                    if self.metrics['confidence_scores'] else 0, 2
                )
            }
        }

    def export_to_json(self, filepath: str):
        """Export metrics to JSON file."""
        summary = self.get_summary()
        with open(filepath, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"✅ Metrics exported to {filepath}")


class WebSearchValidator:
    """Validate and check web search results."""

    def __init__(self):
        self.valid_domains = self._get_valid_domains()

    def _get_valid_domains(self) -> set:
        """Get list of valid domains."""
        return {
            'dgft.gov.in', 'cbic.gov.in', 'icegate.gov.in',
            'cbp.gov', 'trade.gov', 'usitc.gov',
            'access2markets.ec.europa.eu', 'taxation-customs.ec.europa.eu',
            'ec.europa.eu'
        }

    def is_valid_domain(self, url: str) -> bool:
        """
        Check if a URL is from a valid domain.

        Args:
            url: URL to validate

        Returns:
            True if valid domain, False otherwise
        """
        if not url:
            return False

        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace('www.', '')
            return domain in self.valid_domains
        except:
            return False

    def validate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate search results.

        Args:
            results: Search results to validate

        Returns:
            Validation report
        """
        valid = []
        invalid = []
        suspicious = []

        for result in results:
            url = result.get('url', '')

            if self.is_valid_domain(url):
                valid.append(result)
            else:
                invalid.append(result)

            # Flag suspicious domains (not gov, edu, official)
            domain = url.lower()
            if not any(x in domain for x in ['gov', 'edu', 'official']):
                suspicious.append(result)

        return {
            'total': len(results),
            'valid': len(valid),
            'invalid': len(invalid),
            'suspicious': len(suspicious),
            'valid_percentage': round(len(valid) / len(results) * 100, 1) if results else 0,
            'valid_results': valid[:10],  # Top 10 valid
            'invalid_urls': [r.get('url') for r in invalid[:5]]
        }


class WebSearchCache:
    """Cache web search results for performance."""

    def __init__(self, ttl_seconds: int = 3600):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time to live for cached entries
        """
        self.cache = {}
        self.ttl_seconds = ttl_seconds
        self.hits = 0
        self.misses = 0

    def get(self, query: str, region: str = None) -> Optional[Dict[str, Any]]:
        """
        Get cached search results.

        Args:
            query: Search query
            region: Region

        Returns:
            Cached results or None
        """
        cache_key = self._make_key(query, region)
        now = datetime.now()

        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if (now - entry['timestamp']).total_seconds() < self.ttl_seconds:
                self.hits += 1
                logger.debug(f"✅ Cache hit for query: {query[:50]}")
                return entry['data']
            else:
                # Expired entry
                del self.cache[cache_key]

        self.misses += 1
        logger.debug(f"❌ Cache miss for query: {query[:50]}")
        return None

    def set(self, query: str, results: Dict[str, Any], region: str = None):
        """
        Store search results in cache.

        Args:
            query: Search query
            results: Search results
            region: Region
        """
        cache_key = self._make_key(query, region)
        self.cache[cache_key] = {
            'data': results,
            'timestamp': datetime.now()
        }
        logger.debug(f"💾 Cached results for query: {query[:50]}")

    def _make_key(self, query: str, region: str = None) -> str:
        """Create cache key from query and region."""
        region_part = f"-{region}" if region else ""
        return f"web_search:{query[:50]}{region_part}".lower()

    def clear(self):
        """Clear all cached entries."""
        self.cache.clear()
        self.hits = 0
        self.misses = 0
        logger.info("🧹 Web search cache cleared")

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self.hits + self.misses
        hit_rate = (self.hits / total * 100) if total > 0 else 0

        return {
            'hits': self.hits,
            'misses': self.misses,
            'hit_rate': round(hit_rate, 2),
            'entries': len(self.cache),
            'ttl_seconds': self.ttl_seconds
        }


# Singleton instances
_web_search_metrics = WebSearchMetrics()
_web_search_validator = WebSearchValidator()
_web_search_cache = WebSearchCache(ttl_seconds=3600)  # 1 hour TTL


def get_web_search_metrics() -> WebSearchMetrics:
    """Get the web search metrics instance."""
    return _web_search_metrics


def get_web_search_validator() -> WebSearchValidator:
    """Get the web search validator instance."""
    return _web_search_validator


def get_web_search_cache() -> WebSearchCache:
    """Get the web search cache instance."""
    return _web_search_cache


def reset_web_search_cache():
    """Reset the web search cache."""
    _web_search_cache.clear()
