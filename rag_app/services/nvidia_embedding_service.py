import logging
from collections import OrderedDict
from typing import List, Optional
from django.conf import settings
from llama_index.embeddings.nvidia import NVIDIAEmbedding

logger = logging.getLogger('rag_pipeline')

class NVIDIAEmbeddingService:
    """
    Service for generating embeddings using the NVIDIA API via LlamaIndex.
    Uses the dedicated embedding model (e.g., llama-nemotron-embed-1b-v2).
    """
    _query_cache = OrderedDict()
    _QUERY_CACHE_MAX = 512

    def __init__(self):
        self.api_key = settings.NVIDIA_EMBEDDING_API_KEY
        if not self.api_key:
            logger.warning("⚠️ NVIDIA_EMBEDDING_API_KEY is missing. Embedding generation may fail.")
        
        # Initialize the NVIDIA embedding model (nemotron-3-embed-1b: best 1B text retrieval model)
        self.model = NVIDIAEmbedding(
            model="nvidia/nemotron-3-embed-1b",
            api_key=self.api_key,
            truncate="NONE"
        )

    def embed_query(self, query: str) -> Optional[List[float]]:
        """
        Generates an embedding for a user query, with a small in-memory LRU
        cache so repeated/near-duplicate queries skip the expensive API call.
        """
        key = ' '.join(query.lower().split())  # normalize whitespace + case
        cached = self._query_cache.get(key)
        if cached is not None:
            self._query_cache.move_to_end(key)
            return cached

        try:
            emb = self.model.get_query_embedding(query)
        except Exception as e:
            logger.error(f"❌ Failed to embed query: {e}")
            return None

        if emb is not None:
            self._query_cache[key] = emb
            if len(self._query_cache) > self._QUERY_CACHE_MAX:
                self._query_cache.popitem(last=False)  # evict oldest
        return emb

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generates an embedding for a given text snippet (e.g., document chunk).
        """
        try:
            return self.model.get_text_embedding(text)
        except Exception as e:
            logger.error(f"❌ Failed to embed text: {e}")
            return None

    def embed_batch(self, texts: List[str]) -> Optional[List[List[float]]]:
        """
        Generates embeddings for a batch of text snippets.
        """
        try:
            return self.model.get_text_embedding_batch(texts)
        except Exception as e:
            logger.error(f"❌ Failed to embed batch texts: {e}")
            return None
