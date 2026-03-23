"""
Abstract base class for OAuth providers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class OAuthTokens:
    """Token set returned after a successful OAuth exchange."""
    access_token: str
    refresh_token: str
    expires_at: int  # unix timestamp
    token_type: str = "bearer"
    scopes: str = ""
    provider_meta: dict = field(default_factory=dict)


class OAuthProvider(ABC):
    """Base class all OAuth providers must implement."""

    @abstractmethod
    def generate_auth_url(self, redirect_uri: str, state: str) -> tuple[str, dict]:
        """
        Generate an authorization URL for the user.

        Returns:
            (auth_url, pkce_params) where pkce_params contains code_verifier etc.
        """
        ...

    @abstractmethod
    async def exchange_code(
        self, code: str, redirect_uri: str, pkce_params: dict
    ) -> OAuthTokens:
        """Exchange an authorization code for tokens."""
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> OAuthTokens:
        """Refresh an expired access token."""
        ...
