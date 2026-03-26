"""
OpenAI OAuth 2.0 + PKCE provider.

Uses code-paste flow: the Codex CLI client ID only allows localhost redirect.
User authenticates in a popup, gets redirected to localhost (which won't load),
then copies the full URL from the address bar and pastes it into the panel.
The backend extracts the code from the URL and exchanges it for tokens.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import base64
import logging
from urllib.parse import quote

import httpx

from app.oauth.base import OAuthProvider, OAuthTokens

logger = logging.getLogger(__name__)

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTH_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
REDIRECT_URI = "http://localhost:1455/auth/callback"
SCOPES = "openid profile email offline_access"
# Refresh scope — no offline_access (aligned with Codex CLI / CRS behavior)
REFRESH_SCOPES = "openid profile email"

TOKEN_HEADERS = {
    "User-Agent": "codex-cli/0.91.0",
}


def _pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256).

    OpenAI / Codex CLI uses hex-encoded verifier.
    """
    verifier = secrets.token_bytes(64).hex()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


class OpenAIOAuth(OAuthProvider):
    """OpenAI OAuth 2.0 with PKCE (S256)."""

    def generate_auth_url(self, redirect_uri: str, state: str) -> tuple[str, dict]:
        # OpenAI Codex client only allows localhost redirect
        code_verifier, code_challenge = _pkce_pair()

        params = {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
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
        async with httpx.AsyncClient(timeout=30, headers=TOKEN_HEADERS) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
                    "code_verifier": pkce_params["code_verifier"],
                },
            )
            if resp.status_code != 200:
                logger.error(
                    "OpenAI token exchange failed: status=%d body=%s",
                    resp.status_code,
                    resp.text[:500],
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
        async with httpx.AsyncClient(timeout=30, headers=TOKEN_HEADERS) as client:
            resp = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                    "refresh_token": refresh_token,
                    "scope": REFRESH_SCOPES,
                },
            )
            if resp.status_code != 200:
                logger.error(
                    "OpenAI token refresh failed: status=%d body=%s",
                    resp.status_code,
                    resp.text[:500],
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
