from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from app.plugins.exceptions import PluginSignatureError

logger = logging.getLogger("acp.plugins.signature_verifier")

MARKET_PUBLIC_KEY_ENV = "ACP_MARKET_PUBLIC_KEY"


class BundleSignatureVerifier:
    """Verify Ed25519 signatures and SHA-256 hashes of plugin bundles.

    If no public key is configured (via ACP_MARKET_PUBLIC_KEY env var),
    verification is skipped with a warning (dev mode).
    """

    def __init__(self) -> None:
        self._public_key: Ed25519PublicKey | None = None
        self._load_public_key()

    def _load_public_key(self) -> None:
        """Load the marketplace Ed25519 public key from env var."""
        pem_data = os.environ.get(MARKET_PUBLIC_KEY_ENV)
        if not pem_data:
            logger.warning(
                "No %s env var set — signature verification disabled (dev mode)",
                MARKET_PUBLIC_KEY_ENV,
            )
            return

        try:
            key = load_pem_public_key(pem_data.encode())
            if not isinstance(key, Ed25519PublicKey):
                raise PluginSignatureError(
                    f"{MARKET_PUBLIC_KEY_ENV} is not an Ed25519 public key"
                )
            self._public_key = key
        except Exception as exc:
            raise PluginSignatureError(
                f"Failed to load public key from {MARKET_PUBLIC_KEY_ENV}: {exc}"
            ) from exc

    def verify(self, zip_path: Path, sig_path: Path) -> bool:
        """Verify the Ed25519 signature of a plugin bundle.

        Returns True if verification succeeds or is skipped (dev mode).
        Raises PluginSignatureError on verification failure.
        """
        if self._public_key is None:
            logger.warning(
                "Skipping signature verification for %s (no public key)",
                zip_path.name,
            )
            return True

        bundle_data = zip_path.read_bytes()
        signature = sig_path.read_bytes()

        try:
            self._public_key.verify(signature, bundle_data)
            logger.info("Signature verified for %s", zip_path.name)
            return True
        except InvalidSignature as exc:
            raise PluginSignatureError(
                f"Invalid signature for bundle {zip_path.name}"
            ) from exc

    def verify_hash(self, zip_path: Path, expected_hash: str) -> bool:
        """Verify the SHA-256 hash of a plugin bundle.

        Returns True if the hash matches.
        Raises PluginSignatureError if it does not.
        """
        actual_hash = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        if actual_hash != expected_hash:
            raise PluginSignatureError(
                f"SHA-256 mismatch for {zip_path.name}: "
                f"expected {expected_hash}, got {actual_hash}"
            )
        logger.info("SHA-256 hash verified for %s", zip_path.name)
        return True
