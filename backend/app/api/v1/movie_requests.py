"""
REST API for movie request management and TMDB API key CRUD.
"""
from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, require_admin, require_super_admin
from app.models.admin import Admin
from app.models.movie_request import MediaLibraryConfig, MovieRequest, MovieRequestUser, TmdbApiKey
from app.schemas.common import APIResponse
from app.schemas.movie_request import (
    MediaLibraryConfigCreate,
    MediaLibraryConfigOut,
    MovieRequestDetail,
    MovieRequestOut,
    MovieRequestStats,
    MovieRequestUpdate,
    MovieRequestUserOut,
    TmdbApiKeyCreate,
    TmdbApiKeyOut,
)

router = APIRouter()


# ──────────────────────────────────────────────
#  Movie Requests
# ──────────────────────────────────────────────

@router.get("/stats", response_model=APIResponse)
async def get_request_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_admin)],
) -> APIResponse:
    """Get movie request statistics."""
    total_q = select(func.count()).select_from(MovieRequest)
    total = (await db.execute(total_q)).scalar() or 0

    stats = MovieRequestStats(total=total)

    for st in ("pending", "fulfilled", "rejected"):
        cnt_q = select(func.count()).select_from(MovieRequest).where(MovieRequest.status == st)
        cnt = (await db.execute(cnt_q)).scalar() or 0
        setattr(stats, st, cnt)

    return APIResponse(data=stats.model_dump())


@router.get("", response_model=APIResponse)
async def list_requests(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_admin)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    media_type: Optional[str] = Query(default=None),
) -> APIResponse:
    """List movie requests with pagination and filters."""
    query = select(MovieRequest)

    if status_filter:
        query = query.where(MovieRequest.status == status_filter)
    if media_type:
        query = query.where(MovieRequest.media_type == media_type)

    # Count
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar() or 0
    total_pages = (total + page_size - 1) // page_size

    # Fetch
    query = query.order_by(MovieRequest.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = result.scalars().all()

    return APIResponse(
        data={
            "items": [MovieRequestOut.model_validate(r).model_dump() for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }
    )


@router.get("/{request_id}", response_model=APIResponse)
async def get_request_detail(
    request_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_admin)],
) -> APIResponse:
    """Get movie request detail with requesting users."""
    result = await db.execute(
        select(MovieRequest)
        .options(selectinload(MovieRequest.request_users))
        .where(MovieRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    # Build user list with TG info via joined relationship
    user_list: list[dict] = []
    for ru in req.request_users:
        tg = ru.tg_user  # lazy="joined" on MovieRequestUser.tg_user
        user_list.append(
            MovieRequestUserOut(
                id=ru.id,
                tg_user_id=ru.tg_user_id,
                tg_username=tg.username if tg else None,
                tg_first_name=tg.first_name if tg else None,
                created_at=ru.created_at,
            ).model_dump()
        )

    detail = MovieRequestDetail.model_validate(req)
    data = detail.model_dump()
    data["request_users"] = user_list

    return APIResponse(data=data)


@router.patch("/{request_id}", response_model=APIResponse)
async def update_request(
    request_id: int,
    body: MovieRequestUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_admin)],
) -> APIResponse:
    """Update movie request status / admin note."""
    result = await db.execute(
        select(MovieRequest).where(MovieRequest.id == request_id)
    )
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

    if body.status is not None:
        req.status = body.status
    if body.admin_note is not None:
        req.admin_note = body.admin_note

    await db.flush()
    return APIResponse(data=MovieRequestOut.model_validate(req).model_dump())


# ──────────────────────────────────────────────
#  TMDB API Keys
# ──────────────────────────────────────────────

def _mask_key(key: str) -> str:
    if len(key) <= 8:
        return "***"
    return key[:4] + "***" + key[-4:]


@router.get("/tmdb-keys", response_model=APIResponse)
async def list_tmdb_keys(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """List all TMDB API keys."""
    result = await db.execute(
        select(TmdbApiKey).order_by(TmdbApiKey.created_at.desc())
    )
    keys = result.scalars().all()

    items = []
    for k in keys:
        out = TmdbApiKeyOut(
            id=k.id,
            name=k.name,
            api_key_masked=_mask_key(k.api_key),
            access_token_masked=_mask_key(k.access_token) if k.access_token else None,
            is_active=k.is_active,
            is_rate_limited=k.is_rate_limited,
            rate_limited_until=k.rate_limited_until,
            request_count=k.request_count,
            created_at=k.created_at,
            updated_at=k.updated_at,
        )
        items.append(out.model_dump())

    return APIResponse(data={"items": items})


@router.post("/tmdb-keys", response_model=APIResponse)
async def create_tmdb_key(
    body: TmdbApiKeyCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Add a new TMDB API key."""
    key = TmdbApiKey(
        name=body.name,
        api_key=body.api_key,
        access_token=body.access_token,
    )
    db.add(key)
    await db.flush()

    return APIResponse(
        data={
            "id": key.id,
            "name": key.name,
            "api_key_masked": _mask_key(key.api_key),
        }
    )


@router.delete("/tmdb-keys/{key_id}", response_model=APIResponse)
async def delete_tmdb_key(
    key_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Delete a TMDB API key."""
    result = await db.execute(
        select(TmdbApiKey).where(TmdbApiKey.id == key_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="TMDB key not found")

    await db.delete(key)
    await db.flush()
    return APIResponse(message="TMDB key deleted")


# ──────────────────────────────────────────────
#  Media Library Config
# ──────────────────────────────────────────────

@router.get("/media-library", response_model=APIResponse)
async def get_media_library_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Get the current media library config (if any)."""
    result = await db.execute(
        select(MediaLibraryConfig).order_by(MediaLibraryConfig.created_at.desc()).limit(1)
    )
    cfg = result.scalar_one_or_none()
    if not cfg:
        return APIResponse(data=None)

    out = MediaLibraryConfigOut(
        id=cfg.id,
        name=cfg.name,
        db_type=cfg.db_type,
        host=cfg.host,
        port=cfg.port,
        database=cfg.database,
        username=cfg.username,
        password_masked=_mask_key(cfg.password),
        table_name=cfg.table_name,
        tmdb_id_column=cfg.tmdb_id_column,
        media_type_column=cfg.media_type_column,
        is_active=cfg.is_active,
        created_at=cfg.created_at,
        updated_at=cfg.updated_at,
    )
    return APIResponse(data=out.model_dump())


@router.post("/media-library", response_model=APIResponse)
async def save_media_library_config(
    body: MediaLibraryConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Create or replace the media library config (only one allowed)."""
    # Delete existing configs
    result = await db.execute(select(MediaLibraryConfig))
    for old in result.scalars().all():
        await db.delete(old)

    cfg = MediaLibraryConfig(
        name=body.name,
        db_type=body.db_type,
        host=body.host,
        port=body.port,
        database=body.database,
        username=body.username,
        password=body.password,
        table_name=body.table_name,
        tmdb_id_column=body.tmdb_id_column,
        media_type_column=body.media_type_column,
        is_active=True,
    )
    db.add(cfg)
    await db.flush()

    return APIResponse(data={"id": cfg.id, "name": cfg.name})


@router.delete("/media-library", response_model=APIResponse)
async def delete_media_library_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Remove the media library config (disables library check)."""
    result = await db.execute(select(MediaLibraryConfig))
    for cfg in result.scalars().all():
        await db.delete(cfg)
    await db.flush()
    return APIResponse(message="Media library config removed")


@router.post("/media-library/test", response_model=APIResponse)
async def test_media_library_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _admin: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Test the media library connection."""
    from app.services.media_library import check_in_library
    try:
        # Just test connectivity by running a harmless check
        await check_in_library(session=db, tmdb_id=0, media_type="movie")
        return APIResponse(data={"success": True, "message": "Connection successful"})
    except Exception as e:
        return APIResponse(data={"success": False, "message": str(e)})
