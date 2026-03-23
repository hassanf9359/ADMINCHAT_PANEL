"""
RAG module - modular Retrieval-Augmented Generation provider system.

Usage:
    from app.faq.rag import get_rag_provider
    provider = await get_rag_provider()           # first active config
    provider = await get_rag_provider(config_id=3) # specific config
"""
from __future__ import annotations

import asyncio
import logging
from typing import Dict, Optional

from .base import RAGProvider, RAGResult

logger = logging.getLogger(__name__)

# Cache: config_id -> provider instance
_provider_cache: Dict[int, RAGProvider] = {}
_init_lock = asyncio.Lock()


async def _load_config_by_id(config_id: int) -> Optional[dict]:
    """Load a specific RAG config from the rag_configs table."""
    try:
        from app.database import async_session_factory
        from app.models.rag_config import RagConfig
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(RagConfig).where(RagConfig.id == config_id, RagConfig.is_active.is_(True))
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "provider": row.provider,
                "base_url": row.base_url,
                "api_key": row.api_key,
                "dataset_id": row.dataset_id,
                "top_k": row.top_k,
            }
    except Exception:
        logger.debug("Could not load RAG config id=%s from DB", config_id)
        return None


async def _load_first_active_config() -> Optional[dict]:
    """Load the first active RAG config from the rag_configs table."""
    try:
        from app.database import async_session_factory
        from app.models.rag_config import RagConfig
        from sqlalchemy import select

        async with async_session_factory() as session:
            result = await session.execute(
                select(RagConfig)
                .where(RagConfig.is_active.is_(True))
                .order_by(RagConfig.id.asc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return {
                "id": row.id,
                "provider": row.provider,
                "base_url": row.base_url,
                "api_key": row.api_key,
                "dataset_id": row.dataset_id,
                "top_k": row.top_k,
            }
    except Exception:
        logger.debug("Could not load any active RAG config from DB")
        return None


def _build_provider(cfg: dict) -> Optional[RAGProvider]:
    """Instantiate a RAGProvider from a config dict."""
    provider_name = (cfg.get("provider") or "").strip().lower()
    if provider_name == "dify":
        base_url = cfg.get("base_url", "")
        api_key = cfg.get("api_key", "")
        dataset_id = cfg.get("dataset_id", "")
        if not all([base_url, api_key, dataset_id]):
            logger.error("RAG config id=%s incomplete: missing base_url/api_key/dataset_id", cfg.get("id"))
            return None
        if not base_url.startswith(("http://", "https://")):
            logger.error("RAG config id=%s: base_url must start with http:// or https://", cfg.get("id"))
            return None

        from .dify_provider import DifyRAGProvider
        return DifyRAGProvider(
            base_url=base_url,
            api_key=api_key,
            dataset_id=dataset_id,
        )

    logger.warning("Unknown RAG provider: %s (config id=%s)", provider_name, cfg.get("id"))
    return None


async def get_rag_provider(config_id: Optional[int] = None) -> Optional[RAGProvider]:
    """
    Factory function: return a RAG provider.

    - config_id given → load that specific config from rag_configs table
    - config_id None  → load first active config (backward compatible)

    Returns None if not configured. Caches provider instances per config_id.
    """
    global _provider_cache

    async with _init_lock:
        if config_id is not None:
            # Check cache
            if config_id in _provider_cache:
                return _provider_cache[config_id]

            cfg = await _load_config_by_id(config_id)
            if cfg is None:
                logger.warning("RAG config id=%s not found or inactive", config_id)
                return None

            provider = _build_provider(cfg)
            if provider:
                _provider_cache[config_id] = provider
                logger.info("RAG provider initialized from config id=%s: %s", config_id, cfg.get("provider"))
            return provider
        else:
            # Fallback: first active config
            # Check if any cached provider exists (return first one)
            if _provider_cache:
                return next(iter(_provider_cache.values()))

            cfg = await _load_first_active_config()
            if cfg is None:
                return None

            cid = cfg["id"]
            if cid in _provider_cache:
                return _provider_cache[cid]

            provider = _build_provider(cfg)
            if provider:
                _provider_cache[cid] = provider
                logger.info("RAG provider initialized from first active config id=%s: %s", cid, cfg.get("provider"))
            return provider


async def reset_rag_provider() -> None:
    """Reset the cached providers so next get_rag_provider() rebuilds them."""
    global _provider_cache
    async with _init_lock:
        for provider in _provider_cache.values():
            await provider.close()
        _provider_cache.clear()
        logger.info("RAG provider cache reset")


async def shutdown_rag_provider() -> None:
    """Shut down and release all RAG providers. Call from FastAPI shutdown event."""
    await reset_rag_provider()


__all__ = ["get_rag_provider", "shutdown_rag_provider", "reset_rag_provider", "RAGProvider", "RAGResult"]
