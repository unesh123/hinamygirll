"""At-rest encryption for OAuth tokens (Fernet / AES-128-CBC + HMAC).

The repo had no encrypt-at-rest helper (security/secrets.py only scrubs and
probes keystores), so this is the first. Key order:
  1. HINAA_SOCIAL_TOKEN_KEY (any string; stretched with SHA-256 to a Fernet key)
  2. a generated key file at .runtime/social/token.key (mode 0600), created on first use.
Losing the key makes stored tokens unreadable; the user simply reconnects.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from ..config import Settings, get_settings
from ..runtime_paths import runtime_dir


def _key_bytes(settings: Settings) -> bytes:
    configured = (
        settings.social_token_key.get_secret_value().strip() if settings.social_token_key else ""
    )
    if configured:
        return base64.urlsafe_b64encode(hashlib.sha256(configured.encode()).digest())
    path = runtime_dir("social", "token.key")
    if path.is_file():
        return path.read_bytes().strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as handle:
        handle.write(key)
    return key


def _fernet(settings: Settings | None) -> Fernet:
    return Fernet(_key_bytes(settings or get_settings()))


def encrypt_json(settings: Settings | None, payload: dict[str, Any]) -> str:
    return _fernet(settings).encrypt(json.dumps(payload).encode()).decode()


def decrypt_json(settings: Settings | None, ciphertext: str) -> dict[str, Any]:
    try:
        return json.loads(_fernet(settings).decrypt(ciphertext.encode()))
    except InvalidToken as error:
        raise ValueError(
            "Stored credentials cannot be decrypted; reconnect the account."
        ) from error


def signing_key(settings: Settings | None) -> bytes:
    """Key for OAuth `state` signatures, derived so it never equals the encryption key."""
    return hashlib.sha256(b"oauth-state|" + _key_bytes(settings or get_settings())).digest()
