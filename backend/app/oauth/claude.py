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
from urllib.parse import quote

import httpx

from app.oauth.base import OAuthProvider, OAuthTokens

logger = logging.getLogger(__name__)

CLIENT_ID = "9d1c250a-e61b-44d9-88ed-5944d1962f5e"
AUTH_URL = "https://claude.ai/oauth/authorize"
TOKEN_URL = "https://platform.claude.com/v1/oauth/token"
# Claude's fixed redirect — it shows the code on its own page
REDIRECT_URI = "https://platform.claude.com/oauth/code/callback"

# Scopes — browser (code-paste) flow includes org:create_api_key
SCOPES_BROWSER = "org:create_api_key user:profile user:inference user:sessions:claude_code user:mcp_servers"
# Scopes — internal API call (org:create_api_key not supported in API)
SCOPES_API = "user:profile user:inference user:sessions:claude_code user:mcp_servers"

# Token exchange headers — no anthropic-beta (deprecated)
TOKEN_HEADERS = {
    "User-Agent": "axios/1.13.6",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
}

# Code verifier charset (RFC 7636 compliant)
_CODE_VERIFIER_CHARSET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


def _pkce_pair() -> tuple[str, str]:
    """Generate PKCE code_verifier and code_challenge (S256).

    Uses RFC 7636 compliant character set method matching Claude CLI behavior.
    """
    # Generate 32 random characters from the charset
    charset = _CODE_VERIFIER_CHARSET
    charset_len = len(charset)
    limit = 256 - (256 % charset_len)

    raw = bytearray()
    while len(raw) < 32:
        rand_bytes = secrets.token_bytes(64)
        for b in rand_bytes:
            if b < limit:
                raw.append(charset[b % charset_len].encode()[0])
                if len(raw) >= 32:
                    break

    verifier = base64.urlsafe_b64encode(bytes(raw)).rstrip(b"=").decode()

    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def _split_code(code: str) -> tuple[str, str]:
    """Split authorization code that may contain state in 'authCode#state' format."""
    if "#" in code:
        parts = code.split("#", 1)
        return parts[0], parts[1]
    return code, ""


class ClaudeOAuth(OAuthProvider):
    """Claude OAuth with code-paste flow."""

    def generate_auth_url(self, redirect_uri: str, state: str) -> tuple[str, dict]:
        # Claude always uses its fixed redirect_uri
        code_verifier, code_challenge = _pkce_pair()

        # Build URL with code=true parameter (required for code-paste flow)
        encoded_redirect = quote(REDIRECT_URI, safe="")
        encoded_scope = quote(SCOPES_BROWSER, safe="").replace("%20", "+")

        auth_url = (
            f"{AUTH_URL}"
            f"?code=true"
            f"&client_id={CLIENT_ID}"
            f"&response_type=code"
            f"&redirect_uri={encoded_redirect}"
            f"&scope={encoded_scope}"
            f"&code_challenge={code_challenge}"
            f"&code_challenge_method=S256"
            f"&state={state}"
        )

        pkce_params = {"code_verifier": code_verifier}
        return auth_url, pkce_params

    async def exchange_code(
        self, code: str, redirect_uri: str, pkce_params: dict
    ) -> OAuthTokens:
        # Code may contain state appended as 'authCode#state'
        auth_code, code_state = _split_code(code.strip())

        body: dict = {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": auth_code,
            "redirect_uri": REDIRECT_URI,
            "code_verifier": pkce_params["code_verifier"],
        }
        if code_state:
            body["state"] = code_state

        async with httpx.AsyncClient(timeout=30, headers=TOKEN_HEADERS) as client:
            resp = await client.post(TOKEN_URL, json=body)
            if resp.status_code != 200:
                logger.error(
                    "Claude token exchange failed: status=%d body=%s",
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
            scopes=SCOPES_API,
        )

    async def refresh_token(self, refresh_token: str) -> OAuthTokens:
        async with httpx.AsyncClient(timeout=30, headers=TOKEN_HEADERS) as client:
            resp = await client.post(
                TOKEN_URL,
                json={
                    "grant_type": "refresh_token",
                    "client_id": CLIENT_ID,
                    "refresh_token": refresh_token,
                },
            )
            if resp.status_code != 200:
                logger.error(
                    "Claude token refresh failed: status=%d body=%s",
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
            scopes=SCOPES_API,
        )

    async def exchange_session_token(self, session_cookie: str) -> OAuthTokens:
        """
        Exchange a claude.ai sessionKey cookie for OAuth tokens.

        Flow:
        1. Use the cookie to GET the user's organization UUID
        2. Generate PKCE params
        3. Automatically obtain authorization code via API (no user interaction)
        4. Exchange code for tokens
        """
        cookie_header = (
            f"sessionKey={session_cookie}"
            if not session_cookie.startswith("sessionKey=")
            else session_cookie
        )
        session_headers = {
            "Cookie": cookie_header,
        }

        async with httpx.AsyncClient(
            timeout=30, headers=session_headers, follow_redirects=True
        ) as client:
            # Step 1: Get organization info
            org_resp = await client.get(
                "https://claude.ai/api/organizations",
            )
            org_resp.raise_for_status()
            orgs = org_resp.json()
            if not orgs:
                raise ValueError("No organizations found for this session")

            # Prefer team org if available
            org_uuid = orgs[0].get("uuid", orgs[0].get("id", ""))
            if len(orgs) > 1:
                for org in orgs:
                    if org.get("raven_type") == "team":
                        org_uuid = org["uuid"]
                        break

            # Step 2: PKCE
            code_verifier, code_challenge = _pkce_pair()
            state = secrets.token_urlsafe(16)

            # Step 3: Authorize via API (POST, not GET)
            auth_url = f"https://claude.ai/v1/oauth/{org_uuid}/authorize"
            auth_body = {
                "response_type": "code",
                "client_id": CLIENT_ID,
                "organization_uuid": org_uuid,
                "redirect_uri": REDIRECT_URI,
                "scope": SCOPES_API,
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }

            auth_resp = await client.post(
                auth_url,
                json=auth_body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "Origin": "https://claude.ai",
                    "Referer": "https://claude.ai/new",
                },
            )
            auth_resp.raise_for_status()
            auth_data = auth_resp.json()

            # Extract code from redirect_uri in response
            redirect_uri_str = auth_data.get("redirect_uri", "")
            if not redirect_uri_str:
                raise ValueError("No redirect_uri in authorization response")

            from urllib.parse import urlparse, parse_qs

            parsed = urlparse(redirect_uri_str)
            qs = parse_qs(parsed.query)
            auth_code = qs.get("code", [""])[0]
            response_state = qs.get("state", [""])[0]

            if not auth_code:
                raise ValueError("No authorization code in redirect_uri")

            # Combine code with state if present
            full_code = auth_code
            if response_state:
                full_code = f"{auth_code}#{response_state}"

        # Step 4: Exchange code
        return await self.exchange_code(
            code=full_code,
            redirect_uri=REDIRECT_URI,
            pkce_params={"code_verifier": code_verifier},
        )
