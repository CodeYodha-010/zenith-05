"""
Web Search Service - Tavily AI Integration

This service provides semantic web search capabilities using Tavily AI's search API.
It searches ONLY official government domains for India, USA, and EU trade compliance.

Features:
- Official-only domain search (no fake sites)
- Region-specific domain filtering
- Topic-based secondary domain selection
- Structured JSON responses
- Error handling with graceful fallbacks
- Jina AI Reranking for high-precision results
"""

import logging
from typing import List, Dict, Optional, Any
from django.conf import settings

logger = logging.getLogger('rag_pipeline')


class TavilySearchService:
    """
    Web search service using Tavily AI for official government domain search.
    
    This service ensures ONLY official government websites are searched,
    preventing hallucinated or fake sources.
    """
    
    def __init__(self):
        """
        Initialize the TavilySearchService with API configuration.
        """
        self.api_key = getattr(settings, 'TAVILY_API_KEY', None)
        self.jina_api_key = getattr(settings, 'JINA_API_KEY', None)
        
        if not self.api_key:
            logger.warning("TAVILY_API_KEY not configured. Web search will not work.")
        if not self.jina_api_key:
            logger.warning("JINA_API_KEY not configured. Reranking will be skipped.")

        # Import search configuration
        from .search_config import (
            PRIMARY_DOMAINS,
            SECONDARY_DOMAINS,
            TOPIC_KEYWORDS,
            REGION_NAMES,
            TARIFF_DOMAINS,
            TARIFF_TRIGGER_KEYWORDS,
            SEARCH_FULL_WEB
        )
        self.search_full_web = SEARCH_FULL_WEB
        self.primary_domains = PRIMARY_DOMAINS
        self.secondary_domains = SECONDARY_DOMAINS
        self.topic_keywords = TOPIC_KEYWORDS
        self.region_names = REGION_NAMES
        self.tariff_domains = TARIFF_DOMAINS
        self.tariff_trigger_keywords = TARIFF_TRIGGER_KEYWORDS
        
        logger.info("TavilySearchService initialized with Jina support")
    
    def search_official(self, question: str, region: str) -> List[Dict]:
        """
        Search official government domains for the given region.
        
        Args:
            question: The search query string
            region: Region code ('india', 'us', 'eu')
            
        Returns:
            List of dictionaries containing search results with keys:
            - title: The title of the result
            - content: The content/snippet
            - url: The URL of the result
            - region: The region searched
            
        Raises:
            No exceptions raised - errors are logged and empty list returned
        """
        if not self.api_key:
            logger.error("Cannot perform web search: TAVILY_API_KEY not configured")
            return []
        
        if not question or not question.strip():
            logger.warning("Empty search query provided")
            return []
        
        # Validate region
        if region not in self.primary_domains:
            logger.warning(f"Invalid region: {region}. Supported: {list(self.primary_domains.keys())}")
            return []

        try:
            # Step 0: Check search mode
            if self.search_full_web:
                logger.info("SEARCH_MODE = FULL_WEB | No domain filtering, searching entire web")
                domains_to_search = None  # None means no domain filtering
            else:
                logger.info("SEARCH_MODE = OFFICIAL_ONLY | Using government domain filtering")

                # Step 1: Check if this is a TARIFF query (HS Code/Duty Rate)
                is_tariff_query = self._is_tariff_query(question)
                logger.info(f"TAVILY TRIGGERED | Detected as Tariff Query: {is_tariff_query}")

                if is_tariff_query:
                    # Use TARIFF domains only (Eximpedia, Trade.gov, Access2Markets)
                    domains_to_search = list(self.tariff_domains.get(region, []))
                else:
                    # Step 1b: Get primary domains for region
                    domains_to_search = list(self.primary_domains[region])

                    # Step 2: Check for topic keywords and add secondary domains
                    triggered_topics = self._detect_topics(question, region)
                    for topic in triggered_topics:
                        if topic in self.secondary_domains.get(region, {}):
                            domains_to_search.extend(self.secondary_domains[region][topic])

                # Remove duplicates
                domains_to_search = list(set(domains_to_search))

                logger.info(f"TAVILY DOMAINS | Searching only: {domains_to_search}")

            # Step 4: Call Tavily API
            results = self._call_tavily_api(question, domains_to_search)
            
            # Step 5: Log raw Tavily results
            for i, result in enumerate(results, 1):
                url = result.get('url', 'N/A')
                title = result.get('title', 'N/A')
                content = result.get('content', result.get('snippet', ''))[:150]
                logger.info(f"TAVILY RAW RESULT {i} | URL: {url} | Title: {title} | Snippet: {content}...")
            
            # Step 6: Format results
            formatted_results = []
            for result in results:
                formatted_results.append({
                    'title': result.get('title', 'No Title'),
                    'content': result.get('content', result.get('snippet', '')),
                    'url': result.get('url', ''),
                    'region': region
                })
            
            # Step 7: RERANK with Jina (New)
            if self.jina_api_key and len(formatted_results) > 1:
                logger.info(f"JINA RERANK | Re-scoring {len(formatted_results)} results...")
                formatted_results = self._rerank_results(question, formatted_results)

            logger.info(f"[TAVILY SEARCH] Found and reranked {len(formatted_results)} results")
            return formatted_results
            
        except Exception as e:
            logger.error(f"Web search error: {str(e)}")
            return []
    
    def _detect_topics(self, question: str, region: str) -> List[str]:
        """
        Detect which topics are mentioned in the question.
        
        Args:
            question: The search query
            region: Region code
            
        Returns:
            List of detected topic names
        """
        question_lower = question.lower()
        detected_topics = []
        
        if region not in self.topic_keywords:
            return detected_topics
        
        for topic, keywords in self.topic_keywords[region].items():
            # Check if any keyword appears in the question
            for keyword in keywords:
                if keyword in question_lower:
                    detected_topics.append(topic)
                    break  # Only add topic once
        
        return detected_topics
    
    def _is_tariff_query(self, question: str) -> bool:
        """
        Check if the question is about HS codes, duty rates, or tariffs.
        
        Args:
            question: The search query
            
        Returns:
            True if this is a tariff-related query, False otherwise
        """
        question_lower = question.lower()
        
        for keyword in self.tariff_trigger_keywords:
            if keyword in question_lower:
                return True
        
        return False
    
    def _call_tavily_api(self, question: str, domains: List[str] = None) -> List[Dict]:
        """
        Call the Tavily API with optional domain filtering.

        Args:
            question: The search query
            domains: List of domains to search (None = search entire web)

        Returns:
            List of raw search results from Tavily
        """
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=self.api_key)

            response = client.search(
                query=question,
                search_depth="advanced",
                max_results=10,  # Increased from 3 to give Reranker more to work with
                include_domains=domains,
                include_answer="advanced",
                include_raw_content=False
            )

            # Extract results from response
            results = response.get('results', [])

            return results

        except ImportError:
            logger.error("tavily-python not installed. Run: pip install tavily-python")
            return []
        except Exception as e:
            logger.error(f"Tavily API error: {str(e)}")
            return []

    def search_semantic(self, question: str, region: str = None) -> List[Dict]:
        """
        Perform semantic search using Jina AI embeddings.

        This method searches the web using Jina AI's embedding-based semantic search
        for better relevance matching.

        Args:
            question: The search query string
            region: Region code ('india', 'us', 'eu') - logged but not used for filtering

        Returns:
            List of search results with semantic scores
        """
        if not self.api_key:
            logger.error("Cannot perform semantic search: TAVILY_API_KEY not configured")
            return []

        if not question or not question.strip():
            logger.warning("Empty search query provided")
            return []

        try:
            import requests

            # Step 1: Search Tavily for initial results
            logger.info(f"SEMANTIC SEARCH START | Query: {question}")
            results = self._call_tavily_api(question)

            if not results:
                logger.warning("No results from Tavily")
                return []

            logger.info(f"   Retrieved {len(results)} raw results from Tavily")

            # Step 2: Calculate embeddings for query and results using Jina
            logger.info(f"   Computing semantic similarity with Jina embeddings...")

            # Get query embedding
            query_embedding = self._get_jina_embedding(question)

            if not query_embedding:
                logger.warning("Failed to get query embedding, returning raw results")
                return self._format_semantic_results(results, [])

            # Get embeddings for each result
            result_embeddings = []
            for result in results:
                content = result.get('content', '')
                if content:
                    emb = self._get_jina_embedding(content)
                    if emb:
                        result_embeddings.append((result, emb))

            logger.info(f"   Processed {len(result_embeddings)} results with embeddings")

            # Step 3: Calculate cosine similarity between query and results
            from numpy import dot
            from numpy.linalg import norm

            query_array = query_embedding
            similarities = []

            for result, emb in result_embeddings:
                if len(query_array) == len(emb):
                    cos_sim = dot(query_array, emb) / (norm(query_array) * norm(emb))
                    similarities.append((result, cos_sim))

            # Sort by similarity score
            similarities.sort(key=lambda x: x[1], reverse=True)

            # Update results with semantic scores
            for result, score in similarities:
                result['semantic_score'] = score
                result['final_score'] = score  # Default: semantic score is final

            logger.info(f"   Semantic search complete - {len(similarities)} results ranked")

            return similarities[:5]  # Return top 5

        except Exception as e:
            logger.error(f"Semantic search failed: {e}")
            return []

    def _get_jina_embedding(self, text: str) -> list:
        """
        Get embedding for text using Jina AI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        try:
            import requests

            if not self.jina_api_key:
                return None

            url = "https://api.jina.ai/v1/embeddings"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.jina_api_key}"
            }

            data = {
                "model": "jina-embeddings-v2-base-en",
                "input": text[:10000]  # Jina API limits input to 10000 chars
            }

            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()

            data = response.json()
            embedding = data['data'][0]['embedding']

            return embedding

        except Exception as e:
            logger.error(f"Failed to get Jina embedding: {e}")
            return None

    def _format_semantic_results(self, results: List[Dict], embeddings: List[list]) -> List[Dict]:
        """
        Format results with semantic scores.

        Args:
            results: Raw search results
            embeddings: List of embeddings (may be empty)

        Returns:
            Formatted results with scores
        """
        formatted = []
        for i, result in enumerate(results[:5]):  # Limit to top 5
            formatted.append({
                'title': result.get('title', 'No Title'),
                'content': result.get('content', ''),
                'url': result.get('url', ''),
                'semantic_score': result.get('semantic_score', 0.0),
                'relevance_score': result.get('score', 0.0)
            })

        return formatted
    
    def get_search_summary(self, question: str, region: str) -> Optional[str]:
        """
        Get a quick summary from web search without full content.
        
        Args:
            question: The search query
            region: Region code
            
        Returns:
            Brief summary string or None if no results
        """
        results = self.search_official(question, region)
        
        if not results:
            return None
        
        # Combine snippets from top results
        summaries = []
        for r in results[:3]:
            if r.get('content'):
                summaries.append(r['content'][:200])
        
        return ' | '.join(summaries) if summaries else None

    def _rerank_results(self, query: str, results: List[Dict], top_k: int = 5) -> List[Dict]:
        """
        Rerank search results using Jina AI's rerank API.
        """
        if not self.jina_api_key:
            return results[:top_k]

        try:
            import requests
            
            url = "https://api.jina.ai/v1/rerank"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.jina_api_key}"
            }
            
            # Prepare documents for reranking
            documents = [r['content'] for r in results]
            
            data = {
                "model": "jina-reranker-v2-base-multilingual",
                "query": query,
                "top_n": top_k,
                "documents": documents
            }
            
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            
            reranked_data = response.json()
            
            new_results = []
            for item in reranked_data.get('results', []):
                idx = item['index']
                result = results[idx]
                # Add rerank score
                result['relevance_score'] = item['relevance_score']
                new_results.append(result)
                
            return new_results
            
        except Exception as e:
            logger.error(f"Jina rerank failed: {e}")
            return results[:top_k]

    def search_enhanced(self, question: str, region: Optional[str] = None,
                       query_type: str = 'general') -> Dict[str, Any]:
        """
        Use the enhanced web search service with multi-source search.

        This method provides advanced query transformation, multi-domain search,
        and intelligent result synthesis.

        Args:
            question: The search query
            region: Region to focus search on (india, us, eu)
            query_type: Type of query for better domain selection

        Returns:
            Enhanced search response with multi-source results
        """
        try:
            from .web_search_enhanced import get_enhanced_web_search_service

            # Initialize enhanced search service
            enhanced_service = get_enhanced_web_search_service()

            # Perform enhanced search
            response = enhanced_service.multi_source_search(
                query=question,
                region=region,
                query_type=query_type,
                max_results=15
            )

            # If synthesis requested, also run it
            if response['success']:
                try:
                    from .result_synthesizer import get_result_synthesizer
                    synthesizer = get_result_synthesizer()

                    synthesis_response = synthesizer.synthesize_results(
                        response, question
                    )

                    response['synthesis'] = synthesis_response

                    # Add LLM context if available
                    if synthesis_response['synthesized_count'] > 0:
                        llm_context = synthesizer.create_llm_context(
                            synthesis_response, question
                        )
                        response['llm_context'] = llm_context
                except Exception as e:
                    logger.warning(f"Result synthesis failed: {e}")

            logger.info(f"Enhanced search complete: {response['total_results']} results found")
            return response

        except Exception as e:
            logger.error(f"Enhanced search failed: {e}")
            # Fallback to original search
            return {
                'success': False,
                'error': str(e),
                'results': [],
                'total_results': 0
            }