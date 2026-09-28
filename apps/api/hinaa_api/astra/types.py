"""HINA ASTRA — Core Cognitive Types & Request Envelopes.

Defines the universal request envelope, context snapshot, semantic event types,
and capability manifest schemas for the unified Astra cognitive operating system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Awaitable, Callable, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# -----------------------------------------------------------------------------
# 1. Request Envelope (§2)
# -----------------------------------------------------------------------------

class AstraAttachment(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: f"att_{uuid4().hex[:12]}")
    kind: str = "image"  # image, document, pdf, audio, code, video
    mime_type: str = "image/png"
    name: str = "attachment"
    url: str | None = None
    data_base64: str | None = None
    role: str | None = None  # user role tag (e.g. look_at_this, reference)


class TextRange(BaseModel):
    model_config = ConfigDict(extra="ignore")
    start_line: int
    end_line: int
    start_col: int = 0
    end_col: int = 0


class PreviewSelection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    component_id: str | None = None
    dom_path: str | None = None
    source_file: str | None = None
    source_line: int | None = None


class WorkspaceContext(BaseModel):
    model_config = ConfigDict(extra="ignore")
    workspace_id: str
    active_file: str | None = None
    selected_range: TextRange | None = None
    preview_selection: PreviewSelection | None = None
    project_id: str | None = None
    open_files: list[str] = Field(default_factory=list)


class ClientInfo(BaseModel):
    model_config = ConfigDict(extra="ignore")
    timezone: str = "UTC"
    locale: str = "en-US"
    surface: Literal["chat", "workspace", "mobile"] = "chat"
    client_version: str | None = None


class AstraInput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    text: str = ""
    attachments: list[AstraAttachment] = Field(default_factory=list)


class AstraRequest(BaseModel):
    """Universal Normalized Request Envelope for all Hina subsystems."""
    model_config = ConfigDict(extra="ignore")
    request_id: str = Field(default_factory=lambda: f"req_{uuid4().hex[:12]}")
    turn_id: str = Field(default_factory=lambda: f"turn_{uuid4().hex[:12]}")
    conversation_id: str
    user_id: str | None = None
    input: AstraInput
    client: ClientInfo = Field(default_factory=ClientInfo)
    workspace: WorkspaceContext | None = None
    created_at: str = Field(default_factory=_utc_now_iso)
    metadata: dict[str, Any] = Field(default_factory=dict)


# -----------------------------------------------------------------------------
# 2. Context Snapshot (§3)
# -----------------------------------------------------------------------------

class ContextTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    role: Literal["user", "assistant", "system"]
    content: str
    turn_id: str | None = None
    timestamp: str = Field(default_factory=_utc_now_iso)
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)


class ActiveEntity(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    canonical_name: str
    entity_type: str = "unknown"  # character, person, concept, location, file, asset
    domain: str | None = None     # e.g., Attack on Titan, React, Python
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    salience: float = 1.0         # 0.0 to 1.0 (decays over turns)
    confidence: float = 1.0
    first_turn: int = 1
    last_turn: int = 1


class EntityEdge(BaseModel):
    model_config = ConfigDict(extra="ignore")
    source_id: str
    target_id: str
    relation: str  # part_of, creator_of, belongs_to, reference_to, opponent_of
    weight: float = 1.0


class AstraMemory(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    kind: str = "semantic"  # episodic, semantic, preference, project, procedural, entity
    content: str
    importance: float = 0.5
    confidence: float = 1.0
    created_at: str = Field(default_factory=_utc_now_iso)
    last_used_at: str = Field(default_factory=_utc_now_iso)
    source_turn_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    kind: str  # image, document, pdf, spreadsheet, code, website, preview, diff
    mime_type: str
    title: str
    uri: str | None = None
    version: int = 1
    parent_object_id: str | None = None
    created_at: str = Field(default_factory=_utc_now_iso)


class HinaObjectReference(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str
    capability_id: str | None = None
    state: Literal["suggested", "draft", "ready", "running", "waiting", "completed", "failed"] = "ready"
    title: str = ""
    summary: str = ""


class CapabilityCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    capability_id: str
    relevance_score: float
    reason: str = ""


class ContextBudget(BaseModel):
    model_config = ConfigDict(extra="ignore")
    max_tokens: int = 8192
    allocated_tokens: int = 0
    remaining_tokens: int = 8192
    output_reserve: int = 2048


class AstraContext(BaseModel):
    """Canonical Context Snapshot constructed ONCE per turn."""
    model_config = ConfigDict(extra="ignore")
    request: AstraRequest
    conversation: dict[str, Any] = Field(default_factory=lambda: {"recent_turns": [], "summary": None})
    entities: dict[str, Any] = Field(default_factory=lambda: {"active": [], "graph": []})
    memories: list[AstraMemory] = Field(default_factory=list)
    workspace: WorkspaceContext | None = None
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    active_object: HinaObjectReference | None = None
    capabilities: list[CapabilityCandidate] = Field(default_factory=list)
    token_budget: ContextBudget = Field(default_factory=ContextBudget)
    compiled_at: str = Field(default_factory=_utc_now_iso)


# -----------------------------------------------------------------------------
# 3. Router & Execution States (§7)
# -----------------------------------------------------------------------------

class AstraRoute(str, Enum):
    CHAT = "CHAT"
    DIRECT_ACTION = "DIRECT_ACTION"
    AGENT_RUN = "AGENT_RUN"
    WORKSPACE = "WORKSPACE"
    CLARIFICATION = "CLARIFICATION"


class RouteDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")
    route: AstraRoute = AstraRoute.CHAT
    confidence: float = 1.0
    goal: str = ""
    candidate_capabilities: list[str] = Field(default_factory=list)
    reasoning: str = ""
    requires_confirmation: bool = False


# -----------------------------------------------------------------------------
# 4. Capability Manifest (§8)
# -----------------------------------------------------------------------------

CapabilityRiskLevel = Literal["local", "read_only", "external_mutation", "destructive"]
CapabilityHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


@dataclass
class AstraCapability:
    """Canonical registry entry for an Astra capability."""
    id: str
    version: str = "1.0.0"
    title: str = ""
    description: str = ""
    parameter_schema: dict[str, Any] = field(default_factory=dict)
    result_schema: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    risk_level: CapabilityRiskLevel = "read_only"
    requires_confirmation: bool = False
    supports_progress: bool = False
    supports_cancel: bool = False
    handler: CapabilityHandler | None = None


# -----------------------------------------------------------------------------
# 5. Semantic Event Stream Protocol (§16)
# -----------------------------------------------------------------------------

class AstraEvent(BaseModel):
    """Semantic Typed Event for SSE and Client UI synchronization."""
    model_config = ConfigDict(extra="ignore")
    type: str
    data: dict[str, Any] = Field(default_factory=dict)
    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex[:12]}")
    timestamp: str = Field(default_factory=_utc_now_iso)

    def to_sse(self) -> str:
        import json
        payload = json.dumps(self.model_dump(), ensure_ascii=False)
        return f"data: {payload}\n\n"
