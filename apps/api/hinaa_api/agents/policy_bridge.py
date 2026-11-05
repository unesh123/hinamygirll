"""
HINAA OS — Phase 11 & Phase 12 Universal Policy Bridge & Approval Gate
Bridges to Phase 07 and 08 security policies, enforces multi-tenant boundaries,
and verifies HMAC-SHA256 one-time-use action approval tokens with complete ancestry binding.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    ApprovalRecord,
    PermissionTier,
    _digest_dict,
    _now_iso,
)

logger = logging.getLogger("hinaa.agents.policy_bridge")

_APPROVAL_SECRET = os.getenv("HINAA_APPROVAL_SECRET", "hinaa_secure_approval_secret_2026")


class PolicyBridge:
    """Enforces authorization tiers, HMAC approval validation, ancestry binding, and tenant isolation."""

    def __init__(self) -> None:
        self._approvals: Dict[str, ApprovalRecord] = {}
        self._emergency_stop: bool = False

    def trigger_emergency_stop(self) -> None:
        """Trigger emergency kill-switch; immediately blocks all running and queued actions."""
        self._emergency_stop = True
        logger.critical("EMERGENCY STOP TRIGGERED: All agent execution suspended.")

    def resume_from_emergency_stop(self) -> None:
        """Clear emergency stop after audit sign-off."""
        self._emergency_stop = False
        logger.info("Emergency stop cleared. Resuming standard governance.")

    def is_stopped(self) -> bool:
        return self._emergency_stop

    def create_approval_request(
        self,
        tenant_id: str,
        user_id: str,
        task_id: str,
        node_id: str,
        action: str,
        arguments: dict[str, Any],
        amount_paisa: int = 0,
        currency: str = "NPR",
        ttl_seconds: int = 600,
        team_id: Optional[str] = None,
        ancestry: Optional[List[str]] = None,
    ) -> ApprovalRecord:
        """Generate a cryptographically signed approval record bound to exact action, arguments, and optional ancestry."""
        arg_digest = _digest_dict(arguments)
        now_ts = time.time()
        expires_at = datetime.fromtimestamp(now_ts + ttl_seconds, tz=timezone.utc).isoformat()
        nonce = uuid.uuid4().hex

        ancestry_list = ancestry or []
        team_str = team_id or ""
        if ancestry_list or team_str:
            ancestry_str = ":".join(ancestry_list)
            raw_msg = f"{ancestry_str}:{tenant_id}:{user_id}:{team_str}:{node_id}:{action}:{arg_digest}:{amount_paisa}:{nonce}:{expires_at}"
        else:
            raw_msg = f"{tenant_id}:{user_id}:{task_id}:{node_id}:{action}:{arg_digest}:{amount_paisa}:{nonce}:{expires_at}"

        sig = hmac.new(_APPROVAL_SECRET.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256).hexdigest()

        rec = ApprovalRecord(
            tenant_id=tenant_id,
            user_id=user_id,
            task_id=task_id,
            node_id=node_id,
            action=action,
            argument_digest=arg_digest,
            amount_paisa=amount_paisa,
            currency=currency,
            nonce=nonce,
            expires_at=expires_at,
            approved=False,
            used=False,
            signature=sig,
            team_id=team_id,
            ancestry=ancestry_list,
        )
        self._approvals[rec.approval_id] = rec
        return rec

    def verify_and_consume_approval(
        self,
        approval_id: str,
        tenant_id: str,
        action: str,
        arguments: dict[str, Any],
        amount_paisa: int = 0,
        team_id: Optional[str] = None,
        ancestry: Optional[List[str]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Verify token integrity, single-use nonce, ancestry binding, and exact argument match before consumption.
        Fails closed on any discrepancy.
        """
        if self._emergency_stop:
            return False, "EMERGENCY_STOP_ACTIVE"

        rec = self._approvals.get(approval_id)
        if not rec:
            return False, "APPROVAL_NOT_FOUND"

        if rec.tenant_id != tenant_id:
            return False, "TENANT_MISMATCH"

        if rec.used:
            return False, "APPROVAL_ALREADY_USED"

        if not rec.approved:
            return False, "ACTION_NOT_YET_APPROVED"

        # Check TTL
        now_iso = _now_iso()
        if now_iso > rec.expires_at:
            return False, "APPROVAL_EXPIRED"

        if rec.action != action:
            return False, "ACTION_NAME_MISMATCH"

        if rec.amount_paisa != amount_paisa:
            return False, "PRICE_AMOUNT_MISMATCH"

        if ancestry is not None and rec.ancestry != ancestry:
            return False, "ANCESTRY_MISMATCH"

        if team_id is not None and rec.team_id != team_id:
            return False, "TEAM_MISMATCH"

        # Verify argument digest match
        cur_digest = _digest_dict(arguments)
        if rec.argument_digest != cur_digest:
            return False, "ARGUMENTS_TAMPERED"

        # Re-verify HMAC signature
        if rec.ancestry or rec.team_id:
            ancestry_str = ":".join(rec.ancestry)
            expected_raw = f"{ancestry_str}:{rec.tenant_id}:{rec.user_id}:{rec.team_id or ''}:{rec.node_id}:{rec.action}:{rec.argument_digest}:{rec.amount_paisa}:{rec.nonce}:{rec.expires_at}"
        else:
            expected_raw = f"{rec.tenant_id}:{rec.user_id}:{rec.task_id}:{rec.node_id}:{rec.action}:{rec.argument_digest}:{rec.amount_paisa}:{rec.nonce}:{rec.expires_at}"

        expected_sig = hmac.new(_APPROVAL_SECRET.encode("utf-8"), expected_raw.encode("utf-8"), hashlib.sha256).hexdigest()

        if not hmac.compare_digest(rec.signature, expected_sig):
            return False, "SIGNATURE_INVALID"

        # Mark consumed
        rec.used = True
        return True, None

    def get_approval(self, approval_id: str) -> Optional[ApprovalRecord]:
        """Fetch approval record by ID."""
        return self._approvals.get(approval_id)

    def approve_action(self, approval_id: str, tenant_id: str) -> bool:
        """Mark approval record as approved by user/operator."""
        rec = self._approvals.get(approval_id)
        if not rec or rec.tenant_id != tenant_id or rec.used:
            return False
        rec.approved = True
        rec.approved_at = _now_iso()
        return True


# Singleton policy bridge instance
policy_bridge = PolicyBridge()
