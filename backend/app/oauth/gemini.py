"""
Google / Gemini OAuth 2.0 + PKCE provider.

Uses popup-based flow similar to OpenAI.
Requires GEMINI_OAUTH_CLIENT_ID and GEMINI_OAUTH_CLIENT_SECRET in .env.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import base64
import logging

import httpx

from app.config import settings
from app.oauth.base import OAuthProvider, OAuthTokens

logger = logging.getLogger(__name__)

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPES = "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/generative-language.retriever"


def _client_id() -> str:
    return settings.GEMINI_OAUTH_CLIENT_ID


def _client_secret() -> str:
    return settings.GEMINI_OAUTH_CLIENT_SECRET


class GeminiOAuth(OAuthProvider):
    """Google OAuth 2.0 with PKCE for Gemini API access."""

    def generate_auth_url(self, redirect_uri: str, state: str) -> tuple[str, dict]:
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = (
            base64.urlsafe_b64encode(
                hashlib.sha256(code_verifier.encode()).digest()
            )
            .rstrip(b"=")
            .decode()
        )

        params = {
            "client_id": _client_id(),
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
        }
        qs = "&".join(
            f"{k}={httpx.URL('', params={k: v}).params[k]}" for k, v in params.items()
        )
        auth_url = f"{AUTH_URL}?{qs}"

        pkce_params = {"code_verifier": code_verifier}
        return auth_url, pkce_params

    async def exchange_code(
        self, code: str, redirect_uri: str, pkce_params: dict
    ) -> OAuthTokens:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": pkce_params["code_verifier"],
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", ""),
            expires_at=int(time.time()) + data.get("expires_in", 3600),
            token_type=data.get("token_type", "bearer"),
            scopes=SCOPES,
        )

    async def refresh_token(self, refresh_token: str) -> OAuthTokens:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": _client_id(),
                    "client_secret": _client_secret(),
                    "refresh_token": refresh_token,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        return OAuthTokens(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token", refresh_token),
            expires_at=int(time.time()) + data.get("expires_in", 3600),
            token_type=data.get("token_type", "bearer"),
            scopes=SCOPES,
        )
