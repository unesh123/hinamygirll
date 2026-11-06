"""
HINAA OS — Phase 18 Full Autonomous Convergence (Manus-Grade OS) Contracts.

Defines schemas for:
- Unified Mission state machine and lifecycle.
- Autonomous operational modes (Reactive, Bounded Delegated, Scheduled, Proactive).
- Typed verified output artifacts with cryptographic provenance digests.
- Scoped user autonomy contracts, spending limits in integer paisa, and approval states.
- Empirical capability truth matrix statuses.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MissionStatus(str, Enum):
    CREATED = "CREATED"
    SCOPING = "SCOPING"
    PLANNING = "PLANNING"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    PAUSED_OFFLINE = "PAUSED_OFFLINE"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    COMPLETED_VERIFIED = "COMPLETED_VERIFIED"
    PARTIAL = "PARTIAL"
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AutonomousMode(str, Enum):
    REACTIVE = "REACTIVE"                     # Immediate conversational turn (fast-path)
    BOUNDED_DELEGATED = "BOUNDED_DELEGATED"   # User-approved bounded multi-step mission
    SCHEDULED = "SCHEDULED"                   # Authorized background recurring task
    PROACTIVE_SUGGESTION = "PROACTIVE_SUGGESTION"  # Advice/proposal only, zero consequential mutations


class CapabilityStatus(str, Enum):
    AVAILABLE_VERIFIED = "AVAILABLE_VERIFIED"   # Executed and verified on current host/runtime
    AVAILABLE_DEGRADED = "AVAILABLE_DEGRADED"   # Operational with reduced speed/fallback backend
    CONFIG_REQUIRED = "CONFIG_REQUIRED"         # Supported in code, needs API key / infrastructure
    BLOCKED_UNAVAILABLE = "BLOCKED_UNAVAILABLE" # Not possible on host (e.g. neural video without weights)
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"     # Blocked pending Tier C human approval ceremony


class ArtifactType(str, Enum):
    RESEARCH_FINDING = "RESEARCH_FINDING"
    CODE_CHANGE = "CODE_CHANGE"
    TEST_REPORT = "TEST_REPORT"
    BROWSER_RECEIPT = "BROWSER_RECEIPT"
    IMAGE_ASSET = "IMAGE_ASSET"
    VIDEO_ASSET = "VIDEO_ASSET"
    VOICE_EXPLANATION = "VOICE_EXPLANATION"
    MEMORY_CANDIDATE = "MEMORY_CANDIDATE"
    APPROVAL_RECEIPT = "APPROVAL_RECEIPT"
    DEPLOYMENT_RECEIPT = "DEPLOYMENT_RECEIPT"


class TypedArtifact(BaseModel):
    artifact_id: str
    artifact_type: ArtifactType
    title: str
    content_digest: str  # SHA-256 of file/content bytes
    tenant_id: str = "default"
    producer_role: str = "orchestrator"
    confidence: float = 1.0
    limitations: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    payload: Dict[str, Any] = Field(default_factory=dict)
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    is_verified: bool = False
    verification_method: str = "unverified"


class BudgetConstraint(BaseModel):
    max_tokens: int = 50000
    max_cost_paisa: int = 5000  # 50 NPR default ceiling
    max_duration_seconds: float = 300.0
    gpu_allowed: bool = True
    spent_tokens: int = 0
    spent_cost_paisa: int = 0
    spent_duration_seconds: float = 0.0

    def has_budget(self) -> bool:
        return (
            self.spent_tokens < self.max_tokens
            and self.spent_cost_paisa < self.max_cost_paisa
            and self.spent_duration_seconds < self.max_duration_seconds
        )


class AutonomyContract(BaseModel):
    contract_id: str
    tenant_id: str = "default"
    permitted_domains: List[str] = Field(default_factory=lambda: ["local", "research", "coding"])
    spending_ceiling_paisa: int = 10000  # 100 NPR
    active_hours_start: int = 0   # 00:00
    active_hours_end: int = 24    # 24:00
    require_approval_for_money: bool = True
    require_approval_for_deploy: bool = True
    require_approval_for_deletion: bool = True
    emergency_stop_active: bool = False
    updated_at: float = Field(default_factory=time.time)


class UnifiedMission(BaseModel):
    mission_id: str
    tenant_id: str = "default"
    authenticated_actor: str = "user"
    objective: str
    success_rubric: str = "Objective must produce testable outputs with cryptographic checksums."
    constraints: List[str] = Field(default_factory=list)
    policy_version: str = "18.0.0"
    deployment_profile: str = "LOCAL_DESKTOP"
    capability_snapshot: Dict[str, CapabilityStatus] = Field(default_factory=dict)
    budget: BudgetConstraint = Field(default_factory=BudgetConstraint)
    consent_state: str = "USER_REQUESTED"  # USER_REQUESTED, APPROVED, REJECTED, EXPIRED
    goal_dag_version: int = 1
    checkpoint_lineage: List[str] = Field(default_factory=list)
    evidence_refs: List[Dict[str, Any]] = Field(default_factory=list)
    output_artifacts: List[TypedArtifact] = Field(default_factory=list)
    run_state: MissionStatus = MissionStatus.CREATED
    autonomous_mode: AutonomousMode = AutonomousMode.BOUNDED_DELEGATED
    side_effect_registry: List[Dict[str, Any]] = Field(default_factory=list)
    audit_correlation_id: str
    status_reason: Optional[str] = None
    reason_code: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

    def is_terminal(self) -> bool:
        return self.run_state in (
            MissionStatus.COMPLETED_VERIFIED,
            MissionStatus.PARTIAL,
            MissionStatus.BLOCKED_UNAVAILABLE,
            MissionStatus.FAILED,
            MissionStatus.CANCELLED,
        )
