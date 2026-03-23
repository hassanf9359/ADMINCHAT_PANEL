"""
RAG Configuration API endpoints.

GET    /rag/configs          - list all RAG configurations
POST   /rag/configs          - create RAG config
PATCH  /rag/configs/:id      - update RAG config
DELETE /rag/configs/:id      - delete RAG config
POST   /rag/configs/:id/test - test RAG connectivity
"""
from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_super_admin
from app.models.admin import Admin
from app.models.rag_config import RagConfig
from app.schemas.common import APIResponse
from app.schemas.rag_config import (
    RagConfigCreate,
    RagConfigListResponse,
    RagConfigResponse,
    RagConfigTestResponse,
    RagConfigUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_api_key(key: str) -> str:
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


def _config_to_response(config: RagConfig) -> RagConfigResponse:
    return RagConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=_mask_api_key(config.api_key),
        dataset_id=config.dataset_id,
        top_k=config.top_k,
        is_active=config.is_active,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/configs", response_model=APIResponse)
async def list_rag_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """List all RAG configurations."""
    result = await db.execute(
        select(RagConfig).order_by(RagConfig.created_at.asc())
    )
    configs = result.scalars().all()

    count_result = await db.execute(select(func.count(RagConfig.id)))
    total = count_result.scalar_one()

    return APIResponse(
        data=RagConfigListResponse(
            items=[_config_to_response(c) for c in configs],
            total=total,
        ).model_dump()
    )


@router.post("/configs", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_rag_config(
    body: RagConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Create a new RAG configuration."""
    config = RagConfig(
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        api_key=body.api_key,
        dataset_id=body.dataset_id,
        top_k=body.top_k,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)

    # Reset RAG provider cache
    from app.faq.rag import reset_rag_provider
    await reset_rag_provider()

    return APIResponse(
        code=201,
        message="RAG config created successfully",
        data=_config_to_response(config).model_dump(),
    )


@router.patch("/configs/{config_id}", response_model=APIResponse)
async def update_rag_config(
    config_id: int,
    body: RagConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Update a RAG configuration."""
    result = await db.execute(select(RagConfig).where(RagConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAG config not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)

    # Reset RAG provider cache
    from app.faq.rag import reset_rag_provider
    await reset_rag_provider()

    return APIResponse(
        message="RAG config updated successfully",
        data=_config_to_response(config).model_dump(),
    )


@router.delete("/configs/{config_id}", response_model=APIResponse)
async def delete_rag_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Delete a RAG configuration."""
    result = await db.execute(select(RagConfig).where(RagConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAG config not found",
        )

    await db.delete(config)
    await db.flush()

    # Reset RAG provider cache
    from app.faq.rag import reset_rag_provider
    await reset_rag_provider()

    return APIResponse(message="RAG config deleted")


@router.post("/configs/{config_id}/test", response_model=APIResponse)
async def test_rag_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Test a RAG configuration by performing a test search."""
    result = await db.execute(select(RagConfig).where(RagConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RAG config not found",
        )

    try:
        from app.faq.rag.dify_provider import DifyRAGProvider

        provider = DifyRAGProvider(
            base_url=config.base_url,
            api_key=config.api_key,
            dataset_id=config.dataset_id,
        )
        try:
            results = await provider.search("test", top_k=3)
            return APIResponse(
                data=RagConfigTestResponse(
                    success=True,
                    result_count=len(results),
                ).model_dump()
            )
        finally:
            await provider.close()
    except Exception as exc:
        logger.exception("RAG config test failed for config %s", config_id)
        return APIResponse(
            data=RagConfigTestResponse(
                success=False,
                error=str(exc)[:500],
            ).model_dump()
        )
