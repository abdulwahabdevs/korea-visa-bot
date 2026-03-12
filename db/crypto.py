"""
Lightweight Fernet encryption for student PII stored in SQLite.

The encryption key is derived from the SECRET_KEY environment variable.
If SECRET_KEY is not set, data is stored unencrypted with a warning
(acceptable for local dev; required for production).

Usage:
    from db.crypto import encrypt, decrypt
    stored  = encrypt("FA4166021")   # → base64 ciphertext string
    plain   = decrypt(stored)        # → "FA4166021"
"""

from __future__ import annotations
import base64
import hashlib
import logging
import os

logger = logging.getLogger(__name__)

_fernet = None


def _get_fernet():
    """Lazy-init Fernet instance from SECRET_KEY env var."""
    global _fernet
    if _fernet is not None:
        return _fernet

    try:
        from cryptography.fernet import Fernet
    except ImportError:
        logger.warning(
            "cryptography package not installed — PII stored unencrypted. "
            "Run: pip install cryptography"
        )
        return None

    secret = os.getenv("SECRET_KEY", "")
    if not secret:
        logger.warning(
            "SECRET_KEY env var not set — student PII will be stored unencrypted. "
            "Set SECRET_KEY to a secure random string in your .env file."
        )
        return None

    # Derive a 32-byte key from any-length SECRET_KEY via SHA-256 + base64
    key_bytes = hashlib.sha256(secret.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key_bytes)
    _fernet = Fernet(fernet_key)
    return _fernet


# Sentinel prefix so we can distinguish encrypted from plaintext legacy values
_ENC_PREFIX = "enc:"


def encrypt(plaintext: str) -> str:
    """Encrypt a string. Returns prefixed ciphertext, or plaintext if no key."""
    if not plaintext:
        return plaintext
    fernet = _get_fernet()
    if fernet is None:
        return plaintext   # fallback: unencrypted
    token = fernet.encrypt(plaintext.encode()).decode()
    return _ENC_PREFIX + token


def decrypt(value: str) -> str:
    """Decrypt a value produced by encrypt(). Handles legacy unencrypted values."""
    if not value:
        return value
    if not value.startswith(_ENC_PREFIX):
        return value   # legacy plaintext value — return as-is
    fernet = _get_fernet()
    if fernet is None:
        # Key disappeared after data was encrypted — cannot decrypt
        logger.error("SECRET_KEY not set but encrypted PII found in DB — cannot decrypt!")
        return ""
    try:
        return fernet.decrypt(value[len(_ENC_PREFIX):].encode()).decode()
    except Exception as exc:
        logger.error("Decryption failed: %s", exc)
        return ""
