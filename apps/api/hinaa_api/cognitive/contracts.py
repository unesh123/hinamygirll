"""
HINAA Cognitive Kernel Contracts.

Canonical types for the Frontier AI Operating System:
- CognitiveRun: The canonical state machine object shared across Web, Mobile, Desktop, Voice.
- WorldState: The operational multi-surface world model.
- HinaEvent: Canonical event bus envelope.
- TaskGraph & EvidenceGraph: Plan decomposition and evidence provenance.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# 1. World State Model
# ---------------------------------------------------------------------------

class UserState(BaseModel):
    user_id: str
    tenant_id: str = "default"
    role: str = "owner"
    preferred_language: str = "en"
    active_preferences: Dict[str, Any] = Field(default_factory=dict)


class DeviceState(BaseModel):
    device_id: str = "local-host"
    platform: str = "windows"  # "windows" | "macos" | "linux" | "mobile" | "cloud"
    active_window: str = "Desktop"
    active_process: str = "unknown"
    screen_width: int = 1920
    screen_height: int = 1080
    connected_devices: List[str] = Field(default_factory=list)


class ApplicationState(BaseModel):
    active_app: str = "none"
    running_apps: List[str] = Field(default_factory=list)
    focused_element: Optional[str] = None
    media_playing: bool = False
    media_track: Optional[str] = None


class BrowserState(BaseModel):
    active_url: Optional[str] = None
    open_tabs: List[str] = Field(default_factory=list)
    dom_title: Optional[str] = None
    is_scraping: bool = False


class FileSystemState(BaseModel):
    working_directory: str = "."
    modified_files: List[str] = Field(default_factory=list)
    active_project_id: Optional[str] = None


class ApprovalState(BaseModel):
    required: bool = False
    status: str = "none"  # "none" | "pending" | "granted" | "rejected"
    pending_token: Optional[str] = None
    target_action: Optional[str] = None
    target_resource: Optional[str] = None


class EnvironmentState(BaseModel):
    timestamp: float = Field(default_factory=time.time)
    online: bool = True
    cpu_percent: float = 0.0
    memory_percent: float = 0.0


class WorldState(BaseModel):
    """Canonical operational world state across physical machine, browser, and runtime."""
    model_config = ConfigDict(extra="ignore")

    user: UserState
    device: DeviceState = Field(default_factory=DeviceState)
    app: ApplicationState = Field(default_factory=ApplicationState)
    browser: BrowserState = Field(default_factory=BrowserState)
    filesystem: FileSystemState = Field(default_factory=FileSystemState)
    approval: ApprovalState = Field(default_factory=ApprovalState)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    active_task_id: Optional[str] = None
    active_agent_ids: List[str] = Field(default_factory=list)
    artifact_ids: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 2. Goal, Task Graph & Plan
# ---------------------------------------------------------------------------

class Goal(BaseModel):
    goal_id: str = Field(default_factory=lambda: f"goal_{uuid4().hex[:10]}")
    text: str
    goal_type: str = "general"  # "conversation" | "research" | "computer_use" | "coding" | "artifact"
    constraints: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)


class TaskNode(BaseModel):
    node_id: str = Field(default_factory=lambda: f"node_{uuid4().hex[:8]}")
    title: str
    action: str
    tool_or_skill: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    depends_on: List[str] = Field(default_factory=list)
    status: str = "pending"  # "pending" | "running" | "completed" | "failed" | "skipped"
    result: Optional[Any] = None
    error: Optional[str] = None
    attempt_count: int = 0
    idempotency_key: str = Field(default_factory=lambda: f"idem_{uuid4().hex[:12]}")


class TaskGraph(BaseModel):
    graph_id: str = Field(default_factory=lambda: f"graph_{uuid4().hex[:10]}")
    nodes: List[TaskNode] = Field(default_factory=list)
    current_node_id: Optional[str] = None
    version: int = 1


# ---------------------------------------------------------------------------
# 3. Evidence Graph & Lineage
# ---------------------------------------------------------------------------

class EvidenceNode(BaseModel):
    evidence_id: str = Field(default_factory=lambda: f"ev_{uuid4().hex[:8]}")
    claim: str
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    passage: Optional[str] = None
    screenshot_asset: Optional[str] = None
    confidence: float = 1.0
    verified: bool = True
    timestamp: float = Field(default_factory=time.time)


class EvidenceGraph(BaseModel):
    nodes: List[EvidenceNode] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# 4. Capabilities, Policy & Budget
# ---------------------------------------------------------------------------

class CapabilitySet(BaseModel):
    allowed_tools: List[str] = Field(default_factory=list)
    allowed_skills: List[str] = Field(default_factory=list)
    model_family: str = "auto"
    enable_desktop_actuation: bool = True
    enable_browser_playwright: bool = True


class Budget(BaseModel):
    max_steps: int = 30
    max_wall_time_seconds: float = 180.0
    max_cost_units: float = 1.0
    consumed_steps: int = 0
    consumed_wall_time_seconds: float = 0.0
    consumed_cost_units: float = 0.0


class PolicySnapshot(BaseModel):
    policy_id: str = "default_policy"
    require_confirmation_for: List[str] = Field(
        default_factory=lambda: [
            "send_message",
            "purchase",
            "delete_file",
            "publish",
            "deploy",
            "change_credentials",
        ]
    )
    tenant_isolation_enabled: bool = True


class VerificationState(BaseModel):
    passed: bool = True
    confidence: float = 1.0
    issues: List[str] = Field(default_factory=list)
    replan_required: bool = False
    replan_guidance: Optional[str] = None


# ---------------------------------------------------------------------------
# 5. Canonical CognitiveRun
# ---------------------------------------------------------------------------

class CognitiveRun(BaseModel):
    """The unified cognitive state machine object shared across Web, Mobile, Desktop, Voice."""
    model_config = ConfigDict(extra="ignore")

    run_id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    tenant_id: str = "default"
    user_id: str
    session_id: str

    goal: Goal
    world_state: WorldState
    plan: TaskGraph = Field(default_factory=TaskGraph)

    active_agents: List[str] = Field(default_factory=list)
    capabilities: CapabilitySet = Field(default_factory=CapabilitySet)
    budget: Budget = Field(default_factory=Budget)
    policy: PolicySnapshot = Field(default_factory=PolicySnapshot)

    evidence: EvidenceGraph = Field(default_factory=EvidenceGraph)
    artifacts: List[Dict[str, Any]] = Field(default_factory=list)
    verification: VerificationState = Field(default_factory=VerificationState)

    status: str = "initialized"  # "initialized" | "planning" | "executing" | "verifying" | "completed" | "failed" | "interrupted"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


# ---------------------------------------------------------------------------
# 6. Canonical Event Envelope (HinaEvent)
# ---------------------------------------------------------------------------

class HinaEvent(BaseModel):
    """Universal event envelope emitted to Web UI, Mobile, Desktop Companion, and Replay Engine."""
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    run_id: str
    session_id: str
    sequence: int = 1
    event_type: str  # e.g. "turn.started", "world.updated", "plan.generated", "tool.executed", "run.completed"
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    tenant_id: str = "default"
    user_id: str
    device_id: Optional[str] = None
    agent_id: Optional[str] = None

    action: Optional[str] = None
    resource: Optional[str] = None
    policy_decision: Optional[str] = None
    approval_token: Optional[str] = None

    pre_state_hash: Optional[str] = None
    post_state_hash: Optional[str] = None

    payload: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# 7. Cross-Session Continuity Summary
# ---------------------------------------------------------------------------

class SessionSummary(BaseModel):
    """Emitted at session finalization to bootstrap subsequent sessions without transcript bloat."""
    session_id: str
    user_id: str
    project_id: Optional[str] = None
    summary_text: str
    key_decisions: List[str] = Field(default_factory=list)
    completed_tasks: List[str] = Field(default_factory=list)
    unresolved_items: List[str] = Field(default_factory=list)
    learned_facts: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
