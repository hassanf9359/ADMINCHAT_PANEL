from __future__ import annotations

import base64
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

    Public key sources (in priority order):
    1. ACP_MARKET_PUBLIC_KEY environment variable
    2. Runtime key set via set_public_key_pem() (fetched from Market)

    If no public key is available, verification is skipped with a warning (dev mode).
    """

    def __init__(self) -> None:
        self._public_key: Ed25519PublicKey | None = None
        self._load_public_key()

    def _load_public_key(self) -> None:
        """Load the marketplace Ed25519 public key from env var."""
        pem_data = os.environ.get(MARKET_PUBLIC_KEY_ENV)
        if not pem_data:
            logger.warning(
                "No %s env var set — signature verification disabled until "
                "Market public key is fetched or env var is configured",
                MARKET_PUBLIC_KEY_ENV,
            )
            return

        self._set_key_from_pem(pem_data, source=MARKET_PUBLIC_KEY_ENV, strict=True)

    def _set_key_from_pem(self, pem_data: str, source: str = "unknown", strict: bool = False) -> None:
        """Parse a PEM string and set it as the public key.

        Args:
            strict: If True, raise on failure instead of logging. Used when
                    the key comes from an explicit config (env var).
        """
        try:
            key = load_pem_public_key(pem_data.encode())
            if not isinstance(key, Ed25519PublicKey):
                raise PluginSignatureError(
                    f"Key from {source} is not an Ed25519 public key"
                )
            self._public_key = key
            logger.info("Ed25519 public key loaded from %s", source)
        except PluginSignatureError:
            raise
        except Exception as exc:
            if strict:
                raise PluginSignatureError(
                    f"Failed to load public key from {source}: {exc}"
                ) from exc
            logger.error("Failed to load public key from %s: %s", source, exc)

    def set_public_key_pem(self, pem: str) -> None:
        """Set the public key at runtime (e.g., fetched from Market API).

        Does NOT override an existing env-var-configured key.
        """
        if os.environ.get(MARKET_PUBLIC_KEY_ENV):
            logger.debug("Ignoring runtime key — env var %s takes priority", MARKET_PUBLIC_KEY_ENV)
            return
        self._set_key_from_pem(pem, source="Market API")

    @property
    def has_key(self) -> bool:
        """Check whether a public key is loaded."""
        return self._public_key is not None

    def verify(self, zip_path: Path, sig_path: Path) -> bool:
        """Verify the Ed25519 signature of a plugin bundle.

        The sig_path file should contain raw signature bytes.

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

    def verify_base64(self, zip_path: Path, signature_b64: str) -> bool:
        """Verify an Ed25519 signature given as a base64 string.

        Used when the signature comes from Market API (e.g., X-Bundle-Signature header).
        """
        if self._public_key is None:
            logger.warning(
                "Skipping signature verification for %s (no public key)",
                zip_path.name,
            )
            return True

        bundle_data = zip_path.read_bytes()
        try:
            signature = base64.b64decode(signature_b64)
        except Exception as exc:
            raise PluginSignatureError(
                f"Invalid base64 signature for {zip_path.name}"
            ) from exc

        try:
            self._public_key.verify(signature, bundle_data)
            logger.info("Signature verified for %s (base64)", zip_path.name)
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
