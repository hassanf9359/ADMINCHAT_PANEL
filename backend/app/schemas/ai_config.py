"""
Pydantic schemas for AI Config API endpoints.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---- Request schemas ----

class AIConfigCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., pattern=r"^(openai|anthropic|custom)$")
    base_url: str = Field(..., min_length=1, max_length=500)
    api_key: str = Field(..., min_length=1, max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    api_format: str = Field(default="openai_chat", pattern=r"^(openai_chat|anthropic_responses)$")
    default_params: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.7,
        "max_tokens": 500,
    })
    is_active: bool = True


class AIConfigUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    provider: Optional[str] = Field(None, pattern=r"^(openai|anthropic|custom)$")
    base_url: Optional[str] = Field(None, min_length=1, max_length=500)
    api_key: Optional[str] = Field(None, min_length=1, max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    api_format: Optional[str] = Field(None, pattern=r"^(openai_chat|anthropic_responses)$")
    default_params: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class AIConfigTestRequest(BaseModel):
    """Optional override params for test connection."""
    prompt: Optional[str] = Field(None, max_length=500)


# ---- Response schemas ----

class AIConfigResponse(BaseModel):
    id: int
    name: str
    provider: str
    base_url: str
    api_key_masked: str = ""  # Only show last 4 chars
    model: Optional[str] = None
    api_format: str = "openai_chat"
    default_params: Dict[str, Any] = {}
    is_active: bool = True
    auth_method: str = "api_key"
    oauth_status: Optional[str] = None  # 'active' | 'expiring' | 'expired' | 'no_token'
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class AIConfigListResponse(BaseModel):
    items: List[AIConfigResponse] = []
    total: int = 0


class AIConfigTestResponse(BaseModel):
    success: bool
    response_text: Optional[str] = None
    latency_ms: float = 0.0
    tokens_used: int = 0
    error: Optional[str] = None


class AIUsageStatsResponse(BaseModel):
    total_requests: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    daily_stats: List[Dict[str, Any]] = []
    per_config_stats: List[Dict[str, Any]] = []


# ---- RAG Config schemas ----

# ---- OAuth schemas ----

class OAuthAuthUrlRequest(BaseModel):
    """Metadata for creating a config after OAuth success."""
    name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., pattern=r"^(openai|anthropic|custom)$")
    base_url: str = Field(default="", max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    api_format: str = Field(default="openai_chat", pattern=r"^(openai_chat|anthropic_responses)$")
    default_params: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.7,
        "max_tokens": 500,
    })


class OAuthAuthUrlResponse(BaseModel):
    auth_url: str
    state: str
    flow_type: str  # 'popup' | 'code_paste'


class OAuthExchangeRequest(BaseModel):
    """Claude code-paste exchange."""
    code: str = Field(..., min_length=1)
    state: str = Field(..., min_length=1)


class OAuthSessionTokenRequest(BaseModel):
    """Claude session cookie exchange."""
    session_cookie: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1, max_length=100)
    base_url: str = Field(default="https://api.anthropic.com/v1", max_length=500)
    model: Optional[str] = Field(None, max_length=100)
    api_format: str = Field(default="openai_chat", pattern=r"^(openai_chat|anthropic_responses)$")
    default_params: Dict[str, Any] = Field(default_factory=lambda: {
        "temperature": 0.7,
        "max_tokens": 500,
    })


class OAuthStatusResponse(BaseModel):
    config_id: int
    auth_method: str
    oauth_status: str  # 'active' | 'expiring' | 'expired' | 'no_token'
    expires_at: Optional[int] = None


class RAGConfigSave(BaseModel):
    """Request body to save RAG configuration."""
    provider: str = Field(..., pattern=r"^(dify)$")
    dify_base_url: str = Field(..., min_length=1, max_length=500)
    dify_api_key: Optional[str] = Field(None, max_length=500)
    dify_dataset_id: str = Field(..., min_length=1, max_length=200)
    top_k: int = Field(default=3, ge=1, le=20)


class RAGConfigResponse(BaseModel):
    """Response for RAG configuration (api_key masked)."""
    provider: Optional[str] = None
    dify_base_url: Optional[str] = None
    dify_api_key_masked: Optional[str] = None
    dify_dataset_id: Optional[str] = None
    top_k: int = 3
    source: str = "none"  # "database" | "env" | "none"


class RAGTestResponse(BaseModel):
    """Response for RAG connectivity test."""
    success: bool
    result_count: int = 0
    error: Optional[str] = None
