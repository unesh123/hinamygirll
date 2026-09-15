from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, Field


class MemoryScope(str, Enum):
    CONVERSATION = "conversation"
    PROJECT = "project"
    WORKSPACE = "workspace"
    USER_GLOBAL = "user_global"


class MemoryWriteAction(str, Enum):
    DISCARD = "discard"
    KEEP_EPISODIC = "keep_episodic"
    KEEP_SEMANTIC = "keep_semantic"
    KEEP_PROCEDURAL = "keep_procedural"
    KEEP_PROJECT = "keep_project"
    KEEP_ENTITY = "keep_entity"
    PROMOTE_GLOBAL = "promote_global"


class UserContinuitySnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    owner_id: str
    tenant_id: str | None = None
    preferred_name: str | None = None
    language_preferences: list[str] = Field(default_factory=lambda: ["en-US"])
    communication_style: str | None = None
    verbosity_preferences: str | None = None

    important_entities: list[dict[str, Any]] = Field(default_factory=list)
    important_projects: list[str] = Field(default_factory=list)
    recent_projects: list[str] = Field(default_factory=list)
    recurring_topics: list[str] = Field(default_factory=list)

    active_long_running_tasks: list[dict[str, Any]] = Field(default_factory=list)
    recent_conversation_ids: list[str] = Field(default_factory=list)
    recent_asset_ids: list[str] = Field(default_factory=list)
    approved_asset_ids: list[str] = Field(default_factory=list)

    persistent_preferences: list[dict[str, Any] | str] = Field(default_factory=list)
    relationship_context: dict[str, Any] = Field(default_factory=dict)

    last_interaction_at: datetime | None = None
    memory_revision: int = 1


class MemoryEvidence(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_type: str  # "entity", "project", "semantic_memory", "episodic_memory", "asset", "conversation_summary", "message"
    source_id: str | None = None
    scope: MemoryScope = MemoryScope.USER_GLOBAL
    content: str
    score: float = 0.0
    confidence: float = 1.0
    recency_turns: int = 0
    source_conversation_id: str | None = None
    source_turn_ref: str | None = None
    project_id: str | None = None
    entity_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationSummaryData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conversation_id: str
    topics: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    important_user_statements: list[str] = Field(default_factory=list)
    important_assistant_actions: list[str] = Field(default_factory=list)
    entities: list[dict[str, Any]] = Field(default_factory=list)
    assets: list[dict[str, Any]] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    tasks: list[dict[str, Any]] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    unfinished_work: list[str] = Field(default_factory=list)
    corrections: list[dict[str, Any]] = Field(default_factory=list)
    important_social_context: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime | None = None
