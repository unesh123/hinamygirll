"""
HINAA OS — Phase 15 Security, Permissions & Governance Guardrails
Contracts, Enums, and Data Models.

Adheres to:
- OWASP ASVS 5.0 (Server-side access control, tenant isolation)
- OWASP Top 10 for Agentic Applications (2026) (Delegation bounds, prompt-injection defense)
- NIST SP 800-63B / NIST SP 800-57 (Session lifetimes, token binding, cryptographic key hygiene)
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


class SecurityRole(str, Enum):
    OWNER = "owner"
    TENANT_ADMIN = "tenant_admin"
    OPERATOR = "operator"
    MEMBER = "member"
    VIEWER = "viewer"
    SERVICE_WORKER = "service_worker"


class SecurityPermission(str, Enum):
    # Read & Observe
    READ = "read"
    AUDIT_READ = "audit:read"
    AUDIT_EXPORT = "audit:export"
    
    # Write & Mutate
    WRITE = "write"
    
    # Tool Execution & Sandbox
    EXEC_TOOL = "tool:execute"
    EXEC_CODE = "code:execute"
    BROWSE = "browser:navigate"
    
    # Memory Governance
    MEMORY_READ = "memory:read"
    MEMORY_WRITE = "memory:write"
    MEMORY_EXPORT = "memory:export"
    MEMORY_DELETE = "memory:delete"
    
    # High-Impact & Governance
    TIER_C_APPROVE = "approval:tier_c"
    MANAGE_POLICIES = "security:manage_policies"
    EMERGENCY_STOP = "security:emergency_stop"
    COMMERCE_CHARGE = "commerce:charge"
    SECRETS_MANAGE = "secrets:manage"


class DecisionEffect(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


class KeystoreType(str, Enum):
    SOFTWARE_DPAPI = "SOFTWARE_DPAPI"
    SOFTWARE_ENV = "SOFTWARE_ENV"
    HARDWARE_TPM_CNG = "HARDWARE_TPM_CNG"
    CONFIG_REQUIRED = "CONFIG_REQUIRED"


class HostIsolationLevel(str, Enum):
    PROCESS_JOB_OBJECT = "PROCESS_JOB_OBJECT"
    CONTAINER_STRONG = "CONTAINER_STRONG"
    UNTRUSTED_BLOCKED = "UNTRUSTED_BLOCKED"


class SecuritySubject(BaseModel):
    user_id: str
    tenant_id: str
    role: SecurityRole
    scopes: Set[str] = Field(default_factory=set)
    delegation_chain: List[str] = Field(default_factory=list)  # ["agent:supervisor", "agent:coder"]
    is_service_worker: bool = False
    session_id: Optional[str] = None
    created_at: float = Field(default_factory=time.time)


class PolicyContext(BaseModel):
    subject: SecuritySubject
    action: str
    resource: str
    resource_tenant_id: Optional[str] = None
    parameters: Dict[str, Any] = Field(default_factory=dict)
    approval_token_id: Optional[str] = None
    client_ip: Optional[str] = None
    trace_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)


class PolicyDecision(BaseModel):
    effect: DecisionEffect
    reason_code: str
    policy_version: str = "15.0"
    subject_id: str
    tenant_id: str
    action: str
    resource: str
    trace_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    approval_challenge_id: Optional[str] = None


class ApprovalCeremonyToken(BaseModel):
    token_id: str
    tenant_id: str
    action: str
    parameters_digest: str  # SHA-256 of canonical JSON parameters
    nonce: str
    issued_at: float
    expires_at: float
    consumed_at: Optional[float] = None
    amount_paisa: Optional[int] = None
    currency: str = "NPR"
    approved_by: Optional[str] = None
    signature: str
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED, CONSUMED, EXPIRED


class AuditEvent(BaseModel):
    sequence_id: int
    event_id: str
    timestamp: float
    tenant_id: str
    subject_id: str
    action: str
    resource: str
    decision: str
    reason_code: str
    prev_hash: str
    event_hash: str
    signature: str


class KeystoreProbeResult(BaseModel):
    keystore_type: KeystoreType
    is_hardware_backed: bool
    provider_name: str
    capabilities: List[str]
    status_details: str


class HostIsolationProbeResult(BaseModel):
    isolation_level: HostIsolationLevel
    can_execute_untrusted_code: bool
    os_platform: str
    job_objects_available: bool
    wsl_available: bool
    status_details: str
