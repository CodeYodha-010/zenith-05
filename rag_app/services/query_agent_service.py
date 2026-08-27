import logging
import asyncio
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple

import httpx
from django.conf import settings
from llama_index.llms.openai_like import OpenAILike
from asgiref.sync import sync_to_async

from .service_registry import get_qa
from ..retrieval_service import _multi_source_retrieve, _multi_source_retrieve_rrf
from rag_app.prompts import SYSTEM_PROMPT
from .search_config import get_domain_credibility_boost

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
        # LLM chat/generation now served via OpenRouter (OpenAI-compatible API).
        # Embeddings and OCR remain on NVIDIA.
        self.api_key = settings.OPENROUTER_API_KEY
        self.model = settings.OPENROUTER_MODEL
        self.base_url = settings.OPENROUTER_API_URL
        
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



    async def _search_kb(self, query: str, region: Optional[str]) -> Tuple[str, float]:
        """Retrieves from local documents (0 LLM calls). Returns (context, faiss_score)."""
        kb_start_time = time.time()
        logger.info(f"🔍 STARTING KB SEARCH | Query: {query}")

        def _sync_search():
            qa = get_qa()
            understood = qa.understand(query, region)
            logger.info(f"   ✓ Query understood: {understood}")

            # Use original retrieval (RRF was slower)
            pages, sources, scores, context = _multi_source_retrieve(query, region, understood)
            logger.info(f"   ✓ RRF Retrieved {len(pages)} pages, {len(sources)} sources")

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

    async def ask(self, question: str, region: Optional[str] = None, 
                  attached_doc_text: Optional[str] = None, attached_doc_filename: Optional[str] = None) -> Dict[str, Any]:
        """Single-Call Agentic RAG: High speed, 0 Rate Limit issues."""
        logger.info(f"🚀 FAST-RAG START | Question: {question} | Region: {region} | Attached: {attached_doc_filename}")

        # Check if query is too short - skip KB and web search, answer directly
        query_word_count = len(question.strip().split())
        if query_word_count < 3:
            logger.info(f"⚡ SHORT QUERY DETECTED | Words: {query_word_count} - Direct answer only")
            direct_prompt = f"""You are a Trade Compliance Expert. Answer the user's question directly.

QUESTION: {question}

Answer concisely and helpfully. If you need more details, ask the user to elaborate."""

            try:
                response = await self.llm.acomplete(direct_prompt)
                return {"success": True, "answer": str(response)}
            except Exception as e:
                return {"success": False, "error": str(e)}

        # PARALLEL HYBRID: Run KB and Web searches AT THE SAME TIME (saves ~30 seconds)
        async def run_kb_search():
            return await self._search_kb(question, region)

        async def run_web_search():
            try:
                return await self._search_web(question, region) or ""
            except Exception as e:
                logger.warning(f"   ⚠️ Web search failed: {e}")
                return ""

        # Run both searches in parallel
        logger.info("   🔄 Running KB + Web searches in PARALLEL...")
        kb_result, web_result = await asyncio.gather(
            run_kb_search(),
            run_web_search(),
            return_exceptions=True
        )

        # Extract KB results
        if isinstance(kb_result, Exception):
            logger.error(f"   ❌ KB search failed: {kb_result}")
            kb_context = ""
            faiss_score = 0.0
        else:
            kb_context, faiss_score = kb_result
            logger.info(f"   ✅ KB search done: {len(kb_context)} chars")

        # Extract Web results
        if isinstance(web_result, Exception):
            logger.warning(f"   ⚠️ Web search error: {web_result}")
            web_context = ""
        else:
            web_context = web_result
            logger.info(f"   ✅ Web search done: {len(web_context)} chars")

        # Add attached document content if provided
        if attached_doc_text:
            attached_context = f"\n\n=== ATTACHED DOCUMENT: {attached_doc_filename or 'User Upload'} ===\n"
            attached_context += attached_doc_text[:10000]  # Limit to 10k chars
            kb_context = attached_context + "\n\n" + (kb_context or "")
            logger.info(f"   📎 Attached doc included: {attached_doc_filename}")

        # 2. Synthesize Answer (Exactly 1 LLM Call)
        # Determine which context to prioritize
        is_kb_weak = faiss_score < 0.3 or len(kb_context) < 200
        context_priority = "WEB SEARCH RESULTS (prioritized — KB results are weak)" if is_kb_weak else "LOCAL KNOWLEDGE BASE (prioritized — strong match found)"
        
        final_prompt = f"""{SYSTEM_PROMPT}

{context_priority}:

LOCAL KNOWLEDGE BASE (from your documents):
{kb_context if kb_context else "None found."}

WEB SEARCH RESULTS (from internet):
{web_context if web_context else "None found."}

QUESTION: {question}

Answer accurately with citations.

RULES:
- Every specific number (duty rate, %, date, quota, fee) MUST carry a citation from the LOCAL KNOWLEDGE BASE or WEB SEARCH RESULTS above.
- If a number is not in the provided sources, label it exactly: "⚠️ UNVERIFIED (not in my sources)".
- If the answer is not in the provided sources at all, write "⚠️ NOT FOUND in my sources" and suggest where to verify.
- Never estimate or invent precise figures."""

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
        base = query
        if "rates" in query.lower() and "india" not in query.lower():
            base = f"{query} India"

        if ("export" in query.lower() or "import" in query.lower()) and "procedure" not in base.lower():
            base = f"{base} procedure"

        # 3. If contains "and", split into sub-queries
        if "and" in base.lower():
            sub_queries = [q.strip() for q in base.split("and")]
            queries.extend([q for q in sub_queries if q])
        else:
            queries.append(base)

        # 4. HS-code surgical queries (priority for duty/tariff lookups)
        hs_match = re.search(r'\b\d{4}(?:[.\s-]?\d{2}){0,3}\b', query)
        if hs_match:
            hs_code = re.sub(r'[.\s-]', '', hs_match.group(0))
            # Ignore 4-digit years (e.g. "2026") as pseudo-HS codes
            if not (len(hs_code) == 4 and hs_code.startswith('20')):
                region_lower = query.lower()
                if any(w in region_lower for w in ['usa', 'united states', 'america', 'us ']):
                    queries.append(f"HTS {hs_code} duty rate site:usitc.gov")
                elif any(w in region_lower for w in ['germany', 'eu', 'europe']):
                    queries.append(f"{hs_code} import duty site:ec.europa.eu OR site:trade.ec.europa.eu")
                else:
                    queries.append(f"HTS {hs_code} duty rate")
                queries.append(f"{hs_code} import duty United States")

        # 5. Dedupe, drop empties, cap
        seen = set()
        final = []
        for q in queries:
            if q and q not in seen:
                seen.add(q)
                final.append(q)
        return final[:4]  # Max 4 queries

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
            final_score = result.get('final_score', score)
            boost = result.get('credibility_boost', 1.0)

            formatted += f"Source {i}: {title}\n"
            formatted += f"URL: {url}\n"
            formatted += f"Relevance: {score:.2f} (boosted to {final_score:.2f} via credibility factor {boost:.1f}x)\n"
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
            # Create fresh client for each search to avoid event loop issues
            from tavily import AsyncTavilyClient
            client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)

            logger.debug("✅ Tavily client created")

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
            collected_answers = []  # Tavily AI answers for extra grounding
            fallback_time = 0  # Initialize for logging

            for i, var in enumerate(variations):
                logger.debug(f"      Searching variation {i+1}/{len(variations)}: {var}")
                response = await client.search(
                    query=var,
                    search_depth=SEARCH_DEPTH,
                    chunks_per_source=CHUNKS_PER_SOURCE,
                    max_results=MAX_RESULTS,
                    include_raw_content=False,
                    include_answer="advanced"
                )

                result_count = len(response.get('results', []))
                logger.debug(f"      ✓ Variation {i+1} returned {result_count} results")

                # Capture Tavily's AI answer for extra grounding
                tavily_answer = response.get('answer')
                if tavily_answer and tavily_answer.strip():
                    collected_answers.append(tavily_answer)

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
                        include_raw_content=False,
                        include_answer="advanced"
                    )

                    for result in response.get('results', []):
                        url = result.get('url', '')
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(result)

                fallback_time = time.time() - fallback_start
                logger.warning(f"   ⚠️ Two-pass fallback completed in {fallback_time:.2f}s")
                logger.warning(f"      Total unique results after fallback: {len(all_results)}")

            # 3b. VERIFY PASS: one targeted retry for numeric/tariff questions
            verify_keywords = ('duty', 'rate', 'tariff', 'quota', 'fee', '%')
            is_numeric_query = any(k in query.lower() for k in verify_keywords)
            if is_numeric_query:
                verify_query = query.strip()[:70]
                if region == 'us':
                    verify_query = f"{verify_query} site:usitc.gov OR site:cbp.gov"
                elif region == 'eu':
                    verify_query = f"{verify_query} site:ec.europa.eu OR site:trade.ec.europa.eu"
                elif region == 'india':
                    verify_query = f"{verify_query} site:dgft.gov.in OR site:cbic.gov.in"
                logger.info(f"   🔍 VERIFY PASS | {verify_query[:80]}")
                try:
                    verify_resp = await client.search(
                        query=verify_query,
                        search_depth=SEARCH_DEPTH,
                        max_results=5,
                        include_raw_content=False,
                        include_answer="advanced"
                    )
                    verify_answer = verify_resp.get('answer')
                    if verify_answer and verify_answer.strip():
                        collected_answers.append(verify_answer)
                    for result in verify_resp.get('results', []):
                        url = result.get('url', '')
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(result)
                except Exception as e:
                    logger.warning(f"   ⚠️ Verify pass failed: {e}")

            # 4. Conditional extract (if snippets insufficient)
            total_chars = sum(len(r.get('content', '')) for r in all_results)
            logger.info(f"   Step 4: Analyzing results ({len(all_results)} results, {total_chars} chars)...")
            extract_start = time.time()

            if total_chars < 500:
                logger.info(f"   ⚠️ Snippets too short ({total_chars} chars), extracting full page content...")
                urls = [r['url'] for r in all_results[:3]]
                logger.info(f"      Extracting {len(urls)} URLs...")

                try:
                    # Create fresh client for extract to avoid event loop issues
                    extract_client = AsyncTavilyClient(api_key=settings.TAVILY_API_KEY)
                    extract_response = await asyncio.wait_for(
                        extract_client.extract(urls),
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

            # 5. Apply domain credibility boost and sort
            sort_start = time.time()
            for result in all_results:
                base_score = result.get('score', 0)
                domain_boost = get_domain_credibility_boost(result.get('url', ''))
                result['credibility_boost'] = domain_boost
                result['final_score'] = base_score * domain_boost
            
            all_results.sort(key=lambda x: x.get('final_score', 0), reverse=True)
            sort_time = time.time() - sort_start

            # Prepend Tavily's AI answer to the results so the LLM gets grounded context
            if collected_answers:
                all_results.insert(0, {
                    'title': 'Tavily AI Answer',
                    'url': '',
                    'content': '\n\n'.join(collected_answers[:2]),
                    'score': 1.0,
                })

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

    async def stream_ask(self, question: str, region: Optional[str] = None, attached_doc_id: Optional[int] = None):
        """Asynchronously streams with exactly 1 LLM call.
        
        Args:
            question: The user's question
            region: Filter by region (india, us, eu)
            attached_doc_id: Optional document ID to use as additional context (for uploaded docs)
        """
        stream_start_time = time.time()
        logger.info(f"🚀 FAST-STREAM START | Question: {question} | Region: {region} | Attached Doc: {attached_doc_id}")

        # Check if query is too short - skip KB and web search, answer directly
        query_word_count = len(question.strip().split())
        if query_word_count < 3:
            logger.info(f"⚡ SHORT QUERY DETECTED | Words: {query_word_count} - Skipping KB/Web search")
            yield json.dumps({"type": "status", "text": "⚡ Generating direct answer..."}) + "\n"
            yield json.dumps({"type": "answer_start"}) + "\n"
            
            direct_prompt = f"""You are a Trade Compliance Expert. Answer the user's question directly.

QUESTION: {question}

Answer concisely and helpfully. If you need more details, ask the user to elaborate."""

            try:
                response_gen = await self.llm.astream_complete(direct_prompt)
                async for chunk in response_gen:
                    yield json.dumps({"type": "answer_chunk", "text": chunk.delta}) + "\n"
                yield json.dumps({"type": "done"}) + "\n"
                return
            except Exception as e:
                yield json.dumps({"type": "error", "text": str(e)}) + "\n"
                return

        # Step 1: Gather Context (0 LLM Calls)
        yield json.dumps({"type": "status", "text": "📚 Consulting knowledge base — embedding your question…"}) + "\n"
        kb_start = time.time()
        kb_context, faiss_score = await self._search_kb(question, region)
        
        # Add attached document content if provided
        attached_doc_context = ""
        if attached_doc_id:
            try:
                from rag_app.models import Document, DocumentPage
                doc = Document.objects.get(id=attached_doc_id)
                attached_doc_context = f"\n\n=== ATTACHED DOCUMENT: {doc.title} ===\n"
                for page in doc.pages.all().order_by('page_number'):
                    attached_doc_context += f"\n--- Page {page.page_number} ---\n"
                    attached_doc_context += page.original_text[:5000] + "\n"  # Limit to first 5000 chars
                logger.info(f"   📎 Attached doc loaded: {doc.title}")
            except Document.DoesNotExist:
                logger.warning(f"   ⚠️ Attached doc not found: ID {attached_doc_id}")
            except Exception as e:
                logger.warning(f"   ⚠️ Error loading attached doc: {e}")
        
        # Prepend attached doc to KB context
        if attached_doc_context:
            kb_context = attached_doc_context + "\n\n" + kb_context
        
        kb_time = time.time() - kb_start
        logger.info(f"   ✓ KB search completed in {kb_time:.2f}s | faiss_score: {faiss_score:.3f}, ctx_len: {len(kb_context)}")

        # Step 2: ALWAYS run web search (HYBRID approach)
        web_start = time.time()
        web_context = ""
        try:
            yield json.dumps({"type": "status", "text": "🌐 Running web search (parallel)…"}) + "\n"
            web_context = await self._search_web(question, region)
            if web_context:
                logger.info(f"   ✅ Web search got {len(web_context)} chars")
            else:
                logger.info("   ⚠️ Web search returned empty")
        except Exception as web_err:
            logger.warning(f"   ⚠️ Web search failed: {web_err}")
        web_time = time.time() - web_start
        logger.info(f"   ✓ Web search completed in {web_time:.2f}s")

        # Step 3: Generate Answer (Exactly 1 LLM Call)
        yield json.dumps({"type": "status", "text": "🧠 Analyzing and generating answer…"}) + "\n"
        yield json.dumps({"type": "answer_start"}) + "\n"

        llm_start = time.time()
        # Determine which context to prioritize
        is_kb_weak = faiss_score < 0.3 or len(kb_context) < 200
        context_priority = "WEB SEARCH RESULTS (prioritized — KB results are weak)" if is_kb_weak else "LOCAL KNOWLEDGE BASE (prioritized — strong match found)"
        
        final_prompt = f"""{SYSTEM_PROMPT}

{context_priority}:

LOCAL KNOWLEDGE BASE (from your documents):
{kb_context if kb_context else "None found."}

WEB SEARCH RESULTS (from internet):
{web_context if web_context else "None found."}

QUESTION: {question}

Answer accurately with citations.

RULES:
- Every specific number (duty rate, %, date, quota, fee) MUST carry a citation from the LOCAL KNOWLEDGE BASE or WEB SEARCH RESULTS above.
- If a number is not in the provided sources, label it exactly: "⚠️ UNVERIFIED (not in my sources)".
- If the answer is not in the provided sources at all, write "⚠️ NOT FOUND in my sources" and suggest where to verify.
- Never estimate or invent precise figures."""

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

    def stream_ask_sync(self, question: str, region: Optional[str] = None, attached_doc_id: Optional[int] = None):
        """Synchronous wrapper for stream_ask. Yields JSON event strings.
        
        This is called from the Django view which runs synchronously.
        For short queries (under 3 words), uses synchronous LLM to avoid event loop issues.
        For normal queries, collects all events from the async generator via asyncio.run(),
        then yields them — avoids per-chunk event loop overhead.
        """
        stream_start_time = time.time()
        
        # Short query path — handled synchronously to avoid event loop issues
        query_word_count = len(question.strip().split())
        if query_word_count < 3:
            logger.info(f"⚡ STREAM_SYNC SHORT QUERY | Words: {query_word_count} - Direct answer (sync)")
            yield json.dumps({"type": "status", "text": "⚡ Generating direct answer..."}) + "\n"
            yield json.dumps({"type": "answer_start"}) + "\n"
            
            direct_prompt = f"""You are a Trade Compliance Expert. Answer the user's question directly.

QUESTION: {question}

Answer concisely and helpfully. If you need more details, ask the user to elaborate."""
            
            try:
                from rag_app.services.llm_service import NVIDIALLMService
                llm = NVIDIALLMService()
                answer = llm.generate(direct_prompt, max_tokens=1024)
                yield json.dumps({"type": "answer_chunk", "text": answer}) + "\n"
                total_time = time.time() - stream_start_time
                logger.info(f"✅ STREAM_SYNC SHORT QUERY DONE | Time: {total_time:.2f}s")
                yield json.dumps({"type": "done"}) + "\n"
                return
            except Exception as e:
                logger.error(f"❌ STREAM_SYNC SHORT QUERY ERROR: {e}", exc_info=True)
                yield json.dumps({"type": "error", "text": str(e)}) + "\n"
                return
        
        # Normal query path — collect all events via asyncio.run(), then yield
        # This avoids the massive overhead of run_until_complete() per chunk
        logger.info(f"🔄 STREAM_SYNC NORMAL QUERY | Collecting events...")
        
        async def _collect_all():
            events = []
            async_gen = self.stream_ask(question, region, attached_doc_id)
            async for event in async_gen:
                events.append(event)
            return events
        
        try:
            all_events = asyncio.run(_collect_all())
            logger.info(f"✅ STREAM_SYNC COLLECTED {len(all_events)} events | Time: {time.time() - stream_start_time:.2f}s")
            for event in all_events:
                yield event
        except Exception as e:
            logger.error(f"❌ STREAM_SYNC ERROR: {e}", exc_info=True)
            yield json.dumps({"type": "error", "text": str(e)}) + "\n"
