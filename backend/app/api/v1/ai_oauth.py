"""
OAuth endpoints for AI provider authentication.

POST   /ai/oauth/{provider}/auth-url      - Generate OAuth URL + PKCE
GET    /ai/oauth/callback                  - Popup callback (OpenAI/Gemini)
POST   /ai/oauth/claude/exchange           - Claude code-paste exchange
POST   /ai/oauth/claude/session-token      - Claude session cookie exchange
GET    /ai/oauth/{config_id}/status        - Token status
"""
from __future__ import annotations

import html
import json
import logging
import secrets
import time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_super_admin
from app.config import settings
from app.models.admin import Admin
from app.models.ai_config import AiConfig
from app.oauth.base import OAuthTokens
from app.oauth.encryption import encrypt_oauth_data
from app.schemas.ai_config import (
    OAuthAuthUrlRequest,
    OAuthAuthUrlResponse,
    OAuthExchangeRequest,
    OAuthSessionTokenRequest,
    OAuthStatusResponse,
)
from app.schemas.common import APIResponse
from app.services.redis import get_redis

logger = logging.getLogger(__name__)

router = APIRouter()

# Provider registry
PROVIDER_MAP = {
    "openai_oauth": {
        "flow_type": "code_paste",
        "provider_value": "openai",
        "base_url_default": "https://api.openai.com/v1",
    },
    "claude_oauth": {
        "flow_type": "code_paste",
        "provider_value": "anthropic",
        "base_url_default": "https://api.anthropic.com/v1",
    },
    "claude_session": {
        "flow_type": "session_token",
        "provider_value": "anthropic",
        "base_url_default": "https://api.anthropic.com/v1",
    },
    "gemini_oauth": {
        "flow_type": "code_paste",
        "provider_value": "custom",
        "base_url_default": "https://generativelanguage.googleapis.com/v1beta",
    },
}


def _get_provider_instance(auth_method: str):
    """Instantiate the correct OAuth provider."""
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


def _get_redirect_uri() -> str:
    """Build the OAuth callback URL."""
    base = settings.PANEL_BASE_URL.rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PANEL_BASE_URL is not configured. Set it in .env.",
        )
    return f"{base}/api/v1/ai/oauth/callback"


def _tokens_to_oauth_data(tokens: OAuthTokens) -> dict:
    """Convert OAuthTokens to the dict stored in oauth_data column."""
    return encrypt_oauth_data({
        "access_token": tokens.access_token,
        "refresh_token": tokens.refresh_token,
        "expires_at": tokens.expires_at,
        "scopes": tokens.scopes,
        "provider_meta": tokens.provider_meta,
    })


async def _consume_oauth_state(redis, state: str) -> dict | None:
    """Atomically consume an OAuth state from Redis (get + delete).

    Returns the state data dict, or None if not found / already consumed.
    """
    pipe = redis.pipeline()
    pipe.get(f"oauth_state:{state}")
    pipe.delete(f"oauth_state:{state}")
    results = await pipe.execute()
    state_json = results[0]
    if not state_json:
        return None
    try:
        return json.loads(state_json)
    except (json.JSONDecodeError, TypeError):
        return None


def _validate_state_data(state_data: dict) -> tuple[str, dict, dict]:
    """Extract and validate required fields from state_data.

    Returns (auth_method, config_meta, pkce_params).
    Raises HTTPException on missing fields.
    """
    auth_method = state_data.get("auth_method")
    config_meta = state_data.get("config_meta")
    code_verifier = state_data.get("code_verifier")

    if not auth_method or not config_meta or not code_verifier:
        raise HTTPException(status_code=400, detail="Corrupt OAuth state data")

    return auth_method, config_meta, {"code_verifier": code_verifier}


async def _create_config_from_oauth(
    db: AsyncSession,
    tokens: OAuthTokens,
    auth_method: str,
    config_meta: dict,
) -> AiConfig:
    """Create an AiConfig record from OAuth tokens + metadata."""
    info = PROVIDER_MAP.get(auth_method, {})

    config = AiConfig(
        name=config_meta.get("name", f"{auth_method} config"),
        provider=config_meta.get("provider", info.get("provider_value", "custom")),
        base_url=config_meta.get("base_url") or info.get("base_url_default", ""),
        api_key=tokens.access_token,
        model=config_meta.get("model"),
        api_format=config_meta.get("api_format", "openai_chat"),
        default_params=config_meta.get("default_params", {"temperature": 0.7, "max_tokens": 500}),
        is_active=True,
        auth_method=auth_method,
        oauth_data=_tokens_to_oauth_data(tokens),
    )
    db.add(config)
    await db.flush()
    await db.refresh(config)
    return config


# ==================== Endpoints ====================


@router.post("/{auth_method}/auth-url", response_model=APIResponse)
async def generate_auth_url(
    auth_method: str,
    body: OAuthAuthUrlRequest,
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Generate OAuth authorization URL with PKCE parameters."""
    if auth_method not in PROVIDER_MAP:
        raise HTTPException(status_code=400, detail=f"Unknown auth method: {auth_method}")

    info = PROVIDER_MAP[auth_method]
    if info["flow_type"] == "session_token":
        raise HTTPException(status_code=400, detail="Session token flow does not use auth URL")

    provider = _get_provider_instance(auth_method)
    if not provider:
        raise HTTPException(status_code=400, detail=f"No provider for: {auth_method}")

    state = secrets.token_urlsafe(32)

    # All providers use their own fixed redirect_uri (localhost or provider page)
    # The redirect_uri param here is ignored by providers that have a fixed one
    auth_url, pkce_params = provider.generate_auth_url("", state)

    # Store state + PKCE + config metadata in Redis (TTL 10 min)
    redis = await get_redis()
    state_data = {
        "code_verifier": pkce_params["code_verifier"],
        "auth_method": auth_method,
        "config_meta": body.model_dump(),
    }
    await redis.setex(f"oauth_state:{state}", 600, json.dumps(state_data))

    return APIResponse(
        data=OAuthAuthUrlResponse(
            auth_url=auth_url,
            state=state,
            flow_type=info["flow_type"],
        ).model_dump()
    )


@router.get("/callback")
async def oauth_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
) -> HTMLResponse:
    """
    OAuth callback for popup flows (OpenAI/Gemini).
    This is a PUBLIC endpoint — no JWT required (called by OAuth provider redirect).
    Returns HTML that posts a message to the opener window and closes.
    """
    redis = await get_redis()
    state_data = await _consume_oauth_state(redis, state)
    if not state_data:
        return HTMLResponse(
            "<html><body><h2>OAuth Error</h2>"
            "<p>State expired or invalid. Please try again.</p>"
            "<script>setTimeout(()=>window.close(),3000)</script>"
            "</body></html>",
            status_code=400,
        )

    try:
        auth_method, config_meta, pkce_params = _validate_state_data(state_data)
    except HTTPException:
        return HTMLResponse(
            "<html><body><h2>OAuth Error</h2>"
            "<p>Invalid state data. Please try again.</p>"
            "<script>setTimeout(()=>window.close(),3000)</script>"
            "</body></html>",
            status_code=400,
        )

    try:
        provider = _get_provider_instance(auth_method)
        if not provider:
            raise ValueError(f"Unknown auth method: {auth_method}")
        redirect_uri = _get_redirect_uri()
        tokens = await provider.exchange_code(code, redirect_uri, pkce_params)
        config = await _create_config_from_oauth(db, tokens, auth_method, config_meta)
        await db.commit()

        return HTMLResponse(
            f"""<html><body>
            <h2>Authentication Successful</h2>
            <p>You can close this window.</p>
            <script>
                window.opener.postMessage({{
                    type: 'oauth-complete',
                    configId: {config.id}
                }}, '*');
                setTimeout(() => window.close(), 1000);
            </script>
            </body></html>"""
        )
    except Exception as exc:
        await db.rollback()
        logger.exception("OAuth callback failed for %s", auth_method)
        error_msg = html.escape(str(exc)[:200])
        error_json = json.dumps(str(exc)[:200])
        return HTMLResponse(
            f"""<html><body>
            <h2>Authentication Failed</h2>
            <p>{error_msg}</p>
            <script>
                window.opener.postMessage({{
                    type: 'oauth-error',
                    error: {error_json}
                }}, '*');
                setTimeout(() => window.close(), 5000);
            </script>
            </body></html>""",
            status_code=400,
        )


@router.post("/exchange", response_model=APIResponse)
async def exchange_code(
    body: OAuthExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Generic code exchange for all OAuth providers (code-paste flow).

    The 'code' field can be either:
    - A raw authorization code
    - A full callback URL containing ?code=...
    The backend will extract the code automatically.
    """
    import re as _re

    redis = await get_redis()
    state_data = await _consume_oauth_state(redis, body.state)
    if not state_data:
        raise HTTPException(status_code=400, detail="State expired or invalid")

    auth_method, config_meta, pkce_params = _validate_state_data(state_data)

    # Extract code from URL if user pasted the full callback URL
    code = body.code.strip()
    code_match = _re.search(r"[?&]code=([^&]+)", code)
    if code_match:
        code = code_match.group(1)

    try:
        provider = _get_provider_instance(auth_method)
        if not provider:
            raise ValueError(f"Unknown auth method: {auth_method}")
        tokens = await provider.exchange_code(code, "", pkce_params)
        config = await _create_config_from_oauth(db, tokens, auth_method, config_meta)

        from app.api.v1.ai_config import _config_to_response
        return APIResponse(
            code=201,
            message=f"{auth_method} config created",
            data=_config_to_response(config).model_dump(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Code exchange failed for %s", auth_method)
        raise HTTPException(status_code=400, detail=str(exc)[:500])


@router.post("/claude/exchange", response_model=APIResponse)
async def claude_exchange_code(
    body: OAuthExchangeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Exchange a manually-pasted Claude authorization code for tokens."""
    redis = await get_redis()
    state_data = await _consume_oauth_state(redis, body.state)
    if not state_data:
        raise HTTPException(status_code=400, detail="State expired or invalid")

    if state_data.get("auth_method") != "claude_oauth":
        raise HTTPException(status_code=400, detail="State does not match Claude OAuth flow")

    _, config_meta, pkce_params = _validate_state_data(state_data)

    try:
        from app.oauth.claude import ClaudeOAuth, REDIRECT_URI
        provider = ClaudeOAuth()
        tokens = await provider.exchange_code(body.code, REDIRECT_URI, pkce_params)
        config = await _create_config_from_oauth(db, tokens, "claude_oauth", config_meta)

        from app.api.v1.ai_config import _config_to_response
        return APIResponse(
            code=201,
            message="Claude OAuth config created",
            data=_config_to_response(config).model_dump(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Claude code exchange failed")
        raise HTTPException(status_code=400, detail=str(exc)[:500])


@router.post("/claude/session-token", response_model=APIResponse)
async def claude_session_token(
    body: OAuthSessionTokenRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Exchange a claude.ai session cookie for OAuth tokens."""
    try:
        from app.oauth.claude import ClaudeOAuth
        provider = ClaudeOAuth()
        tokens = await provider.exchange_session_token(body.session_cookie)

        config_meta = {
            "name": body.name,
            "provider": "anthropic",
            "base_url": body.base_url,
            "model": body.model,
            "api_format": body.api_format,
            "default_params": body.default_params,
        }
        config = await _create_config_from_oauth(db, tokens, "claude_session", config_meta)

        from app.api.v1.ai_config import _config_to_response
        return APIResponse(
            code=201,
            message="Claude session token config created",
            data=_config_to_response(config).model_dump(),
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Claude session token exchange failed")
        raise HTTPException(status_code=400, detail=str(exc)[:500])


@router.get("/{config_id}/status", response_model=APIResponse)
async def get_oauth_status(
    config_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[Admin, Depends(require_super_admin)],
) -> APIResponse:
    """Get OAuth token status for a config."""
    result = await db.execute(select(AiConfig).where(AiConfig.id == config_id))
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Config not found")

    auth_method = config.auth_method or "api_key"
    oauth_data = config.oauth_data

    if auth_method == "api_key":
        oauth_status = "no_token"
        expires_at = None
    elif not oauth_data:
        oauth_status = "no_token"
        expires_at = None
    else:
        expires_at = oauth_data.get("expires_at", 0)
        now = int(time.time())
        if not expires_at or expires_at < now:
            oauth_status = "expired"
        elif expires_at < now + 600:
            oauth_status = "expiring"
        else:
            oauth_status = "active"

    return APIResponse(
        data=OAuthStatusResponse(
            config_id=config_id,
            auth_method=auth_method,
            oauth_status=oauth_status,
            expires_at=expires_at,
        ).model_dump()
    )
