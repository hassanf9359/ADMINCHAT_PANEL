"""
AI Configuration API endpoints.

GET    /ai/configs        - list AI configurations
POST   /ai/configs        - create config
PATCH  /ai/configs/:id    - update config
DELETE /ai/configs/:id    - delete config
POST   /ai/configs/:id/test - test connection
GET    /ai/usage          - usage statistics
GET    /ai/rag-config     - get RAG configuration
PUT    /ai/rag-config     - save RAG configuration
DELETE /ai/rag-config     - delete RAG configuration (fallback to .env)
POST   /ai/rag-config/test - test RAG connectivity
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_super_admin
from app.faq.ai_handler import AIConfig as AIRuntimeConfig
from app.faq.ai_handler import ai_handler
from app.models.admin import Admin
from app.models.ai_config import AiConfig, AiUsageLog
from app.models.settings import SystemSetting
from app.schemas.ai_config import (
    AIConfigCreate,
    AIConfigListResponse,
    AIConfigResponse,
    AIConfigTestRequest,
    AIConfigTestResponse,
    AIConfigUpdate,
    AIUsageStatsResponse,
    RAGConfigResponse,
    RAGConfigSave,
    RAGTestResponse,
)
from app.schemas.common import APIResponse

logger = logging.getLogger(__name__)

router = APIRouter()


def _mask_api_key(key: str) -> str:
    """Mask API key showing only last 4 characters."""
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


def _get_oauth_status(config: AiConfig) -> str | None:
    """Derive OAuth token status from oauth_data."""
    import time
    auth_method = config.auth_method or "api_key"
    if auth_method == "api_key":
        return None
    oauth_data = config.oauth_data
    if not oauth_data:
        return "no_token"
    expires_at = oauth_data.get("expires_at", 0)
    if not expires_at:
        return "no_token"
    now = int(time.time())
    if expires_at < now:
        return "expired"
    if expires_at < now + 600:  # within 10 minutes
        return "expiring"
    return "active"


def _config_to_response(config: AiConfig) -> AIConfigResponse:
    return AIConfigResponse(
        id=config.id,
        name=config.name,
        provider=config.provider,
        base_url=config.base_url,
        api_key_masked=_mask_api_key(config.api_key),
        model=config.model,
        api_format=getattr(config, "api_format", "openai_chat") or "openai_chat",
        default_params=config.default_params or {},
        is_active=config.is_active,
        auth_method=config.auth_method or "api_key",
        oauth_status=_get_oauth_status(config),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


@router.get("/configs", response_model=APIResponse)
async def list_ai_configs(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """List all AI configurations. Requires super_admin."""
    result = await db.execute(
        select(AiConfig).order_by(AiConfig.created_at.asc())
    )
    configs = result.scalars().all()

    count_result = await db.execute(select(func.count(AiConfig.id)))
    total = count_result.scalar_one()

    return APIResponse(
        data=AIConfigListResponse(
            items=[_config_to_response(c) for c in configs],
            total=total,
        ).model_dump()
    )


@router.post("/configs", response_model=APIResponse, status_code=status.HTTP_201_CREATED)
async def create_ai_config(
    body: AIConfigCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Create a new AI configuration. Requires super_admin."""
    config = AiConfig(
        name=body.name,
        provider=body.provider,
        base_url=body.base_url,
        # NOTE: In production, API keys should be encrypted at rest using a
        # proper encryption layer (e.g., AWS KMS, HashiCorp Vault, or
        # Fernet symmetric encryption with a securely managed master key).
        # This requires a key management system and is not implemented here.
        api_key=body.api_key,
        model=body.model,
        default_params=body.default_params,
        is_active=body.is_active,
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)

    return APIResponse(
        code=201,
        message="AI config created successfully",
        data=_config_to_response(config).model_dump(),
    )


@router.patch("/configs/{config_id}", response_model=APIResponse)
async def update_ai_config(
    config_id: int,
    body: AIConfigUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Update an AI configuration. Requires super_admin."""
    result = await db.execute(select(AiConfig).where(AiConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(config, field, value)

    await db.flush()
    await db.refresh(config)

    return APIResponse(
        message="AI config updated successfully",
        data=_config_to_response(config).model_dump(),
    )


@router.delete("/configs/{config_id}", response_model=APIResponse)
async def delete_ai_config(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Delete an AI configuration. Requires super_admin."""
    result = await db.execute(select(AiConfig).where(AiConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )

    await db.delete(config)
    await db.flush()

    return APIResponse(message="AI config deleted")


@router.post("/configs/{config_id}/test", response_model=APIResponse)
async def test_ai_config(
    config_id: int,
    body: AIConfigTestRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _current_user: Admin = Depends(require_super_admin),
) -> APIResponse:
    """Test an AI configuration by calling the API with a simple prompt."""
    result = await db.execute(select(AiConfig).where(AiConfig.id == config_id))
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="AI config not found",
        )

    runtime_config = AIRuntimeConfig(
        base_url=config.base_url,
        api_key=config.api_key,
        model=config.model or "gpt-3.5-turbo",
        max_tokens=config.default_params.get("max_tokens", 100),
        temperature=config.default_params.get("temperature", 0.7),
        api_format=getattr(config, "api_format", "openai_chat") or "openai_chat",
    )

    try:
        ai_resp = await ai_handler.test_connection(runtime_config)
        test_result = AIConfigTestResponse(
            success=True,
            response_text=ai_resp.content[:500],
            latency_ms=ai_resp.latency_ms,
            tokens_used=ai_resp.tokens_used,
        )
    except Exception as exc:
        logger.exception("AI config test failed for config %s", config_id)
        test_result = AIConfigTestResponse(
            success=False,
            error=str(exc)[:500],
        )

    return APIResponse(data=test_result.model_dump())


@router.get("/usage", response_model=APIResponse)
async def get_ai_usage(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_admin)],
    days: int = 30,
) -> APIResponse:
    """Get AI usage statistics. Requires admin+."""
    cutoff = datetime.utcnow() - timedelta(days=days)

    # Total stats
    total_result = await db.execute(
        select(
            func.count(AiUsageLog.id),
            func.coalesce(func.sum(AiUsageLog.tokens_used), 0),
            func.coalesce(func.sum(AiUsageLog.cost_estimate), 0),
        ).where(AiUsageLog.created_at >= cutoff)
    )
    row = total_result.one()
    total_requests = row[0]
    total_tokens = int(row[1])
    total_cost = float(row[2])

    # Daily stats
    daily_result = await db.execute(
        select(
            func.date_trunc("day", AiUsageLog.created_at).label("day"),
            func.count(AiUsageLog.id).label("requests"),
            func.coalesce(func.sum(AiUsageLog.tokens_used), 0).label("tokens"),
            func.coalesce(func.sum(AiUsageLog.cost_estimate), 0).label("cost"),
        )
        .where(AiUsageLog.created_at >= cutoff)
        .group_by("day")
        .order_by("day")
    )
    daily_stats = [
        {
            "date": str(r.day.date()) if r.day else "",
            "requests": r.requests,
            "tokens": int(r.tokens),
            "cost": float(r.cost),
        }
        for r in daily_result.all()
    ]

    # Per-config stats
    config_result = await db.execute(
        select(
            AiUsageLog.ai_config_id,
            AiConfig.name,
            func.count(AiUsageLog.id).label("requests"),
            func.coalesce(func.sum(AiUsageLog.tokens_used), 0).label("tokens"),
            func.coalesce(func.sum(AiUsageLog.cost_estimate), 0).label("cost"),
        )
        .outerjoin(AiConfig, AiUsageLog.ai_config_id == AiConfig.id)
        .where(AiUsageLog.created_at >= cutoff)
        .group_by(AiUsageLog.ai_config_id, AiConfig.name)
    )
    per_config = [
        {
            "config_id": r.ai_config_id,
            "config_name": r.name or "Unknown",
            "requests": r.requests,
            "tokens": int(r.tokens),
            "cost": float(r.cost),
        }
        for r in config_result.all()
    ]

    usage = AIUsageStatsResponse(
        total_requests=total_requests,
        total_tokens=total_tokens,
        total_cost=total_cost,
        daily_stats=daily_stats,
        per_config_stats=per_config,
    )

    return APIResponse(data=usage.model_dump())


# ==================== RAG Config ====================

RAG_SETTINGS_KEY = "rag_config"


def _build_rag_response_from_db(row_value: dict) -> RAGConfigResponse:
    """Build RAGConfigResponse from a DB JSON value."""
    return RAGConfigResponse(
        provider=row_value.get("provider"),
        dify_base_url=row_value.get("dify_base_url"),
        dify_api_key_masked=_mask_api_key(row_value["dify_api_key"]) if row_value.get("dify_api_key") else None,
        dify_dataset_id=row_value.get("dify_dataset_id"),
        top_k=row_value.get("top_k", 3),
        source="database",
    )


def _build_rag_response_from_env() -> RAGConfigResponse | None:
    """Build RAGConfigResponse from .env settings, or None if not configured."""
    from app.config import settings

    provider = (settings.RAG_PROVIDER or "").strip().lower()
    if not provider:
        return None
    return RAGConfigResponse(
        provider=provider,
        dify_base_url=settings.DIFY_BASE_URL or None,
        dify_api_key_masked=_mask_api_key(settings.DIFY_API_KEY) if settings.DIFY_API_KEY else None,
        dify_dataset_id=settings.DIFY_DATASET_ID or None,
        top_k=3,
        source="env",
    )


@router.get("/rag-config", response_model=APIResponse)
async def get_rag_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Get current RAG configuration. DB config takes priority over .env."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == RAG_SETTINGS_KEY)
    )
    row = result.scalar_one_or_none()

    if row is not None:
        return APIResponse(data=_build_rag_response_from_db(row.value).model_dump())

    env_resp = _build_rag_response_from_env()
    if env_resp:
        return APIResponse(data=env_resp.model_dump())

    return APIResponse(data=RAGConfigResponse(source="none").model_dump())


@router.put("/rag-config", response_model=APIResponse)
async def save_rag_config(
    body: RAGConfigSave,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Save RAG configuration to system_settings (overrides .env)."""
    config_value = body.model_dump()

    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == RAG_SETTINGS_KEY)
    )
    row = result.scalar_one_or_none()

    # If API key is None/empty, preserve existing key from DB
    if not config_value.get("dify_api_key") and row is not None:
        config_value["dify_api_key"] = row.value.get("dify_api_key", "")

    # For new configs, API key is required
    if not config_value.get("dify_api_key") and row is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="dify_api_key is required for new RAG configuration",
        )

    if row is not None:
        row.value = config_value
    else:
        db.add(SystemSetting(
            key=RAG_SETTINGS_KEY,
            value=config_value,
            description="RAG provider configuration (managed via Web UI)",
        ))

    await db.flush()

    # Reset cached RAG provider so next call picks up new config
    from app.faq.rag import reset_rag_provider
    await reset_rag_provider()

    return APIResponse(
        message="RAG configuration saved",
        data=_build_rag_response_from_db(config_value).model_dump(),
    )


@router.delete("/rag-config", response_model=APIResponse)
async def delete_rag_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Delete DB RAG configuration, falling back to .env if available."""
    await db.execute(
        delete(SystemSetting).where(SystemSetting.key == RAG_SETTINGS_KEY)
    )
    await db.flush()

    # Reset cached RAG provider
    from app.faq.rag import reset_rag_provider
    await reset_rag_provider()

    env_resp = _build_rag_response_from_env()
    if env_resp:
        return APIResponse(
            message="Database config deleted. Falling back to .env configuration.",
            data=env_resp.model_dump(),
        )

    return APIResponse(
        message="RAG configuration deleted",
        data=RAGConfigResponse(source="none").model_dump(),
    )


@router.post("/rag-config/test", response_model=APIResponse)
async def test_rag_config(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Test RAG connectivity by performing a test search."""
    from app.faq.rag import get_rag_provider

    provider = await get_rag_provider()
    if provider is None:
        return APIResponse(
            data=RAGTestResponse(
                success=False,
                error="RAG provider not configured or initialization failed",
            ).model_dump()
        )

    try:
        results = await provider.search("test", top_k=3)
        return APIResponse(
            data=RAGTestResponse(
                success=True,
                result_count=len(results),
            ).model_dump()
        )
    except Exception as exc:
        logger.exception("RAG config test failed")
        return APIResponse(
            data=RAGTestResponse(
                success=False,
                error=str(exc)[:500],
            ).model_dump()
        )
