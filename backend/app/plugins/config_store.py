from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select, update

from app.database import async_session_factory
from app.plugins.registry import InstalledPlugin

logger = logging.getLogger("acp.plugins.config_store")


class PluginConfigStore:
    """Read/write access to a plugin's config JSONB column.

    Maintains an in-memory cache that is loaded on first access
    and refreshed on writes.
    """

    def __init__(self, plugin_id: str) -> None:
        self.plugin_id = plugin_id
        self._cache: dict[str, Any] | None = None

    async def _ensure_loaded(self) -> None:
        """Load config from DB into cache if not already loaded."""
        if self._cache is not None:
            return
        async with async_session_factory() as session:
            result = await session.execute(
                select(InstalledPlugin.config).where(
                    InstalledPlugin.plugin_id == self.plugin_id,
                )
            )
            row = result.scalar_one_or_none()
            self._cache = dict(row) if row else {}

    async def get(self, key: str, default: Any = None) -> Any:
        """Get a single config value by key."""
        await self._ensure_loaded()
        assert self._cache is not None
        return self._cache.get(key, default)

    async def set(self, key: str, value: Any) -> None:
        """Set a single config value and persist to DB."""
        await self._ensure_loaded()
        assert self._cache is not None
        self._cache[key] = value
        await self._persist()

    async def get_all(self) -> dict[str, Any]:
        """Return the full config dict."""
        await self._ensure_loaded()
        assert self._cache is not None
        return dict(self._cache)

    async def set_all(self, config: dict[str, Any]) -> None:
        """Replace the entire config dict and persist to DB."""
        self._cache = dict(config)
        await self._persist()

    async def _persist(self) -> None:
        """Write the current cache to the database."""
        async with async_session_factory() as session:
            await session.execute(
                update(InstalledPlugin)
                .where(InstalledPlugin.plugin_id == self.plugin_id)
                .values(config=self._cache)
            )
            await session.commit()
        logger.debug("Persisted config for plugin %s", self.plugin_id)

    def invalidate_cache(self) -> None:
        """Clear the in-memory cache so next access reloads from DB."""
        self._cache = None
