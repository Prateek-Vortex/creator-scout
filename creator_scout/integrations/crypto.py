from __future__ import annotations

import os

from cryptography.fernet import Fernet, InvalidToken


_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is not None:
        return _fernet
    key = os.environ.get("OAUTH_TOKEN_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "OAUTH_TOKEN_ENCRYPTION_KEY is not set — required to store OAuth tokens"
        )
    try:
        _fernet = Fernet(key.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise RuntimeError(
            "OAUTH_TOKEN_ENCRYPTION_KEY is not a valid Fernet key (32-byte url-safe base64)"
        ) from exc
    return _fernet


def encrypt(plaintext: str) -> str:
    return _get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt(ciphertext: str) -> str:
    try:
        return _get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Stored OAuth token could not be decrypted") from exc
