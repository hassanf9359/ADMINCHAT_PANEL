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
import hashlib
import json
import logging
from typing import Optional

from .base import RAGProvider, RAGResult

logger = logging.getLogger(__name__)

# Module-level cached instance + lock for thread-safe init
_provider_instance: Optional[RAGProvider] = None
_config_hash: Optional[str] = None
_init_lock = asyncio.Lock()


def _hash_config(cfg: dict) -> str:
    """Produce a stable hash for a config dict to detect changes."""
    return hashlib.md5(json.dumps(cfg, sort_keys=True).encode()).hexdigest()


async def _load_db_config() -> Optional[dict]:
    """Load RAG config from system_settings table. Returns None if not found."""
    try:
        from app.database import async_session_factory
        from app.models.settings import SystemSetting
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(SystemSetting.value).where(SystemSetting.key == "rag_config")
            )
            row = result.scalar_one_or_none()
            return row if isinstance(row, dict) else None
    except Exception:
        logger.debug("Could not load RAG config from DB (DB may not be ready)")
        return None


async def get_rag_provider() -> Optional[RAGProvider]:
    """
    Factory function: return a RAG provider based on configuration.

    Priority: DB system_settings → .env settings.
    Returns None if RAG is not configured. Thread-safe singleton.

    After reset_rag_provider(), the next call rebuilds from config.
    Between resets, the cached instance is returned without DB queries.
    """
    global _provider_instance, _config_hash

    # Fast path: if already initialized, return cached instance
    if _provider_instance is not None:
        return _provider_instance
    # If we've already checked and found no config, don't re-query every call.
    # _config_hash == "__none__" means "checked, nothing configured".
    if _config_hash == "__none__":
        return None

    async with _init_lock:
        # Double-check after lock
        if _provider_instance is not None:
            return _provider_instance
        if _config_hash == "__none__":
            return None

        # Try DB config first
        db_config = await _load_db_config()

        if db_config:
            provider_name = (db_config.get("provider") or "").strip().lower()
            if provider_name == "dify":
                base_url = db_config.get("dify_base_url", "")
                api_key = db_config.get("dify_api_key", "")
                dataset_id = db_config.get("dify_dataset_id", "")
                if not all([base_url, api_key, dataset_id]):
                    logger.error("DB RAG config incomplete: missing dify_base_url/dify_api_key/dify_dataset_id")
                    _config_hash = "__none__"
                    return None
                if not base_url.startswith(("http://", "https://")):
                    logger.error("dify_base_url must start with http:// or https://")
                    _config_hash = "__none__"
                    return None

                from .dify_provider import DifyRAGProvider
                _provider_instance = DifyRAGProvider(
                    base_url=base_url,
                    api_key=api_key,
                    dataset_id=dataset_id,
                )
                _config_hash = _hash_config(db_config)
                logger.info("RAG provider initialized from DB config: dify")
                return _provider_instance

            logger.warning("Unknown RAG provider in DB config: %s", provider_name)
            _config_hash = "__none__"
            return None

        # Fallback to .env
        from app.config import settings

        provider_name = (settings.RAG_PROVIDER or "").strip().lower()
        if not provider_name:
            _config_hash = "__none__"
            return None

        if provider_name == "dify":
            if not all([settings.DIFY_BASE_URL, settings.DIFY_API_KEY, settings.DIFY_DATASET_ID]):
                logger.error("RAG_PROVIDER=dify but DIFY_BASE_URL/DIFY_API_KEY/DIFY_DATASET_ID not all set")
                _config_hash = "__none__"
                return None
            if not settings.DIFY_BASE_URL.startswith(("http://", "https://")):
                logger.error("DIFY_BASE_URL must start with http:// or https://")
                _config_hash = "__none__"
                return None

            from .dify_provider import DifyRAGProvider
            _provider_instance = DifyRAGProvider(
                base_url=settings.DIFY_BASE_URL,
                api_key=settings.DIFY_API_KEY,
                dataset_id=settings.DIFY_DATASET_ID,
            )
            _config_hash = "env"
            logger.info("RAG provider initialized from .env: dify")
            return _provider_instance

        logger.warning("Unknown RAG_PROVIDER: %s", provider_name)
        _config_hash = "__none__"
        return None


async def reset_rag_provider() -> None:
    """Reset the cached provider so next get_rag_provider() rebuilds it."""
    global _provider_instance, _config_hash
    async with _init_lock:
        if _provider_instance is not None:
            await _provider_instance.close()
        _provider_instance = None
        _config_hash = None
        logger.info("RAG provider cache reset")


async def shutdown_rag_provider() -> None:
    """Shut down and release the RAG provider. Call from FastAPI shutdown event."""
    await reset_rag_provider()


__all__ = ["get_rag_provider", "shutdown_rag_provider", "reset_rag_provider", "RAGProvider", "RAGResult"]
