from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RunStatus(str, Enum):
    QUEUED = "queued"; UNDERSTANDING = "understanding"; PLANNING = "planning"; EXECUTING = "executing"
    VERIFYING = "verifying"; COMPLETED = "completed"; FAILED = "failed"; CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"; AWAITING_CONFIRMATION = "awaiting_confirmation"


class StepState(str, Enum):
    PENDING = "pending"; READY = "ready"; AWAITING_CONFIRMATION = "awaiting_confirmation"; RUNNING = "running"
    COMPLETED = "completed"; FAILED = "failed"; SKIPPED = "skipped"; CANCELLED = "cancelled"; INTERRUPTED = "interrupted"; BLOCKED = "blocked"


class OperationType(str, Enum):
    RESPOND = "respond"; TOOL = "tool"; VERIFY = "verify"; SUMMARIZE = "summarize"; WAIT_FOR_CONFIRMATION = "wait_for_confirmation"


class IntentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    primary_intent: str = "conversation"
    goal: str
    requested_outcome: str = ""
    constraints: list[str] = Field(default_factory=list)
    required_modalities: list[str] = Field(default_factory=list)
    candidate_tools: list[str] = Field(default_factory=list)
    requires_planning: bool = False
    requires_confirmation: bool = False
    expected_response_type: str = "conversation"
    confidence: float = Field(default=0.5, ge=0, le=1)


class TurnContextItem(BaseModel):
    source_type: str
    source_id: str | None = None
    content: str
    timestamp: datetime | None = None
    priority: int = 0
    token_size: int = 0


class TurnContext(BaseModel):
    current_message: str
    items: list[TurnContextItem] = Field(default_factory=list)
    attachments: list[str] = Field(default_factory=list)
    token_estimate: int = 0


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    step_id: str = Field(default_factory=lambda: f"step_{uuid4().hex[:12]}")
    plan_id: str
    sequence: int = Field(ge=0)
    title: str
    description: str = ""
    operation_type: OperationType
    dependencies: list[str] = Field(default_factory=list)
    tool_name: str | None = None
    tool_parameters: dict[str, Any] = Field(default_factory=dict)
    status: StepState = StepState.PENDING
    attempt_count: int = 0
    maximum_attempts: int = Field(default=2, ge=1, le=5)
    timeout_seconds: float = Field(default=60, gt=0, le=600)
    requires_confirmation: bool = False
    idempotency_key: str = Field(default_factory=lambda: f"idem_{uuid4().hex}")
    result: Any = None
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None


class AgentPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_id: str = Field(default_factory=lambda: f"plan_{uuid4().hex[:12]}")
    run_id: str
    goal: str
    version: int = Field(default=1, ge=1)
    status: str = "draft"
    steps: list[PlanStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    supersedes_plan_id: str | None = None


class AgentRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    user_id: str
    conversation_id: str | None = None
    project_id: str | None = None
    status: RunStatus = RunStatus.QUEUED
    goal: str
    current_step_id: str | None = None
    provider_route: list[str] = Field(default_factory=list)
    cancellation_requested: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = None
    completed_at: datetime | None = None
    failure_code: str | None = None
    failure_message: str | None = None
    total_steps: int = 0
    completed_steps: int = 0
    replan_count: int = 0
    maximum_replans: int = 2
    maximum_steps: int = 12
    version: int = 1


class AgentEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    sequence: int = Field(ge=1)
    event_type: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    run_id: str
    conversation_id: str | None = None
    step_id: str | None = None
    tool_execution_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    correlation_id: str | None = None


class VerificationResult(BaseModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)
    corrected_response: str | None = None
    failure_code: str | None = None


LEGAL_RUN_TRANSITIONS: dict[RunStatus, set[RunStatus]] = {
    RunStatus.QUEUED: {RunStatus.UNDERSTANDING, RunStatus.CANCELLED},
    RunStatus.UNDERSTANDING: {RunStatus.PLANNING, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED},
    RunStatus.PLANNING: {RunStatus.EXECUTING, RunStatus.AWAITING_CONFIRMATION, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED},
    RunStatus.EXECUTING: {RunStatus.VERIFYING, RunStatus.AWAITING_CONFIRMATION, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED},
    RunStatus.AWAITING_CONFIRMATION: {RunStatus.EXECUTING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.VERIFYING: {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.INTERRUPTED},
    RunStatus.INTERRUPTED: {RunStatus.EXECUTING, RunStatus.CANCELLED, RunStatus.FAILED},
    RunStatus.COMPLETED: set(),
    RunStatus.FAILED: set(),
    RunStatus.CANCELLED: set(),
}

LEGAL_STEP_TRANSITIONS: dict[StepState, set[StepState]] = {
    StepState.PENDING: {StepState.READY, StepState.CANCELLED, StepState.BLOCKED},
    StepState.READY: {StepState.RUNNING, StepState.AWAITING_CONFIRMATION, StepState.CANCELLED},
    StepState.AWAITING_CONFIRMATION: {StepState.READY, StepState.CANCELLED, StepState.FAILED},
    StepState.RUNNING: {StepState.COMPLETED, StepState.FAILED, StepState.CANCELLED, StepState.INTERRUPTED},
    StepState.FAILED: {StepState.READY},
    StepState.INTERRUPTED: {StepState.READY, StepState.CANCELLED, StepState.AWAITING_CONFIRMATION},
    StepState.COMPLETED: set(),
    StepState.CANCELLED: set(),
    StepState.SKIPPED: set(),
    StepState.BLOCKED: {StepState.READY, StepState.CANCELLED},
}


def validate_run_transition(current: RunStatus, target: RunStatus) -> bool:
    if target == current:
        return True
    allowed = LEGAL_RUN_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Illegal run transition: {current.value} -> {target.value}")
    return True


def validate_step_transition(current: StepState, target: StepState) -> bool:
    if target == current:
        return True
    allowed = LEGAL_STEP_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise ValueError(f"Illegal step transition: {current.value} -> {target.value}")
    return True


class ToolObservation(BaseModel):
    model_config = ConfigDict(extra="ignore")
    tool_name: str
    call_id: str = Field(default_factory=lambda: f"call_{uuid4().hex[:8]}")
    content: Any
    provenance: str = "tool"  # "web_external", "file_system", "system", "user", "tool"
    trust: str = "untrusted"  # "trusted" | "untrusted"
    instruction_authority: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def sanitize_for_prompt(self) -> str:
        """Wrap observation with strict isolation tags and neutralize prompt injection delimiters."""
        import json
        raw_text = self.content if isinstance(self.content, str) else json.dumps(self.content, ensure_ascii=False)
        safe_text = (
            raw_text
            .replace("</external_untrusted_observation>", "[ESCAPED_TAG]")
            .replace("<|im_start|>", "[STRIPPED_IM_START]")
            .replace("<|im_end|>", "[STRIPPED_IM_END]")
            .replace("```system", "'''system")
            .replace("Human:", "[User Context]:")
            .replace("Assistant:", "[Agent Response]:")
        )
        return (
            f'<external_untrusted_observation tool="{self.tool_name}" '
            f'provenance="{self.provenance}" authority="false">\n'
            f'{safe_text}\n'
            f'</external_untrusted_observation>'
        )



