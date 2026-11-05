"""
HINAA OS — Phase 15 Security REST Endpoints
Mounted under `/api/security` providing posture auditing, permission introspection,
cryptographic approval ceremony management, hash-chain audit verification, and emergency controls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from hinaa_api.security.approvals import ApprovalCeremonyManager, get_ceremony_manager
from hinaa_api.security.audit import AuditChainLogger, get_audit_logger
from hinaa_api.security.contracts import (
    ApprovalCeremonyToken,
    AuditEvent,
    HostIsolationProbeResult,
    KeystoreProbeResult,
    SecurityPermission,
    SecurityRole,
    SecuritySubject,
)
from hinaa_api.security.identity import get_current_subject
from hinaa_api.security.pdp import (
    ROLE_PERMISSIONS,
    PolicyDecisionPoint,
    get_pdp,
)
from hinaa_api.security.posture import HostPostureGuard, get_host_posture_guard
from hinaa_api.security.secrets import KeystoreManager, get_keystore_manager
from hinaa_api.security.store import SecurityStore, get_security_store

logger = logging.getLogger(__name__)

security_router = APIRouter(prefix="/api/security", tags=["Security & Governance"])


# Zero-arg FastAPI dependency providers
def _dep_store() -> SecurityStore:
    return get_security_store()


def _dep_keystore() -> KeystoreManager:
    return get_keystore_manager()


def _dep_posture() -> HostPostureGuard:
    return get_host_posture_guard()


def _dep_pdp() -> PolicyDecisionPoint:
    return get_pdp()


def _dep_ceremony() -> ApprovalCeremonyManager:
    return get_ceremony_manager()


def _dep_audit() -> AuditChainLogger:
    return get_audit_logger()


class ChallengeCreateRequest(BaseModel):
    action: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    amount_paisa: Optional[int] = None
    ttl_seconds: float = 300.0


class ChallengeDecideRequest(BaseModel):
    token_id: str
    decision: str  # "APPROVE" or "REJECT"


class EmergencyStopRequest(BaseModel):
    tenant_id: str = "*"
    reason: str = "Operator emergency stop"


class RevocationRequest(BaseModel):
    target_type: str  # 'user', 'role', 'agent', 'token', 'session'
    target_id: str
    reason: str


class PermissionIntrospectionResponse(BaseModel):
    user_id: str
    tenant_id: str
    role: SecurityRole
    scopes: List[str]
    effective_permissions: List[str]
    is_emergency_stopped: bool


class SecurityPostureResponse(BaseModel):
    keystore: KeystoreProbeResult
    host_isolation: HostIsolationProbeResult
    active_revocations_count: int
    is_emergency_stopped: bool


@security_router.get("/posture", response_model=SecurityPostureResponse)
def get_security_posture(
    keystore: KeystoreManager = Depends(_dep_keystore),
    posture_guard: HostPostureGuard = Depends(_dep_posture),
    store: SecurityStore = Depends(_dep_store),
    pdp: PolicyDecisionPoint = Depends(_dep_pdp),
) -> SecurityPostureResponse:
    """Returns honest host privilege boundary and platform keystore probe status."""
    ks_res = keystore.probe_keystore()
    host_res = posture_guard.probe_host_posture()
    revocations = store.list_revocations()

    return SecurityPostureResponse(
        keystore=ks_res,
        host_isolation=host_res,
        active_revocations_count=len(revocations),
        is_emergency_stopped=pdp.is_emergency_stopped("*"),
    )


@security_router.get("/my-permissions", response_model=PermissionIntrospectionResponse)
def get_my_permissions(
    subject: SecuritySubject = Depends(get_current_subject),
    pdp: PolicyDecisionPoint = Depends(_dep_pdp),
) -> PermissionIntrospectionResponse:
    """Returns verified server-side identity, tenant, role, and effective permissions."""
    base_perms = ROLE_PERMISSIONS.get(subject.role, set())
    if subject.scopes:
        base_perms = base_perms.intersection(subject.scopes)

    return PermissionIntrospectionResponse(
        user_id=subject.user_id,
        tenant_id=subject.tenant_id,
        role=subject.role,
        scopes=list(subject.scopes),
        effective_permissions=sorted(list(base_perms)),
        is_emergency_stopped=pdp.is_emergency_stopped(subject.tenant_id),
    )


@security_router.post("/ceremonies/create", response_model=ApprovalCeremonyToken)
def create_approval_ceremony(
    req: ChallengeCreateRequest,
    subject: SecuritySubject = Depends(get_current_subject),
    ceremony_mgr: ApprovalCeremonyManager = Depends(_dep_ceremony),
) -> ApprovalCeremonyToken:
    """Creates a cryptographic parameter-bound human approval challenge."""
    try:
        return ceremony_mgr.create_challenge(
            tenant_id=subject.tenant_id,
            action=req.action,
            parameters=req.parameters,
            amount_paisa=req.amount_paisa,
            ttl_seconds=req.ttl_seconds,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@security_router.post("/ceremonies/decide", response_model=ApprovalCeremonyToken)
def decide_approval_ceremony(
    req: ChallengeDecideRequest,
    subject: SecuritySubject = Depends(get_current_subject),
    ceremony_mgr: ApprovalCeremonyManager = Depends(_dep_ceremony),
) -> ApprovalCeremonyToken:
    """Explicitly approves or rejects a pending human authorization challenge."""
    # Only Owner or Tenant Admin or Operator can sign off
    allowed_roles = {SecurityRole.OWNER, SecurityRole.TENANT_ADMIN}
    if subject.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only OWNER or TENANT_ADMIN can approve authorization ceremonies.",
        )

    try:
        if req.decision.upper() == "APPROVE":
            return ceremony_mgr.approve_challenge(
                token_id=req.token_id,
                approver_id=subject.user_id,
                approver_role=subject.role.value,
            )
        else:
            return ceremony_mgr.reject_challenge(
                token_id=req.token_id,
                rejecter_id=subject.user_id,
            )
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Challenge not found.")
    except (ValueError, TimeoutError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@security_router.get("/audit", response_model=List[AuditEvent])
def get_audit_events(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    subject: SecuritySubject = Depends(get_current_subject),
    store: SecurityStore = Depends(_dep_store),
) -> List[AuditEvent]:
    """Retrieves paginated audit events strictly scoped to caller tenant."""
    # Viewer cannot access sensitive audit logs
    if subject.role == SecurityRole.VIEWER:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="VIEWER role is not authorized to inspect audit logs.",
        )

    # Scoped strictly to caller's tenant unless OWNER
    tenant_filter = None if subject.role == SecurityRole.OWNER else subject.tenant_id
    return store.list_audit_events(tenant_id=tenant_filter, limit=limit, offset=offset)


@security_router.post("/audit/verify")
def verify_audit_trail(
    subject: SecuritySubject = Depends(get_current_subject),
    audit_logger: AuditChainLogger = Depends(_dep_audit),
) -> Dict[str, Any]:
    """Scans and cryptographically verifies unbroken hash chain and signatures."""
    if subject.role not in {SecurityRole.OWNER, SecurityRole.TENANT_ADMIN}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only OWNER or TENANT_ADMIN can trigger audit chain verification.",
        )
    return audit_logger.verify_chain()


@security_router.post("/emergency-stop")
def trigger_emergency_stop(
    req: EmergencyStopRequest,
    subject: SecuritySubject = Depends(get_current_subject),
    pdp: PolicyDecisionPoint = Depends(_dep_pdp),
) -> Dict[str, str]:
    """Immediately halts agent execution and tool invocations."""
    if subject.role not in {SecurityRole.OWNER, SecurityRole.TENANT_ADMIN, SecurityRole.OPERATOR}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to trigger emergency stop.")

    target_tenant = subject.tenant_id if subject.role != SecurityRole.OWNER else req.tenant_id
    pdp.trigger_emergency_stop(tenant_id=target_tenant, triggered_by=subject.user_id)
    return {"status": "EMERGENCY_STOP_ACTIVE", "tenant_id": target_tenant}


@security_router.post("/emergency-stop/lift")
def lift_emergency_stop(
    req: EmergencyStopRequest,
    subject: SecuritySubject = Depends(get_current_subject),
    pdp: PolicyDecisionPoint = Depends(_dep_pdp),
) -> Dict[str, str]:
    """Lifts active emergency stop (Owner only)."""
    if subject.role != SecurityRole.OWNER:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only OWNER can lift emergency stop.")

    pdp.lift_emergency_stop(tenant_id=req.tenant_id, lifted_by=subject.user_id)
    return {"status": "EMERGENCY_STOP_LIFTED", "tenant_id": req.tenant_id}


@security_router.get("/revocations")
def list_revocations(
    subject: SecuritySubject = Depends(get_current_subject),
    store: SecurityStore = Depends(_dep_store),
) -> List[Dict[str, Any]]:
    tenant_filter = None if subject.role == SecurityRole.OWNER else subject.tenant_id
    return store.list_revocations(tenant_id=tenant_filter)


@security_router.post("/revocations")
def add_revocation(
    req: RevocationRequest,
    subject: SecuritySubject = Depends(get_current_subject),
    store: SecurityStore = Depends(_dep_store),
) -> Dict[str, str]:
    if subject.role not in {SecurityRole.OWNER, SecurityRole.TENANT_ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized to revoke privileges.")

    import uuid
    rev_id = f"rev_{uuid.uuid4().hex}"
    store.add_revocation(
        revocation_id=rev_id,
        target_type=req.target_type,
        target_id=req.target_id,
        tenant_id=subject.tenant_id,
        reason=req.reason,
        revoked_by=subject.user_id,
    )
    return {"status": "REVOKED", "revocation_id": rev_id}
