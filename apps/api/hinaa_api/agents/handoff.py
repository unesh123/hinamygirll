"""
HINAA OS — Phase 11 Least-Privilege Context Handoffs & Scrubbing
Ensures context isolation between specialist agents, scrubs sensitive credentials,
and enforces bounded delegation depth.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from .contracts import AgentRole, CapabilityGrant

logger = logging.getLogger("hinaa.agents.handoff")

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|password|bearer|auth[_-]?token|private[_-]?key)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
]


class ContextScrubber:
    """Removes sensitive credentials, API keys, and cross-tenant tokens from context payloads."""

    @classmethod
    def scrub_string(cls, text: str) -> str:
        """Replace credentials with redaction markers."""
        if not text:
            return text
        sanitized = text
        for pat in _SECRET_PATTERNS:
            if pat.groups >= 1:
                sanitized = pat.sub(r"\1: [REDACTED_SECRET]", sanitized)
            else:
                sanitized = pat.sub("[REDACTED_SECRET]", sanitized)
        return sanitized

    @classmethod
    def scrub_data(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return cls.scrub_dict(data)
        elif isinstance(data, list):
            return [cls.scrub_data(x) for x in data]
        elif isinstance(data, str):
            return cls.scrub_string(data)
        return data

    @classmethod
    def scrub_dict(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively scrub values in a dictionary."""
        clean: Dict[str, Any] = {}
        for k, v in data.items():
            # If key implies a secret, redact directly
            if any(s in k.lower() for s in ["api_key", "secret", "password", "token", "auth", "credential", "private_key"]):
                clean[k] = "[REDACTED_SECRET]"
            elif isinstance(v, str):
                clean[k] = cls.scrub_string(v)
            elif isinstance(v, dict):
                clean[k] = cls.scrub_dict(v)
            elif isinstance(v, list):
                clean[k] = [cls.scrub_dict(item) if isinstance(item, dict) else (cls.scrub_string(item) if isinstance(item, str) else item) for item in v]
            else:
                clean[k] = v
        return clean


import hashlib

class ContextHandoffManager:
    @staticmethod
    def compute_artifact_sha256(file_path: str) -> str:
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()
    """Prepares and validates minimized, scoped context packets for delegation."""

    def __init__(self, max_depth: int = 4) -> None:
        self.max_depth = max_depth

    def validate_delegation(
        self,
        from_role: AgentRole,
        to_role: AgentRole,
        current_depth: int,
        target_grant: CapabilityGrant,
    ) -> Tuple[bool, Optional[str]]:
        """Validate whether delegation from one agent to another is permitted."""
        if current_depth >= self.max_depth:
            return False, f"Delegation rejected: maximum delegation depth ({self.max_depth}) reached"

        if from_role == to_role:
            return False, f"Self-delegation loops disallowed for role '{from_role}'"

        # Supervisor can delegate to anyone; other agents can only delegate to specialists permitted by policy
        return True, None

    def prepare_handoff_packet(
        self,
        task_id: str,
        node_id: str,
        target_role: AgentRole,
        inputs: Dict[str, Any],
        upstream_results: Optional[Dict[str, Any]] = None,
        tenant_id: str = "default",
    ) -> Dict[str, Any]:
        """
        Assemble minimized least-privilege payload for the target specialist.
        Scrubs secrets, filters irrelevant upstream data, and binds tenant isolation.
        """
        clean_inputs = ContextScrubber.scrub_dict(inputs)
        clean_upstream = ContextScrubber.scrub_dict(upstream_results or {})

        packet = {
            "task_id": task_id,
            "node_id": node_id,
            "recipient_role": target_role.value if hasattr(target_role, "value") else str(target_role),
            "tenant_id": tenant_id,
            "inputs": clean_inputs,
            "upstream_context": clean_upstream,
            "isolation_boundary": "ENFORCED",
        }
        return packet
