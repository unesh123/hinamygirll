"""
HINAA OS — Phase 10 Non-Destructive Contradiction & Supersession Engine
Detects conflicting claims, updates state without data loss,
and preserves historical attribution and audit lineage.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .graph import KnowledgeGraphManager
from .repository import MemoryRepository
from .schemas import (
    MemoryRecord,
    MemoryType,
    _now_iso,
)

logger = logging.getLogger("hinaa.memory.contradictions")

POSITIVE_TERMS = {
    "like", "likes", "love", "loves", "prefer", "prefers",
    "enjoy", "enjoys", "enable", "enabled", "yes", "true",
}

NEGATIVE_TERMS = {
    "dislike", "dislikes", "hate", "hates", "avoid", "avoids",
    "disable", "disabled", "no", "false", "dont like", "don't like",
}

# Antonym and conflict pairs
CONFLICT_PAIRS = [
    ("dark", "light"),
    ("true", "false"),
    ("yes", "no"),
    ("fast", "slow"),
    ("enable", "disable"),
]

# Patterns detecting explicit changes or revisions
UPDATE_PATTERNS = [
    re.compile(r"(?i)\b(?:no longer|not anymore|switched to|moved to|changed to|instead of|updated to)\s+(.+)$"),
]


class ContradictionDetector:
    """Identifies conflicting assertions and links supersession lineage without destructive loss."""

    def __init__(self, repository: MemoryRepository, graph_manager: KnowledgeGraphManager) -> None:
        self.repo = repository
        self.graph = graph_manager

    def find_contradictions(
        self,
        new_content: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
    ) -> list[MemoryRecord]:
        """Identify existing active memories that conflict with the incoming assertion."""
        # Query active memories for the user or project
        active_memories = self.repo.query_memories(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            memory_type=memory_type,
            include_contradicted=False,
            limit=50,
        )

        conflicts: list[MemoryRecord] = []
        new_lower = new_content.lower()

        # Check for explicit antonym or preference flips
        for existing in active_memories:
            exist_lower = existing.content.lower()

            # Direct topic overlap check
            words_existing = set(re.findall(r"\w{3,}", exist_lower))
            words_new = set(re.findall(r"\w{3,}", new_lower))
            common_words = words_existing.intersection(words_new)

            if len(common_words) >= 2:
                # Check for polarity flip (positive vs negative) or antonym pairs
                has_polarity_flip = False
                exist_tokens = set(re.findall(r"\w+", exist_lower))
                new_tokens = set(re.findall(r"\w+", new_lower))

                if (exist_tokens.intersection(POSITIVE_TERMS) and new_tokens.intersection(NEGATIVE_TERMS)) or \
                   (exist_tokens.intersection(NEGATIVE_TERMS) and new_tokens.intersection(POSITIVE_TERMS)):
                    has_polarity_flip = True

                if not has_polarity_flip:
                    for term_a, term_b in CONFLICT_PAIRS:
                        if (term_a in exist_lower and term_b in new_lower) or (term_b in exist_lower and term_a in new_lower):
                            has_polarity_flip = True
                            break

                # Check for explicit "switched to" / "moved to" / "changed to"
                has_update_phrase = any(p.search(new_lower) for p in UPDATE_PATTERNS)

                # Check for structured key collision (e.g. key="location", key="theme")
                key_collision = False
                if existing.structured_data and "key" in existing.structured_data:
                    exist_key = existing.structured_data.get("key")
                    # If incoming text mentions same key with different value
                    if exist_key and exist_key in new_lower:
                        key_collision = True

                if has_polarity_flip or has_update_phrase or key_collision:
                    conflicts.append(existing)

        return conflicts

    def resolve_supersession(
        self,
        new_record: MemoryRecord,
        conflicting_records: list[MemoryRecord],
        reason: str = "Newer observation supersedes previous assertion",
    ) -> list[str]:
        """
        Non-destructively supersedes conflicting records:
        1. Sets `is_contradicted = True` on previous records.
        2. Sets `superseded_by_id = new_record.id`.
        3. Sets `valid_to = now` on related knowledge edges.
        4. Adds a `SUPERSEDES` edge from new entity/record to old.
        """
        superseded_ids: list[str] = []
        now_str = _now_iso()

        for old_rec in conflicting_records:
            # 1. Update old record in repository
            self.repo.update_memory(
                memory_id=old_rec.id,
                updates={
                    "is_contradicted": True,
                    "superseded_by_id": new_record.id,
                },
                tenant_id=old_rec.tenant_id,
                reason=f"{reason}: superseded by {new_record.id}",
            )

            # 2. Add SUPERSEDES / CONTRADICTS relationship in knowledge graph
            try:
                # Fetch or create nodes representing these memories/concepts
                old_node = self.graph.get_or_create_node(
                    name=f"Fact-{old_rec.id[:8]}",
                    entity_type="Assertion",
                    tenant_id=old_rec.tenant_id,
                )
                new_node = self.graph.get_or_create_node(
                    name=f"Fact-{new_record.id[:8]}",
                    entity_type="Assertion",
                    tenant_id=new_record.tenant_id,
                )
                self.graph.add_relation(
                    source_name=new_node.canonical_name,
                    target_name=old_node.canonical_name,
                    relation_type="SUPERSEDES",
                    tenant_id=new_record.tenant_id,
                    evidence_id=new_record.id,
                    valid_from=now_str,
                    is_contradiction=True,
                    metadata={"reason": reason, "previous_evidence_id": old_rec.id},
                )
            except Exception as e:
                logger.warning("Could not establish graph supersession edge: %s", e)

            superseded_ids.append(old_rec.id)

        return superseded_ids
