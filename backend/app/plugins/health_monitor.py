from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from sqlalchemy import select, update

from app.database import async_session_factory
from app.plugins.registry import InstalledPlugin

if TYPE_CHECKING:
    pass

logger = logging.getLogger("acp.plugins.health_monitor")

ERROR_THRESHOLD = 5


class PluginHealthMonitor:
    """Tracks plugin errors and auto-disables plugins that exceed the threshold."""

    def __init__(self) -> None:
        self._plugin_manager: Any | None = None

    def set_plugin_manager(self, plugin_manager: Any) -> None:
        """Set a reference to the PluginManager for auto-deactivation."""
        self._plugin_manager = plugin_manager

    async def record_error(self, plugin_id: str, error: str) -> None:
        """Increment error count and auto-disable if threshold exceeded."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(InstalledPlugin).where(
                    InstalledPlugin.plugin_id == plugin_id,
                )
            )
            plugin = result.scalar_one_or_none()
            if plugin is None:
                logger.warning(
                    "Cannot record error for unknown plugin %s", plugin_id
                )
                return

            plugin.error_count += 1
            plugin.last_error = error
            await session.commit()

            new_count = plugin.error_count

        logger.warning(
            "Plugin %s error (%d/%d): %s",
            plugin_id,
            new_count,
            ERROR_THRESHOLD,
            error,
        )

        if new_count >= ERROR_THRESHOLD:
            logger.error(
                "Plugin %s exceeded error threshold (%d), auto-disabling",
                plugin_id,
                ERROR_THRESHOLD,
            )
            if self._plugin_manager is not None:
                try:
                    await self._plugin_manager.deactivate(plugin_id)
                except Exception:
                    logger.exception(
                        "Failed to auto-deactivate plugin %s", plugin_id
                    )

    async def record_success(self, plugin_id: str) -> None:
        """Reset the error count for a plugin on successful operation."""
        async with async_session_factory() as session:
            await session.execute(
                update(InstalledPlugin)
                .where(InstalledPlugin.plugin_id == plugin_id)
                .values(error_count=0)
            )
            await session.commit()

    async def get_health(self, plugin_id: str) -> dict[str, Any]:
        """Return health info for a plugin."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(
                    InstalledPlugin.error_count,
                    InstalledPlugin.last_error,
                    InstalledPlugin.status,
                ).where(InstalledPlugin.plugin_id == plugin_id)
            )
            row = result.one_or_none()
            if row is None:
                return {"error_count": 0, "last_error": None, "status": "unknown"}
            return {
                "error_count": row.error_count,
                "last_error": row.last_error,
                "status": row.status,
            }
