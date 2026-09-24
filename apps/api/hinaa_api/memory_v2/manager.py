from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from .partitions import (
    EpisodicMemoryEvent,
    MemoryPartition,
    ProceduralMemoryRule,
    ProjectMemoryFact,
    SemanticMemoryItem,
    WorkingMemoryTurn,
)


class MemoryManagerV2:
    """Unified coordinator for HINAA Memory v2.

    Maintains clean partition isolation between:
    - Working Memory (exact dialogue turns per conversation)
    - Episodic Memory (append-only timeline of discrete events & actions)
    - Semantic Memory (facts & preferences with supersession and temporal validity)
    - Procedural Memory (workflow methods, recipes, and tool usage rules)
    - Project Memory (architectural context, key/value decisions per project)
    """

    def __init__(self, max_working_turns_per_convo: int = 50) -> None:
        self.max_working_turns = max_working_turns_per_convo
        self._working: dict[str, list[WorkingMemoryTurn]] = defaultdict(list)
        self._episodic: list[EpisodicMemoryEvent] = []
        self._semantic: dict[str, dict[str, SemanticMemoryItem]] = defaultdict(dict)  # user_id -> id -> item
        self._procedural: list[ProceduralMemoryRule] = []
        self._project: dict[str, dict[str, ProjectMemoryFact]] = defaultdict(dict)  # project_id -> key -> fact

    # -------------------------------------------------------------------------
    # 1. Working Memory
    # -------------------------------------------------------------------------

    def add_turn(
        self,
        conversation_id: str,
        role: str,
        content: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> WorkingMemoryTurn:
        turn = WorkingMemoryTurn(
            turn_id=str(uuid4()),
            conversation_id=conversation_id,
            role=role,
            content=content,
            metadata=metadata or {},
        )
        turns = self._working[conversation_id]
        turns.append(turn)
        if len(turns) > self.max_working_turns:
            self._working[conversation_id] = turns[-self.max_working_turns :]
        return turn

    def get_working_turns(
        self,
        conversation_id: str,
        limit: int = 20,
    ) -> list[WorkingMemoryTurn]:
        turns = self._working.get(conversation_id, [])
        return turns[-limit:]

    def clear_working_memory(self, conversation_id: str) -> None:
        self._working.pop(conversation_id, None)

    # -------------------------------------------------------------------------
    # 2. Episodic Memory
    # -------------------------------------------------------------------------

    def record_event(
        self,
        description: str,
        *,
        event_type: str = "interaction",
        importance: int = 1,
        conversation_id: str | None = None,
        project_id: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> EpisodicMemoryEvent:
        event = EpisodicMemoryEvent(
            event_id=str(uuid4()),
            event_type=event_type,
            description=description.strip(),
            importance=max(1, min(5, importance)),
            conversation_id=conversation_id,
            project_id=project_id,
            details=details or {},
        )
        self._episodic.append(event)
        return event

    def get_events(
        self,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        min_importance: int = 1,
        limit: int = 50,
    ) -> list[EpisodicMemoryEvent]:
        matching = []
        for e in self._episodic:
            if conversation_id and e.conversation_id != conversation_id:
                continue
            if project_id and e.project_id != project_id:
                continue
            if e.importance < min_importance:
                continue
            matching.append(e)
        return matching[-limit:]

    # -------------------------------------------------------------------------
    # 3. Semantic Memory & Supersession
    # -------------------------------------------------------------------------

    def remember(
        self,
        user_id: str,
        content: str,
        *,
        category: str = "fact",
        valid_until: str | None = None,
        confidence: float = 1.0,
        source_turn_ref: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SemanticMemoryItem:
        mem_id = str(uuid4())
        item = SemanticMemoryItem(
            memory_id=mem_id,
            user_id=user_id,
            content=content.strip(),
            category=category,
            status="active",
            valid_until=valid_until,
            confidence=confidence,
            source_turn_ref=source_turn_ref,
            metadata=metadata or {},
        )
        self._semantic[user_id][mem_id] = item
        return item

    def supersede_memory(
        self,
        user_id: str,
        old_id: str,
        new_content: str,
        *,
        new_category: str | None = None,
        valid_until: str | None = None,
        source_turn_ref: str | None = None,
    ) -> tuple[SemanticMemoryItem, SemanticMemoryItem]:
        """Supersede an obsolete or updated memory with a new fact.

        Points old_memory -> new_memory and marks old_memory as superseded.
        """
        user_mems = self._semantic.get(user_id, {})
        old_item = user_mems.get(old_id)
        if old_item is None:
            raise KeyError(f"Memory {old_id} not found for user {user_id}")

        new_item = self.remember(
            user_id=user_id,
            content=new_content,
            category=new_category or old_item.category,
            valid_until=valid_until,
            source_turn_ref=source_turn_ref,
        )

        old_item.status = "superseded"
        old_item.superseded_by_id = new_item.memory_id

        # Record episodic event for auditability
        self.record_event(
            description=f"Superseded memory '{old_item.content}' -> '{new_item.content}'",
            event_type="memory_superseded",
            importance=2,
            details={"old_id": old_id, "new_id": new_item.memory_id},
        )

        return old_item, new_item

    def get_active_semantic_memories(
        self,
        user_id: str,
        category: str | None = None,
    ) -> list[SemanticMemoryItem]:
        user_mems = self._semantic.get(user_id, {})
        active: list[SemanticMemoryItem] = []
        for item in user_mems.values():
            if not item.is_temporally_valid:
                continue
            if category and item.category != category:
                continue
            active.append(item)
        return active

    def forget(self, user_id: str, memory_id: str) -> bool:
        user_mems = self._semantic.get(user_id, {})
        item = user_mems.get(memory_id)
        if item is None:
            return False
        item.status = "revoked"
        return True

    # -------------------------------------------------------------------------
    # 4. Procedural Memory
    # -------------------------------------------------------------------------

    def add_rule(
        self,
        trigger_pattern: str,
        action_workflow: str,
        *,
        priority: int = 0,
        tool_constraints: list[str] | None = None,
        verified: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> ProceduralMemoryRule:
        rule = ProceduralMemoryRule(
            rule_id=str(uuid4()),
            trigger_pattern=trigger_pattern,
            action_workflow=action_workflow,
            priority=priority,
            tool_constraints=tool_constraints or [],
            verified=verified,
            metadata=metadata or {},
        )
        self._procedural.append(rule)
        self._procedural.sort(key=lambda r: r.priority, reverse=True)
        return rule

    def match_rules(self, text: str) -> list[ProceduralMemoryRule]:
        matched: list[ProceduralMemoryRule] = []
        for r in self._procedural:
            if not r.verified:
                continue
            if re.search(r.trigger_pattern, text, re.IGNORECASE):
                matched.append(r)
        return matched

    # -------------------------------------------------------------------------
    # 5. Project Memory
    # -------------------------------------------------------------------------

    def set_project_fact(
        self,
        project_id: str,
        key: str,
        value: Any,
        *,
        category: str = "architecture",
    ) -> ProjectMemoryFact:
        fact = ProjectMemoryFact(
            fact_id=str(uuid4()),
            project_id=project_id,
            key=key,
            value=value,
            category=category,
        )
        self._project[project_id][key] = fact
        return fact

    def get_project_fact(self, project_id: str, key: str) -> Any | None:
        fact = self._project.get(project_id, {}).get(key)
        return fact.value if fact else None

    def get_project_facts(
        self,
        project_id: str,
        category: str | None = None,
    ) -> list[ProjectMemoryFact]:
        facts = self._project.get(project_id, {}).values()
        if category:
            return [f for f in facts if f.category == category]
        return list(facts)

    # -------------------------------------------------------------------------
    # Cross-Partition Compilation for Prompt Context
    # -------------------------------------------------------------------------

    def compile_partition_summary(
        self,
        user_id: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        query: str = "",
    ) -> dict[str, Any]:
        """Compile an integrated view across all 5 partitions."""
        active_semantic = self.get_active_semantic_memories(user_id)
        recent_working = self.get_working_turns(conversation_id, limit=6) if conversation_id else []
        recent_events = self.get_events(conversation_id=conversation_id, project_id=project_id, limit=5)
        matched_rules = self.match_rules(query) if query else []
        proj_facts = self.get_project_facts(project_id) if project_id else []

        return {
            "working_turns_count": len(recent_working),
            "working_recent": [{"role": t.role, "content": t.content[:120]} for t in recent_working],
            "episodic_events": [e.description for e in recent_events],
            "semantic_memories": [s.content for s in active_semantic],
            "procedural_workflows": [r.action_workflow for r in matched_rules],
            "project_facts": {f.key: f.value for f in proj_facts},
        }
