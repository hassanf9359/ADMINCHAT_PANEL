"""
Background task to refresh expiring OAuth tokens.

Runs every 5 minutes via APScheduler.
Refreshes tokens that expire within 10 minutes.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy import select

from app.database import async_session_factory
from app.models.ai_config import AiConfig
from app.oauth.encryption import decrypt_oauth_data, encrypt_oauth_data

logger = logging.getLogger(__name__)

# Max consecutive refresh failures before deactivating
MAX_FAILURES = 3


def _get_provider_instance(auth_method: str):
    """Instantiate the correct OAuth provider for refreshing."""
    if auth_method == "openai_oauth":
        from app.oauth.openai import OpenAIOAuth
        return OpenAIOAuth()
    elif auth_method in ("claude_oauth", "claude_session"):
        from app.oauth.claude import ClaudeOAuth
        return ClaudeOAuth()
    elif auth_method == "gemini_oauth":
        from app.oauth.gemini import GeminiOAuth
        return GeminiOAuth()
    return None


async def refresh_expiring_tokens() -> None:
    """
    Find OAuth configs with tokens expiring within 10 minutes and refresh them.
    """
    logger.debug("Checking for expiring OAuth tokens...")

    async with async_session_factory() as session:
        try:
            # Get all OAuth configs
            result = await session.execute(
                select(AiConfig).where(
                    AiConfig.auth_method != "api_key",
                    AiConfig.oauth_data.isnot(None),
                    AiConfig.is_active.is_(True),
                )
            )
            configs = result.scalars().all()

            if not configs:
                return

            now = int(time.time())
            threshold = now + 600  # 10 minutes from now
            refreshed = 0

            for config in configs:
                oauth_data = config.oauth_data
                if not oauth_data:
                    continue

                expires_at = oauth_data.get("expires_at", 0)
                if expires_at > threshold:
                    continue  # Still valid, skip

                # Needs refresh
                try:
                    decrypted = decrypt_oauth_data(oauth_data)
                except ValueError:
                    logger.error(
                        "Config %s (%s) — cannot decrypt oauth_data, skipping",
                        config.id, config.name,
                    )
                    continue
                refresh_tok = decrypted.get("refresh_token", "")
                if not refresh_tok:
                    logger.warning(
                        "Config %s (%s) has no refresh_token — cannot refresh",
                        config.id, config.name,
                    )
                    continue

                provider = _get_provider_instance(config.auth_method)
                if not provider:
                    continue

                try:
                    tokens = await provider.refresh_token(refresh_tok)

                    # Update oauth_data with new tokens
                    new_oauth_data = encrypt_oauth_data({
                        "access_token": tokens.access_token,
                        "refresh_token": tokens.refresh_token,
                        "expires_at": tokens.expires_at,
                        "scopes": tokens.scopes,
                        "provider_meta": tokens.provider_meta,
                    })
                    config.oauth_data = new_oauth_data

                    # Update the api_key field so ai_handler uses the fresh token
                    config.api_key = tokens.access_token

                    # Reset failure counter
                    meta = config.oauth_data.get("provider_meta", {})
                    if "refresh_failures" in meta:
                        meta.pop("refresh_failures")
                        config.oauth_data = {**config.oauth_data, "provider_meta": meta}

                    refreshed += 1
                    logger.info(
                        "Refreshed OAuth token for config %s (%s)",
                        config.id, config.name,
                    )

                except Exception:
                    logger.exception(
                        "Failed to refresh OAuth token for config %s (%s)",
                        config.id, config.name,
                    )
                    # Track failures
                    meta = oauth_data.get("provider_meta", {})
                    failures = meta.get("refresh_failures", 0) + 1
                    meta["refresh_failures"] = failures
                    config.oauth_data = {**oauth_data, "provider_meta": meta}

                    if failures >= MAX_FAILURES:
                        config.is_active = False
                        logger.warning(
                            "Config %s (%s) deactivated after %d refresh failures",
                            config.id, config.name, failures,
                        )

            await session.commit()

            if refreshed:
                logger.info("Refreshed %d OAuth token(s)", refreshed)

        except Exception:
            await session.rollback()
            logger.exception("Error during OAuth token refresh sweep")
