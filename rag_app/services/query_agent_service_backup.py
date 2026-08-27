import logging
import asyncio
import json
import time
from typing import List, Dict, Any, Optional, Tuple

import httpx
from django.conf import settings
from llama_index.llms.openai_like import OpenAILike
from asgiref.sync import sync_to_async

from .service_registry import get_qa
from ..retrieval_service import _multi_source_retrieve

logger = logging.getLogger('rag_pipeline')

logger = logging.getLogger('rag_pipeline')

# Common keywords for date-aware search
LATEST_KEYWORDS = ['2024', '2025', 'latest', 'news', 'update', 'current',
                   'today', 'now', 'recent']

# Web search parameters
SEARCH_DEPTH = "advanced"
CHUNKS_PER_SOURCE = 3
MAX_RESULTS = 5

# Fast query rewriting patterns (no LLM calls)
QUERY_REWRITE_PATTERNS = {
    'rates': [
        '{query} India',
        '{query} duty rate',
        '{query} export rate',
    ],
    'procedure': [
        '{query} export procedure',
        '{query} import procedure',
        '{query} step by step',
    ],
    'duty': [
        '{query} India',
        '{query} tariff rate',
    ],
    'quota': [
        '{query} India',
        '{query} limit',
    ],
}

class QueryAgentService:
    """
    High-Efficiency Agentic RAG Service.
    Optimized for Free Tier: Reduces LLM calls from 4-5 down to exactly 1.
    """
    
    def __init__(self):
        self.api_key = settings.NVIDIA_LLM_API_KEY
        self.model = "minimaxai/minimax-m2.7"
        self.base_url = "https://integrate.api.nvidia.com/v1"
        
        # Unified LLM for synthesis with extended httpx timeout for long streaming responses
        self._httpx_client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=60.0)
        )
        self.llm = OpenAILike(
            model=self.model,
            api_key=self.api_key,
            api_base=self.base_url,
            is_chat_model=True,
            temperature=1.0,
            max_tokens=8192,
            context_window=128000,
            timeout=300.0,
            http_client=self._httpx_client,
            additional_kwargs={"top_p": 0.95}
        )

    def _should_use_web(self, query: str, context: str, faiss_score: float = 1.0) -> bool:
        """4-condition early-exit logic for web search fallback."""
        logger.info(f"[WEB-SEARCH-CHECK] faiss_score={faiss_score:.3f}, ctx_len={len(context)}, query={query[:50]}")
        query_lower = query.lower()

        # Condition 1: Latest information keywords (FASTEST check)
        if any(kw in query_lower for kw in LATEST_KEYWORDS):
            return True

        # Condition 2: Empty or insufficient KB results
        if not context or len(context) < 50:
            return True

        # Condition 3: Low FAISS relevance score (FAST check)
        if faiss_score < 0.3:
            return True

        # Condition 4: Topic not in DocumentMetadata (improved check)
        if not self._topic_exists_in_metadata(query):
            return True

        return False

    def _topic_exists_in_metadata(self, query: str) -> bool:
        """Check if query topic exists in DocumentMetadata."""
        try:
            from rag_app.models import DocumentMetadata

            query_lower = query.lower()
            query_words = set(query_lower.split())

            # Check if any metadata record contains query terms
            for meta in DocumentMetadata.objects.all():
                all_text = f"{meta.topics} {meta.commodities} {meta.regulations}".lower()
                all_words = set(all_text.split())
                if query_words & all_words:  # Any overlap
                    return True
            return False
        except:
            return True  # Fallback to True if check fails

    def _has_latest_keywords(self, query: str) -> bool:
        """Check if query contains latest/dated information keywords."""
        latest_keywords = ['2024', '2025', 'latest', 'news', 'update', 'current',
                          'today', 'now', 'recent']
        return any(kw in query.lower() for kw in latest_keywords)

    def _rewrite_query_fast(self, query: str) -> List[str]:
        """Rewrite query into variations WITHOUT LLM calls (FAST)."""
        variations = [query]  # Always include original

        query_lower = query.lower()

        # Apply patterns based on query type
        for pattern_key, pattern_list in QUERY_REWRITE_PATTERNS.items():
            if pattern_key in query_lower:
                for pattern in pattern_list:
                    # Replace {query} with actual query
                    rewritten = pattern.replace('{query}', query)
                    if rewritten not in variations:
                        variations.append(rewritten)

        return variations[:4]  # Max 4 variations

    async def _single_call_web_search(self, query: str, region: Optional[str] = None) -> str:
        """Single call web search with query rewriting (FAST, no ReAct loop)."""
        try:
            from llama_index.tools.tavily_research import TavilyToolSpec
            from tavily import TavilyClient

            logger.info(f"⚡ SINGLE CALL WEB SEARCH | Query: {query}")

            # Step 1: Rewrite query (FAST, no LLM)
            variations = self._rewrite_query_fast(query)
            logger.debug(f"Query variations: {variations}")

            # Step 2: Search all variations (single pass)
            all_results = []
            tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)

            for var in variations:
                response = tavily_client.search(
                    query=var,
                    max_results=5,
                    search_depth="basic",
                    include_raw_content=False
                )
                all_results.extend(response.get('results', []))

            # Step 3: Combine and deduplicate
            seen_urls = set()
            combined = []

            for result in all_results:
                url = result.get('url', '')
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    combined.append(result)

            # Step 4: Format results (FAST)
            context = "WEB SEARCH RESULTS:\n"
            for result in combined[:5]:
                url = result.get('url', 'N/A')
                title = result.get('title', 'No Title')
                content = result.get('content', '')[:200]
                context += f"Source: {url}\nTitle: {title}\nContent: {content}\n\n"

            logger.info(f"✅ Single call search: {len(combined)} unique results")
            return context

        except Exception as e:
            logger.error(f"Single call search failed: {e}", exc_info=True)
            return ""

    async def _search_kb(self, query: str, region: Optional[str]) -> Tuple[str, float]:
        """Retrieves from local documents (0 LLM calls). Returns (context, faiss_score)."""
        kb_start_time = time.time()
        logger.info(f"🔍 STARTING KB SEARCH | Query: {query}")

        def _sync_search():
            qa = get_qa()
            understood = qa.understand(query, region)
            logger.info(f"   ✓ Query understood: {understood}")

            pages, sources, scores, context = _multi_source_retrieve(query, region, understood)
            logger.info(f"   ✓ Retrieved {len(pages)} pages, {len(sources)} sources")

            # Use actual retrieval scores (from FAISS + BM25 + keyword boost)
            logger.info(f"   Raw scores from retrieval: {scores}")
            faiss_score = 0.5  # Default to medium score
            if scores and len(scores) > 0:
                avg_score = sum(scores) / len(scores)
                logger.info(f"   Calculated avg_score: {avg_score}")
                # Higher avg = better match; lower = more relevant results needed from web
                faiss_score = max(0.0, min(avg_score, 1.0))

            return context, faiss_score

        result = await sync_to_async(_sync_search)()
        kb_time = time.time() - kb_start_time
        logger.info(f"✅ KB SEARCH COMPLETE | Time: {kb_time:.2f}s | Context length: {len(result[0])}")

        return result

    async def _search_web(self, query: str, region: Optional[str]) -> str:
        """Single call web search optimization (no ReAct)."""
        return await self._single_call_web_search(query, region)

    async def ask(self, question: str, region: Optional[str] = None) -> Dict[str, Any]:
        """Single-Call Agentic RAG: High speed, 0 Rate Limit issues."""
        logger.info(f"🚀 FAST-RAG START | Question: {question}")

        # 1. Gather Context (0 LLM Calls)
        kb_context, faiss_score = await self._search_kb(question, region)

        web_context = ""
        if self._should_use_web(question, kb_context, faiss_score):
            web_context = await self._search_web(question, region)

        # 2. Synthesize Answer (Exactly 1 LLM Call)
        final_prompt = f"""You are a Trade Compliance Expert. Answer the question using the provided context.

LOCAL KNOWLEDGE BASE:
{kb_context if kb_context else "None found."}

LATEST WEB SEARCH:
{web_context if web_context else "None performed."}

QUESTION: {question}

Instructions:
- If KB and Web conflict, prefer Web for dates after 2024.
- Cite sources clearly ([Source: URL] or [Document Name]).
- Be specific (HS codes, rates).
"""

        try:
            response = await self.llm.acomplete(final_prompt)
            return {"success": True, "answer": str(response)}
        except Exception as e:
            logger.error(f"❌ LLM failed: {e}")
            return {"success": False, "error": str(e)}

    def _optimize_query(self, query: str) -> list:
        """Optimize query for Tavily search."""
        queries = []

        # 1. Truncate to 400 characters
        if len(query) > 400:
            query = query[:400]

        # 2. Add context if needed
        if "rates" in query.lower() and "india" not in query.lower():
            query = f"{query} India"

        if "export" in query.lower() or "import" in query.lower():
            query = f"{query} procedure"

        # 3. If contains "and", split into sub-queries
        if "and" in query.lower():
            sub_queries = [q.strip() for q in query.split("and")]
            queries.extend(sub_queries)
        else:
            queries.append(query)

        return queries[:3]  # Max 3 queries

    def _has_latest_keywords(self, query: str) -> bool:
        """Check if query contains explicit recency keywords."""
        query_lower = query.lower()
        return any(kw in query_lower for kw in LATEST_KEYWORDS)

    async def _extract_from_urls(self, urls: list) -> list:
        """Extract full page content from URLs."""
        try:
            from tavily import AsyncTavilyClient

            client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
            response = await client.extract(urls)

            # Extract gives full page content
            for result in response.get('results', []):
                result['content'] = result.get('rawContent', '')
                result['source_type'] = 'extracted'

            return response.get('results', [])

        except Exception as e:
            logger.error(f"Extract failed: {e}")
            return []

    def _should_extract(self, results: list) -> bool:
        """Determine if extract is needed based on snippet length."""
        total_chars = sum(len(r.get('content', '')) for r in results)
        return total_chars < 500  # Extract if snippets < 500 chars

    def _format_results(self, results: list) -> str:
        """Format results as LLM-ready citations."""
        if not results:
            return "No relevant web search results found."

        formatted = "=== WEB SEARCH RESULTS ===\n\n"

        for i, result in enumerate(results[:5], 1):
            title = result.get('title', 'No Title')
            url = result.get('url', 'N/A')
            content = result.get('content', '')
            score = result.get('score', 0)

            formatted += f"Source {i}: {title}\n"
            formatted += f"URL: {url}\n"
            formatted += f"Relevance: {score:.2f}\n"
            formatted += f"Content:\n{content}\n\n"

        formatted += "=== END WEB SEARCH RESULTS ===\n"
        return formatted

    def _get_tavily_client(self) -> Any:
        """Get or create Tavily async client (singleton)."""
        if not hasattr(self, '_tavily_client') or self._tavily_client is None:
            try:
                from tavily import AsyncTavilyClient
                self._tavily_client = AsyncTavilyClient(
                    api_key=settings.TAVILY_API_KEY
                )
                logger.info("✅ Tavily async client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Tavily client: {e}")
                return None
        return self._tavily_client

    async def _single_call_web_search(self, query: str, region: Optional[str] = None) -> str:
        """Single call web search with all enhancements."""
        search_start_time = time.time()
        logger.info(f"🌐 STARTING WEB SEARCH | Query: {query}")

        try:
            client = self._get_tavily_client()
            if not client:
                search_time = time.time() - search_start_time
                logger.warning(f"❌ Web search failed: Could not initialize Tavily client | Time: {search_time:.2f}s")
                return ""

            # 1. Optimize query
            logger.info(f"   Step 1: Optimizing query...")
            query_opt_start = time.time()
            variations = self._optimize_query(query)
            query_opt_time = time.time() - query_opt_start
            logger.info(f"   ✓ Query optimization: {len(variations)} variations in {query_opt_time:.2f}s")
            logger.debug(f"      Variations: {variations}")

            # 2. Search all variations
            logger.info(f"   Step 2: Searching web...")
            search_start = time.time()
            all_results = []
            seen_urls = set()

            for i, var in enumerate(variations):
                logger.debug(f"      Searching variation {i+1}/{len(variations)}: {var}")
                response = await client.search(
                    query=var,
                    search_depth=SEARCH_DEPTH,
                    chunks_per_source=CHUNKS_PER_SOURCE,
                    max_results=MAX_RESULTS,
                    include_raw_content=False
                )

                result_count = len(response.get('results', []))
                logger.debug(f"      ✓ Variation {i+1} returned {result_count} results")

                # Deduplicate by URL
                for result in response.get('results', []):
                    url = result.get('url', '')
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        all_results.append(result)

            search_time = time.time() - search_start
            logger.info(f"   ✓ All searches completed in {search_time:.2f}s")
            logger.info(f"      Total unique results: {len(all_results)}")

            # 3. Two-pass domain fallback
            if len(all_results) < 3:
                logger.warning(f"⚠️ Only {len(all_results)} results (need 3+), performing two-pass fallback...")
                fallback_start = time.time()

                for i, var in enumerate(variations):
                    logger.debug(f"      Retry variation {i+1}/{len(variations)}: {var}")
                    response = await client.search(
                        query=var,
                        search_depth=SEARCH_DEPTH,
                        chunks_per_source=CHUNKS_PER_SOURCE,
                        max_results=MAX_RESULTS,
                        include_raw_content=False
                    )

                    for result in response.get('results', []):
                        url = result.get('url', '')
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(result)

                fallback_time = time.time() - fallback_start
                logger.warning(f"   ⚠️ Two-pass fallback completed in {fallback_time:.2f}s")
                logger.warning(f"      Total unique results after fallback: {len(all_results)}")

            # 4. Conditional extract (if snippets insufficient)
            total_chars = sum(len(r.get('content', '')) for r in all_results)
            logger.info(f"   Step 4: Analyzing results ({len(all_results)} results, {total_chars} chars)...")
            extract_start = time.time()

            if total_chars < 500:
                logger.info(f"   ⚠️ Snippets too short ({total_chars} chars), extracting full page content...")
                urls = [r['url'] for r in all_results[:3]]
                logger.info(f"      Extracting {len(urls)} URLs...")

                try:
                    extract_response = await asyncio.wait_for(
                        client.extract(urls),
                        timeout=30.0  # 30 second timeout for extract
                    )
                    extract_count = len(extract_response.get('results', []))
                    all_results.extend(extract_response.get('results', []))
                    extract_time = time.time() - extract_start
                    logger.info(f"   ✓ Extract completed in {extract_time:.2f}s")
                    logger.info(f"      Extracted {extract_count} new results")
                except asyncio.TimeoutError:
                    extract_time = time.time() - extract_start
                    logger.warning(f"   ⚠️ Extract timed out after {extract_time:.2f}s")
            else:
                extract_time = 0
                logger.info(f"   ✓ Results sufficient, skipping extract")

            # 5. Sort by relevance and return formatted results
            sort_start = time.time()
            all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
            sort_time = time.time() - sort_start

            formatted_results = self._format_results(all_results[:10])
            search_total_time = time.time() - search_start_time

            logger.info(f"✅ WEB SEARCH COMPLETE | Time: {search_total_time:.2f}s | Results: {len(all_results)}")
            logger.debug(f"      Breakdown: Query opt {query_opt_time:.2f}s | Search {search_time:.2f}s | Fallback {fallback_time:.2f}s | Extract {extract_time:.2f}s | Sort {sort_time:.2f}s")

            return formatted_results

        except asyncio.TimeoutError:
            search_time = time.time() - search_start_time
            logger.error(f"❌ Web search TIMEOUT after {search_time:.2f}s")
            return ""
        except Exception as e:
            search_time = time.time() - search_start_time
            logger.error(f"❌ Web search failed after {search_time:.2f}s: {e}", exc_info=True)
            return ""

    async def _search_web(self, query: str, region: Optional[str] = None) -> str:
        """Single call web search with all enhancements (no ReAct)."""
        return await self._single_call_web_search(query, region)

    async def stream_ask(self, question: str, region: Optional[str] = None):
        """Asynchronously streams with exactly 1 LLM call."""
        stream_start_time = time.time()
        logger.info(f"🚀 FAST-STREAM START | Question: {question}")

        # Step 1: Gather Context (0 LLM Calls)
        yield json.dumps({"type": "status", "text": "Consulting official documents..."}) + "\n"
        kb_start = time.time()
        kb_context, faiss_score = await self._search_kb(question, region)
        kb_time = time.time() - kb_start
        logger.info(f"   ✓ KB search completed in {kb_time:.2f}s | faiss_score: {faiss_score:.3f}, ctx_len: {len(kb_context)}")
        should_web = self._should_use_web(question, kb_context, faiss_score)
        logger.info(f"   Web search needed: {should_web}")

        # Step 2: Web Search
        web_start = time.time()
        web_context = ""
        if should_web:
            yield json.dumps({"type": "status", "text": "Searching live web portals for latest updates..."}) + "\n"
            web_context = await self._search_web(question, region)
        web_time = time.time() - web_start
        logger.info(f"   ✓ Web search completed in {web_time:.2f}s")

        # Step 3: Generate Answer (Exactly 1 LLM Call)
        yield json.dumps({"type": "status", "text": "Analyzing data and generating answer..."}) + "\n"
        yield json.dumps({"type": "answer_start"}) + "\n"

        llm_start = time.time()
        final_prompt = f"""You are a Trade Compliance Expert.
LOCAL KB: {kb_context}
WEB: {web_context}
QUESTION: {question}
Answer accurately with citations."""

        logger.info(f"   🎤 Starting LLM streaming (final prompt length: {len(final_prompt)} chars)...")

        try:
            response_gen = await self.llm.astream_complete(final_prompt)
            chunk_count = 0
            async for chunk in response_gen:
                chunk_count += 1
                if chunk_count % 10 == 0:  # Log every 10 chunks
                    logger.debug(f"      Streaming chunk {chunk_count}...")
                yield json.dumps({"type": "answer_chunk", "text": chunk.delta}) + "\n"

            llm_time = time.time() - llm_start
            total_time = time.time() - stream_start_time

            logger.info(f"✅ STREAM COMPLETE | Time: {total_time:.2f}s | LLM chunks: {chunk_count} | Breakdown: KB {kb_time:.2f}s + Web {web_time:.2f}s + LLM {llm_time:.2f}s")
            yield json.dumps({"type": "done"}) + "\n"

        except asyncio.TimeoutError:
            llm_time = time.time() - llm_start
            total_time = time.time() - stream_start_time
            logger.error(f"❌ LLM stream TIMEOUT after {llm_time:.2f}s")
            logger.error(f"   Total stream time: {total_time:.2f}s | KB: {kb_time:.2f}s | Web: {web_time:.2f}s")
            yield json.dumps({"type": "error", "text": "LLM streaming timed out (waited too long for response)"}) + "\n"
        except Exception as e:
            llm_time = time.time() - llm_start
            total_time = time.time() - stream_start_time
            logger.error(f"❌ Stream failed after {total_time:.2f}s | LLM time: {llm_time:.2f}s: {e}", exc_info=True)
            yield json.dumps({"type": "error", "text": str(e)}) + "\n"

