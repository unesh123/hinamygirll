"""
HINAA OS — Phase 15 Central Policy Decision Point (PDP)
Implements server-side RBAC + ABAC + Capability Intersection for agents,
multi-tenant boundary enforcement, dynamic revocations, emergency stop, and default DENY.
"""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

from hinaa_api.security.approvals import ApprovalCeremonyManager, get_ceremony_manager
from hinaa_api.security.audit import AuditChainLogger, get_audit_logger
from hinaa_api.security.contracts import (
    DecisionEffect,
    PolicyContext,
    PolicyDecision,
    SecurityPermission,
    SecurityRole,
    SecuritySubject,
)
from hinaa_api.security.store import SecurityStore, get_security_store

logger = logging.getLogger(__name__)

# Base role-to-permission mapping
ROLE_PERMISSIONS: Dict[SecurityRole, Set[str]] = {
    SecurityRole.OWNER: {
        SecurityPermission.READ,
        SecurityPermission.WRITE,
        SecurityPermission.EXEC_TOOL,
        SecurityPermission.EXEC_CODE,
        SecurityPermission.BROWSE,
        SecurityPermission.MEMORY_READ,
        SecurityPermission.MEMORY_WRITE,
        SecurityPermission.MEMORY_EXPORT,
        SecurityPermission.MEMORY_DELETE,
        SecurityPermission.AUDIT_READ,
        SecurityPermission.AUDIT_EXPORT,
        SecurityPermission.TIER_C_APPROVE,
        SecurityPermission.MANAGE_POLICIES,
        SecurityPermission.EMERGENCY_STOP,
        SecurityPermission.COMMERCE_CHARGE,
        SecurityPermission.SECRETS_MANAGE,
    },
    SecurityRole.TENANT_ADMIN: {
        SecurityPermission.READ,
        SecurityPermission.WRITE,
        SecurityPermission.EXEC_TOOL,
        SecurityPermission.EXEC_CODE,
        SecurityPermission.BROWSE,
        SecurityPermission.MEMORY_READ,
        SecurityPermission.MEMORY_WRITE,
        SecurityPermission.MEMORY_EXPORT,
        SecurityPermission.MEMORY_DELETE,
        SecurityPermission.AUDIT_READ,
        SecurityPermission.TIER_C_APPROVE,
        SecurityPermission.EMERGENCY_STOP,
    },
    SecurityRole.OPERATOR: {
        SecurityPermission.READ,
        SecurityPermission.WRITE,
        SecurityPermission.EXEC_TOOL,
        SecurityPermission.EXEC_CODE,
        SecurityPermission.BROWSE,
        SecurityPermission.MEMORY_READ,
        SecurityPermission.MEMORY_WRITE,
        SecurityPermission.AUDIT_READ,
    },
    SecurityRole.MEMBER: {
        SecurityPermission.READ,
        SecurityPermission.WRITE,
        SecurityPermission.MEMORY_READ,
    },
    SecurityRole.VIEWER: {
        SecurityPermission.READ,
        SecurityPermission.MEMORY_READ,
    },
    SecurityRole.SERVICE_WORKER: {
        SecurityPermission.READ,
        SecurityPermission.WRITE,
        SecurityPermission.EXEC_TOOL,
    },
}

# Action to required permission mapping
ACTION_PERMISSION_MAP: Dict[str, str] = {
    # Goals & Autopilot
    "goals:read": SecurityPermission.READ,
    "goals:submit": SecurityPermission.WRITE,
    "goals:replan": SecurityPermission.WRITE,
    "autopilot:run": SecurityPermission.EXEC_TOOL,
    
    # Coding & Sandbox
    "coding:run": SecurityPermission.EXEC_CODE,
    "coding:diff": SecurityPermission.READ,
    "sandbox:execute": SecurityPermission.EXEC_CODE,
    
    # Memory
    "memory:read": SecurityPermission.MEMORY_READ,
    "memory:search": SecurityPermission.MEMORY_READ,
    "memory:write": SecurityPermission.MEMORY_WRITE,
    "memory:export": SecurityPermission.MEMORY_EXPORT,
    "memory:delete": SecurityPermission.MEMORY_DELETE,
    
    # Browser
    "browser:navigate": SecurityPermission.BROWSE,
    "browser:screenshot": SecurityPermission.BROWSE,
    
    # High-impact actions
    "commerce:charge": SecurityPermission.COMMERCE_CHARGE,
    "deploy:production": SecurityPermission.EXEC_TOOL,
    "terminal:rm_rf_root": SecurityPermission.EXEC_TOOL,
    
    # Governance & Audit
    "audit:read": SecurityPermission.AUDIT_READ,
    "audit:export": SecurityPermission.AUDIT_EXPORT,
    "audit:verify": SecurityPermission.AUDIT_READ,
    "security:emergency_stop": SecurityPermission.EMERGENCY_STOP,
    "security:manage_policies": SecurityPermission.MANAGE_POLICIES,
    "security:posture": SecurityPermission.READ,
}

# Actions that unconditionally require single-use cryptographic human approval ceremony
TIER_C_ACTIONS = {
    "commerce:charge",
    "deploy:production",
    "terminal:rm_rf_root",
    "security:manage_policies",
}


class PolicyDecisionPoint:
    """
    Central server-side Policy Decision Point.
    Enforces RBAC, ABAC, delegation capability intersection, and default deny.
    """

    def __init__(
        self,
        store: Optional[SecurityStore] = None,
        ceremony_mgr: Optional[ApprovalCeremonyManager] = None,
        audit_logger: Optional[AuditChainLogger] = None,
    ) -> None:
        self.store = store or get_security_store()
        self.ceremony_mgr = ceremony_mgr or get_ceremony_manager(self.store)
        self.audit_logger = audit_logger or get_audit_logger(self.store)
        self._emergency_stops: Set[str] = set()  # Set of stopped tenant_ids ("*" for global)

    def trigger_emergency_stop(self, tenant_id: str = "*", triggered_by: str = "operator") -> None:
        self._emergency_stops.add(tenant_id)
        self.audit_logger.log_event(
            tenant_id=tenant_id,
            subject_id=triggered_by,
            action="security:emergency_stop",
            resource="platform",
            decision="ALLOW",
            reason_code="EMERGENCY_STOP_TRIGGERED",
        )

    def lift_emergency_stop(self, tenant_id: str = "*", lifted_by: str = "owner") -> None:
        self._emergency_stops.discard(tenant_id)
        self.audit_logger.log_event(
            tenant_id=tenant_id,
            subject_id=lifted_by,
            action="security:lift_emergency_stop",
            resource="platform",
            decision="ALLOW",
            reason_code="EMERGENCY_STOP_LIFTED",
        )

    def is_emergency_stopped(self, tenant_id: str) -> bool:
        return "*" in self._emergency_stops or tenant_id in self._emergency_stops

    def evaluate_delegation_intersection(
        self,
        parent_role: SecurityRole,
        child_role: SecurityRole,
        task_scoped_grants: Set[str],
        delegation_chain: List[str],
    ) -> Set[str]:
        """
        Computes strict capability intersection:
        effective = parent_perms ∩ child_perms ∩ task_scoped_grants
        Ensures agents cannot escalate privileges or grant permissions they do not possess.
        """
        parent_perms = ROLE_PERMISSIONS.get(parent_role, set())
        child_perms = ROLE_PERMISSIONS.get(child_role, set())

        # If any agent in delegation chain is revoked, effective perms are empty
        for agent_id in delegation_chain:
            if self.store.is_revoked("agent", agent_id):
                return set()

        effective = parent_perms.intersection(child_perms)
        if task_scoped_grants:
            effective = effective.intersection(task_scoped_grants)

        return effective

    def evaluate(self, context: PolicyContext) -> PolicyDecision:
        """
        Evaluates policy context against RBAC, ABAC, tenant boundary, and revocations.
        Defaults to DENY on any unknown action or failure.
        """
        subject = context.subject
        action = context.action
        resource = context.resource
        tenant_id = subject.tenant_id

        # 1. Emergency stop check
        if self.is_emergency_stopped(tenant_id) and action != "security:emergency_stop":
            decision = PolicyDecision(
                effect=DecisionEffect.DENY,
                reason_code="EMERGENCY_STOP_ACTIVE",
                subject_id=subject.user_id,
                tenant_id=tenant_id,
                action=action,
                resource=resource,
                trace_id=context.trace_id,
            )
            self._log_audit(context, decision)
            return decision

        # 2. Revocation checks (user, session, role)
        if self.store.is_revoked("user", subject.user_id):
            return self._deny(context, "SUBJECT_USER_REVOKED")
        if subject.session_id and self.store.is_revoked("session", subject.session_id):
            return self._deny(context, "SESSION_REVOKED")
        if self.store.is_revoked("role", f"{tenant_id}:{subject.role.value}"):
            return self._deny(context, "ROLE_REVOKED_FOR_TENANT")

        # 3. Multi-Tenant isolation (BOLA check)
        if context.resource_tenant_id and context.resource_tenant_id != tenant_id:
            # Cross-tenant access strictly forbidden
            return self._deny(context, "CROSS_TENANT_ACCESS_DENIED")

        # 4. Unknown action default deny
        if action not in ACTION_PERMISSION_MAP and not action.startswith("custom:"):
            return self._deny(context, "UNKNOWN_ACTION_DEFAULT_DENY")

        required_perm = ACTION_PERMISSION_MAP.get(action, SecurityPermission.READ)

        # 5. Administrative policy changes strictly forbidden for agents/workers
        if action == "security:manage_policies" and subject.role != SecurityRole.OWNER:
            return self._deny(context, "POLICY_MANAGEMENT_OWNER_ONLY")

        # 6. Tier C high-impact human approval ceremony requirement
        if action in TIER_C_ACTIONS:
            token_id = context.approval_token_id
            if not token_id:
                # Issue or require challenge
                challenge = self.ceremony_mgr.create_challenge(
                    tenant_id=tenant_id,
                    action=action,
                    parameters=context.parameters,
                    amount_paisa=context.parameters.get("amount_paisa"),
                )
                decision = PolicyDecision(
                    effect=DecisionEffect.REQUIRE_APPROVAL,
                    reason_code="TIER_C_CEREMONY_REQUIRED",
                    subject_id=subject.user_id,
                    tenant_id=tenant_id,
                    action=action,
                    resource=resource,
                    trace_id=context.trace_id,
                    approval_challenge_id=challenge.token_id,
                )
                self._log_audit(context, decision)
                return decision

            # Verify cryptographic token and anti-replay nonce
            amt = context.parameters.get("amount_paisa")
            ok, reason = self.ceremony_mgr.verify_and_consume(
                token_id=token_id,
                action=action,
                parameters=context.parameters,
                tenant_id=tenant_id,
                amount_paisa=amt,
            )
            if not ok:
                return self._deny(context, f"APPROVAL_CEREMONY_FAILED_{reason}")

            # Approved ceremony allows high-impact execution
            decision = PolicyDecision(
                effect=DecisionEffect.ALLOW,
                reason_code="AUTHORIZED_VIA_CEREMONY",
                subject_id=subject.user_id,
                tenant_id=tenant_id,
                action=action,
                resource=resource,
                trace_id=context.trace_id,
            )
            self._log_audit(context, decision)
            return decision

        # 6. Standard Role-based permission evaluation for non-Tier C actions
        allowed_perms = ROLE_PERMISSIONS.get(subject.role, set())
        if subject.scopes:
            # Further restricted by subject scopes
            allowed_perms = allowed_perms.intersection(subject.scopes)

        # If subject is a delegated child agent, compute delegation intersection
        if subject.delegation_chain:
            # Check every agent in ancestry
            for ancestor in subject.delegation_chain:
                if self.store.is_revoked("agent", ancestor):
                    return self._deny(context, "DELEGATION_ANCESTRY_REVOKED")

        if required_perm not in allowed_perms:
            return self._deny(context, f"ROLE_{subject.role.name}_MISSING_PERM_{required_perm}")

        # 7. Allowed
        decision = PolicyDecision(
            effect=DecisionEffect.ALLOW,
            reason_code="AUTHORIZED",
            subject_id=subject.user_id,
            tenant_id=tenant_id,
            action=action,
            resource=resource,
            trace_id=context.trace_id,
        )
        self._log_audit(context, decision)
        return decision

    def _deny(self, context: PolicyContext, reason_code: str) -> PolicyDecision:
        decision = PolicyDecision(
            effect=DecisionEffect.DENY,
            reason_code=reason_code,
            subject_id=context.subject.user_id,
            tenant_id=context.subject.tenant_id,
            action=context.action,
            resource=context.resource,
            trace_id=context.trace_id,
        )
        self._log_audit(context, decision)
        return decision

    def _log_audit(self, context: PolicyContext, decision: PolicyDecision) -> None:
        try:
            self.audit_logger.log_event(
                tenant_id=decision.tenant_id,
                subject_id=decision.subject_id,
                action=decision.action,
                resource=decision.resource,
                decision=decision.effect.value,
                reason_code=decision.reason_code,
            )
        except Exception as e:
            logger.error(f"Audit log write failed: {e}")


_global_pdp: Optional[PolicyDecisionPoint] = None


def get_pdp(
    store: Optional[SecurityStore] = None,
    ceremony_mgr: Optional[ApprovalCeremonyManager] = None,
    audit_logger: Optional[AuditChainLogger] = None,
) -> PolicyDecisionPoint:
    global _global_pdp
    if store is not None or ceremony_mgr is not None or audit_logger is not None:
        return PolicyDecisionPoint(store, ceremony_mgr, audit_logger)
    if _global_pdp is None:
        _global_pdp = PolicyDecisionPoint()
    return _global_pdp
