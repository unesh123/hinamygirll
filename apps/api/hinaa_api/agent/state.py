from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class GoalType(str, Enum):
    INFORMATIONAL = "informational"
    MULTI_STEP_RESEARCH = "multi_step_research"
    CREATIVE_GENERATION = "creative_generation"
    SYSTEM_AUTOMATION = "system_automation"
    VERIFICATION = "verification"


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class AgentGoal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(default_factory=lambda: f"goal_{uuid.uuid4().hex[:10]}")
    user_id: str
    conversation_id: str | None = None
    session_id: str | None = None
    text: str
    goal_type: GoalType = GoalType.INFORMATIONAL
    constraints: list[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)


class StepResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step_id: str
    output: Any = None
    observations: str = ""
    latency_ms: int = 0
    is_untrusted_content: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    model_config = ConfigDict(extra="ignore")

    step_id: str = Field(default_factory=lambda: f"step_{uuid.uuid4().hex[:8]}")
    title: str
    skill_id: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    depends_on: list[str] = Field(default_factory=list)
    risk_tier: int = 0  # 0: observe, 1: reversible, 2: external effect, 3: sensitive
    status: StepStatus = StepStatus.PENDING
    result: StepResult | None = None
    error: str | None = None
    idempotency_key: str = Field(default_factory=lambda: f"idem_{uuid.uuid4().hex[:12]}")
    retry_count: int = 0
    max_retries: int = 2


class VerificationReport(BaseModel):
    model_config = ConfigDict(extra="ignore")

    passed: bool = True
    confidence: float = 1.0  # 0.0 to 1.0
    evidence: list[str] = Field(default_factory=list)
    unresolved_issues: list[str] = Field(default_factory=list)
    needs_replan: bool = False
    replan_guidance: str | None = None


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="ignore")

    goal_id: str
    final_answer: str
    spoken_text: str | None = None
    confidence: float = 0.95
    evidence: list[str] = Field(default_factory=list)
    steps_executed: list[PlanStep] = Field(default_factory=list)
    replans_count: int = 0
    total_latency_ms: int = 0
    artifacts: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None
    # Structured lifecycle breadcrumbs make long-running runs diagnosable
    # without exposing private chain-of-thought.  Consumers can persist these
    # events or stream them to the activity panel.
    audit_events: list[dict[str, Any]] = Field(default_factory=list)
    cost_units: int = 0
    # ``cost_units`` is the local execution budget consumed (one unit per
    # executor attempt). It is deliberately not presented as provider spend;
    # providers may expose billing data separately in ``provider_cost``.
    provider_cost: float | None = None
    attempts: int = 0
    status: str = "completed"
