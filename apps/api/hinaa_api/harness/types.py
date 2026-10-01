"""
HINAA Frontier Agent Harness - Domain Types and Protocols.

Architectural implementation modeled on OpenAI Codex Core / ThreadManager:
1. AgentSession: Rich session state (model, instructions, capabilities, environment, history, ancestry).
2. EnvironmentState: First-class environment state separated from model cognition.
3. CapabilityPermissions: Granular capability-scoped permissions (filesystem, network, process, browser).
4. AgentGraph & AgentNode: Persistent multi-agent hierarchical tree with recursion limits.
5. LocalAgentMessageBoard: Intra-agent messaging, delegation, and broadcast.
6. EffectiveConfig: Cascading configuration resolver.
7. ContextWindowIdentity: Protocol-level context window tracking and compaction lineage.
8. WorldModel & VerifierReport: Cognitive world model and autonomous verification contracts.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from uuid import uuid4
from pydantic import BaseModel, ConfigDict, Field


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MAX = "max"
    PRO = "pro"


class SessionStatus(str, Enum):
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPACTING = "compacting"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(str, Enum):
    ROOT = "root"
    RESEARCHER = "researcher"
    CODER = "coder"
    CREATIVE = "creative"
    VERIFIER = "verifier"
    CRITIC = "critic"
    SECURITY = "security"
    BROWSER = "browser"


# ---------------------------------------------------------------------------
# 1. Capability-Scoped Permissions & Security Policies
# ---------------------------------------------------------------------------

class CapabilityPermissions(BaseModel):
    """
    Granular capability-based access control rather than binary root/admin.
    Directly addresses CVE-2025-59532 / GHSA-w5fx-fh39-j5rw threat models.
    """
    model_config = ConfigDict(extra="ignore")

    filesystem_read: List[str] = Field(default_factory=lambda: ["."])
    filesystem_write: List[str] = Field(default_factory=lambda: ["."])
    network_domains: List[str] = Field(default_factory=list)
    network_enabled: bool = False
    process_types: List[str] = Field(default_factory=lambda: ["python", "node", "git", "npm", "pytest"])
    browser_origins: List[str] = Field(default_factory=list)
    github_repos: List[str] = Field(default_factory=list)
    cloud_resources: List[str] = Field(default_factory=list)
    requires_approval_for: List[str] = Field(
        default_factory=lambda: ["filesystem.write_outside_root", "network.wildcard", "process.sudo", "credential.export"]
    )
    is_full_access: bool = False


class NetworkSandboxPolicy(BaseModel):
    """
    Controls network egress across all network layers (HTTP, DNS, TCP, UDP, IPC).
    Prevents covert DNS exfiltration or sandbox tunneling.
    """
    model_config = ConfigDict(extra="ignore")

    allowed_domains: List[str] = Field(default_factory=lambda: ["github.com", "api.github.com", "pypi.org", "npmjs.org"])
    blocked_protocols: List[str] = Field(default_factory=lambda: ["raw_tcp", "udp", "unfiltered_dns"])
    dns_allowlist_only: bool = True
    egress_enabled: bool = True
    audit_all_requests: bool = True


# ---------------------------------------------------------------------------
# 2. First-Class Environment State
# ---------------------------------------------------------------------------

class EnvironmentState(BaseModel):
    """
    Independent Environment State distinct from Model Cognition.
    MODEL STATE != ENVIRONMENT STATE.
    """
    model_config = ConfigDict(extra="ignore")

    environment_id: str = Field(default_factory=lambda: f"env_{uuid4().hex[:10]}")
    cwd: str = Field(default=".")
    workspace_roots: List[str] = Field(default_factory=lambda: ["."])
    network_policy: NetworkSandboxPolicy = Field(default_factory=NetworkSandboxPolicy)
    shell_runtime: str = "auto"  # "kali-linux-wsl" | "powershell" | "cmd" | "auto"
    shell_snapshot_id: Optional[str] = None
    active_processes: List[int] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)

    def canonical_roots(self) -> List[str]:
        """Return realpath canonicalized roots for boundary checks."""
        return [os.path.realpath(os.path.abspath(r)) for r in self.workspace_roots]


# ---------------------------------------------------------------------------
# 3. Context Window Identity & Compaction Lineage
# ---------------------------------------------------------------------------

class ContextWindowIdentity(BaseModel):
    """
    Tracks context window generation and compaction at protocol level.
    """
    model_config = ConfigDict(extra="ignore")

    context_window_id: str = Field(default_factory=lambda: f"ctx_{uuid4().hex[:12]}")
    window_number: int = 1
    turn_started_at: datetime = Field(default_factory=_utc_now)
    compaction_generation: int = 0
    token_usage_estimated: int = 0
    token_budget_max: int = 200_000
    tool_namespaces: List[str] = Field(default_factory=list)
    fork_origin_id: Optional[str] = None


class CompactionItem(BaseModel):
    """
    Durable checkpoint produced by background compaction worker.
    Retains goals, machine state, active tools, and opaque reasoning continuity.
    """
    model_config = ConfigDict(extra="ignore")

    compaction_id: str = Field(default_factory=lambda: f"compact_{uuid4().hex[:10]}")
    generation: int
    created_at: datetime = Field(default_factory=_utc_now)
    summary_text: str
    active_goals: List[str] = Field(default_factory=list)
    unresolved_tasks: List[str] = Field(default_factory=list)
    preserved_state_refs: List[str] = Field(default_factory=list)
    environment_snapshot: Dict[str, Any] = Field(default_factory=dict)
    opaque_reasoning_token_ref: Optional[str] = None


# ---------------------------------------------------------------------------
# 4. Multi-Agent Graph & Intra-Agent Message Board
# ---------------------------------------------------------------------------

class AgentNode(BaseModel):
    """
    Node in the persistent hierarchical agent execution graph.
    """
    model_config = ConfigDict(extra="ignore")

    node_id: str = Field(default_factory=lambda: f"ag_{uuid4().hex[:10]}")
    parent_id: Optional[str] = None
    role: AgentRole = AgentRole.ROOT
    status: SessionStatus = SessionStatus.IDLE
    session_id: str
    depth: int = 0
    children: List[str] = Field(default_factory=list)
    tool_permissions: List[str] = Field(default_factory=list)
    budget_tokens: int = 50_000
    spent_tokens: int = 0
    result_refs: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utc_now)


class AgentMessage(BaseModel):
    """
    Message routed across agents via LocalAgentMessageBoard.
    """
    model_config = ConfigDict(extra="ignore")

    message_id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:10]}")
    sender_id: str
    recipient_id: str  # "broadcast" or target node_id
    message_type: str  # "task_assignment" | "status_update" | "followup_task" | "critic_feedback" | "tool_result"
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=_utc_now)
    handled: bool = False


# ---------------------------------------------------------------------------
# 5. Rich AgentSession (Model + Environment + Capabilities + Ancestry)
# ---------------------------------------------------------------------------

class ForkInfo(BaseModel):
    forked_from_thread_id: str
    forked_from_ordinal_exclusive: int
    created_at: datetime = Field(default_factory=_utc_now)


class AgentSession(BaseModel):
    """
    The complete AgentSession state - much richer than a flat message list.
    """
    model_config = ConfigDict(extra="ignore")

    session_id: str = Field(default_factory=lambda: f"sess_{uuid4().hex[:12]}")
    thread_id: str
    parent_thread_id: Optional[str] = None
    fork_info: Optional[ForkInfo] = None
    model_name: str = "agnes-2.5-flash"
    provider_mode: str = "agent-router"
    reasoning_effort: ReasoningEffort = ReasoningEffort.MEDIUM
    status: SessionStatus = SessionStatus.IDLE

    # Instruction composition pieces
    base_instructions: str = ""
    developer_instructions: str = ""
    skills_catalog: List[str] = Field(default_factory=list)
    dynamic_tools: List[str] = Field(default_factory=list)

    # State pillars
    permissions: CapabilityPermissions = Field(default_factory=CapabilityPermissions)
    environment: EnvironmentState = Field(default_factory=EnvironmentState)
    context_window: ContextWindowIdentity = Field(default_factory=ContextWindowIdentity)
    compactions: List[CompactionItem] = Field(default_factory=list)

    # Multi-agent linkage
    graph_node_id: Optional[str] = None

    # Metrics & telemetry
    metrics: Dict[str, Any] = Field(default_factory=lambda: {
        "tokens_input": 0,
        "tokens_output": 0,
        "turns_completed": 0,
        "tool_calls_count": 0,
        "duration_seconds": 0.0,
    })

    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# 6. Event Sourced Thread Lifecycle
# ---------------------------------------------------------------------------

class TurnItemType(str, Enum):
    USER_MESSAGE = "user_message"
    AGENT_MESSAGE = "agent_message"
    TOOL_EXECUTION = "tool_execution"
    APPROVAL_REQUEST = "approval_request"
    DIFF = "diff"
    ARTIFACT = "artifact"
    COMPACTION = "compaction"
    VERIFICATION = "verification"
    AGENT_SPAWN = "agent_spawn"
    ERROR = "error"


class TurnItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id: str = Field(default_factory=lambda: f"item_{uuid4().hex[:10]}")
    item_type: TurnItemType
    payload: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "agent"  # "system" | "user" | "agent" | "tool" | "external"
    trust_level: str = "trusted"
    timestamp: datetime = Field(default_factory=_utc_now)


class Turn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    turn_id: str = Field(default_factory=lambda: f"turn_{uuid4().hex[:10]}")
    ordinal: int
    items: List[TurnItem] = Field(default_factory=list)
    status: str = "completed"
    created_at: datetime = Field(default_factory=_utc_now)
    completed_at: Optional[datetime] = None


class HinaThread(BaseModel):
    model_config = ConfigDict(extra="ignore")

    thread_id: str = Field(default_factory=lambda: f"thr_{uuid4().hex[:12]}")
    project_id: str = "default-project"
    user_id: str = "default-user"
    parent_thread_id: Optional[str] = None
    title: str = "Autonomous Hina Session"
    turns: List[Turn] = Field(default_factory=list)
    active_session: Optional[AgentSession] = None
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)


# ---------------------------------------------------------------------------
# 7. World Model & Autonomous Verifier Contracts
# ---------------------------------------------------------------------------

class WorldEntity(BaseModel):
    id: str
    kind: str  # "person" | "project" | "repo" | "environment" | "task" | "artifact" | "deployment"
    name: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class WorldModel(BaseModel):
    """
    Explicit World Model tracking real entities, repositories, tasks, and deployments.
    Allows HINA to reason about world-state rather than just textual strings.
    """
    model_config = ConfigDict(extra="ignore")

    entities: Dict[str, WorldEntity] = Field(default_factory=dict)
    dependencies: List[Dict[str, str]] = Field(default_factory=list)
    last_synchronized_at: datetime = Field(default_factory=_utc_now)

    def register_entity(self, kind: str, name: str, metadata: Optional[Dict[str, Any]] = None) -> WorldEntity:
        eid = f"{kind}:{name.lower().replace(' ', '_')}"
        ent = WorldEntity(id=eid, kind=kind, name=name, metadata=metadata or {})
        self.entities[eid] = ent
        return ent


class VerifierReport(BaseModel):
    """
    Result of autonomous verification loop:
    candidate -> verifier -> pass/fail -> repair
    """
    model_config = ConfigDict(extra="ignore")

    valid: bool
    score: float = 1.0  # 0.0 to 1.0
    issues: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    security_clean: bool = True
    test_results: Dict[str, Any] = Field(default_factory=dict)
    suggested_repairs: List[str] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=_utc_now)
