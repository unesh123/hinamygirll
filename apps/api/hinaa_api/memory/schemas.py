"""
HINAA OS — Phase 10 Memory & Continuous Knowledge Graph Data Models
Schemas for durable transactional memory, temporal knowledge graph,
hybrid retrieval, non-destructive contradiction detection, and continuous ingestion.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MemoryScope(str, Enum):
    USER = "user"
    PROJECT = "project"
    SYSTEM = "system"
    SESSION = "session"


class MemoryType(str, Enum):
    FACT = "fact"
    PREFERENCE = "preference"
    ENTITY = "entity"
    INSTRUCTION = "instruction"
    PROCEDURE = "procedure"
    EPISODE = "episode"


class TrustTier(str, Enum):
    VERIFIED = "verified"
    USER_EXPLICIT = "user_explicit"
    INFERRED = "inferred"
    UNVERIFIED = "unverified"
    STAGED = "staged"


class CandidateStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MemoryRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    scope: MemoryScope = MemoryScope.USER
    memory_type: MemoryType = MemoryType.FACT
    content: str
    structured_data: dict[str, Any] = Field(default_factory=dict)
    trust_tier: TrustTier = TrustTier.USER_EXPLICIT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_url: Optional[str] = None
    source_tool: Optional[str] = None
    source_turn_id: Optional[str] = None
    evidence_text: Optional[str] = None
    is_active: bool = True
    is_contradicted: bool = False
    superseded_by_id: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)
    updated_at: str = Field(default_factory=_now_iso)
    expires_at: Optional[str] = None
    embedding: Optional[list[float]] = None


class KnowledgeNode(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    scope: MemoryScope = MemoryScope.USER
    entity_type: str = "Concept"  # e.g. Person, Project, Technology, Location, Concept
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=_now_iso)
    valid_from: str = Field(default_factory=_now_iso)
    valid_to: Optional[str] = None


class KnowledgeEdge(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    source_id: str
    target_id: str
    relation_type: str = "RELATED_TO"  # e.g. PREFERS, WORKS_ON, LOCATED_IN, USES, CONTRADICTS, SUPERSEDES
    evidence_id: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    valid_from: str = Field(default_factory=_now_iso)
    valid_to: Optional[str] = None
    is_contradiction: bool = False
    superseded_by: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class IngestionCandidate(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    candidate_fact: str
    source_url: Optional[str] = None
    source_tool: Optional[str] = None
    raw_evidence: str = ""
    extracted_entities: list[dict[str, str]] = Field(default_factory=list)
    trust_tier: TrustTier = TrustTier.STAGED
    status: CandidateStatus = CandidateStatus.PENDING
    review_notes: Optional[str] = None
    created_at: str = Field(default_factory=_now_iso)


class MemoryEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "default"
    event_type: str  # create, update, delete, supersede, review, purge
    target_id: str
    target_type: str  # memory, node, edge, candidate
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=_now_iso)


class HybridSearchResult(BaseModel):
    record: MemoryRecord
    score: float
    lexical_score: float = 0.0
    semantic_score: float = 0.0
    graph_score: float = 0.0
    matched_terms: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class MemoryStats(BaseModel):
    total_memories: int = 0
    active_memories: int = 0
    contradicted_memories: int = 0
    total_nodes: int = 0
    total_edges: int = 0
    pending_candidates: int = 0
    db_size_bytes: int = 0
    db_path: str = ""


# ---------------------------------------------------------------------------
# API Request & Response Schemas
# ---------------------------------------------------------------------------

class CreateMemoryRequest(BaseModel):
    content: str
    tenant_id: str = "default"
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    scope: MemoryScope = MemoryScope.USER
    memory_type: MemoryType = MemoryType.FACT
    structured_data: dict[str, Any] = Field(default_factory=dict)
    trust_tier: TrustTier = TrustTier.USER_EXPLICIT
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_url: Optional[str] = None
    source_tool: Optional[str] = None
    evidence_text: Optional[str] = None
    expires_at: Optional[str] = None


class UpdateMemoryRequest(BaseModel):
    content: Optional[str] = None
    structured_data: Optional[dict[str, Any]] = None
    confidence: Optional[float] = None
    is_active: Optional[bool] = None
    expires_at: Optional[str] = None
    reason: Optional[str] = None


class MemorySearchRequest(BaseModel):
    query: str
    tenant_id: str = "default"
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    scope: Optional[MemoryScope] = None
    memory_type: Optional[MemoryType] = None
    include_contradicted: bool = False
    limit: int = Field(default=10, ge=1, le=100)
    token_budget: Optional[int] = Field(default=2048, ge=64, le=16384)


class MemorySearchResponse(BaseModel):
    query: str
    results: list[HybridSearchResult]
    total_found: int
    token_budget_used: int
    truncated: bool = False


class MemoryExportRequest(BaseModel):
    tenant_id: str = "default"
    user_id: Optional[str] = None
    project_id: Optional[str] = None
    scope: Optional[MemoryScope] = None
    format: str = Field(default="json", pattern="^(json|csv)$")


class ReviewCandidateRequest(BaseModel):
    decision: str = Field(pattern="^(approve|reject)$")
    review_notes: Optional[str] = None
    promoted_scope: Optional[MemoryScope] = MemoryScope.USER
    promoted_type: Optional[MemoryType] = MemoryType.FACT


class GraphQueryRequest(BaseModel):
    tenant_id: str = "default"
    entity_name: Optional[str] = None
    entity_type: Optional[str] = None
    max_depth: int = Field(default=2, ge=1, le=3)
    max_nodes: int = Field(default=30, ge=1, le=50)
    as_of_date: Optional[str] = None


class GraphResponse(BaseModel):
    nodes: list[KnowledgeNode]
    edges: list[KnowledgeEdge]
    total_nodes: int
    total_edges: int
