import logging
from typing import List, Dict, Optional, Any
import json

logger = logging.getLogger('rag_pipeline')


class ResultSynthesizer:
    """Synthesize and rank web search results for better quality."""

    def __init__(self):
        self.min_relevance_score = 0.3
        self.max_sources = 5
        self.max_words_per_source = 200

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ''

        # Remove extra whitespace
        text = ' '.join(text.split())

        # Truncate if too long
        if len(text) > self.max_words_per_source * 10:  # 10 words per char
            text = text[:self.max_words_per_source * 10] + '...'

        return text

    def _extract_important_sentences(self, text: str, num_sentences: int = 3) -> str:
        """
        Extract the most important sentences from text.

        Args:
            text: Text to extract from
            num_sentences: Number of sentences to extract

        Returns:
            Extracted sentences
        """
        if not text:
            return ''

        sentences = text.split('.')

        # Score sentences by length and content density
        scored_sentences = []
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Score: longer sentences are generally more informative
            length_score = min(len(sentence) / 100, 1.0)

            # Content density: words per sentence
            word_count = len(sentence.split())
            density_score = min(word_count / 20, 1.0)

            # Final score
            score = (length_score + density_score) / 2
            scored_sentences.append((sentence, score))

        # Sort by score
        scored_sentences.sort(key=lambda x: x[1], reverse=True)

        # Extract top sentences
        top_sentences = [s for s, _ in scored_sentences[:num_sentences]]

        # Join sentences
        return '. '.join(top_sentences) + '.'

    def _verify_source_credibility(self, source_type: str, domain: str) -> float:
        """
        Verify source credibility score.

        Args:
            source_type: Type of source (primary, secondary, topic)
            domain: Domain name

        Returns:
            Credibility score (0-1)
        """
        credibility = 0.5

        # Boost primary domains
        if source_type == 'primary':
            credibility += 0.4
        elif source_type == 'secondary':
            credibility += 0.2

        # Boost official domains
        domain_lower = domain.lower()
        if any(x in domain_lower for x in ['gov', 'official', 'europe', 'eu']):
            credibility += 0.2

        # Boost educational domains
        if 'edu' in domain_lower:
            credibility += 0.1

        return min(credibility, 1.0)

    def _summarize_source_content(self, result: Dict[str, Any]) -> str:
        """
        Summarize the content from a single search result.

        Args:
            result: Search result dict

        Returns:
            Summarized content
        """
        content = result.get('content', '')
        title = result.get('title', '')
        url = result.get('url', '')

        # Extract important sentences
        summary = self._extract_important_sentences(content, num_sentences=3)

        # Format citation
        citation = f"**{title}** ([{result.get('domain', 'Source')}])"

        return f"{citation}\n\n{summary}"

    def _validate_cross_reference(self, results: List[Dict[str, Any]],
                                    key_info: str) -> float:
        """
        Validate information across multiple sources.

        Args:
            results: Search results
            key_info: Information to validate

        Returns:
            Cross-reference score (0-1)
        """
        if len(results) < 2:
            return 0.5  # Not enough sources for validation

        # Count sources mentioning the key info
        mentioned_sources = 0
        for result in results:
            content = result.get('content', '').lower()
            if key_info.lower() in content:
                mentioned_sources += 1

        # Cross-reference score based on number of sources
        score = mentioned_sources / len(results)

        return score

    def _rank_sources(self, results: List[Dict[str, Any]],
                      query: str) -> List[Dict[str, Any]]:
        """
        Rank search results by relevance and credibility.

        Args:
            results: Search results
            query: Original query

        Returns:
            Ranked results
        """
        ranked = []

        for result in results:
            # Base score from search result
            score = result.get('relevance_score', 0)

            # Apply credibility boost
            credibility = self._verify_source_credibility(
                result.get('source_type', 'secondary'),
                result.get('domain', '')
            )
            score *= credibility

            # Apply content quality boost
            content = result.get('content', '')
            if content and len(content) > 50:
                score += 0.1  # Bonus for substantive content

            # Apply domain trust boost
            domain = result.get('domain', '').lower()
            if any(x in domain for x in ['gov', 'edu', 'official']):
                score += 0.1

            result['final_score'] = round(score, 3)
            ranked.append(result)

        # Sort by final score
        ranked.sort(key=lambda x: x.get('final_score', 0), reverse=True)

        return ranked

    def synthesize_results(self, search_response: Dict[str, Any],
                           query: str) -> Dict[str, Any]:
        """
        Synthesize and rank web search results for LLM context.

        Args:
            search_response: Raw search response from EnhancedWebSearchService
            query: Original user query

        Returns:
            Synthesized and ranked results
        """
        logger.info(f"🧠 SYNTHESIZING WEB SEARCH RESULTS | Query: {query}")

        results = search_response.get('results', [])
        total_results = len(results)

        if not results:
            logger.warning("⚠️ No results to synthesize")
            return {
                'success': True,
                'total': 0,
                'synthesized_results': []
            }

        # Rank sources
        ranked_results = self._rank_sources(results, query)

        # Filter by relevance score
        relevant_results = [
            r for r in ranked_results
            if r.get('final_score', 0) >= self.min_relevance_score
        ]

        # Limit number of sources
        relevant_results = relevant_results[:self.max_sources]

        # Synthesize each source
        synthesized = []
        cross_ref_score = 0.0

        for i, result in enumerate(relevant_results):
            # Summarize content
            summary = self._summarize_source_content(result)

            # Calculate cross-reference score for top source
            if i == 0 and relevant_results:
                key_info = query[:50]  # Use first part of query as key info
                cross_ref_score = self._validate_cross_reference(
                    relevant_results, key_info
                )

            synthesized.append({
                'source_id': i + 1,
                'source_type': result.get('source_type'),
                'region': result.get('region'),
                'domain': result.get('domain'),
                'title': result.get('title', ''),
                'url': result.get('url', ''),
                'relevance_score': result.get('relevance_score', 0),
                'final_score': result.get('final_score', 0),
                'synthesized_content': summary,
                'credibility_score': result.get('final_score', 0)
            })

        # Calculate overall confidence
        overall_confidence = search_response.get('confidence', 0)
        if cross_ref_score > 0:
            overall_confidence = min(1.0, overall_confidence + cross_ref_score * 0.2)

        logger.info(f"✅ SYNTHESIS COMPLETE | Synthesized: {len(synthesized)} of {total_results} results")
        logger.info(f"   Cross-reference score: {cross_ref_score:.2f}")
        logger.info(f"   Overall confidence: {overall_confidence:.2f}")

        return {
            'success': True,
            'total': total_results,
            'synthesized_count': len(synthesized),
            'synthesized_results': synthesized,
            'cross_reference_score': round(cross_ref_score, 3),
            'overall_confidence': round(overall_confidence, 3),
            'query': search_response.get('query'),
            'region': search_response.get('region')
        }

    def create_llm_context(self, synthesis_response: Dict[str, Any],
                           query: str) -> str:
        """
        Create LLM-ready context from synthesized results.

        Args:
            synthesis_response: Synthesis response from ResultSynthesizer
            query: Original user query

        Returns:
            LLM-ready context string
        """
        synthesized = synthesis_response.get('synthesized_results', [])
        confidence = synthesis_response.get('overall_confidence', 0)
        cross_ref_score = synthesis_response.get('cross_reference_score', 0)

        if not synthesized:
            return f"⚠️ No relevant web search results found for query: {query}"

        # Build context header
        context_parts = [
            f"🌐 WEB SEARCH RESULTS (Confidence: {confidence:.0%})",
            f"📊 Cross-reference score: {cross_ref_score:.2f}",
            f"📝 Total sources found: {len(synthesized)}",
            f"{'=' * 80}"
        ]

        # Add each source
        for source in synthesized:
            context_parts.append(
                f"SOURCE {source['source_id']} [{source['source_type'].upper()}]",
                f"   Domain: {source['domain']}",
                f"   Title: {source['title']}",
                f"   URL: {source['url']}",
                f"   Relevance: {source['final_score']:.2f}",
                f"   Content:",
                source['synthesized_content']
            )

        context_parts.append(f"{'=' * 80}")

        return '\n\n'.join(context_parts)


# Singleton instance
_result_synthesizer = None

def get_result_synthesizer() -> ResultSynthesizer:
    """Get or create the result synthesizer singleton."""
    global _result_synthesizer
    if _result_synthesizer is None:
        _result_synthesizer = ResultSynthesizer()
    return _result_synthesizer
