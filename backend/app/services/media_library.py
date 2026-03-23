"""
Remote media library checker.
Connects to a user-configured external database (MySQL or PostgreSQL)
to check if a given tmdb_id already exists in their media library.

If no external DB is configured, always returns False (not in library),
and the request is forwarded to the admin panel as usual.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.movie_request import MediaLibraryConfig

logger = logging.getLogger(__name__)


async def _get_config(session: AsyncSession) -> Optional[MediaLibraryConfig]:
    """Load the active media library config (only one can be active)."""
    result = await session.execute(
        select(MediaLibraryConfig).where(MediaLibraryConfig.is_active.is_(True)).limit(1)
    )
    return result.scalar_one_or_none()


def _build_dsn(cfg: MediaLibraryConfig) -> str:
    """Build an async SQLAlchemy DSN from config fields."""
    if cfg.db_type == "postgresql":
        driver = "postgresql+asyncpg"
    elif cfg.db_type == "mysql":
        driver = "mysql+aiomysql"
    else:
        raise ValueError(f"Unsupported db_type: {cfg.db_type}")

    port = cfg.port or (5432 if cfg.db_type == "postgresql" else 3306)
    return f"{driver}://{cfg.username}:{cfg.password}@{cfg.host}:{port}/{cfg.database}"


async def check_in_library(
    session: AsyncSession,
    tmdb_id: int,
    media_type: str,
) -> bool:
    """
    Check if a title exists in the remote media library.

    Returns False if:
    - No MediaLibraryConfig is configured/active
    - The external DB is unreachable
    - The tmdb_id is not found in the specified table
    """
    cfg = await _get_config(session)
    if cfg is None:
        return False

    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        dsn = _build_dsn(cfg)
        engine = create_async_engine(dsn, pool_pre_ping=True, pool_size=2)

        try:
            async with engine.connect() as conn:
                # Build safe query using quoted identifiers
                # The table_name, tmdb_id_column, media_type_column are admin-configured
                query_str = f'SELECT 1 FROM "{cfg.table_name}" WHERE "{cfg.tmdb_id_column}" = :tmdb_id'
                params = {"tmdb_id": tmdb_id}

                if cfg.media_type_column:
                    query_str += f' AND "{cfg.media_type_column}" = :media_type'
                    params["media_type"] = media_type

                query_str += " LIMIT 1"

                result = await conn.execute(text(query_str), params)
                row = result.fetchone()
                return row is not None
        finally:
            await engine.dispose()

    except Exception:
        logger.exception("Failed to check remote media library (tmdb_id=%s)", tmdb_id)
        return False
