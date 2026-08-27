from django.apps import AppConfig
import os
import threading


class RagAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'rag_app'

    def ready(self):
        # Database operations removed to prevent hanging makemigrations.
        # Warm up expensive services at server start so the first query is instant.
        import sys
        if 'runserver' in sys.argv:
            import logging
            logger = logging.getLogger('rag_pipeline')
            try:
                from .services.service_registry import get_embedding_model, get_faiss_service
                get_embedding_model()
                get_faiss_service()
                logger.info("✅ Warm-up complete: embedding model + FAISS index ready (no first-query delay)")
            except Exception as e:
                logger.warning(f"⚠️ Startup warm-up failed (will lazy-load on first query): {e}")
