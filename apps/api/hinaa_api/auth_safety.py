"""Public, value-free report of the settings that decide whether private data is safe.

The readiness route is public, so this reports only booleans and the names of
missing settings. It never returns a key, an owner ID, or an origin.
"""
from __future__ import annotations

from typing import Any


def auth_safety_report(settings: Any) -> dict[str, Any]:
    """Booleans an operator needs to confirm the owner gate is actually closed."""
    secret = getattr(settings, "clerk_secret_key", None)
    secret_set = bool(secret and secret.get_secret_value().strip())
    jwt_key_set = bool(str(getattr(settings, "clerk_jwt_key", "") or "").strip())
    owner_set = bool(str(getattr(settings, "hinaa_allowed_user_ids", "") or "").strip())
    tunnel_dev_off = not bool(getattr(settings, "allow_tunnel_dev_auth", False))
    clerk_ready = secret_set or jwt_key_set
    closed = (
        getattr(settings, "auth_mode", "dev") == "clerk"
        and clerk_ready
        and owner_set
        and tunnel_dev_off
    )
    missing = [
        name
        for name, present in (
            ("CLERK_SECRET_KEY or CLERK_JWT_KEY", clerk_ready),
            ("HINAA_ALLOWED_USER_IDS", owner_set),
        )
        if not present
    ]
    return {
        "ownerGateClosed": closed,
        "clerkVerifierConfigured": clerk_ready,
        "ownerAllowlistConfigured": owner_set,
        "tunnelDevAuthOff": tunnel_dev_off,
        "missing": missing,
    }
