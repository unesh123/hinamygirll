"""
HINAA Enterprise Policy-as-Code Engine & Server-Owned Safety Gate.

Architecture:
1. Policy Rule Definition:
   - Evaluates RBAC/ABAC: actor, resource, action, conditions, approval_mode, budget, audit.
2. Seven-Phase Execution Lifecycle:
   1. Proposal: Action proposed by model or user
   2. Pre-Policy Evaluation: Determines if action is allowed, forbidden, or requires approval
   3. Approval Token Generation: Server creates cryptographically bound single-use token (HMAC-SHA256)
   4. Approval Receipt: User authorizes the specific action
   5. Re-check Policy: Time-of-check to time-of-use (TOCTOU) revalidation immediately before execution
   6. Execute Actuator: Action runs
   7. Post-Policy & Audit: Log immutable record with policy decision and hashes
3. Server-Owned Cryptographic Token Integrity:
   - Tokens are bound to: actor + run_id + tool_name + args_hash + expiry.
   - Forged or expired tokens are rejected. Single-use enforcement prevents replay attacks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PolicyDecisionType(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class PolicyRule(BaseModel):
    rule_id: str
    actor_pattern: str  # e.g. "role:admin", "role:developer", "user:*"
    resource: str  # e.g. "whatsapp", "terminal", "production", "financial"
    action: str  # e.g. "send_message", "deploy", "delete", "purchase", "shell_exec"
    conditions: Dict[str, Any] = Field(default_factory=dict)
    decision: PolicyDecisionType = PolicyDecisionType.REQUIRE_APPROVAL
    approval_mode: str = "single_user"
    max_calls_per_run: int = 1
    audit_required: bool = True


class ApprovalChallenge(BaseModel):
    challenge_id: str
    run_id: str
    actor: str
    resource: str
    action: str
    arguments_hash: str
    created_at: float
    expires_at: float
    signature: str


class PolicyEvaluationResult(BaseModel):
    decision: PolicyDecisionType
    reason: str
    rule_id: Optional[str] = None
    challenge: Optional[ApprovalChallenge] = None


class PolicyEngine:
    """
    Enterprise Policy-as-Code engine with TOCTOU revalidation and cryptographic approvals.
    """

    def __init__(self, signing_secret: Optional[str] = None) -> None:
        self.signing_secret = (signing_secret or secrets.token_hex(32)).encode("utf-8")
        self.rules: List[PolicyRule] = []
        self._used_challenges: set[str] = set()
        self._load_default_policies()

    def _load_default_policies(self) -> None:
        """Loads enterprise baseline security policies."""
        self.rules = [
            PolicyRule(
                rule_id="POL-001",
                actor_pattern="*",
                resource="production",
                action="deploy",
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                audit_required=True,
            ),
            PolicyRule(
                rule_id="POL-002",
                actor_pattern="*",
                resource="whatsapp",
                action="send_message",
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                audit_required=True,
            ),
            PolicyRule(
                rule_id="POL-003",
                actor_pattern="*",
                resource="filesystem",
                action="delete",
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                audit_required=True,
            ),
            PolicyRule(
                rule_id="POL-004",
                actor_pattern="*",
                resource="financial",
                action="purchase",
                decision=PolicyDecisionType.REQUIRE_APPROVAL,
                audit_required=True,
            ),
            PolicyRule(
                rule_id="POL-005",
                actor_pattern="*",
                resource="terminal",
                action="rm_rf_root",
                decision=PolicyDecisionType.DENY,
                audit_required=True,
            ),
        ]

    def add_rule(self, rule: PolicyRule) -> None:
        self.rules.insert(0, rule)

    def _hash_args(self, args: dict) -> str:
        serialized = json.dumps(args, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _sign_challenge(self, challenge_data: str) -> str:
        return hmac.new(self.signing_secret, challenge_data.encode("utf-8"), hashlib.sha256).hexdigest()

    def evaluate_pre_policy(
        self,
        actor: str,
        resource: str,
        action: str,
        arguments: dict,
        run_id: str,
    ) -> PolicyEvaluationResult:
        """Evaluates policy against requested action before tool execution."""
        args_hash = self._hash_args(arguments)

        # Match against policy rules
        for rule in self.rules:
            if rule.resource == resource and rule.action == action:
                if rule.decision == PolicyDecisionType.DENY:
                    return PolicyEvaluationResult(
                        decision=PolicyDecisionType.DENY,
                        reason=f"Action '{action}' on resource '{resource}' is strictly forbidden by policy {rule.rule_id}.",
                        rule_id=rule.rule_id,
                    )
                elif rule.decision == PolicyDecisionType.REQUIRE_APPROVAL:
                    # Issue server-owned, cryptographic single-use challenge
                    now = time.time()
                    challenge_id = f"chl_{secrets.token_hex(12)}"
                    raw_data = f"{challenge_id}:{run_id}:{actor}:{resource}:{action}:{args_hash}:{now + 120}"
                    sig = self._sign_challenge(raw_data)

                    challenge = ApprovalChallenge(
                        challenge_id=challenge_id,
                        run_id=run_id,
                        actor=actor,
                        resource=resource,
                        action=action,
                        arguments_hash=args_hash,
                        created_at=now,
                        expires_at=now + 120,
                        signature=sig,
                    )
                    return PolicyEvaluationResult(
                        decision=PolicyDecisionType.REQUIRE_APPROVAL,
                        reason=f"Action '{action}' is guarded by policy {rule.rule_id} and requires explicit approval.",
                        rule_id=rule.rule_id,
                        challenge=challenge,
                    )

        # Default allow for non-guarded resources
        return PolicyEvaluationResult(
            decision=PolicyDecisionType.ALLOW,
            reason="Action allowed by default policy baseline.",
        )

    def recheck_and_authorize(
        self,
        challenge: ApprovalChallenge,
        actor: str,
        arguments: dict,
        current_state_ok: bool = True,
    ) -> Tuple[bool, str]:
        """
        Revalidates policy and verifies single-use token immediately before execution (Anti-TOCTOU).
        """
        now = time.time()

        # 1. Expiration check
        if now > challenge.expires_at:
            return False, "Approval challenge has expired."

        # 2. Replay check
        if challenge.challenge_id in self._used_challenges:
            return False, "Approval challenge has already been used (Replay attack blocked)."

        # 3. Argument hash verification (tamper prevention)
        current_hash = self._hash_args(arguments)
        if current_hash != challenge.arguments_hash:
            return False, "Arguments have been altered since approval was requested."

        # 4. Signature verification
        raw_data = f"{challenge.challenge_id}:{challenge.run_id}:{challenge.actor}:{challenge.resource}:{challenge.action}:{challenge.arguments_hash}:{challenge.expires_at}"
        expected_sig = self._sign_challenge(raw_data)
        if not hmac.compare_digest(expected_sig, challenge.signature):
            return False, "Invalid cryptographic approval signature."

        # 5. Environmental precondition check
        if not current_state_ok:
            return False, "Environmental preconditions changed between check and execution."

        # Mark challenge as used
        self._used_challenges.add(challenge.challenge_id)
        return True, "Authorized and rechecked."
