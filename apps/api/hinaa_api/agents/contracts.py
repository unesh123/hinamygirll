"""
HINAA OS — Phase 11 & Phase 12 Multi-Agent Contracts & Schemas
Authoritative typed data contracts for autonomous agent orchestration,
DAG execution, tool receipts, cryptographic approvals, budget tracking,
and Phase 12 hierarchical team delegation.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _digest_dict(payload: dict[str, Any]) -> str:
    """Generate deterministic SHA-256 digest of dictionary payload."""
    import json
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class AgentRole(str, Enum):
    SUPERVISOR = "supervisor"
    PLANNER = "planner"
    RESEARCHER = "researcher"
    ENGINEER = "engineer"
    QA = "qa"
    BROWSER_OPERATOR = "browser_operator"
    CREATIVE_OPERATOR = "creative_operator"
    KNOWLEDGE_CURATOR = "knowledge_curator"
    LOCALIZATION_SPECIALIST = "localization_specialist"
    SECURITY_REVIEWER = "security_reviewer"


class TaskStatus(str, Enum):
    CREATED = "CREATED"
    PLANNING = "PLANNING"
    READY = "READY"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    RETRYING = "RETRYING"
    RECOVERING = "RECOVERING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    BLOCKED = "BLOCKED"


class PermissionTier(str, Enum):
    TIER_A_READ_ONLY = "TIER_A_READ_ONLY"
    TIER_B_SCOPED_DEV = "TIER_B_SCOPED_DEV"
    TIER_C_EXPLICIT_APPROVAL = "TIER_C_EXPLICIT_APPROVAL"
    DENIED = "DENIED"


class ExecutionMode(str, Enum):
    SINGLE_AGENT_FAST_PATH = "SINGLE_AGENT_FAST_PATH"
    FLAT_MULTI_AGENT = "FLAT_MULTI_AGENT"
    HIERARCHICAL_TEAM = "HIERARCHICAL_TEAM"


class TeamType(str, Enum):
    ENGINEERING = "engineering"
    RESEARCH = "research"
    CREATIVE = "creative"
    OPERATIONS = "operations"


class CapabilityGrant(BaseModel):
    grant_id: str = Field(default_factory=lambda: f"grant-{uuid.uuid4().hex[:8]}")
    role: AgentRole
    allowed_tools: list[str] = Field(default_factory=list)
    permission_tier: PermissionTier = PermissionTier.TIER_A_READ_ONLY
    max_tokens: int = 16384
    max_tool_calls: int = 20
    max_wall_time_seconds: float = 120.0
    network_egress_allowed: bool = False
    workspace_scoped: bool = True


class AgentSpec(BaseModel):
    agent_id: str
    role: AgentRole
    display_name: str
    description: str
    model: str = "default-routing"
    provider: str = "local"
    capability_grant: CapabilityGrant
    is_available: bool = True
    health_status: str = "HEALTHY"  # HEALTHY | DEGRADED | UNAVAILABLE


class TeamSpec(BaseModel):
    team_id: str
    team_type: TeamType
    display_name: str
    description: str = ""
    lead_role: AgentRole
    member_roles: list[AgentRole] = Field(default_factory=list)
    capability_grant: CapabilityGrant
    budget_slice: BudgetLedger = Field(default_factory=lambda: BudgetLedger())
    max_workers: int = 4


class ToolReceipt(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"rcpt-{uuid.uuid4().hex[:12]}")
    task_id: str
    node_id: Optional[str] = None
    agent_role: AgentRole
    tool_name: str
    action: str
    input_digest: str
    output_digest: str
    exit_code: int = 0
    duration_ms: float = 0.0
    verified: bool = False
    verification_notes: Optional[str] = None
    idempotency_key: str
    timestamp: str = Field(default_factory=_now_iso)
    artifact_paths: list[str] = Field(default_factory=list)


class ApprovalRecord(BaseModel):
    approval_id: str = Field(default_factory=lambda: f"appr-{uuid.uuid4().hex[:10]}")
    tenant_id: str
    user_id: str
    task_id: str
    node_id: str
    action: str
    argument_digest: str
    amount_paisa: int = 0  # 1 NPR = 100 paisa
    currency: str = "NPR"
    nonce: str = Field(default_factory=lambda: uuid.uuid4().hex)
    expires_at: str
    approved: bool = False
    used: bool = False
    signature: str = ""
    created_at: str = Field(default_factory=_now_iso)
    approved_at: Optional[str] = None
    ancestry: list[str] = Field(default_factory=list)
    team_id: Optional[str] = None


class BudgetLedger(BaseModel):
    allocated_tokens: int = 32768
    consumed_tokens: int = 0
    allocated_tool_calls: int = 50
    consumed_tool_calls: int = 0
    allocated_cost_usd: float = 2.00
    consumed_cost_usd: float = 0.00
    allocated_cost_paisa: int = 25000  # NPR 250.00
    consumed_cost_paisa: int = 0
    allocated_seconds: float = 300.0
    elapsed_seconds: float = 0.0
    max_recursion_depth: int = 4
    current_depth: int = 0

    def is_exceeded(self) -> tuple[bool, Optional[str]]:
        if self.consumed_tokens >= self.allocated_tokens:
            return True, "TOKEN_BUDGET_EXCEEDED"
        if self.consumed_tool_calls >= self.allocated_tool_calls:
            return True, "TOOL_CALL_BUDGET_EXCEEDED"
        if self.consumed_cost_usd >= self.allocated_cost_usd:
            return True, "COST_BUDGET_EXCEEDED"
        if self.consumed_cost_paisa >= self.allocated_cost_paisa:
            return True, "COST_PAISA_BUDGET_EXCEEDED"
        if self.elapsed_seconds >= self.allocated_seconds:
            return True, "DEADLINE_EXCEEDED"
        if self.current_depth >= self.max_recursion_depth:
            return True, "RECURSION_DEPTH_EXCEEDED"
        return False, None


class DelegationRequest(BaseModel):
    parent_task_id: str
    team_run_id: str = Field(default_factory=lambda: f"team-run-{uuid.uuid4().hex[:8]}")
    principal_id: str = "user-default"
    tenant_id: str = "default"
    team_type: TeamType
    lead_role: AgentRole
    objective: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    input_artifact_refs: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    allowed_resources: dict[str, Any] = Field(default_factory=dict)
    budget_slice: BudgetLedger = Field(default_factory=BudgetLedger)
    deadline: float = 300.0
    approval_state: str = "GRANTED"
    context_provenance: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str = Field(default_factory=lambda: f"idem-del-{uuid.uuid4().hex[:10]}")
    trace_id: str = Field(default_factory=lambda: f"trc-{uuid.uuid4().hex[:12]}")
    depth: int = 1
    ancestry: list[str] = Field(default_factory=list)


class TeamResult(BaseModel):
    team_run_id: str
    parent_task_id: str
    team_type: TeamType
    status: TaskStatus
    output_artifact_refs: list[str] = Field(default_factory=list)
    verified_postconditions: list[str] = Field(default_factory=list)
    evidence_receipts: list[ToolReceipt] = Field(default_factory=list)
    cost_metrics: dict[str, Any] = Field(default_factory=dict)
    failure_reasons: list[str] = Field(default_factory=list)
    scoped_context_summary: str = ""
    signature: str = ""
    duration_ms: float = 0.0


class TaskNode(BaseModel):
    node_id: str = Field(default_factory=lambda: f"node-{uuid.uuid4().hex[:8]}")
    task_id: str
    title: str
    specialist_role: AgentRole
    dependencies: list[str] = Field(default_factory=list)  # node_ids that must complete first
    allowed_tools: list[str] = Field(default_factory=list)
    permission_tier: PermissionTier = PermissionTier.TIER_A_READ_ONLY
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_schema: Optional[dict[str, Any]] = None
    expected_postcondition: Optional[str] = None
    status: TaskStatus = TaskStatus.READY
    result_data: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    attempts: int = 0
    max_attempts: int = 3
    lease_owner: Optional[str] = None
    lease_expires_at: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    receipts: list[ToolReceipt] = Field(default_factory=list)
    team_id: Optional[str] = None
    team_type: Optional[TeamType] = None
    ancestry: list[str] = Field(default_factory=list)
    depth: int = 0


class TaskEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt-{uuid.uuid4().hex[:10]}")
    sequence: int
    task_id: str
    node_id: Optional[str] = None
    team_run_id: Optional[str] = None
    timestamp: str = Field(default_factory=_now_iso)
    actor_role: AgentRole
    event_type: str  # task.started, node.dispatched, team.delegated, team.completed, etc.
    payload: dict[str, Any] = Field(default_factory=dict)
    state_before: Optional[TaskStatus] = None
    state_after: Optional[TaskStatus] = None
    trace_id: str = Field(default_factory=lambda: f"trc-{uuid.uuid4().hex[:12]}")
    depth: int = 0


class TaskSpec(BaseModel):
    task_id: str = Field(default_factory=lambda: f"task-{uuid.uuid4().hex[:10]}")
    tenant_id: str = "default"
    user_id: str = "user-default"
    goal: str
    instruction_hash: str = ""
    language: str = "en"  # "en", "ne", "ne-rom"
    status: TaskStatus = TaskStatus.CREATED
    budget: BudgetLedger = Field(default_factory=BudgetLedger)
    nodes: list[TaskNode] = Field(default_factory=list)
    active_node_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    completed_at: Optional[str] = None
    version: int = 1
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.FLAT_MULTI_AGENT
    team_runs: list[DelegationRequest] = Field(default_factory=list)
    team_results: list[TeamResult] = Field(default_factory=list)
    hierarchy_depth: int = 1


class TaskResult(BaseModel):
    task_id: str
    status: TaskStatus
    summary: str
    completed_actions: list[str] = Field(default_factory=list)
    uncompleted_actions: list[str] = Field(default_factory=list)
    receipts: list[ToolReceipt] = Field(default_factory=list)
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    budget_used: BudgetLedger
    total_duration_ms: float
    verification_passed: bool
    evidence_trail: list[str] = Field(default_factory=list)
    team_results: list[TeamResult] = Field(default_factory=list)
    execution_mode: ExecutionMode = ExecutionMode.FLAT_MULTI_AGENT
