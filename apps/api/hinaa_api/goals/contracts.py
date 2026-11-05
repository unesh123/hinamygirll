"""
HINAA OS — Phase 14: Autonomous Goal Planner & Continuous Self-Correction
Data Contracts & Typed Schemas.

Defines the core domain model for multi-stage bounded goals, hierarchical milestone DAGs,
verifiable evidence receipts, versioned plans, bounded replanning decisions, observed self-model
capabilities, quarantined reflections, and cryptographic parameter-bound approvals.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _now_epoch() -> float:
    return time.time()


class GoalStatus(str, Enum):
    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class MilestoneStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    VERIFIED = "VERIFIED"
    PARTIAL = "PARTIAL"
    UNVERIFIED = "UNVERIFIED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"
    SKIPPED = "SKIPPED"


class RiskTier(str, Enum):
    TIER_A_READONLY = "TIER_A_READONLY"
    TIER_B_INTERNAL_DEV = "TIER_B_INTERNAL_DEV"
    TIER_C_CONSEQUENTIAL = "TIER_C_CONSEQUENTIAL"  # Payments, deploy, account changes, destructive file ops


class CostCategory(str, Enum):
    MEASURED = "MEASURED"
    PROVIDER_ESTIMATED = "PROVIDER_ESTIMATED"
    SYNTHETIC_TEST_ONLY = "SYNTHETIC_TEST_ONLY"


class RootCauseType(str, Enum):
    TEST_FAILURE = "TEST_FAILURE"
    CONTRADICTION = "CONTRADICTION"
    UNAVAILABLE_DEPENDENCY = "UNAVAILABLE_DEPENDENCY"
    RESOURCE_EXCEEDED = "RESOURCE_EXCEEDED"
    REQUIREMENT_CHANGE = "REQUIREMENT_CHANGE"
    DEADLINE_MISSED = "DEADLINE_MISSED"
    POOR_QUALITY = "POOR_QUALITY"
    EXTERNAL_STATE_CHANGED = "EXTERNAL_STATE_CHANGED"


class EvidenceReceipt(BaseModel):
    """Verifiable proof of milestone execution, test run, or research claim."""
    receipt_id: str = Field(default_factory=lambda: f"rcpt-{uuid.uuid4().hex[:8]}")
    milestone_id: str
    goal_id: str
    tool_name: str
    exit_code: int = 0
    output_hash: str = ""
    source_provenance: Dict[str, Any] = Field(default_factory=dict)
    verified_by_qa: bool = False
    timestamp_utc: float = Field(default_factory=_now_epoch)
    is_valid: bool = True
    raw_snippet: Optional[str] = None
    signature: Optional[str] = None


class Milestone(BaseModel):
    """An executable node within a Goal's milestone DAG."""
    milestone_id: str = Field(default_factory=lambda: f"ms-{uuid.uuid4().hex[:8]}")
    goal_id: str
    title: str
    description: str = ""
    inputs: Dict[str, Any] = Field(default_factory=dict)
    outputs: Dict[str, Any] = Field(default_factory=dict)
    prerequisites: List[str] = Field(default_factory=list)  # Milestone IDs that must complete first
    preconditions: List[str] = Field(default_factory=list)  # Environmental/auth conditions
    exit_criteria: List[str] = Field(default_factory=list)
    evidence_requirements: List[str] = Field(default_factory=list)
    estimated_paisa: int = 0
    estimated_tokens: int = 0
    actual_paisa: int = 0
    actual_tokens: int = 0
    cost_category: CostCategory = CostCategory.PROVIDER_ESTIMATED
    deadline_utc: Optional[float] = None
    risks: List[str] = Field(default_factory=list)
    fallbacks: List[str] = Field(default_factory=list)
    status: MilestoneStatus = MilestoneStatus.PENDING
    assigned_role: str = "engineer"
    execution_mode: str = "single_agent"  # single_agent, flat_swarm, hierarchical
    evidence_receipts: List[EvidenceReceipt] = Field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 2
    started_at_utc: Optional[float] = None
    completed_at_utc: Optional[float] = None
    failure_reason: Optional[str] = None


class PlanVersion(BaseModel):
    """Immutable version of a goal's plan graph."""
    plan_version_id: str = Field(default_factory=lambda: f"pv-{uuid.uuid4().hex[:8]}")
    goal_id: str
    version_number: int = 1
    parent_version_id: Optional[str] = None
    milestones: List[Milestone] = Field(default_factory=list)
    edges: List[List[str]] = Field(default_factory=list)  # [from_ms_id, to_ms_id]
    reason_for_change: Optional[str] = None
    triggering_evidence_receipt_id: Optional[str] = None
    verification_reserve_paisa: int = 500  # 10% reserve for QA verification
    verification_reserve_tokens: int = 2000
    created_at_utc: float = Field(default_factory=_now_epoch)


class GoalSpec(BaseModel):
    """User-authorized, multi-stage objective pursued within explicit bounds."""
    goal_id: str = Field(default_factory=lambda: f"goal-{uuid.uuid4().hex[:8]}")
    tenant_id: str = "default_tenant"
    user_id: str = "default_user"
    project_id: str = "default_project"
    title: str
    description: str = ""
    origin: str = "USER_PROMPT"  # USER_PROMPT, SCHEDULED_JOB, CONTINUATION, UNFINISHED_WORK
    authorized_scope: List[str] = Field(default_factory=lambda: ["read", "sandbox_exec"])
    priority: int = 50  # 1 to 100
    risk_tier: RiskTier = RiskTier.TIER_B_INTERNAL_DEV
    time_horizon_seconds: float = 3600.0  # 1 hour default
    deadline_utc: Optional[float] = None
    success_criteria: List[str] = Field(default_factory=list)
    stop_conditions: List[str] = Field(default_factory=list)
    budget_paisa: int = 5000  # 50 NPR = 5000 paisa
    budget_tokens: int = 50000
    consumed_paisa: int = 0
    consumed_tokens: int = 0
    source_refs: List[str] = Field(default_factory=list)
    status: GoalStatus = GoalStatus.PROPOSED
    active_plan_version: int = 1
    replan_count: int = 0
    max_replans: int = 3
    created_at_utc: float = Field(default_factory=_now_epoch)
    last_reviewed_at_utc: float = Field(default_factory=_now_epoch)
    completed_at_utc: Optional[float] = None
    termination_reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReplanDecision(BaseModel):
    """Audit trail record of a plan change and evidence-grounded explanation."""
    replan_id: str = Field(default_factory=lambda: f"rpl-{uuid.uuid4().hex[:8]}")
    goal_id: str
    prior_plan_version: int
    new_plan_version: int
    root_cause: RootCauseType
    trigger_evidence_id: Optional[str] = None
    explanation_en: str
    explanation_ne: str
    explanation_romanized: str
    superseded_milestone_ids: List[str] = Field(default_factory=list)
    reused_milestone_ids: List[str] = Field(default_factory=list)
    added_milestone_ids: List[str] = Field(default_factory=list)
    created_at_utc: float = Field(default_factory=_now_epoch)


class SelfModelCapability(BaseModel):
    """Active, observed tool and model availability probe."""
    capability_id: str
    category: str  # "llm", "vision", "video", "voice", "sandbox", "browser", "payments"
    provider: str
    is_available: bool
    last_checked_utc: float = Field(default_factory=_now_epoch)
    error_details: Optional[str] = None
    rate_limit_info: Dict[str, Any] = Field(default_factory=dict)
    is_mock: bool = False


class QuarantinedReflection(BaseModel):
    """Validated lesson learned from task failure or self-correction, staged for review."""
    reflection_id: str = Field(default_factory=lambda: f"refl-{uuid.uuid4().hex[:8]}")
    goal_id: str
    tenant_id: str = "default_tenant"
    lesson: str
    trigger_failure: str
    corrective_action: str
    source_receipts: List[str] = Field(default_factory=list)
    status: str = "PENDING_REVIEW"  # PENDING_REVIEW, APPROVED, REJECTED
    created_at_utc: float = Field(default_factory=_now_epoch)


class GoalApprovalRequest(BaseModel):
    """Cryptographically verifiable, parameter-bound approval for Tier C operations."""
    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:8]}")
    goal_id: str
    tenant_id: str
    action_type: str  # "payment", "production_deploy", "credential_access", "delete_records"
    resource: str
    amount_paisa: int = 0
    recipient: Optional[str] = None
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    expires_at_utc: float
    is_consumed: bool = False
    hmac_signature: str = ""

    def compute_signature(self, secret: str) -> str:
        import hmac
        payload = f"{self.approval_id}:{self.goal_id}:{self.tenant_id}:{self.action_type}:{self.resource}:{self.amount_paisa}:{self.recipient}:{self.nonce}:{self.expires_at_utc}"
        return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify_signature(self, secret: str) -> bool:
        expected = self.compute_signature(secret)
        import hmac
        return hmac.compare_digest(self.hmac_signature, expected)
