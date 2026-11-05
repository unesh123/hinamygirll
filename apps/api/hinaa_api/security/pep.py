"""
HINAA OS — Phase 15 Policy Enforcement Points (PEP)
Provides endpoint dependencies, tool execution gates, prompt injection sanitizers,
and filesystem traversal defenses across all system boundaries.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Callable, Dict, Optional, Set
from fastapi import Depends, HTTPException, Request, status

from hinaa_api.security.contracts import (
    DecisionEffect,
    PolicyContext,
    PolicyDecision,
    SecuritySubject,
)
from hinaa_api.security.identity import get_current_subject
from hinaa_api.security.pdp import PolicyDecisionPoint, get_pdp
from hinaa_api.security.posture import HostPostureGuard, get_host_posture_guard

logger = logging.getLogger(__name__)

# Prompt injection patterns attempting policy bypass or privilege escalation
INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior)\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*prompt\s*override", re.IGNORECASE),
    re.compile(r"grant\s+(me\s+)?(admin|owner|superuser)\s+role", re.IGNORECASE),
    re.compile(r"bypass\s+(all\s+)?(safety|security|policy)\s+gates?", re.IGNORECASE),
    re.compile(r"disable\s+(audit|pdp|guardrails?)", re.IGNORECASE),
    re.compile(r"reveal\s+(all\s+)?(secrets?|tokens?|keys?|credentials?)", re.IGNORECASE),
]


def detect_prompt_injection(text: Any) -> Optional[str]:
    """Scans text or structured parameters for policy override attacks."""
    if not isinstance(text, str):
        text = str(text)

    for pat in INJECTION_PATTERNS:
        match = pat.search(text)
        if match:
            return match.group(0)
    return None


class PolicyEnforcementGate:
    """
    Central enforcement gate for REST, agent tools, memory, and coding runs.
    """

    def __init__(
        self,
        pdp: Optional[PolicyDecisionPoint] = None,
        posture_guard: Optional[HostPostureGuard] = None,
    ) -> None:
        self.pdp = pdp or get_pdp()
        self.posture_guard = posture_guard or get_host_posture_guard()

    def enforce_tool_execution(
        self,
        subject: SecuritySubject,
        action: str,
        tool_name: str,
        arguments: Dict[str, Any],
        approval_token_id: Optional[str] = None,
        resource_tenant_id: Optional[str] = None,
    ) -> PolicyDecision:
        """
        Enforces security checks prior to executing any tool:
        1. Prompt injection detection in tool arguments
        2. Filesystem path containment check
        3. Policy Decision Point (RBAC + ABAC + delegation intersection)
        """
        # 1. Prompt injection inspection
        for key, val in arguments.items():
            injected = detect_prompt_injection(val)
            if injected:
                # Block attempted override
                context = PolicyContext(
                    subject=subject,
                    action=action,
                    resource=tool_name,
                    parameters=arguments,
                )
                return self.pdp._deny(context, f"PROMPT_INJECTION_DETECTED: {injected}")

        # 2. Path validation if argument contains file path
        for param_name in ["path", "file_path", "target_path", "workspace_path"]:
            if param_name in arguments and isinstance(arguments[param_name], str):
                try:
                    self.posture_guard.validate_workspace_path(arguments[param_name])
                except PermissionError as e:
                    context = PolicyContext(
                        subject=subject,
                        action=action,
                        resource=tool_name,
                        parameters=arguments,
                    )
                    return self.pdp._deny(context, f"PATH_TRAVERSAL_BLOCKED: {e}")

        # 3. Policy evaluation
        context = PolicyContext(
            subject=subject,
            action=action,
            resource=tool_name,
            resource_tenant_id=resource_tenant_id or subject.tenant_id,
            parameters=arguments,
            approval_token_id=approval_token_id,
        )
        return self.pdp.evaluate(context)


_global_enforcement_gate: Optional[PolicyEnforcementGate] = None


def get_enforcement_gate(
    pdp: Optional[PolicyDecisionPoint] = None,
    posture_guard: Optional[HostPostureGuard] = None,
) -> PolicyEnforcementGate:
    global _global_enforcement_gate
    if pdp is not None or posture_guard is not None:
        return PolicyEnforcementGate(pdp, posture_guard)
    if _global_enforcement_gate is None:
        _global_enforcement_gate = PolicyEnforcementGate()
    return _global_enforcement_gate


def require_permission(action: str, resource_from_param: Optional[str] = None) -> Callable:
    """
    FastAPI dependency factory enforcing PDP authorization for route endpoints.
    """
    async def dependency(
        request: Request,
        subject: SecuritySubject = Depends(get_current_subject),
    ) -> PolicyDecision:
        pdp = get_pdp()
        resource = resource_from_param or request.url.path

        # Check approval challenge token from headers if supplied
        approval_token_id = request.headers.get("X-Approval-Token")

        context = PolicyContext(
            subject=subject,
            action=action,
            resource=resource,
            resource_tenant_id=subject.tenant_id,
            approval_token_id=approval_token_id,
            client_ip=request.client.host if request.client else None,
        )

        decision = pdp.evaluate(context)
        if decision.effect == DecisionEffect.DENY:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied: {decision.reason_code}",
            )
        elif decision.effect == DecisionEffect.REQUIRE_APPROVAL:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED if "commerce" in action else status.HTTP_403_FORBIDDEN,
                detail={
                    "status": "REQUIRE_APPROVAL",
                    "reason": decision.reason_code,
                    "challenge_id": decision.approval_challenge_id,
                },
            )
        return decision

    return dependency
