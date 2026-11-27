"""
Private loopback bridge pairing and local authentication token shared by the
desktop daemon, FastAPI backend, and frontend.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
import secrets
import subprocess

logger = logging.getLogger("hinaa.auth.token")


def _resolve_default_token_path() -> Path:
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "HINA" / "token"
    return Path.home() / ".hina" / "token"


TOKEN_PATH = _resolve_default_token_path()


def set_restricted_permissions(file_path: Path) -> None:
    """Restricts file permissions strictly to the current user."""
    try:
        if os.name == "nt":
            username = os.environ.get("USERNAME") or ""
            if not username:
                try:
                    username = os.getlogin()
                except Exception:
                    username = ""
            if username:
                # /inheritance:r removes inherited ACLs; /grant:r grants read/write to current user only
                subprocess.run(
                    ["icacls", str(file_path), "/inheritance:r", "/grant:r", f"{username}:(R,W)"],
                    capture_output=True,
                    check=False,
                )
        else:
            file_path.chmod(0o600)
    except Exception as exc:
        logger.warning(f"Could not set strict file permissions on {file_path}: {exc}")


def get_hina_token(*, create: bool = True) -> str:
    """
    Retrieve or generate the single shared local authentication token.
    Precedence:
    1. Environment variable HINA_TOKEN or HINAA_DESKTOP_BRIDGE_TOKEN
    2. File at TOKEN_PATH (%LOCALAPPDATA%\\HINA\\token)
    3. Generate new 32-byte URL-safe token if create=True.
    """
    token = (os.getenv("HINA_TOKEN") or os.getenv("HINAA_DESKTOP_BRIDGE_TOKEN") or "").strip()
    if token:
        if len(token) < 32:
            raise ValueError("Authentication token must contain at least 32 characters")
        return token

    try:
        if TOKEN_PATH.exists():
            content = TOKEN_PATH.read_text(encoding="utf-8").strip()
            if content:
                return content
    except OSError:
        pass

    if not create:
        return ""

    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    new_token = secrets.token_urlsafe(32)
    try:
        with TOKEN_PATH.open("w", encoding="utf-8") as file:
            file.write(new_token)
        set_restricted_permissions(TOKEN_PATH)
    except OSError as err:
        if TOKEN_PATH.exists():
            return TOKEN_PATH.read_text(encoding="utf-8").strip()
        raise err

    return new_token


def bridge_token(*, create: bool = False) -> str:
    """Backwards-compatible bridge token accessor."""
    return get_hina_token(create=create)


def verify_hina_token(provided_token: str | None, expected_token: str | None = None) -> bool:
    """Verifies a token in constant time using secrets.compare_digest."""
    if not provided_token:
        return False
    target = expected_token or get_hina_token(create=True)
    if not target:
        return False
    return secrets.compare_digest(provided_token.strip(), target.strip())


def authorized(authorization: str | None, token: str) -> bool:
    """
    Backwards-compatible authorization checker. Supports either
    'Bearer <token>' or raw token comparison.
    """
    if not token or not authorization:
        return False
    clean_auth = authorization.strip()
    if clean_auth.startswith("Bearer "):
        clean_auth = clean_auth[7:].strip()
    return secrets.compare_digest(clean_auth, token.strip())
