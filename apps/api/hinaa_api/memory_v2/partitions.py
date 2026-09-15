from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import uuid4


class MemoryPartition(str, Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    PROJECT = "project"


@dataclass
class WorkingMemoryTurn:
    turn_id: str
    conversation_id: str
    role: str  # "user" | "assistant" | "system" | "tool"
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EpisodicMemoryEvent:
    event_id: str
    event_type: str  # e.g. "tool_executed", "decision_made", "error_resolved", "milestone_reached"
    description: str
    importance: int = 1  # 1 to 5
    conversation_id: str | None = None
    project_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SemanticMemoryItem:
    memory_id: str
    user_id: str
    content: str
    category: str = "fact"  # "fact", "preference", "constraint", "domain_knowledge"
    status: str = "active"  # "active", "superseded", "revoked", "expired"
    superseded_by_id: str | None = None
    confidence: float = 1.0
    valid_from: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    valid_until: str | None = None
    source_turn_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_temporally_valid(self) -> bool:
        if self.status != "active":
            return False
        if not self.valid_until:
            return True
        try:
            exp = datetime.fromisoformat(self.valid_until)
            return datetime.now(UTC) < exp
        except Exception:
            return True


@dataclass
class ProceduralMemoryRule:
    rule_id: str
    trigger_pattern: str  # regex or keyword trigger
    action_workflow: str
    priority: int = 0
    tool_constraints: list[str] = field(default_factory=list)
    verified: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectMemoryFact:
    fact_id: str
    project_id: str
    key: str
    value: Any
    category: str = "architecture"  # "architecture", "dependency", "decision", "milestone"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
