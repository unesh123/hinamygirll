"""Data models and schemas for HINAA Independent Agency Engine."""

from __future__ import annotations

import enum
import time
import uuid
from typing import Any, Optional
from pydantic import BaseModel, Field


class GoalCategory(str, enum.Enum):
    RESEARCH = "research"
    MAINTENANCE = "maintenance"
    PROJECT = "project"
    LEARNING = "learning"
    CREATIVE = "creative"
    SYSTEM = "system"


class Priority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GoalStatus(str, enum.Enum):
    PROPOSED = "proposed"
    EVALUATED = "evaluated"
    APPROVED = "approved"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PermissionTier(str, enum.Enum):
    LEVEL_A_INDEPENDENT = "level_a_independent"      # Safe read-only, analysis, memory maintenance
    LEVEL_B_CONTROLLED = "level_b_controlled"        # Local dev branch, sandbox code test, workspace tools
    LEVEL_C_APPROVAL_REQUIRED = "level_c_approval"   # Consequential: external post, delete data, system config


class TaskStep(BaseModel):
    step_id: str = Field(default_factory=lambda: f"step-{uuid.uuid4().hex[:8]}")
    description: str
    tool_name: Optional[str] = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"  # "pending", "running", "completed", "failed", "skipped"
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None


class TaskPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    goal_id: str
    summary: str
    steps: list[TaskStep] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class ReflectionRecord(BaseModel):
    reflection_id: str = Field(default_factory=lambda: f"ref-{uuid.uuid4().hex[:8]}")
    goal_id: str
    original_goal: str
    category: str
    actions_taken: list[str] = Field(default_factory=list)
    success: bool
    key_learnings: list[str] = Field(default_factory=list)
    improvements: list[str] = Field(default_factory=list)
    memory_updates: list[dict[str, Any]] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class ProposedGoal(BaseModel):
    goal_id: str = Field(default_factory=lambda: f"goal-{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    category: GoalCategory
    priority: Priority = Priority.MEDIUM
    permission_tier: PermissionTier = PermissionTier.LEVEL_A_INDEPENDENT
    rationale: str = "Autonomous initiative based on current focus and priorities."
    expected_impact: float = 0.5   # 0.0 to 1.0
    resource_cost: float = 0.2     # 0.0 to 1.0
    confidence: float = 0.8        # 0.0 to 1.0
    score: float = 0.0
    status: GoalStatus = GoalStatus.PROPOSED
    created_at: float = Field(default_factory=time.time)
    plan: Optional[TaskPlan] = None
    reflection: Optional[ReflectionRecord] = None
    execution_error: Optional[str] = None

    def calculate_score(self) -> float:
        """Utility calculation: (Impact * Confidence) / (Cost + 0.1)."""
        self.score = round((self.expected_impact * self.confidence) / (self.resource_cost + 0.1), 3)
        return self.score
