"""
TMDB API client with multi-key rotation and rate-limit handling.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta
from typing import Any, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_request import TmdbApiKey

logger = logging.getLogger(__name__)

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMAGE_BASE = "https://image.tmdb.org/t/p"

# Regex to extract media_type and tmdb_id from TMDB URLs
TMDB_URL_PATTERN = re.compile(
    r"themoviedb\.org/(movie|tv)/(\d+)"
)


def parse_tmdb_url(text: str) -> Optional[tuple[str, int]]:
    """Extract (media_type, tmdb_id) from a TMDB URL in text."""
    match = TMDB_URL_PATTERN.search(text)
    if match:
        return match.group(1), int(match.group(2))
    return None


class TmdbClient:
    """TMDB API client with DB-backed multi-key rotation."""

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def _get_best_key(self, session: AsyncSession) -> Optional[TmdbApiKey]:
        """Pick the active, non-rate-limited key with lowest request_count."""
        now = datetime.utcnow()
        # First, clear expired rate limits
        result = await session.execute(
            select(TmdbApiKey).where(
                TmdbApiKey.is_active.is_(True),
                TmdbApiKey.is_rate_limited.is_(True),
                TmdbApiKey.rate_limited_until <= now,
            )
        )
        for key in result.scalars().all():
            key.is_rate_limited = False
            key.rate_limited_until = None

        # Now pick the best available key
        result = await session.execute(
            select(TmdbApiKey)
            .where(
                TmdbApiKey.is_active.is_(True),
                TmdbApiKey.is_rate_limited.is_(False),
            )
            .order_by(TmdbApiKey.request_count.asc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _request(
        self,
        session: AsyncSession,
        path: str,
        params: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Make an authenticated TMDB API request with key rotation."""
        key = await self._get_best_key(session)
        if not key:
            logger.error("No available TMDB API keys")
            return None

        headers = {}
        query_params = params or {}

        if key.access_token:
            headers["Authorization"] = f"Bearer {key.access_token}"
        else:
            query_params["api_key"] = key.api_key

        url = f"{TMDB_BASE_URL}{path}"
        try:
            resp = await self._http.get(url, headers=headers, params=query_params)

            if resp.status_code == 429:
                # Rate limited — mark this key
                key.is_rate_limited = True
                key.rate_limited_until = datetime.utcnow() + timedelta(seconds=60)
                logger.warning("TMDB key %s rate-limited, retrying with next key", key.name)
                await session.flush()
                # Try once more with a different key
                return await self._request(session, path, params)

            key.request_count += 1
            resp.raise_for_status()
            return resp.json()

        except httpx.HTTPStatusError as e:
            logger.error("TMDB API error %s: %s", e.response.status_code, e.response.text[:200])
            return None
        except httpx.RequestError as e:
            logger.error("TMDB request failed: %s", e)
            return None

    async def get_movie(self, session: AsyncSession, tmdb_id: int) -> Optional[dict[str, Any]]:
        """Fetch movie details from TMDB."""
        return await self._request(session, f"/movie/{tmdb_id}", {"language": "zh-CN"})

    async def get_tv(self, session: AsyncSession, tmdb_id: int) -> Optional[dict[str, Any]]:
        """Fetch TV show details from TMDB."""
        return await self._request(session, f"/tv/{tmdb_id}", {"language": "zh-CN"})

    async def get_media(
        self, session: AsyncSession, media_type: str, tmdb_id: int
    ) -> Optional[dict[str, Any]]:
        """Fetch movie or TV details based on media_type."""
        if media_type == "movie":
            return await self.get_movie(session, tmdb_id)
        elif media_type == "tv":
            return await self.get_tv(session, tmdb_id)
        return None


# Module-level singleton
_client: Optional[TmdbClient] = None


def get_tmdb_client() -> TmdbClient:
    global _client
    if _client is None:
        _client = TmdbClient()
    return _client
