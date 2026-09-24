"""HINA ASTRA — Entity Brain Data Models.

Defines rich representation for tracked entities, mentions, and relationships.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class EntityMention:
    """An explicit or resolved mention of an entity in a turn."""
    turn_id: str
    surface_text: str
    canonical_name: str
    confidence: float = 1.0
    is_implicit: bool = False  # True if resolved from pronoun/deictic reference
    char_start: int = 0
    char_end: int = 0


@dataclass
class EntityEdge:
    """A semantic relationship between two entities."""
    source_id: str
    target_id: str
    relation: str  # e.g., "franchise_of", "creator_of", "part_of", "opponent_of"
    weight: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class EntityState:
    """The canonical state of an active entity in a conversation."""
    id: str = field(default_factory=lambda: f"ent_{uuid4().hex[:12]}")
    conversation_id: str = ""
    canonical_name: str = ""
    entity_type: str = "character"  # character, person, concept, technology, file, asset, location
    domain: str | None = None       # e.g., "Attack on Titan", "TypeScript", "Tokyo"
    aliases: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)  # {"gender": "female", ...}
    salience: float = 1.0           # 0.0 to 1.0
    confidence: float = 1.0
    first_turn: int = 1
    last_turn: int = 1
    mention_count: int = 1
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "canonical_name": self.canonical_name,
            "entity_type": self.entity_type,
            "domain": self.domain,
            "aliases": self.aliases,
            "attributes": self.attributes,
            "salience": round(self.salience, 3),
            "confidence": round(self.confidence, 3),
            "first_turn": self.first_turn,
            "last_turn": self.last_turn,
            "mention_count": self.mention_count,
        }
