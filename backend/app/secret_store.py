"""Small encrypted-at-rest helper for runtime secrets.

The project stores runtime provider credentials in the management database.
Values written through the settings APIs are wrapped with AES-GCM authenticated
encryption, while legacy plaintext and v1 values remain readable for compatibility.

For production deployments, set SECRET_ENCRYPTION_KEY to a stable high-entropy
value and rotate it with an operational migration plan.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

from .config import settings

_PREFIX = "enc:v2:"
_LEGACY_PREFIX = "enc:v1:"
_API_KEY_HASH_PREFIX = "hash:v1:"
_SALT_LEN = 16
_NONCE_LEN = 12
_LEGACY_NONCE_LEN = 16
_TAG_LEN = 16
_PBKDF2_ROUNDS = 200_000


def is_encrypted_secret(value: str | None) -> bool:
    """Return True when value uses the local encrypted secret envelope."""

    return bool(value and (value.startswith(_PREFIX) or value.startswith(_LEGACY_PREFIX)))


def encrypt_secret(value: str | None) -> str | None:
    """Encrypt a non-empty secret value; leave empty and already encrypted values as-is."""

    if value is None:
        return None
    if value == "" or is_encrypted_secret(value):
        return value

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = secrets.token_bytes(_SALT_LEN)
    nonce = secrets.token_bytes(_NONCE_LEN)
    key = _derive_key(salt)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), b"secret-store-v2")
    payload = salt + nonce + ciphertext
    encoded = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    return f"{_PREFIX}{encoded}"


def decrypt_secret(value: str | None) -> str:
    """Decrypt an encrypted secret; return legacy plaintext unchanged."""

    if not value:
        return ""
    if not is_encrypted_secret(value):
        return value

    if value.startswith(_LEGACY_PREFIX):
        return _decrypt_legacy_secret(value)

    token = value[len(_PREFIX):]
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii"))
        if len(payload) <= _SALT_LEN + _NONCE_LEN:
            return ""
        salt = payload[:_SALT_LEN]
        nonce = payload[_SALT_LEN:_SALT_LEN + _NONCE_LEN]
        ciphertext = payload[_SALT_LEN + _NONCE_LEN:]
        key = _derive_key(salt)
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        return AESGCM(key).decrypt(nonce, ciphertext, b"secret-store-v2").decode("utf-8")
    except Exception:
        return ""


def hash_api_key(value: str) -> str:
    """Create a non-reversible HMAC hash for API keys."""

    key = _api_hash_key()
    digest = hmac.new(key, value.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{_API_KEY_HASH_PREFIX}{digest}"


def is_hashed_api_key(value: str | None) -> bool:
    return bool(value and value.startswith(_API_KEY_HASH_PREFIX))


def verify_api_key_hash(candidate: str, stored_value: str) -> bool:
    """Verify a presented API key against hashed or legacy plaintext storage."""

    if is_hashed_api_key(stored_value):
        return hmac.compare_digest(hash_api_key(candidate), stored_value)
    return hmac.compare_digest(candidate, stored_value)


def _derive_key(salt: bytes) -> bytes:
    material = (settings.SECRET_ENCRYPTION_KEY or settings.JWT_SECRET_KEY).encode("utf-8")
    return hashlib.pbkdf2_hmac("sha256", material, salt, _PBKDF2_ROUNDS, dklen=32)


def _api_hash_key() -> bytes:
    return hashlib.sha256(
        f"api-key-hash:{settings.SECRET_ENCRYPTION_KEY or settings.JWT_SECRET_KEY}".encode("utf-8")
    ).digest()


def _decrypt_legacy_secret(value: str) -> str:
    token = value[len(_LEGACY_PREFIX):]
    try:
        padded = token + "=" * (-len(token) % 4)
        payload = base64.urlsafe_b64decode(padded.encode("ascii"))
        if len(payload) <= _SALT_LEN + _LEGACY_NONCE_LEN + _TAG_LEN:
            return ""
        salt = payload[:_SALT_LEN]
        nonce = payload[_SALT_LEN:_SALT_LEN + _LEGACY_NONCE_LEN]
        tag = payload[_SALT_LEN + _LEGACY_NONCE_LEN:_SALT_LEN + _LEGACY_NONCE_LEN + _TAG_LEN]
        ciphertext = payload[_SALT_LEN + _LEGACY_NONCE_LEN + _TAG_LEN:]
        key = _derive_key(salt)
        expected = hmac.new(key, b"secret-store-v1" + nonce + ciphertext, hashlib.sha256).digest()[:_TAG_LEN]
        if not hmac.compare_digest(tag, expected):
            return ""
        return _legacy_xor_stream(ciphertext, key, nonce).decode("utf-8")
    except Exception:
        return ""


def _legacy_xor_stream(data: bytes, key: bytes, nonce: bytes) -> bytes:
    out = bytearray()
    counter = 0
    while len(out) < len(data):
        block = hmac.new(key, nonce + counter.to_bytes(8, "big"), hashlib.sha256).digest()
        out.extend(block)
        counter += 1
    return bytes(a ^ b for a, b in zip(data, out))
