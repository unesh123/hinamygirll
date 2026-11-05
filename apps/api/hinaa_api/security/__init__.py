"""
HINAA OS — Phase 15 Security, Permissions & Governance Guardrails
Public Package Exports.
"""

from __future__ import annotations

from hinaa_api.security.contracts import (
    ApprovalCeremonyToken,
    AuditEvent,
    DecisionEffect,
    HostIsolationLevel,
    HostIsolationProbeResult,
    KeystoreProbeResult,
    KeystoreType,
    PolicyContext,
    PolicyDecision,
    SecurityPermission,
    SecurityRole,
    SecuritySubject,
)
from hinaa_api.security.store import SecurityStore, get_security_store
from hinaa_api.security.secrets import (
    KeystoreManager,
    SecretScrubber,
    get_keystore_manager,
)
from hinaa_api.security.posture import (
    HostPostureGuard,
    get_host_posture_guard,
)
from hinaa_api.security.audit import (
    AuditChainLogger,
    get_audit_logger,
)
from hinaa_api.security.approvals import (
    ApprovalCeremonyManager,
    get_ceremony_manager,
)
from hinaa_api.security.pdp import (
    PolicyDecisionPoint,
    get_pdp,
)
from hinaa_api.security.pep import (
    PolicyEnforcementGate,
    get_enforcement_gate,
    require_permission,
    detect_prompt_injection,
)
from hinaa_api.security.identity import (
    IdentityProvider,
    get_current_subject,
    get_identity_provider,
)
from hinaa_api.security.endpoints import security_router

# Backward compatibility with earlier phases
from hinaa_api.security.policy_engine import (
    ApprovalChallenge,
    PolicyDecisionType,
    PolicyEngine,
    PolicyEvaluationResult,
    PolicyRule,
)
from hinaa_api.security.secret_broker import (
    EphemeralCapabilityHandle,
    SecretBroker,
    get_secret_broker,
)

__all__ = [
    # Contracts
    "SecurityRole",
    "SecurityPermission",
    "DecisionEffect",
    "KeystoreType",
    "HostIsolationLevel",
    "SecuritySubject",
    "PolicyContext",
    "PolicyDecision",
    "ApprovalCeremonyToken",
    "AuditEvent",
    "KeystoreProbeResult",
    "HostIsolationProbeResult",
    # Store
    "SecurityStore",
    "get_security_store",
    # Secrets
    "KeystoreManager",
    "SecretScrubber",
    "get_keystore_manager",
    # Posture
    "HostPostureGuard",
    "get_host_posture_guard",
    # Audit
    "AuditChainLogger",
    "get_audit_logger",
    # Approvals
    "ApprovalCeremonyManager",
    "get_ceremony_manager",
    # PDP & PEP
    "PolicyDecisionPoint",
    "get_pdp",
    "PolicyEnforcementGate",
    "get_enforcement_gate",
    "require_permission",
    "detect_prompt_injection",
    # Identity
    "IdentityProvider",
    "get_identity_provider",
    "get_current_subject",
    # Router
    "security_router",
    # Legacy
    "PolicyEngine",
    "PolicyRule",
    "PolicyDecisionType",
    "PolicyEvaluationResult",
    "ApprovalChallenge",
    "SecretBroker",
    "EphemeralCapabilityHandle",
    "get_secret_broker",
]
