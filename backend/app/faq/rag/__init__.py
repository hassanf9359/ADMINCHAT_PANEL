"""
RAG module - modular Retrieval-Augmented Generation provider system.

Usage:
    from app.faq.rag import get_rag_provider
    provider = get_rag_provider()
    if provider:
        results = await provider.search("user question")
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from .base import RAGProvider, RAGResult

logger = logging.getLogger(__name__)

# Module-level cached instance + lock for thread-safe init
_provider_instance: Optional[RAGProvider] = None
_init_lock = asyncio.Lock()


async def get_rag_provider() -> Optional[RAGProvider]:
    """
    Factory function: return a RAG provider based on settings.RAG_PROVIDER.

    Returns None if RAG is not configured. Thread-safe singleton.
    """
    global _provider_instance
    if _provider_instance is not None:
        return _provider_instance

    async with _init_lock:
        # Double-check after acquiring lock
        if _provider_instance is not None:
            return _provider_instance

        from app.config import settings

        provider_name = (settings.RAG_PROVIDER or "").strip().lower()
        if not provider_name:
            return None

        if provider_name == "dify":
            if not all([settings.DIFY_BASE_URL, settings.DIFY_API_KEY, settings.DIFY_DATASET_ID]):
                logger.error("RAG_PROVIDER=dify but DIFY_BASE_URL/DIFY_API_KEY/DIFY_DATASET_ID not all set")
                return None

            # Validate URL scheme
            if not settings.DIFY_BASE_URL.startswith(("http://", "https://")):
                logger.error("DIFY_BASE_URL must start with http:// or https://")
                return None

            from .dify_provider import DifyRAGProvider
            _provider_instance = DifyRAGProvider(
                base_url=settings.DIFY_BASE_URL,
                api_key=settings.DIFY_API_KEY,
                dataset_id=settings.DIFY_DATASET_ID,
            )
            logger.info("RAG provider initialized: dify")
            return _provider_instance

        logger.warning("Unknown RAG_PROVIDER: %s", provider_name)
        return None


async def shutdown_rag_provider() -> None:
    """Shut down and release the RAG provider. Call from FastAPI shutdown event."""
    global _provider_instance
    if _provider_instance is not None:
        await _provider_instance.close()
        _provider_instance = None
        logger.info("RAG provider shut down")


__all__ = ["get_rag_provider", "shutdown_rag_provider", "RAGProvider", "RAGResult"]
