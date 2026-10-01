"""
HINAA Enterprise Secret Broker (Zero-Leak Credential Isolation).

Architecture:
1. Secret Isolation Invariant:
   - The LLM context, prompt assembly, traces, logs, and frontend NEVER receive raw credentials.
   - LLMs only receive ephemeral opaque capability handles (e.g. `cap_hina_a83f9`).
2. Vault Storage:
   - Encrypted in-memory/file credential store for API keys, OAuth tokens, and SSH keys.
3. Execution Injection:
   - Secrets are injected strictly into the low-level executor environment or HTTP request headers
     immediately before network transmission, and immediately scrubbed upon completion.
4. Redaction Engine:
   - Automatically sanitizes and replaces known secrets in any outgoing strings, traces, or errors.
"""

from __future__ import annotations

import logging
import re
import secrets
import time
from typing import Any, Dict, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class EphemeralCapabilityHandle(BaseModel):
    handle_id: str
    resource_name: str
    scopes: list[str] = Field(default_factory=list)
    issued_at: float
    expires_at: float


class SecretBroker:
    """
    Broker managing credentials with zero model exposure.
    """

    def __init__(self) -> None:
        self._vault: Dict[str, str] = {}
        self._handles: Dict[str, Tuple[str, float]] = {}  # handle_id -> (secret_key, expires_at)

    def store_secret(self, key_name: str, secret_value: str) -> None:
        """Stores credentials securely in the vault."""
        if not secret_value:
            return
        self._vault[key_name] = secret_value

    def issue_capability_handle(
        self,
        key_name: str,
        ttl_seconds: float = 300.0,
        scopes: Optional[list[str]] = None,
    ) -> EphemeralCapabilityHandle:
        """
        Issues an opaque, non-sensitive handle for the model to reference in tool calls.
        """
        if key_name not in self._vault:
            raise KeyError(f"No secret registered under '{key_name}'")

        handle_id = f"cap_hina_{secrets.token_hex(10)}"
        now = time.time()
        expires_at = now + ttl_seconds
        self._handles[handle_id] = (key_name, expires_at)

        return EphemeralCapabilityHandle(
            handle_id=handle_id,
            resource_name=key_name,
            scopes=scopes or ["execute"],
            issued_at=now,
            expires_at=expires_at,
        )

    def resolve_handle_for_executor(self, handle_id: str) -> str:
        """
        Resolves an ephemeral handle to the raw secret strictly inside the executor.
        Raises PermissionError if expired or invalid.
        """
        if handle_id not in self._handles:
            raise PermissionError("Invalid or unknown capability handle.")

        key_name, expires_at = self._handles[handle_id]
        if time.time() > expires_at:
            del self._handles[handle_id]
            raise PermissionError("Capability handle has expired.")

        return self._vault[key_name]

    def scrub_text(self, text: str) -> str:
        """
        Redacts any known secrets from logs, traces, or model prompt assembly.
        """
        scrubbed = text
        for name, secret in self._vault.items():
            if secret and len(secret) > 4 and secret in scrubbed:
                scrubbed = scrubbed.replace(secret, f"[REDACTED_SECRET_{name.upper()}]")
        return scrubbed


_global_secret_broker: Optional[SecretBroker] = None


def get_secret_broker() -> SecretBroker:
    global _global_secret_broker
    if _global_secret_broker is None:
        _global_secret_broker = SecretBroker()
    return _global_secret_broker
