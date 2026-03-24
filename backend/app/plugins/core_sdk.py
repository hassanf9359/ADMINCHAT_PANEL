from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.plugins.exceptions import PluginPermissionError

logger = logging.getLogger("acp.plugins.core_sdk")


class _ScopedAPIBase:
    """Base class for scoped API namespaces."""

    def __init__(
        self,
        plugin_id: str,
        allowed_scopes: set[str],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._plugin_id = plugin_id
        self._allowed_scopes = allowed_scopes
        self._session_factory = session_factory

    def _check_scope(self, scope: str) -> None:
        """Raise PluginPermissionError if the scope is not granted."""
        if scope not in self._allowed_scopes:
            raise PluginPermissionError(
                f"Plugin '{self._plugin_id}' lacks scope '{scope}'",
                plugin_id=self._plugin_id,
                scope=scope,
            )


class UsersAPI(_ScopedAPIBase):
    """Read-only API for accessing Telegram user data."""

    SCOPE = "users:read"

    async def get_by_id(self, user_id: int) -> Optional[dict[str, Any]]:
        """Get a TgUser by primary key ID."""
        self._check_scope(self.SCOPE)
        from app.models.user import TgUser

        async with self._session_factory() as session:
            result = await session.execute(
                select(TgUser).where(TgUser.id == user_id)
            )
            user = result.scalar_one_or_none()
            return self._serialize(user) if user else None

    async def get_by_tg_uid(self, tg_uid: int) -> Optional[dict[str, Any]]:
        """Get a TgUser by their Telegram user ID."""
        self._check_scope(self.SCOPE)
        from app.models.user import TgUser

        async with self._session_factory() as session:
            result = await session.execute(
                select(TgUser).where(TgUser.tg_uid == tg_uid)
            )
            user = result.scalar_one_or_none()
            return self._serialize(user) if user else None

    @staticmethod
    def _serialize(user: Any) -> dict[str, Any]:
        """Convert a TgUser to a safe dict for plugin consumption."""
        return {
            "id": user.id,
            "tg_uid": user.tg_uid,
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "is_blocked": user.is_blocked,
            "is_premium": user.is_premium,
            "created_at": user.created_at,
        }


class BotsAPI(_ScopedAPIBase):
    """Read-only API for accessing bot data (tokens are masked)."""

    SCOPE = "bots:read"

    async def get_active(self) -> list[dict[str, Any]]:
        """Get all active bots (tokens masked)."""
        self._check_scope(self.SCOPE)
        from app.models.bot import Bot

        async with self._session_factory() as session:
            result = await session.execute(
                select(Bot).where(Bot.is_active.is_(True)).order_by(Bot.id)
            )
            bots = result.scalars().all()
            return [self._serialize(b) for b in bots]

    async def get_by_id(self, bot_id: int) -> Optional[dict[str, Any]]:
        """Get a single bot by primary key ID (token masked)."""
        self._check_scope(self.SCOPE)
        from app.models.bot import Bot

        async with self._session_factory() as session:
            result = await session.execute(
                select(Bot).where(Bot.id == bot_id)
            )
            bot = result.scalar_one_or_none()
            return self._serialize(bot) if bot else None

    @staticmethod
    def _serialize(bot: Any) -> dict[str, Any]:
        """Convert a Bot to a safe dict with masked token."""
        token = bot.token
        masked = f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "***"
        return {
            "id": bot.id,
            "bot_id": bot.bot_id,
            "bot_username": bot.bot_username,
            "display_name": bot.display_name,
            "is_active": bot.is_active,
            "priority": bot.priority,
            "token_masked": masked,
        }


class MessagesAPI(_ScopedAPIBase):
    """Messages API — not yet implemented."""

    SCOPE = "messages:read"

    async def get_by_id(self, message_id: int) -> dict[str, Any]:
        self._check_scope(self.SCOPE)
        raise NotImplementedError(
            "MessagesAPI.get_by_id is not yet implemented. "
            "It will be available in a future release."
        )


class GroupsAPI(_ScopedAPIBase):
    """Groups API — not yet implemented."""

    SCOPE = "groups:read"

    async def list_groups(self) -> list[dict[str, Any]]:
        self._check_scope(self.SCOPE)
        raise NotImplementedError(
            "GroupsAPI.list_groups is not yet implemented. "
            "It will be available in a future release."
        )


class FAQAPI(_ScopedAPIBase):
    """FAQ API — not yet implemented."""

    SCOPE = "faq:read"

    async def search(self, query: str) -> list[dict[str, Any]]:
        self._check_scope(self.SCOPE)
        raise NotImplementedError(
            "FAQAPI.search is not yet implemented. "
            "It will be available in a future release."
        )


class SettingsAPI(_ScopedAPIBase):
    """Settings API — not yet implemented."""

    SCOPE = "settings:read"

    async def get(self, key: str) -> Any:
        self._check_scope(self.SCOPE)
        raise NotImplementedError(
            "SettingsAPI.get is not yet implemented. "
            "It will be available in a future release."
        )


class CoreSDKBridge:
    """Scoped read API bridge exposed to plugins via PluginContext.

    Access to each sub-API is gated by the ``permissions.core_api_scopes``
    declared in the plugin's ``manifest.json``.
    """

    def __init__(
        self,
        plugin_id: str,
        manifest: dict[str, Any],
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self._plugin_id = plugin_id
        self._allowed_scopes: set[str] = set(
            manifest.get("permissions", {}).get("core_api_scopes", [])
        )
        self._session_factory = session_factory
        logger.debug(
            "CoreSDKBridge for plugin %s: scopes=%s",
            plugin_id,
            self._allowed_scopes,
        )

    @property
    def users(self) -> UsersAPI:
        """Access to the Users API."""
        return UsersAPI(self._plugin_id, self._allowed_scopes, self._session_factory)

    @property
    def bots(self) -> BotsAPI:
        """Access to the Bots API."""
        return BotsAPI(self._plugin_id, self._allowed_scopes, self._session_factory)

    @property
    def messages(self) -> MessagesAPI:
        """Access to the Messages API (stub)."""
        return MessagesAPI(self._plugin_id, self._allowed_scopes, self._session_factory)

    @property
    def groups(self) -> GroupsAPI:
        """Access to the Groups API (stub)."""
        return GroupsAPI(self._plugin_id, self._allowed_scopes, self._session_factory)

    @property
    def faq(self) -> FAQAPI:
        """Access to the FAQ API (stub)."""
        return FAQAPI(self._plugin_id, self._allowed_scopes, self._session_factory)

    @property
    def settings(self) -> SettingsAPI:
        """Access to the Settings API (stub)."""
        return SettingsAPI(self._plugin_id, self._allowed_scopes, self._session_factory)
