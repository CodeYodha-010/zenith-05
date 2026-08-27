import logging
import re
import numpy as np
from typing import List, Dict, Tuple, Any

from django.db.models import Q
from .models import Document, DocumentPage, SearchIndex, DocumentMetadata, FactIndex
from .services.llm_service import NVIDIALLMService
from .services.nvidia_embedding_service import NVIDIAEmbeddingService
from .services.faiss_service import FAISSService

logger = logging.getLogger('rag_pipeline')

# ─────────────────────────────────────────────────────────────
# RECIPROCAL RANK FUSION (RRF) - Re-ranking without LLM
# Combines multiple rankings into one unified score
# ─────────────────────────────────────────────────────────────

def reciprocal_rank_fusion(
    rankings: List[Tuple[Any, float]], 
    k: int = 60
) -> List[Tuple[Any, float]]:
    """
    Combine multiple ranking lists using RRF.
    
    Args:
        rankings: List of (item, score) tuples from different rankers
        k: RRF parameter (higher = less discriminative)
    
    Returns:
        Unified ranking with combined RRF scores
    """
    if not rankings:
        return []
    
    # Collect all unique items
    item_scores = {}
    
    for ranking in rankings:
        if not ranking:
            continue
        # Sort by score descending
        sorted_ranking = sorted(ranking, key=lambda x: x[1], reverse=True)
        
        # Apply RRF formula: score = sum(1 / (k + rank)) for each ranker
        for rank, (item, orig_score) in enumerate(sorted_ranking, start=1):
            if item not in item_scores:
                item_scores[item] = {'rrf': 0.0, 'original_scores': []}
            item_scores[item]['rrf'] += 1.0 / (k + rank)
            item_scores[item]['original_scores'].append(orig_score)
    
    # Combine RRF with original scores
    final_ranking = []
    for item, data in item_scores.items():
        avg_orig = sum(data['original_scores']) / len(data['original_scores']) if data['original_scores'] else 0
        # Weight RRF more heavily for final score
        combined_score = (0.7 * data['rrf']) + (0.3 * avg_orig)
        final_ranking.append((item, combined_score))
    
    return sorted(final_ranking, key=lambda x: x[1], reverse=True)


def get_bm25_ranking(query: str, items: List, content_field: str) -> List[Tuple]:
    """Get BM25 scores for a list of items."""
    if not items:
        return []
    
    texts = [getattr(item, content_field, '') or '' for item in items]
    scores = _bm25_score_list(query.lower(), texts)
    return [(item, score) for item, score in zip(items, scores) if score > 0]


def get_faiss_ranking(query: str, chunks: List[SearchIndex], all_chunk_ids: list) -> List[Tuple]:
    """Get FAISS semantic scores for chunks."""
    from .services.service_registry import get_embedding_model, get_faiss_service
    
    if not chunks or not all_chunk_ids:
        return []
    
    emb_model = get_embedding_model()
    f_service = get_faiss_service()
    
    if emb_model is None or f_service is None:
        return []
    
    try:
        query_emb = emb_model.embed_query(query)
        if not query_emb:
            return []
        
        query_emb = np.array(query_emb, dtype=np.float32)
        query_emb = query_emb / np.linalg.norm(query_emb)
        
        D, I = f_service.search(query_emb.reshape(1, -1), k=min(50, len(all_chunk_ids)))
        
        I = I.flatten().tolist()
        
        # Map FAISS indices back to chunks
        id_to_faiss = {chunk_id: idx for idx, chunk_id in enumerate(all_chunk_ids)}
        faiss_scores = {i: float(D[0][idx]) for idx, i in enumerate(I)}
        
        results = []
        for chunk in chunks:
            faiss_idx = id_to_faiss.get(chunk.id)
            if faiss_idx is not None and faiss_idx in faiss_scores:
                results.append((chunk, faiss_scores[faiss_idx]))
        
        return results
    except Exception as e:
        logger.error(f"FAISS ranking error: {e}")
        return []


# Shared Keyword boost terms (trade-critical)
BOOST_KEYWORDS = [
    "10,000 mt", "10000 mt", "10,000", "10000",
    "export", "import", "duty", "tariff", "compliance",
    "licensing", "quota", "customs", "regulation",
    "dgft", "cbic", "bis", "fssai"
]

def _keyword_boost_score(text: str) -> float:
    """Calculate boost score based on trade-critical keywords."""
    score = 1.0
    text_lower = text.lower()
    for keyword in BOOST_KEYWORDS:
        if keyword in text_lower:
            score += 0.15
    return min(score, 3.0)

def _bm25_score_list(query_lower: str, texts: List[str]) -> List[float]:
    """Compute BM25-like scores for a list of texts."""
    try:
        from rank_bm25 import BM25Okapi
        if not texts:
            return []
        query_tokens = re.findall(r'\w+', query_lower)
        if not query_tokens:
            return [0.0] * len(texts)
        tokenized = [re.findall(r'\w+', t.lower()) for t in texts]
        bm25 = BM25Okapi(tokenized)
        return list(bm25.get_scores(query_tokens))
    except ImportError:
        logger.warning("rank_bm25 not installed, using simple term matching")
        return [1.0] * len(texts)

def _multi_source_retrieve(query: str, region: str = None, understood: Dict = None):
    """
    Advanced 4-source retrieval pipeline.
    1. Metadata (DocumentMetadata)
    2. Structured Facts (FactIndex)
    3. Vector/Semantic (SearchIndex chunks)
    4. Summaries (SearchIndex summaries)
    """
    from .services.service_registry import get_embedding_model, get_faiss_service
    
    query_lower = query.lower()
    
    # ── SOURCE 1: Document Metadata — finding documents by theme/title ──
    metadata_qs = DocumentMetadata.objects.all().select_related('document')
    if region and region in ('eu', 'india', 'us'):
        metadata_qs = metadata_qs.filter(document__region=region)
    
    metadata_candidates = list(metadata_qs[:50])
    relevant_doc_ids = set()
    metadata_context = ""
    
    if metadata_candidates:
        meta_texts = [f"{m.document.title} {m.topics} {m.summary}" for m in metadata_candidates]
        meta_scores = _bm25_score_list(query_lower, meta_texts)
        meta_results = sorted(zip(metadata_candidates, meta_scores), key=lambda x: x[1], reverse=True)
        top_meta = [m for m, score in meta_results[:3] if score > 0.1]
        for m in top_meta:
            relevant_doc_ids.add(m.document_id)
            metadata_context += f"- Document: {m.document.title}\n  Summary: {m.summary}\n  Topics: {m.topics}\n"

    # ── SOURCE 2: Structured Facts — high-precision fact lookup ──
    fact_qs = FactIndex.objects.all().select_related('page__document')
    if region and region in ('eu', 'india', 'us'):
        fact_qs = fact_qs.filter(page__document__region=region)
        
    fact_candidates = list(fact_qs[:50])
    fact_results = []
    fact_context = ""
    
    if fact_candidates:
        fact_texts = [f"{f.subject} {f.fact_type} {f.value} {f.raw_text}" for f in fact_candidates]
        fact_bm25 = _bm25_score_list(query_lower, fact_texts)
        fact_scored = sorted(zip(fact_candidates, fact_bm25), key=lambda x: x[1], reverse=True)
        fact_results = [f for f, score in fact_scored[:4] if score > 0.5]
        for f in fact_results:
            relevant_doc_ids.add(f.page.document_id)
            fact_context += f"- {f.subject}: {f.value} ({f.fact_type}). Source: {f.page.document.title}\n"

    # ── SOURCE 3: Semantic/Vector Search — FAISS indexed chunks ──
    qs = SearchIndex.objects.filter(source_type='chunk').select_related('page__document')
    if region and region in ('eu', 'india', 'us'):
        qs = qs.filter(page__document__region=region)

    all_chunk_ids = list(SearchIndex.objects.filter(source_type='chunk').order_by('id').values_list('id', flat=True))
    
    top_chunks = []
    boosted_candidates = []
    
    emb_model = get_embedding_model()
    if emb_model is None:
        logger.warning("⚠️ Embedding model unavailable")
    else:
        query_emb = emb_model.embed_query(query)
        f_service = get_faiss_service()
        
        if query_emb and f_service:
            query_emb = np.array(query_emb, dtype=np.float32)
            query_emb = query_emb / np.linalg.norm(query_emb)
            
            D, I = f_service.search(query_emb.reshape(1, -1), k=50)
            I = I.flatten().tolist()
            chunk_ids = [all_chunk_ids[i] for i in I if i < len(all_chunk_ids)]
            candidates = list(qs.filter(id__in=chunk_ids))
            
            id_to_faiss_idx = {chunk_id: idx for idx, chunk_id in enumerate(all_chunk_ids)}
            faiss_scores = {i: float(D[0][idx]) for idx, i in enumerate(I) if i < len(all_chunk_ids)}
            
            for chunk in candidates:
                faiss_idx = id_to_faiss_idx.get(chunk.id)
                if faiss_idx is not None and faiss_idx in faiss_scores:
                    score = faiss_scores[faiss_idx]
                    doc_boost = 1.5 if chunk.page.document_id in relevant_doc_ids else 1.0
                    kw_boost = _keyword_boost_score(chunk.content)
                    final_score = score * min(kw_boost, 2.0) * doc_boost
                    boosted_candidates.append((chunk, final_score))
            
            boosted_candidates.sort(key=lambda x: x[1], reverse=True)
            
            # Deduplicate
            seen = set()
            unique = []
            for chunk, score in boosted_candidates:
                dedup_key = f"{chunk.page_id}:{chunk.content[:300].strip()}"
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    unique.append((chunk, score))
            top_chunks = unique[:5]

    # ── SOURCE 4: SearchIndex summaries ──
    summary_qs = SearchIndex.objects.filter(source_type='summary').select_related('page__document')
    if region and region in ('eu', 'india', 'us'):
        summary_qs = summary_qs.filter(page__document__region=region)
        
    summary_candidates = list(summary_qs[:50])
    sum_bm25 = _bm25_score_list(query_lower, [s.content for s in summary_candidates])
    scored_summaries = sorted(zip(summary_candidates, sum_bm25), key=lambda x: x[1], reverse=True)
    top_summaries = scored_summaries[:5]

    # ── Assemble final context ──
    page_ids = set()
    sources = []
    context_parts = []
    
    for chunk, score in top_chunks:
        page = chunk.page
        if page.id not in page_ids:
            page_ids.add(page.id)
            context_parts.append(f"[DOCUMENT: {page.document.title} — Page {page.page_number}]\n{chunk.content}")
        sources.append({
            'type': 'kb', 'document': page.document.title, 'region': page.document.region,
            'page': page.page_number, 'source': 'chunk', 'match_score': round(score, 4),
        })

    if metadata_context: context_parts.insert(0, f"[DOCUMENT METADATA]\n{metadata_context}")
    if fact_context: context_parts.insert(1, f"[STRUCTURED FACTS]\n{fact_context}")
    
    for s, score in top_summaries:
        if s.page.id not in page_ids and len(context_parts) < 8:
            page_ids.add(s.page.id)
            context_parts.append(f"[SUMMARY: {s.page.document.title}]\n{s.content}")
            sources.append({
                'type': 'kb', 'document': s.page.document.title, 'region': s.page.document.region,
                'page': s.page.page_number, 'source': 'summary', 'match_score': round(score, 4),
            })

    kb_context = "\n\n" + "=" * 60 + "\n\n".join(context_parts)
    full_pages = DocumentPage.objects.filter(id__in=page_ids).select_related('document')
    
    actual_scores = [s.get("match_score", 1.0) for s in sources[:5]]
    return list(full_pages), sources[:5], actual_scores, kb_context


# ─────────────────────────────────────────────────────────────
# NEW: RRF-Based Multi-Source Retrieval (Improved)
# Uses Reciprocal Rank Fusion for better re-ranking
# ─────────────────────────────────────────────────────────────

def _multi_source_retrieve_rrf(query: str, region: str = None, understood: Dict = None, top_k: int = 3):
    """
    RRF-based retrieval with better ranking.
    
    Uses Reciprocal Rank Fusion to combine:
    - BM25 keyword matching
    - FAISS semantic similarity
    - Fact confidence scores
    
    Args:
        query: User query
        region: Filter by region (india/eu/us)
        understood: Pre-processed query understanding
        top_k: Number of top results to return (default 3 for better AI focus)
    
    Returns:
        (pages, sources, scores, context_string)
    """
    from .services.service_registry import get_embedding_model, get_faiss_service
    
    query_lower = query.lower()
    logger.info(f"🔄 RRF RETRIEVAL | Query: {query[:50]} | top_k: {top_k}")
    
    # Get all candidate chunks
    chunk_qs = SearchIndex.objects.filter(source_type='chunk').select_related('page__document')
    if region and region in ('eu', 'india', 'us'):
        chunk_qs = chunk_qs.filter(page__document__region=region)
    
    all_chunk_ids = list(SearchIndex.objects.filter(source_type='chunk').order_by('id').values_list('id', flat=True))
    all_chunks = list(chunk_qs)
    
    if not all_chunks:
        logger.warning("⚠️ No chunks found in knowledge base")
        return [], [], [], "No documents in knowledge base."
    
    # ── RANKING 1: BM25 (keyword) ──
    logger.info("   📊 Ranking 1: BM25 (keyword matching)")
    chunk_texts = [c.content for c in all_chunks]
    bm25_scores = _bm25_score_list(query_lower, chunk_texts)
    bm25_ranking = [(c, s) for c, s in zip(all_chunks, bm25_scores)]
    bm25_ranking = sorted(bm25_ranking, key=lambda x: x[1], reverse=True)[:20]  # Top 20
    
    # ── RANKING 2: FAISS (semantic) ──
    logger.info("   📊 Ranking 2: FAISS (semantic similarity)")
    faiss_ranking = get_faiss_ranking(query, all_chunks, all_chunk_ids)
    faiss_ranking = sorted(faiss_ranking, key=lambda x: x[1], reverse=True)[:20]  # Top 20
    
    # ── RANKING 3: Fact matching (if relevant facts exist) ──
    logger.info("   📊 Ranking 3: Fact confidence")
    fact_ranking = []
    if understood and understood.get('fact_types'):
        # Find chunks that contain facts
        fact_types = understood.get('fact_types', [])
        fact_qs = FactIndex.objects.filter(
            fact_type__in=fact_types,
            confidence__gte=0.5
        ).select_related('page__document')
        if region and region in ('eu', 'india', 'us'):
            fact_qs = fact_qs.filter(page__document__region=region)
        
        facts = list(fact_qs[:20])
        fact_page_ids = {f.page_id for f in facts}
        
        # Boost chunks that have related facts
        for chunk in all_chunks:
            if chunk.page_id in fact_page_ids:
                # Find confidence of related fact
                related_facts = [f for f in facts if f.page_id == chunk.page_id]
                max_conf = max((f.confidence for f in related_facts), default=0.5)
                fact_ranking.append((chunk, max_conf))
    
    fact_ranking = sorted(fact_ranking, key=lambda x: x[1], reverse=True)[:20]
    
    # ── COMBINE: RRF ──
    logger.info("   🔀 Combining rankings with RRF...")
    rankings = [bm25_ranking, faiss_ranking, fact_ranking]
    combined = reciprocal_rank_fusion(rankings, k=60)
    
    # Apply keyword boost to final results
    logger.info("   🔼 Applying keyword boost...")
    boosted_results = []
    for chunk, rrf_score in combined[:top_k * 2]:  # Get more for boost
        kw_boost = _keyword_boost_score(chunk.content)
        final_score = rrf_score * min(kw_boost, 2.0)
        boosted_results.append((chunk, final_score))
    
    # Deduplicate and get top_k
    seen = set()
    final_chunks = []
    for chunk, score in boosted_results:
        dedup_key = f"{chunk.page_id}:{chunk.content[:200].strip()}"
        if dedup_key not in seen:
            seen.add(dedup_key)
            final_chunks.append((chunk, score))
            if len(final_chunks) >= top_k:
                break
    
    logger.info(f"   ✅ RRF complete: {len(final_chunks)} final chunks")
    
    # ── Assemble context ──
    page_ids = set()
    sources = []
    context_parts = []
    
    for chunk, score in final_chunks:
        page = chunk.page
        if page.id not in page_ids:
            page_ids.add(page.id)
            context_parts.append(
                f"[DOCUMENT: {page.document.title} — Page {page.page_number}]"
                f"\n{chunk.content}"
            )
        sources.append({
            'type': 'kb',
            'document': page.document.title,
            'region': page.document.region,
            'page': page.page_number,
            'source': 'chunk',
            'match_score': round(score, 4),
            'rank_method': 'rrf'
        })
    
    # Add metadata context
    metadata_context = _get_metadata_context(query, region, understood)
    if metadata_context:
        context_parts.insert(0, f"[DOCUMENT METADATA]\n{metadata_context}")
    
    # Add fact context
    fact_context = _get_fact_context(query, region, understood)
    if fact_context:
        context_parts.insert(1, f"[STRUCTURED FACTS]\n{fact_context}")
    
    kb_context = "\n\n" + "=" * 60 + "\n\n".join(context_parts)
    
    # Get pages
    full_pages = DocumentPage.objects.filter(id__in=page_ids).select_related('document')
    scores = [s.get('match_score', 1.0) for s in sources]
    
    logger.info(f"   📤 Returning {len(sources)} sources with avg score: {sum(scores)/len(scores):.3f}")
    
    return list(full_pages), sources, scores, kb_context


def _get_metadata_context(query: str, region: str, understood: Dict) -> str:
    """Get relevant document metadata."""
    query_lower = query.lower()
    
    meta_qs = DocumentMetadata.objects.all().select_related('document')
    if region and region in ('eu', 'india', 'us'):
        meta_qs = meta_qs.filter(document__region=region)
    
    metas = list(meta_qs[:30])
    if not metas:
        return ""
    
    meta_texts = [f"{m.document.title} {m.topics} {m.summary}" for m in metas]
    scores = _bm25_score_list(query_lower, meta_texts)
    scored = sorted(zip(metas, scores), key=lambda x: x[1], reverse=True)
    
    top_metas = [m for m, s in scored[:3] if s > 0.1]
    
    context = ""
    for m in top_metas:
        context += f"- Document: {m.document.title}\n  Summary: {m.summary[:200]}\n  Topics: {m.topics}\n"
    
    return context


def _get_fact_context(query: str, region: str, understood: Dict) -> str:
    """Get relevant structured facts."""
    if not understood:
        return ""
    
    query_lower = query.lower()
    fact_types = understood.get('fact_types', [])
    topics = understood.get('topics', [])
    
    fact_qs = FactIndex.objects.all().select_related('page__document')
    if region and region in ('eu', 'india', 'us'):
        fact_qs = fact_qs.filter(page__document__region=region)
    
    if fact_types:
        fact_qs = fact_qs.filter(fact_type__in=fact_types)
    
    facts = list(fact_qs[:30])
    if not facts:
        return ""
    
    # Score by relevance
    fact_texts = [f"{f.subject} {f.fact_type} {f.value}" for f in facts]
    scores = _bm25_score_list(query_lower, fact_texts)
    scored = sorted(zip(facts, scores), key=lambda x: x[1], reverse=True)
    
    top_facts = [f for f, s in scored[:5] if s > 0.3]
    
    context = ""
    for f in top_facts:
        context += f"- {f.subject}: {f.value} ({f.fact_type})\n"
        context += f"  Source: {f.page.document.title}\n"
    
    return context
