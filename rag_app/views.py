"""
Zenith Export AI — RAG Pipeline Views v2
=========================================
Multi-granularity retrieval with 4-source search + 4-dimension scoring.

Sources:
  1. DocumentMetadata — document-level topic/commodity matching
  2. SearchIndex summaries — 60-80 word quick-scan entries
  3. SearchIndex chunks — 500-1500 word page-level chunks
  4. FactIndex — structured facts (quantity_limit, deadline, etc.)

Scoring:
  final = 0.20*doc_relevance + 0.25*keyword_match + 0.30*semantic + 0.25*fact_match
"""

import json
import logging
import math
import os
import re
from typing import List, Dict, Tuple

import numpy as np

from django.http import JsonResponse, StreamingHttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.utils import timezone
from asgiref.sync import sync_to_async

from .models import Document, DocumentPage, SearchIndex, DocumentMetadata, FactIndex
from .services.llm_service import NVIDIALLMService
from .services.web_search_service import TavilySearchService
from .services.nvidia_embedding_service import NVIDIAEmbeddingService
from .services.faiss_service import FAISSService
from .services.cache_service import CacheService
from .services.quality_checker import is_answer_weak, get_answer_quality_report
from .services.search_config import TARIFF_TRIGGER_KEYWORDS
from .services.service_registry import (
    get_embedding_model, get_faiss_service, get_cache, get_qa, get_agent
)
from .retrieval_service import _multi_source_retrieve
from .prompts import SYSTEM_PROMPT
from .tariff_disclaimers import get_tariff_disclaimer, is_tariff_query
from .api_auth import require_login_json

logger = logging.getLogger('rag_pipeline')

# ── Keyword boost terms (trade-critical) ──
BOOST_KEYWORDS = [
    "10,000 mt", "10000 mt", "10,000", "10000",
    "quantities less than", "less than 10,000",
    "disqualification", "disqualif",
    "minimum quantity", "minimum quantities", "minimum export",
    "wheat", "barley", "rice", "grain",
    "duty rate", "tariff", "hs code",
    "prohibited", "restricted", "banned",
    "eligibility", "conditions", "shall not",
    "penalty", "fine", "confiscation",
    "export of", "lakh metric tonnes", "lmt",
    "allocation", "re-allocation", "special efc",
    "export authorisation", "authorised dealer",
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _is_tariff_query(question: str) -> bool:
    """Check if the question is about HS codes, duty rates, or tariffs."""
    q = question.lower()
    return any(kw in q for kw in TARIFF_TRIGGER_KEYWORDS)


def _keyword_boost_score(content: str) -> float:
    """Apply keyword boosting for trade-critical terms at retrieval time."""
    content_lower = content.lower()
    matches = sum(1 for kw in BOOST_KEYWORDS if kw in content_lower)
    if matches > 0:
        return 1.0 + (matches * 0.3)
    return 1.0


def _get_semantic_score(query: str, texts: List[str]) -> List[float]:
    """Compute cosine similarity between query and each text."""
    emb_model = get_embedding_model()
    if emb_model is None or not texts:
        return [0.0] * len(texts)

    try:
        query_emb = emb_model.embed_query(query)
        if not query_emb:
            return [0.0] * len(texts)
        query_emb = np.array(query_emb, dtype=np.float32)

        doc_embs = emb_model.embed_batch(texts)
        if not doc_embs:
            return [0.0] * len(texts)
        doc_embs = [np.array(e, dtype=np.float32) for e in doc_embs]

        scores = []
        for d in doc_embs:
            d_norm = np.linalg.norm(d)
            if d_norm == 0:
                scores.append(0.0)
            else:
                sim = float(np.dot(query_emb, d) / (query_norm * d_norm))
                scores.append(max(0.0, min(1.0, (sim + 1.0) / 2.0)))
        return scores
    except Exception as e:
        logger.error(f"⚠️ Semantic scoring failed: {e}")
        return [0.0] * len(texts)


# ============================================================================
# 4-SOURCE RETRIEVAL PIPELINE - lives in retrieval_service.py now.
# _multi_source_retrieve is imported at the top of this module. A former
# local stub here fell through without a return (None), which raised
# TypeError: cannot unpack non-iterable NoneType on /search/. Removed.
# ============================================================================

# ============================================================================
# VIEWS
# ============================================================================

# Landing page URL shown to anonymous visitors (overridable in .env).
LANDING_URL = os.environ.get('LANDING_URL', 'http://localhost:5173')

def index(request):
    """Main page (the chat app). Requires an authenticated session —
    anonymous visitors are bounced to the landing page."""
    if not request.user.is_authenticated:
        return redirect(LANDING_URL)
    import os
    common_queries = []
    try:
        # Resolve path to common_queries.txt in the same directory as views.py
        base_dir = os.path.dirname(os.path.abspath(__file__))
        file_path = os.path.join(base_dir, 'common_queries.txt')
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                # Filter out comments and empty lines
                common_queries = [
                    line.strip() for line in f.readlines() 
                    if line.strip() and not line.strip().startswith('#')
                ]
    except Exception as e:
        logger.error(f"Error reading common_queries.txt: {e}")

    stats = {
        'total_documents': Document.objects.count(),
        'total_pages': DocumentPage.objects.count(),
        'total_indexes': SearchIndex.objects.count(),
        'total_facts': FactIndex.objects.count(),
        'total_metadata': DocumentMetadata.objects.count(),
        'regions': {
            'eu': Document.objects.filter(region='eu').count(),
            'india': Document.objects.filter(region='india').count(),
            'us': Document.objects.filter(region='us').count(),
        }
    }
    return render(request, 'rag_app/index_new.html', {
        'stats': stats,
        'common_queries_json': json.dumps(common_queries)
    })


@csrf_exempt
@require_http_methods(["GET"])
def list_documents(request):
    region = request.GET.get('region', None)
    docs = Document.objects.all()
    if region:
        docs = docs.filter(region=region)
    return JsonResponse({'success': True, 'documents': list(docs.values('id', 'title', 'region', 'processed_at', 'created_at'))})


@csrf_exempt
@require_http_methods(["GET"])
def get_document_pages(request, document_id):
    doc = get_object_or_404(Document, id=document_id)
    return JsonResponse({'success': True, 'document': doc.title, 'pages': list(doc.pages.values('id', 'page_number', 'summary'))})


@csrf_exempt
@require_http_methods(["GET"])
def get_page_content(request, page_id):
    page = get_object_or_404(DocumentPage, id=page_id)
    return JsonResponse({
        'success': True, 'document': page.document.title,
        'page_number': page.page_number, 'summary': page.summary,
        'original_text': page.original_text
    })


@csrf_exempt
@require_http_methods(["GET"])
@require_login_json
def search_knowledge_base(request):
    query = request.GET.get('q', '')
    region = request.GET.get('region', None)
    if not query:
        return JsonResponse({'success': False, 'error': 'Query is required'})

    understood = get_qa().understand(query, region)
    pages, sources, scores, context = _multi_source_retrieve(query, region, understood)

    results = []
    for s in sources:
        results.append({
            'document': s['document'],
            'region': s['region'],
            'page_number': s['page'],
            'section_title': s.get('section_title', ''),
            'source': s.get('source', 'chunk'),
            'match_score': s.get('match_score', 0),
        })

    return JsonResponse({'success': True, 'query': query, 'results_count': len(results), 'results': results})


@csrf_exempt
@require_http_methods(["GET"])
def get_query_suggestions(request):
    query = request.GET.get('q', '').lower().strip()
    max_results = int(request.GET.get('limit', 5))
    
    import os
    suggestions_file = os.path.join(os.path.dirname(__file__), 'common_queries.txt')
    
    suggestions = []
    if os.path.exists(suggestions_file):
        with open(suggestions_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                
                line_lower = line.lower()
                query_words = [w for w in query.split() if w not in ('the', 'a', 'an', 'is', 'are', 'in', 'on', 'of', 'and', 'to', 'for', 'i', 'my')]
                
                is_match = False
                if not query_words:
                    # If query is only stop words, do exact substring match
                    is_match = query in line_lower
                else:
                    # Match if all meaningful words are present in the suggestion
                    is_match = all(word in line_lower for word in query_words)
                    
                if is_match:
                    suggestions.append(line)
                    if len(suggestions) >= max_results:
                        break
    
    return JsonResponse({
        'success': True,
        'query': query,
        'suggestions': suggestions
    })


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
async def ask_question(request):
    """Ask a question using the Agentic RAG (LlamaIndex Async Workflow)."""
    try:
        # Support both JSON and FormData
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            question = data.get('question', '')
            region = data.get('region', None)
            attached_doc_id = data.get('attached_doc_id')
        else:
            # FormData
            question = request.POST.get('question', '')
            region = request.POST.get('region', None)
            attached_doc_id = request.POST.get('attached_doc_id')

        if not question:
            return JsonResponse({'success': False, 'error': 'Question is required'})

        logger.info(f"--- NEW ASYNC AGENT QUERY --- | '{question}' | Region: {region or 'All'}")

        # Cache check (Sync execution for now, or wrap if needed)
        cache_key = f"ask:agent:async:{question.lower().strip()}:{region or 'all'}"
        cache = get_cache()
        cached = await sync_to_async(cache.get)(cache_key)
        
        if cached:
            logger.info(f"✅ Cache HIT")
            cached['cached'] = True
            return JsonResponse(cached)

        # Execute via Async Agent
        agent_service = get_agent()
        # Get uploaded document if attached
        uploaded_doc_text = None
        uploaded_doc_filename = None
        attached_doc_id = data.get("attached_doc_id")
        if attached_doc_id:
            uploaded_docs = request.session.get("uploaded_docs", {})
            if attached_doc_id in uploaded_docs:
                uploaded_doc_text = uploaded_docs[attached_doc_id].get("text", "")
                uploaded_doc_filename = uploaded_docs[attached_doc_id].get("filename", "")
                logger.info(f"Using uploaded document: {uploaded_doc_filename}")
        
        # Execute via Async Agent
        agent_response = await agent_service.ask(question, region, uploaded_doc_text, uploaded_doc_filename)

        if agent_response.get('success'):
            # Add tariff disclaimer post-processing
            if is_tariff_query(question):
                answer = agent_response.get('answer', '')
                sources = agent_response.get('sources', [])
                for source in sources:
                    url = source.get('url', '') or source.get('source', '')
                    if url:
                        disclaimer = get_tariff_disclaimer(url)
                        if disclaimer:
                            agent_response['answer'] = answer + f"\n\n{disclaimer}"
                            break

            await sync_to_async(cache.set)(cache_key, agent_response)
            return JsonResponse(agent_response)
        else:
            return JsonResponse(agent_response, status=500)

    except Exception as e:
        logger.error(f"❌ ask_question error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': f'Error: {str(e)}'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def ask_question_stream(request):
    """Streaming version of ask_question (Agentic RAG)."""
    try:
        data = json.loads(request.body)
        question = data.get('question', '')
        region = data.get('region', None)
        attached_doc_id = data.get('attached_doc_id', None)

        if not question:
            def err():
                yield json.dumps({"type": "error", "text": "Question is required"}) + "\n"
            return StreamingHttpResponse(err(), content_type='text/event-stream')

        logger.info(f"--- STREAMING AGENT QUERY --- | '{question}' | Region: {region or 'All'} | Attached Doc: {attached_doc_id}")

        def generate():
            agent_service = get_agent()
            for event_json in agent_service.stream_ask_sync(question, region, attached_doc_id):
                yield event_json

        return StreamingHttpResponse(generate(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"❌ Streaming error: {e}", exc_info=True)
        def err():
            yield json.dumps({"type": "error", "text": f"Error: {str(e)}"}) + "\n"
        return StreamingHttpResponse(err(), content_type='text/event-stream')


@csrf_exempt
@require_http_methods(["GET"])
def get_knowledge_base_stats(request):
    stats = {
        'documents': {
            'total': Document.objects.count(),
            'eu': Document.objects.filter(region='eu').count(),
            'india': Document.objects.filter(region='india').count(),
            'us': Document.objects.filter(region='us').count(),
        },
        'pages': {'total': DocumentPage.objects.count()},
        'indexes': {
            'total': SearchIndex.objects.count(),
            'summaries': SearchIndex.objects.filter(source_type='summary').count(),
            'chunks': SearchIndex.objects.filter(source_type='chunk').count(),
        },
        'facts': {'total': FactIndex.objects.count()},
        'metadata': {'total': DocumentMetadata.objects.count()},
    }
    return JsonResponse({'success': True, 'stats': stats})


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def enhanced_web_search(request):
    """
    Enhanced web search endpoint with multi-source search and result synthesis.

    POST data:
        {
            "query": "What is the wheat export quota?",
            "region": "india",
            "query_type": "export_procedure"
        }

    Returns:
        JSON with enhanced search results and synthesis
    """
    try:
        from rag_app.services.query_transformer import get_query_transformer
        from rag_app.services.web_search_enhanced import get_enhanced_web_search_service
        from rag_app.services.result_synthesizer import get_result_synthesizer

        data = json.loads(request.body)
        query = data.get('query', '')
        region = data.get('region', None)
        query_type = data.get('query_type', 'general')

        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'})

        logger.info(f"🚀 ENHANCED WEB SEARCH API | Query: {query} | Region: {region}")

        # Transform query
        transformer = get_query_transformer()
        best_query, variations = transformer.enhance_query_for_web_search(
            query, region, max_variations=3
        )

        # Perform enhanced search
        enhanced_service = get_enhanced_web_search_service()
        search_response = enhanced_service.multi_source_search(
            query=best_query,
            region=region,
            query_type=query_type,
            max_results=15
        )

        # Synthesize results
        synthesizer = get_result_synthesizer()
        synthesis_response = synthesizer.synthesize_results(
            search_response, query
        )

        # Create LLM context
        llm_context = synthesizer.create_llm_context(
            synthesis_response, query
        )

        response = {
            'success': True,
            'query': query,
            'best_query': best_query,
            'query_type': query_type,
            'region': region,
            'search_stats': {
                'total_results': search_response['total_results'],
                'confidence': search_response['confidence'],
                'search_time': search_response['search_time']
            },
            'synthesis_stats': {
                'synthesized_count': synthesis_response['synthesized_count'],
                'cross_reference_score': synthesis_response['cross_reference_score'],
                'overall_confidence': synthesis_response['overall_confidence']
            },
            'synthesized_results': synthesis_response['synthesized_results'],
            'llm_context': llm_context
        }

        logger.info(f"✅ ENHANCED SEARCH COMPLETE | Synthesized: {len(synthesis_response['synthesized_results'])} results")

        return JsonResponse(response)

    except Exception as e:
        logger.error(f"❌ Enhanced search error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def enhanced_web_search_stream(request):
    """
    Stream enhanced web search results for real-time feedback.

    POST data:
        {
            "query": "What is the wheat export quota?",
            "region": "india"
        }

    Returns:
        Server-Sent Events (SSE) with search progress and results
    """
    try:
        import asyncio
        from asgiref.sync import sync_to_async

        data = json.loads(request.body)
        query = data.get('query', '')
        region = data.get('region', None)

        if not query:
            async def err():
                yield f"data: {json.dumps({'type': 'error', 'text': 'Query is required'})}\n\n"
            return StreamingHttpResponse(err(), content_type='text/event-stream')

        logger.info(f"🚀 STREAMING ENHANCED SEARCH | Query: {query} | Region: {region}")

        async def generate():
            from rag_app.services.query_transformer import get_query_transformer
            from rag_app.services.web_search_enhanced import get_enhanced_web_search_service
            from rag_app.services.result_synthesizer import get_result_synthesizer

            transformer = get_query_transformer()
            enhanced_service = get_enhanced_web_search_service()
            synthesizer = get_result_synthesizer()

            # Step 1: Transform query
            yield f"data: {json.dumps({'type': 'status', 'text': '🔍 Enhancing query...', 'progress': 10})}\n\n"
            best_query, variations = transformer.enhance_query_for_web_search(query, region)

            yield f"data: {json.dumps({'type': 'status', 'text': f'✅ Query enhanced: {best_query[:100]}...', 'progress': 20})}\n\n"

            # Step 2: Perform enhanced search
            yield f"data: {json.dumps({'type': 'status', 'text': '🌐 Searching multi-source web...', 'progress': 40})}\n\n"

            search_response = enhanced_service.multi_source_search(
                query=best_query,
                region=region,
                query_type=transformer.detect_query_type(query),
                max_results=15
            )

            yield f"data: {json.dumps({'type': 'status', 'text': f'✅ Found {search_response["total_results"]} results', 'progress': 60})}\n\n"

            # Step 3: Synthesize results
            yield f"data: {json.dumps({'type': 'status', 'text': '🧠 Synthesizing results...', 'progress': 80})}\n\n"

            synthesis_response = synthesizer.synthesize_results(search_response, query)

            # Step 4: Stream synthesized results
            for i, result in enumerate(synthesis_response['synthesized_results'], 1):
                yield f"data: {json.dumps({'type': 'result', 'source_id': i, 'source_type': result['source_type'], 'domain': result['domain'], 'title': result['title'], 'relevance_score': result['final_score']})}\n\n"

            # Step 5: Finalize
            yield f"data: {json.dumps({'type': 'done', 'synthesized_count': synthesis_response['synthesized_count'], 'confidence': synthesis_response['overall_confidence']})}\n\n"

        return StreamingHttpResponse(generate(), content_type='text/event-stream')

    except Exception as e:
        logger.error(f"❌ Streaming search error: {e}", exc_info=True)

        async def err():
            yield f"data: {json.dumps({'type': 'error', 'text': str(e)})}\n\n"
        return StreamingHttpResponse(err(), content_type='text/event-stream')


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def synthesize_web_search(request):
    """
    Synthesize web search results for LLM context.

    POST data:
        {
            "query": "What is the wheat export quota?",
            "region": "india",
            "raw_results": [...]
        }

    Returns:
        JSON with synthesized results and LLM context
    """
    try:
        from rag_app.services.result_synthesizer import get_result_synthesizer

        data = json.loads(request.body)
        query = data.get('query', '')
        raw_results = data.get('raw_results', [])

        if not query:
            return JsonResponse({'success': False, 'error': 'Query is required'})

        logger.info(f"🧠 SYNTHESIZING WEB SEARCH | Query: {query}")

        synthesizer = get_result_synthesizer()
        synthesis_response = synthesizer.synthesize_results(
            {'results': raw_results}, query
        )

        llm_context = synthesizer.create_llm_context(
            synthesis_response, query
        )

        response = {
            'success': True,
            'synthesized_count': synthesis_response['synthesized_count'],
            'cross_reference_score': synthesis_response['cross_reference_score'],
            'overall_confidence': synthesis_response['overall_confidence'],
            'synthesized_results': synthesis_response['synthesized_results'],
            'llm_context': llm_context
        }

        logger.info(f"✅ SYNTHESIS COMPLETE | Synthesized: {len(synthesis_response['synthesized_results'])} results")

        return JsonResponse(response)

    except Exception as e:
        logger.error(f"❌ Synthesis error: {e}", exc_info=True)
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def clear_knowledge_base(request):
    FactIndex.objects.all().delete()
    SearchIndex.objects.all().delete()
    DocumentMetadata.objects.all().delete()
    DocumentPage.objects.all().delete()
    Document.objects.all().delete()
    return JsonResponse({'success': True, 'message': 'Knowledge base cleared'})


# ============================================================================
# DOCUMENT UPLOAD HANDLER
# ============================================================================

import uuid
from .utils.document_parser import DocumentParser


MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTENSIONS = ['pdf', 'png', 'jpg', 'jpeg']


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def upload_document(request):
    """
    Upload document, extract text, store in session.
    
    POST: multipart/form-data with file
    Returns JSON: { success, doc_id, filename, text_length, message }
    """
    try:
        # Check if file was uploaded
        if 'file' not in request.FILES:
            return JsonResponse({
                'success': False,
                'error': 'No file provided'
            })
        
        uploaded_file = request.FILES['file']
        filename = uploaded_file.name
        file_ext = filename.split('.')[-1].lower() if '.' in filename else ''
        
        # Validate file extension
        if file_ext not in ALLOWED_EXTENSIONS:
            return JsonResponse({
                'success': False,
                'error': f'Unsupported file type: {file_ext}. Allowed: PDF, PNG, JPG, JPEG'
            })
        
        # Validate file size
        if uploaded_file.size > MAX_UPLOAD_SIZE:
            return JsonResponse({
                'success': False,
                'error': f'File too large. Maximum size is 20MB'
            })
        
        # Parse the document
        parser = DocumentParser()
        result = parser.parse_file(uploaded_file)
        
        if not result.get('success', False):
            return JsonResponse({
                'success': False,
                'error': result.get('error', 'Unknown error')
            })
        
        # Generate unique doc ID
        doc_id = str(uuid.uuid4())
        
        # Store in session
        if 'uploaded_docs' not in request.session:
            request.session['uploaded_docs'] = {}
        
        request.session['uploaded_docs'][doc_id] = {
            'filename': result['filename'],
            'text': result['text'],
            'text_length': len(result['text']),
            'uploaded_at': str(timezone.now())
        }
        request.session.modified = True
        
        logger.info(f'Document uploaded: {filename}, doc_id: {doc_id}, size: {len(result["text"])} chars')
        
        return JsonResponse({
            'success': True,
            'doc_id': doc_id,
            'filename': result['filename'],
            'text_length': len(result['text']),
            'message': 'Document processed successfully'
        })
        
    except Exception as e:
        logger.error(f'upload_document error: {e}', exc_info=True)
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


@csrf_exempt
@require_http_methods(["POST"])
@require_login_json
def clear_uploaded_document(request):
    """
    Clear a specific uploaded document from session.
    
    POST: { doc_id: "xxx" }
    Returns: { success: true }
    """
    try:
        data = json.loads(request.body)
        doc_id = data.get('doc_id')
        
        if doc_id and request.session.get('uploaded_docs', {}).get(doc_id):
            del request.session['uploaded_docs'][doc_id]
            request.session.modified = True
            return JsonResponse({'success': True})
        
        return JsonResponse({'success': False, 'error': 'Document not found'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

