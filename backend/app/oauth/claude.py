"""
Claude (Anthropic) OAuth 2.0 + PKCE provider.

Two flows supported:
1. Code-paste: Claude redirects to its own page showing the code.
   User manually copies and pastes it into our panel.
2. Session token: User pastes claude.ai session cookie,
   backend automatically exchanges it for OAuth tokens.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import base64
import logging
import re

import httpx

from app.oauth.base import OAuthProvider, OAuthTokens

logger = logging.getLogger(__name__)

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
# Claude's fixed redirect — it shows the code on its own page
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"
SCOPES = "user:profile user:inference"

COMMON_HEADERS = {
    "User-Agent": "claude-cli/2.1.22",
    "anthropic-beta": "oauth-2025-04-20",
}


def _pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256)."""
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


class ClaudeOAuth(OAuthProvider):
    """Claude OAuth with code-paste flow."""

    def generate_auth_url(self, redirect_uri: str, state: str) -> tuple[str, dict]:
        # Claude always uses its fixed redirect_uri
        code_verifier, code_challenge = _pkce_pair()

        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": SCOPES,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
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
        async with httpx.AsyncClient(timeout=30, headers=COMMON_HEADERS) as client:
            resp = await client.post(
                TOKEN_URL,
                json={
                    "grant_type": "authorization_code",
                    "client_id": CLIENT_ID,
                    "code": code,
                    "redirect_uri": REDIRECT_URI,
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
        async with httpx.AsyncClient(timeout=30, headers=COMMON_HEADERS) as client:
            resp = await client.post(
                TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
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

    async def exchange_session_token(self, session_cookie: str) -> OAuthTokens:
        """
        Exchange a claude.ai sessionKey cookie for OAuth tokens.

        Flow:
        1. Use the cookie to GET the user's organization UUID
        2. Generate PKCE params
        3. Automatically obtain authorization code (no user interaction)
        4. Exchange code for tokens
        """
        headers = {
            **COMMON_HEADERS,
            "Cookie": f"sessionKey={session_cookie}"
            if not session_cookie.startswith("sessionKey=")
            else session_cookie,
        }

        async with httpx.AsyncClient(
            timeout=30, headers=headers, follow_redirects=True
        ) as client:
            # Step 1: Get organization info
            org_resp = await client.get(
                "https://claude.ai/api/organizations",
            )
            org_resp.raise_for_status()
            orgs = org_resp.json()
            if not orgs:
                raise ValueError("No organizations found for this session")
            org_uuid = orgs[0].get("uuid", orgs[0].get("id", ""))

            # Step 2: PKCE
            code_verifier, code_challenge = _pkce_pair()

            # Step 3: Authorize (auto-approve since we have a valid session)
            auth_params = {
                "client_id": CLIENT_ID,
                "redirect_uri": REDIRECT_URI,
                "response_type": "code",
                "scope": SCOPES,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
                "state": secrets.token_urlsafe(16),
            }
            auth_resp = await client.get(
                AUTH_URL,
                params=auth_params,
            )

            # The redirect URL should contain the code
            final_url = str(auth_resp.url)
            code_match = re.search(r"[?&]code=([^&]+)", final_url)

            if not code_match:
                # Try to find code in response body
                body = auth_resp.text
                code_match = re.search(r'"code"\s*:\s*"([^"]+)"', body)

            if not code_match:
                raise ValueError(
                    "Failed to obtain authorization code from session token. "
                    "The session may be expired or invalid."
                )

            code = code_match.group(1)

        # Step 4: Exchange code
        return await self.exchange_code(
            code=code,
            redirect_uri=REDIRECT_URI,
            pkce_params={"code_verifier": code_verifier},
        )
