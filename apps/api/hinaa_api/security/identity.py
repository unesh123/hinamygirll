"""
HINAA OS — Phase 15 Identity & Authentication Context Provider
Resolves verified server-side identities, generates signed session tokens,
and strips spoofed client headers (X-Tenant-Id, X-User-Role) to guarantee tenant isolation.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from typing import Any, Dict, List, Optional, Set

from fastapi import Header, HTTPException, Request, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from hinaa_api.security.contracts import SecurityRole, SecuritySubject
from hinaa_api.security.secrets import get_keystore_manager

logger = logging.getLogger(__name__)

security_bearer = HTTPBearer(auto_error=False)


class IdentityProvider:
    """
    Issues and cryptographically validates user and service identity sessions.
    Rejects spoofed client headers.
    """

    def __init__(self, signing_key: Optional[bytes] = None) -> None:
        self.keystore = get_keystore_manager()
        self.signing_key = signing_key or self.keystore.get_signing_key("identity_signing_key")

    def create_token(
        self,
        user_id: str,
        tenant_id: str,
        role: SecurityRole,
        scopes: Optional[Set[str]] = None,
        ttl_seconds: float = 3600.0,
    ) -> str:
        now = time.time()
        payload = {
            "sub": user_id,
            "tid": tenant_id,
            "role": role.value,
            "scopes": list(scopes) if scopes else [],
            "iat": round(now, 2),
            "exp": round(now + ttl_seconds, 2),
            "jti": secrets.token_hex(8),
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(self.signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        raw = f"{canonical}.{sig}"
        import base64
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")

    def parse_token(self, token_str: str) -> SecuritySubject:
        import base64
        try:
            raw = base64.urlsafe_b64decode(token_str.encode("utf-8")).decode("utf-8")
            parts = raw.rsplit(".", 1)
            if len(parts) != 2:
                raise ValueError("Malformed token format.")
            canonical, sig = parts[0], parts[1]

            # Signature check
            expected_sig = hmac.new(self.signing_key, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(expected_sig, sig):
                raise ValueError("Invalid token signature.")

            payload = json.loads(canonical)
            now = time.time()
            if now > payload.get("exp", 0):
                raise ValueError("Token expired.")

            role_val = payload.get("role", "viewer")
            try:
                role = SecurityRole(role_val)
            except ValueError:
                role = SecurityRole.VIEWER

            return SecuritySubject(
                user_id=payload["sub"],
                tenant_id=payload["tid"],
                role=role,
                scopes=set(payload.get("scopes", [])),
                session_id=payload.get("jti"),
                created_at=payload.get("iat", now),
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired authentication credentials: {e}",
            )


_global_identity_provider: Optional[IdentityProvider] = None


def get_identity_provider(signing_key: Optional[bytes] = None) -> IdentityProvider:
    global _global_identity_provider
    if signing_key is not None:
        return IdentityProvider(signing_key)
    if _global_identity_provider is None:
        _global_identity_provider = IdentityProvider()
    return _global_identity_provider


async def get_current_subject(
    request: Request,
    bearer: Optional[HTTPAuthorizationCredentials] = Security(security_bearer),
) -> SecuritySubject:
    """
    FastAPI dependency to extract verified subject.
    Rejects spoofed X-Tenant-Id or X-User-Role headers.
    """
    idp = get_identity_provider()

    # If bearer token provided, parse it
    if bearer and bearer.credentials:
        subject = idp.parse_token(bearer.credentials)
        return subject

    # Allow local development default subject if configured, otherwise require auth
    # For testing and local loopback with dev session
    dev_auth = request.headers.get("Authorization")
    if dev_auth and dev_auth.startswith("Bearer "):
        token = dev_auth.split("Bearer ", 1)[1].strip()
        return idp.parse_token(token)

    # In local development mode without token, check if dev fallback allowed
    # Otherwise raise 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please provide a valid Bearer token.",
    )
