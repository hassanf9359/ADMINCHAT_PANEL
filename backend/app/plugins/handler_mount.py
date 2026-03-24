from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from aiogram import Router

if TYPE_CHECKING:
    pass

logger = logging.getLogger("acp.plugins.handler_mount")


class HotSwappableRouter:
    """Manages aiogram Router instances for plugins with priority-based ordering.

    Allows plugins to register Telegram bot handlers via their own Router,
    which are dynamically added/removed from the master router without
    restarting the bot.
    """

    def __init__(self) -> None:
        self.master_router = Router(name="plugins_master")
        self._plugin_routers: dict[str, tuple[Router, int]] = {}

    def add(self, plugin_id: str, router: Router, priority: int = 50) -> None:
        """Add a plugin's aiogram router with a given priority.

        Lower priority values are included first.
        """
        if plugin_id in self._plugin_routers:
            logger.warning(
                "Router for plugin %s already registered, replacing", plugin_id
            )
        self._plugin_routers[plugin_id] = (router, priority)
        self._rebuild()
        logger.info("Added aiogram router for plugin %s (priority=%d)", plugin_id, priority)

    def remove(self, plugin_id: str) -> None:
        """Remove a plugin's aiogram router."""
        if plugin_id not in self._plugin_routers:
            logger.warning("No router registered for plugin %s", plugin_id)
            return
        del self._plugin_routers[plugin_id]
        self._rebuild()
        logger.info("Removed aiogram router for plugin %s", plugin_id)

    def _rebuild(self) -> None:
        """Rebuild the master router's sub_routers list sorted by priority."""
        self.master_router.sub_routers.clear()

        sorted_entries = sorted(
            self._plugin_routers.items(),
            key=lambda item: (item[1][1], item[0]),  # (priority, plugin_id)
        )

        for _plugin_id, (router, _priority) in sorted_entries:
            self.master_router.include_router(router)

    @property
    def active_plugins(self) -> list[str]:
        """Return list of plugin IDs with registered routers."""
        return list(self._plugin_routers.keys())
