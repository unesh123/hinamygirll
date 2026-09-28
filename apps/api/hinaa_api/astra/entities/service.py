"""HINA ASTRA — Entity Brain Service.

Coordinates entity extraction, multi-turn salience decay, and reference resolution.
Provides the central interface for the Context Compiler and Runtime.
"""

from __future__ import annotations

import logging
from typing import Any

from .extractor import EntityExtractor
from .models import EntityState
from .resolver import ReferenceResolver, ResolvedReference
from .salience import SalienceTracker

logger = logging.getLogger("hinaa.astra.entities")


class EntityBrainService:
    """Manages active entity states per conversation with salience tracking and pronoun resolution."""

    def __init__(self) -> None:
        self.extractor = EntityExtractor()
        self.salience = SalienceTracker()
        self.resolver = ReferenceResolver()
        # In-memory fast cache: conversation_id -> list[EntityState]
        self._cache: dict[str, list[EntityState]] = {}
        # Turn counter per conversation: conversation_id -> int
        self._turn_counters: dict[str, int] = {}

    def get_turn_number(self, conversation_id: str) -> int:
        return self._turn_counters.get(conversation_id, 1)

    def get_active_entities(self, conversation_id: str, top_k: int = 5) -> list[EntityState]:
        """Return the current foreground active entities for a conversation."""
        entities = self._cache.get(conversation_id, [])
        return self.salience.active_focus(entities, top_k=top_k)

    def process_turn(
        self,
        conversation_id: str,
        user_text: str,
        *,
        turn_number: int | None = None,
    ) -> list[EntityState]:
        """Ingest a new conversational turn, update entities, decay salience, and record mentions."""
        if turn_number is None:
            turn_number = self._turn_counters.get(conversation_id, 0) + 1
        self._turn_counters[conversation_id] = turn_number

        current_entities = self._cache.setdefault(conversation_id, [])

        # 1. Decay salience on existing entities
        self.salience.step_turn(current_entities, current_turn=turn_number)

        # 2. Extract entities from the user's utterance
        new_extracted = self.extractor.extract(
            user_text,
            conversation_id=conversation_id,
            turn=turn_number,
        )

        # 3. Merge or boost
        for new_ent in new_extracted:
            existing = next(
                (e for e in current_entities if e.canonical_name.lower() == new_ent.canonical_name.lower()),
                None,
            )
            if existing:
                self.salience.boost(existing, current_turn=turn_number)
                # Merge any newly discovered attributes
                existing.attributes.update(new_ent.attributes)
            else:
                current_entities.append(new_ent)

        return self.get_active_entities(conversation_id)

    def resolve_reference(self, conversation_id: str, text: str) -> ResolvedReference:
        """Resolve pronouns and deictic references in input text against the active entities."""
        active = self.get_active_entities(conversation_id)
        return self.resolver.resolve(text, active)

    def register_entity(self, conversation_id: str, entity: EntityState) -> None:
        """Explicitly register an entity into conversation context (e.g. from tool results)."""
        current_entities = self._cache.setdefault(conversation_id, [])
        existing = next(
            (e for e in current_entities if e.canonical_name.lower() == entity.canonical_name.lower()),
            None,
        )
        if existing:
            existing.salience = 1.0
            existing.last_turn = self.get_turn_number(conversation_id)
            existing.attributes.update(entity.attributes)
        else:
            current_entities.append(entity)
