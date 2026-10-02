"""
HINAA Memory Consolidation Engine & Conflict Resolver.

Performs the end-of-session Memory Consolidation Pass:
1. Event extraction from completed turns and runs.
2. Candidate fact extraction with entity resolution.
3. Conflict resolution & temporal supersession:
   - Detects when a new fact contradicts or overrides an older fact.
   - Marks older fact 'superseded', links superseded_by_id, and sets active status.
4. Distinguishes global profile preferences from project-specific overrides.
5. Persists consolidated facts to MemoryManagerV2.
"""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger("hinaa.cognitive.consolidation")


class MemoryConsolidator:
    """Performs semantic consolidation, conflict resolution, and supersession updates."""

    @classmethod
    def resolve_entity(cls, text: str) -> Optional[str]:
        """Resolves natural language tokens to canonical entity identifiers."""
        lowered = text.lower()
        if "hina" in lowered or "hinaa" in lowered:
            return "entity:system:hinaa"
        if "computer" in lowered or "operator" in lowered or "desktop" in lowered:
            return "entity:tool:computer_operator"
        if "browser" in lowered or "playwright" in lowered:
            return "entity:tool:browser"
        if "voice" in lowered or "audio" in lowered:
            return "entity:subsystem:voice"
        if "vrm" in lowered or "avatar" in lowered:
            return "entity:subsystem:avatar"
        return None

    @classmethod
    def detect_conflict(
        cls,
        new_fact: str,
        existing_facts: List[Any],
    ) -> Optional[Any]:
        """
        Determines if a new fact directly supersedes or contradicts an existing fact.
        E.g.: 'User prefers dark mode' vs 'User prefers light mode'.
        """
        new_low = new_fact.lower()
        pref_pattern = re.search(r"prefer(?:s)?\s+([a-zA-Z0-9_\-\s]+)", new_low)
        if not pref_pattern:
            return None

        topic = pref_pattern.group(1).strip()
        for old in existing_facts:
            old_text = getattr(old, "content", str(old)).lower()
            if "prefer" in old_text:
                # If they both mention common categories (e.g. theme, language, style)
                if any(cat in new_low and cat in old_text for cat in ["mode", "theme", "language", "voice", "model"]):
                    return old
        return None

    @classmethod
    def consolidate_turn(
        cls,
        user_id: str,
        user_text: str,
        assistant_text: str,
        memory_manager: Any,
        *,
        conversation_id: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Executes a consolidation pass after a turn/interaction.
        Returns list of newly learned or superseded memory records.
        """
        consolidated = []
        lowered = user_text.lower()

        # Check for user preference statements: "I prefer X", "My name is X", "I use X"
        pref_match = re.search(r"\b(?:i\s+prefer|i\s+like|always\s+use|my\s+name\s+is|i\s+work\s+at)\s+([^\.\n\!]{2,80})", user_text, re.IGNORECASE)
        if pref_match:
            candidate = pref_match.group(0).strip()
            # Verify if this conflicts with existing semantic facts
            existing_facts = (
                memory_manager.get_active_semantic_memories(user_id)
                if hasattr(memory_manager, "get_active_semantic_memories")
                else (memory_manager.get_active_facts(user_id) if hasattr(memory_manager, "get_active_facts") else [])
            )
            conflicting_fact = cls.detect_conflict(candidate, existing_facts)

            if conflicting_fact and hasattr(conflicting_fact, "memory_id"):
                old_id = conflicting_fact.memory_id
                superseded_by_id = str(uuid4())
                if hasattr(memory_manager, "supersede_memory"):
                    _, new_item = memory_manager.supersede_memory(
                        user_id=user_id,
                        old_id=old_id,
                        new_content=candidate,
                        source_turn_ref=conversation_id,
                    )
                    superseded_by_id = new_item.memory_id
                elif hasattr(memory_manager, "supersede_fact"):
                    memory_manager.supersede_fact(
                        old_fact_id=old_id,
                        new_fact_id=superseded_by_id,
                        new_content=candidate,
                        user_id=user_id,
                    )
                consolidated.append({
                    "action": "superseded",
                    "old_id": old_id,
                    "new_id": superseded_by_id,
                    "content": candidate,
                })
            else:
                # Store new active fact
                if hasattr(memory_manager, "remember"):
                    new_item = memory_manager.remember(
                        user_id=user_id,
                        content=candidate,
                        category="preference",
                        confidence=0.9,
                        source_turn_ref=conversation_id,
                    )
                    consolidated.append({
                        "action": "added",
                        "id": getattr(new_item, "memory_id", str(uuid4())),
                        "content": candidate,
                    })
                elif hasattr(memory_manager, "add_fact"):
                    new_item = memory_manager.add_fact(
                        user_id=user_id,
                        content=candidate,
                        category="preference",
                        confidence=0.9,
                        importance=3,
                        source_turn_ref=conversation_id,
                    )
                    consolidated.append({
                        "action": "added",
                        "id": getattr(new_item, "memory_id", str(uuid4())),
                        "content": candidate,
                    })

        # Record episodic event for significant interactions
        if any(w in lowered for w in ["open", "launch", "generate", "create", "fix", "deploy", "build"]):
            if hasattr(memory_manager, "record_event"):
                evt = memory_manager.record_event(
                    description=f"User requested: {user_text[:100]}",
                    event_type="user_action",
                    importance=2,
                    conversation_id=conversation_id,
                    project_id=project_id,
                )
                consolidated.append({
                    "action": "event_recorded",
                    "event_id": getattr(evt, "event_id", ""),
                })

        return consolidated
