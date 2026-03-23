"""
Fernet encryption for OAuth token data.

Only encrypts access_token and refresh_token fields;
expires_at stays plaintext for efficient scheduled queries.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from cryptography.fernet import Fernet

from app.config import settings

logger = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet

    key = settings.OAUTH_ENCRYPTION_KEY
    if not key:
        key = Fernet.generate_key().decode()
        logger.warning(
            "OAUTH_ENCRYPTION_KEY is empty — auto-generated a key for this session. "
            "Set OAUTH_ENCRYPTION_KEY in .env for persistence across restarts. "
            "Key: %s",
            key,
        )
        settings.OAUTH_ENCRYPTION_KEY = key

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_oauth_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Encrypt access_token and refresh_token fields in oauth_data dict."""
    if not data:
        return data
    f = _get_fernet()
    result = dict(data)
    for field in ("access_token", "refresh_token"):
        if field in result and result[field]:
            result[field] = f.encrypt(result[field].encode()).decode()
    return result


def decrypt_oauth_data(data: Dict[str, Any]) -> Dict[str, Any]:
    """Decrypt access_token and refresh_token fields in oauth_data dict."""
    if not data:
        return data
    f = _get_fernet()
    result = dict(data)
    for field in ("access_token", "refresh_token"):
        if field in result and result[field]:
            try:
                result[field] = f.decrypt(result[field].encode()).decode()
            except Exception:
                logger.error(
                    "Failed to decrypt %s — OAUTH_ENCRYPTION_KEY may have changed",
                    field,
                )
                raise ValueError(
                    f"Cannot decrypt {field}. Check OAUTH_ENCRYPTION_KEY."
                )
    return result
