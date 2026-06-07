"""Symmetric encryption for channel credentials at rest.

WhatsApp access tokens are stored in ``tenant_whatsapp_credentials.access_token_enc``
(a ``BYTEA`` column). We encrypt them with Fernet (AES-128-CBC + HMAC) so a
database dump never exposes a usable token.

The Fernet key is *derived* from ``WHATSAPP_APP_SECRET`` (SHA-256 → 32 bytes →
url-safe base64) rather than introducing yet another secret to manage. The
practical consequence: set ``WHATSAPP_APP_SECRET`` **before** connecting a
tenant's WhatsApp number, and treat rotating it as invalidating stored tokens
(reconnect the channel afterwards).
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from .config import get_settings


@lru_cache(maxsize=1)
def _fernet():
    from cryptography.fernet import Fernet

    secret = (get_settings().whatsapp_app_secret or "dev-insecure-fallback-key")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def encrypt_token(plaintext: str) -> bytes:
    """Encrypt a token for storage in a BYTEA column."""
    return _fernet().encrypt(plaintext.encode("utf-8"))


def decrypt_token(blob) -> str:
    """Decrypt a token read back from BYTEA (bytes or memoryview)."""
    return _fernet().decrypt(bytes(blob)).decode("utf-8")
