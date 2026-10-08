"""Private loopback bridge pairing shared by the desktop daemon and API."""
from __future__ import annotations
import os
from pathlib import Path
import secrets

TOKEN_PATH = Path(__file__).resolve().parents[4] / ".runtime" / "desktop" / "bridge.token"

def bridge_token(*, create: bool = False) -> str:
    token = os.getenv("HINAA_DESKTOP_BRIDGE_TOKEN", "").strip()
    if token:
        if len(token) < 32:
            raise ValueError("HINAA_DESKTOP_BRIDGE_TOKEN must contain at least 32 characters")
        return token
    try:
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        if not create:
            return ""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(48)
    try:
        with TOKEN_PATH.open("x", encoding="utf-8") as file:
            file.write(token)
        if os.name != "nt":
            TOKEN_PATH.chmod(0o600)
    except FileExistsError:
        return TOKEN_PATH.read_text(encoding="utf-8").strip()
    return token

def authorized(authorization: str | None, token: str) -> bool:
    return bool(token and authorization and secrets.compare_digest(authorization, "Bearer " + token))
