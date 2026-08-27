import logging
from django.conf import settings

# Service Imports
from .llm_service import NVIDIALLMService
from .web_search_service import TavilySearchService
from .nvidia_embedding_service import NVIDIAEmbeddingService
from .faiss_service import FAISSService
from .cache_service import CacheService
from .query_understanding import QueryUnderstanding
# Use string import or lazy import for QueryAgentService to avoid early recursion
# from .query_agent_service import QueryAgentService 

logger = logging.getLogger('rag_pipeline')

# --- Singletons ---
_embedding_model = None
def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        try:
            _embedding_model = NVIDIAEmbeddingService()
            logger.info("✅ NVIDIAEmbeddingService loaded")
        except Exception as e:
            logger.warning(f"⚠️ NVIDIAEmbeddingService unavailable: {e}")
    return _embedding_model

_faiss_service = None
def get_faiss_service():
    global _faiss_service
    if _faiss_service is None:
        try:
            _faiss_service = FAISSService()
            _faiss_service.load('faiss_index.index')
            logger.info("✅ FAISS index loaded: faiss_index.index")
        except Exception as e:
            logger.warning(f"⚠️ FAISS index unavailable: {e}")
    return _faiss_service

_cache = None
def get_cache():
    global _cache
    if _cache is None:
        _cache = CacheService(ttl_seconds=3600)
    return _cache

_qa = None
def get_qa():
    global _qa
    if _qa is None:
        _qa = QueryUnderstanding()
    return _qa

_agent = None
def get_agent():
    global _agent
    if _agent is None:
        from .query_agent_service import QueryAgentService
        _agent = QueryAgentService()
    return _agent
