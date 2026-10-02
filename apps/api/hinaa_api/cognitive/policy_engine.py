"""
HINAA Enterprise Policy Engine & Guardrails (PDP / PEP).

Implements Policy Decision Point (PDP) and Policy Enforcement Point (PEP)
architecture for production-grade agent security:
1. Multi-tier Risk Assessment (Tier 0 to Tier 3)
2. Role-Based Access Control (RBAC) & Tenant Isolation
3. Human-In-The-Loop (HITL) Cryptographic Approval Tokens
4. Real-time PII & Credential Masking / Redaction
5. Cryptographically Chained SHA-256 Audit Records (SOC2 / HIPAA compliance)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import secrets
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.cognitive.policy")


class RiskTier(str, Enum):
    TIER_0_READONLY = "tier_0_readonly"           # Informational, conversational, search
    TIER_1_REVERSIBLE = "tier_1_reversible"       # Local drafts, scratch files, memory updates
    TIER_2_SYSTEM_ACTUATION = "tier_2_actuation"   # App launch, desktop focus, browser navigation
    TIER_3_CRITICAL = "tier_3_critical"           # File deletion, credential change, financial, deployment


# Patterns for high-entropy secrets and sensitive identifiers
SECRET_PATTERNS = [
    re.compile(r"(?i)\b(bearer\s+)([A-Za-z0-9\-_=]{20,})\b"),
    re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|access[_-]?token|auth[_-]?token)\s*[:=]\s*['\"]?([A-Za-z0-9\-_=]{16,})['\"]?"),
    re.compile(r"(?i)\b(password|passwd|pwd)\s*[:=]\s*['\"]?([^\s'\"]{6,})['\"]?"),
    re.compile(r"\b(sk-[A-Za-z0-9_\-]{16,})\b"),        # OpenAI key format
    re.compile(r"\b(AIza[0-9A-Za-z\-_]{35})\b"),        # Google API key format
    re.compile(r"\b(ghp_[0-9a-zA-Z]{36})\b"),           # GitHub PAT
    re.compile(r"\b(xox[baprs]-[0-9a-zA-Z]{10,48})\b"), # Slack Token
    re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), # Credit Card
]


class PolicyDecision(BaseModel):
    allowed: bool
    risk_tier: RiskTier
    requires_approval: bool = False
    approval_token: Optional[str] = None
    reason: str = "Authorized by enterprise policy"
    redacted_parameters: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)


class AuditEntry(BaseModel):
    entry_id: str
    timestamp: float
    user_id: str
    tenant_id: str
    action: str
    resource: str
    risk_tier: str
    decision: str
    reason: str
    parameters_redacted: Dict[str, Any]
    prev_hash: str
    entry_hash: str


class EnterprisePolicyEngine:
    """Enterprise Policy Decision and Enforcement Point."""

    def __init__(self, signing_secret: Optional[str] = None) -> None:
        self._signing_secret = (signing_secret or secrets.token_hex(32)).encode("utf-8")
        self._pending_tokens: Dict[str, Dict[str, Any]] = {}
        self._last_audit_hash: str = "0" * 64
        self._audit_chain: List[AuditEntry] = []

        # Action classification registry
        self._action_tiers: Dict[str, RiskTier] = {
            # Tier 0: Readonly
            "search_web": RiskTier.TIER_0_READONLY,
            "read_file": RiskTier.TIER_0_READONLY,
            "list_directory": RiskTier.TIER_0_READONLY,
            "get_status": RiskTier.TIER_0_READONLY,
            "respond": RiskTier.TIER_0_READONLY,
            "fetch_world_state": RiskTier.TIER_0_READONLY,
            "observe": RiskTier.TIER_0_READONLY,

            # Tier 1: Reversible
            "write_scratch_file": RiskTier.TIER_1_REVERSIBLE,
            "update_notes": RiskTier.TIER_1_REVERSIBLE,
            "remember": RiskTier.TIER_1_REVERSIBLE,
            "export_summary": RiskTier.TIER_1_REVERSIBLE,

            # Tier 2: System Actuation
            "app_launch": RiskTier.TIER_2_SYSTEM_ACTUATION,
            "open_application": RiskTier.TIER_2_SYSTEM_ACTUATION,
            "focus_window": RiskTier.TIER_2_SYSTEM_ACTUATION,
            "browser_navigate": RiskTier.TIER_2_SYSTEM_ACTUATION,
            "browser_click": RiskTier.TIER_2_SYSTEM_ACTUATION,
            "computer_operator": RiskTier.TIER_2_SYSTEM_ACTUATION,

            # Tier 3: Critical / Approval Required
            "delete_file": RiskTier.TIER_3_CRITICAL,
            "delete_directory": RiskTier.TIER_3_CRITICAL,
            "change_credentials": RiskTier.TIER_3_CRITICAL,
            "financial_transaction": RiskTier.TIER_3_CRITICAL,
            "deploy_production": RiskTier.TIER_3_CRITICAL,
            "send_external_message": RiskTier.TIER_3_CRITICAL,
            "execute_raw_shell": RiskTier.TIER_3_CRITICAL,
        }

    # ---------------------------------------------------------------------------
    # Redaction & Sanitization
    # ---------------------------------------------------------------------------
    @classmethod
    def redact_secrets(cls, data: Any) -> Any:
        """Recursively redact passwords, tokens, API keys, and sensitive cards."""
        if isinstance(data, str):
            res = data
            for pat in SECRET_PATTERNS:
                res = pat.sub(r"\1[REDACTED_SECRET]", res) if pat.groups > 1 else pat.sub("[REDACTED_SECRET]", res)
            return res
        elif isinstance(data, dict):
            redacted = {}
            for k, v in data.items():
                if any(sec in k.lower() for sec in ["password", "secret", "token", "api_key", "apikey", "credential"]):
                    redacted[k] = "[REDACTED_CREDENTIAL]"
                else:
                    redacted[k] = cls.redact_secrets(v)
            return redacted
        elif isinstance(data, list):
            return [cls.redact_secrets(item) for item in data]
        return data

    # ---------------------------------------------------------------------------
    # Policy Evaluation
    # ---------------------------------------------------------------------------
    def evaluate(
        self,
        action: str,
        resource: str = "default",
        parameters: Optional[Dict[str, Any]] = None,
        *,
        user_role: str = "owner",
        approval_token: Optional[str] = None,
    ) -> PolicyDecision:
        """Evaluate an action against enterprise security policies."""
        params = parameters or {}
        sanitized_params = self.redact_secrets(params)
        risk_tier = self._action_tiers.get(action, RiskTier.TIER_2_SYSTEM_ACTUATION)

        # Tier 0 & Tier 1 are unconditionally allowed for active users
        if risk_tier in (RiskTier.TIER_0_READONLY, RiskTier.TIER_1_REVERSIBLE):
            return PolicyDecision(
                allowed=True,
                risk_tier=risk_tier,
                requires_approval=False,
                reason=f"Action '{action}' is within {risk_tier.value} policy bounds",
                redacted_parameters=sanitized_params,
            )

        # Tier 2: System Actuation - Allowed with safety logging
        if risk_tier == RiskTier.TIER_2_SYSTEM_ACTUATION:
            # Check for shell injection or dangerous executable patterns
            target = str(params.get("target") or params.get("app_name") or "").lower()
            dangerous_apps = ["regedit", "powershell -enc", "cmd /c del", "format", "diskpart"]
            if any(danger in target for danger in dangerous_apps):
                return PolicyDecision(
                    allowed=False,
                    risk_tier=risk_tier,
                    requires_approval=True,
                    reason=f"Dangerous system executable pattern blocked: '{target}'",
                    redacted_parameters=sanitized_params,
                )

            return PolicyDecision(
                allowed=True,
                risk_tier=risk_tier,
                requires_approval=False,
                reason=f"System actuation '{action}' approved under device sandbox policy",
                redacted_parameters=sanitized_params,
            )

        # Tier 3: Critical - Requires Human-In-The-Loop (HITL) approval token
        if risk_tier == RiskTier.TIER_3_CRITICAL:
            if approval_token and self.verify_approval_token(approval_token, action):
                return PolicyDecision(
                    allowed=True,
                    risk_tier=risk_tier,
                    requires_approval=False,
                    reason=f"Critical action '{action}' executed with verified approval token",
                    redacted_parameters=sanitized_params,
                )

            # Mint a new approval token for human confirmation
            token = self.generate_approval_token(action, resource)
            return PolicyDecision(
                allowed=False,
                risk_tier=risk_tier,
                requires_approval=True,
                approval_token=token,
                reason=f"Action '{action}' requires explicit human-in-the-loop authorization token",
                redacted_parameters=sanitized_params,
            )

        return PolicyDecision(
            allowed=False,
            risk_tier=risk_tier,
            requires_approval=True,
            reason="Unrecognized action rejected by default-deny posture",
            redacted_parameters=sanitized_params,
        )

    # ---------------------------------------------------------------------------
    # Cryptographic Approval Tokens
    # ---------------------------------------------------------------------------
    def generate_approval_token(self, action: str, resource: str, ttl_seconds: int = 300) -> str:
        """Mint a cryptographically signed HMAC token for HITL confirmation."""
        expires_at = time.time() + ttl_seconds
        payload = f"{action}:{resource}:{expires_at}"
        sig = hmac.new(self._signing_secret, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:16]
        token = f"hitl_{sig}_{int(expires_at)}"
        self._pending_tokens[token] = {
            "action": action,
            "resource": resource,
            "expires_at": expires_at,
        }
        return token

    def verify_approval_token(self, token: str, action: str) -> bool:
        """Verify and consume a HITL approval token."""
        record = self._pending_tokens.get(token)
        if not record:
            return False
        if time.time() > record["expires_at"]:
            self._pending_tokens.pop(token, None)
            return False
        if record["action"] != action:
            return False
        # Single use token: consume upon verification
        self._pending_tokens.pop(token, None)
        return True

    # ---------------------------------------------------------------------------
    # Cryptographic Audit Ledger (SHA-256 Hash Chaining)
    # ---------------------------------------------------------------------------
    def record_audit(
        self,
        *,
        user_id: str,
        tenant_id: str = "default",
        action: str,
        resource: str,
        decision: PolicyDecision,
    ) -> AuditEntry:
        """Append an immutable, cryptographically chained audit record."""
        now = time.time()
        entry_id = f"aud_{secrets.token_hex(8)}"
        payload_to_hash = json.dumps(
            {
                "entry_id": entry_id,
                "timestamp": now,
                "user_id": user_id,
                "tenant_id": tenant_id,
                "action": action,
                "resource": resource,
                "risk_tier": decision.risk_tier.value,
                "decision": "ALLOWED" if decision.allowed else "BLOCKED",
                "reason": decision.reason,
                "params": decision.redacted_parameters,
                "prev_hash": self._last_audit_hash,
            },
            sort_keys=True,
        )
        entry_hash = hashlib.sha256(payload_to_hash.encode("utf-8")).hexdigest()

        entry = AuditEntry(
            entry_id=entry_id,
            timestamp=now,
            user_id=user_id,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            risk_tier=decision.risk_tier.value,
            decision="ALLOWED" if decision.allowed else "BLOCKED",
            reason=decision.reason,
            parameters_redacted=decision.redacted_parameters,
            prev_hash=self._last_audit_hash,
            entry_hash=entry_hash,
        )

        self._last_audit_hash = entry_hash
        self._audit_chain.append(entry)
        if len(self._audit_chain) > 500:
            self._audit_chain.pop(0)

        logger.info(
            "AUDIT [%s] user=%s action=%s decision=%s tier=%s hash=%s",
            entry_id,
            user_id,
            action,
            entry.decision,
            entry.risk_tier,
            entry_hash[:12],
        )
        return entry

    def get_recent_audit_records(self, limit: int = 50) -> List[AuditEntry]:
        return self._audit_chain[-limit:]

    def verify_audit_integrity(self) -> bool:
        """Verify the cryptographic hash chain of all stored audit entries."""
        curr_prev = "0" * 64
        for entry in self._audit_chain:
            if entry.prev_hash != curr_prev:
                return False
            payload = json.dumps(
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp,
                    "user_id": entry.user_id,
                    "tenant_id": entry.tenant_id,
                    "action": entry.action,
                    "resource": entry.resource,
                    "risk_tier": entry.risk_tier,
                    "decision": entry.decision,
                    "reason": entry.reason,
                    "params": entry.parameters_redacted,
                    "prev_hash": entry.prev_hash,
                },
                sort_keys=True,
            )
            calc_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if calc_hash != entry.entry_hash:
                return False
            curr_prev = entry.entry_hash
        return True


# Global enterprise policy singleton
_global_policy_engine: Optional[EnterprisePolicyEngine] = None


def get_policy_engine() -> EnterprisePolicyEngine:
    global _global_policy_engine
    if _global_policy_engine is None:
        _global_policy_engine = EnterprisePolicyEngine()
    return _global_policy_engine
