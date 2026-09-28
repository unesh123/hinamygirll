"""
Hybrid Vector + Graph Memory Store for HINAA.

Implements the 4-tier Elite-Tier Agent Memory Architecture:
1. Working Memory: Short-term conversational buffer, active session context, immediate goals.
2. Episodic Memory: Vector-embedded interactions with cosine similarity, recency decay, and importance weighting.
3. Semantic Memory: Knowledge Graph of entities, attributes, and relationships with fact consolidation.
4. Procedural Memory: Tool recipes, usage patterns, and habit tracking for execution optimization.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Sequence

from ..rag.retrieval import _cosine_similarity, _deterministic_embedding


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


# ============================================================================
# Tier 1: Working Memory Buffer
# ============================================================================

@dataclass
class WorkingMemoryTurn:
    role: str
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class WorkingMemory:
    """Short-term operational buffer holding the immediate conversation context."""
    turns: list[WorkingMemoryTurn] = field(default_factory=list)
    active_goal: str | None = None
    scratchpad: dict[str, Any] = field(default_factory=dict)
    max_turns: int = 12

    def add_turn(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> None:
        self.turns.append(WorkingMemoryTurn(
            role=role,
            content=content,
            timestamp=time.time(),
            metadata=metadata or {},
        ))
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns:]

    def get_recent_history(self, limit: int = 6) -> list[dict[str, str]]:
        return [{"role": t.role, "content": t.content} for t in self.turns[-limit:]]

    def set_goal(self, goal: str | None) -> None:
        self.active_goal = goal

    def get_goal(self) -> str | None:
        return self.active_goal

    def clear(self) -> None:
        self.turns.clear()
        self.active_goal = None
        self.scratchpad.clear()


# ============================================================================
# Tier 2: Episodic Vector Memory Store
# ============================================================================

@dataclass
class Episode:
    id: str
    user_id: str
    conversation_id: str
    content: str
    vector: list[float]
    timestamp: float
    importance: float = 1.0  # Scale 1.0 to 5.0
    category: str = "interaction"
    metadata: dict[str, Any] = field(default_factory=dict)


class EpisodicVectorStore:
    """Vector-indexed episodic memory with cosine similarity and time/importance decay."""

    def __init__(self, dim: int = 128, decay_half_life_days: float = 14.0) -> None:
        self.dim = dim
        self.decay_half_life_days = decay_half_life_days
        self._episodes: list[Episode] = []

    def record_episode(
        self,
        user_id: str,
        conversation_id: str,
        content: str,
        importance: float = 1.0,
        category: str = "interaction",
        metadata: dict[str, Any] | None = None,
        custom_vector: list[float] | None = None,
    ) -> Episode:
        vec = custom_vector or _deterministic_embedding(content, self.dim)
        episode = Episode(
            id=str(uuid.uuid4()),
            user_id=user_id,
            conversation_id=conversation_id,
            content=content.strip(),
            vector=vec,
            timestamp=time.time(),
            importance=max(1.0, min(5.0, importance)),
            category=category,
            metadata=metadata or {},
        )
        self._episodes.append(episode)
        # Keep bounded in-memory
        if len(self._episodes) > 5000:
            self._episodes = self._episodes[-4000:]
        return episode

    def recall(
        self,
        user_id: str,
        query: str,
        top_k: int = 4,
        min_score: float = 0.12,
        query_vector: list[float] | None = None,
    ) -> list[tuple[Episode, float]]:
        """Retrieve most relevant episodes scoring by semantic similarity * decay * importance."""
        if not self._episodes or not query.strip():
            return []

        q_vec = query_vector or _deterministic_embedding(query, self.dim)
        now = time.time()
        scored: list[tuple[Episode, float]] = []

        for ep in self._episodes:
            if ep.user_id != user_id:
                continue

            sim = _cosine_similarity(q_vec, ep.vector)
            if sim < 0.05:
                continue

            # Exponential recency decay
            age_days = max(0.0, (now - ep.timestamp) / 86400.0)
            decay = math.pow(0.5, age_days / self.decay_half_life_days)

            # Importance multiplier: 1.0 -> 1.0, 5.0 -> 1.6
            importance_boost = 1.0 + (ep.importance - 1.0) * 0.15

            final_score = sim * decay * importance_boost
            if final_score >= min_score:
                scored.append((ep, final_score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def count(self, user_id: str | None = None) -> int:
        if user_id is None:
            return len(self._episodes)
        return sum(1 for ep in self._episodes if ep.user_id == user_id)


# ============================================================================
# Tier 3: Semantic Knowledge Graph
# ============================================================================

@dataclass
class GraphEntity:
    name: str
    entity_type: str
    attributes: dict[str, Any] = field(default_factory=dict)
    aliases: set[str] = field(default_factory=set)


@dataclass
class GraphRelation:
    subject: str
    predicate: str
    target: str
    confidence: float = 1.0
    last_seen: float = field(default_factory=time.time)


class SemanticKnowledgeGraph:
    """Consolidated Knowledge Graph storing entities, attributes, and relationships."""

    def __init__(self) -> None:
        # Key: lowercase canonical entity name
        self.entities: dict[str, GraphEntity] = {}
        # List of relations
        self.relations: list[GraphRelation] = []

    def _normalize_name(self, name: str) -> str:
        return re.sub(r"\s+", " ", name.strip().lower())

    def add_entity(
        self,
        name: str,
        entity_type: str = "concept",
        attributes: dict[str, Any] | None = None,
        aliases: list[str] | None = None,
    ) -> GraphEntity:
        norm = self._normalize_name(name)
        if norm not in self.entities:
            self.entities[norm] = GraphEntity(
                name=name.strip(),
                entity_type=entity_type,
                attributes=attributes or {},
                aliases=set(aliases or []),
            )
        else:
            ent = self.entities[norm]
            if attributes:
                ent.attributes.update(attributes)
            if aliases:
                ent.aliases.update(aliases)
        return self.entities[norm]

    def add_fact(
        self,
        subject: str,
        predicate: str,
        target: str,
        confidence: float = 1.0,
        subject_type: str = "concept",
        target_type: str = "concept",
    ) -> GraphRelation:
        s_norm = self._normalize_name(subject)
        t_norm = self._normalize_name(target)
        p_norm = self._normalize_name(predicate)

        self.add_entity(subject, subject_type)
        self.add_entity(target, target_type)

        # Check existing relation to consolidate
        for rel in self.relations:
            if (
                self._normalize_name(rel.subject) == s_norm
                and self._normalize_name(rel.predicate) == p_norm
                and self._normalize_name(rel.target) == t_norm
            ):
                rel.confidence = min(1.0, max(rel.confidence, confidence) + 0.1)
                rel.last_seen = time.time()
                return rel

        new_rel = GraphRelation(
            subject=subject.strip(),
            predicate=predicate.strip(),
            target=target.strip(),
            confidence=confidence,
            last_seen=time.time(),
        )
        self.relations.append(new_rel)
        return new_rel

    def query_subgraph(self, query: str, max_hops: int = 1) -> list[str]:
        """Find facts related to words in the query."""
        q_tokens = set(re.findall(r"\b\w+\b", query.lower()))
        matched_facts: list[str] = []

        for rel in self.relations:
            s_low = rel.subject.lower()
            t_low = rel.target.lower()
            p_low = rel.predicate.lower()

            # Check if any token matches subject or target
            s_match = any(t in s_low for t in q_tokens)
            t_match = any(t in t_low for t in q_tokens)

            if s_match or t_match:
                matched_facts.append(f"{rel.subject} {rel.predicate} {rel.target}")

        return matched_facts[:8]

    def consolidate_turn_text(self, text: str, user_name: str = "User") -> list[str]:
        """Automatically extract user preferences, facts, and projects from dialogue."""
        extracted: list[str] = []
        lowered = text.lower()

        # Pattern: "I like / love / prefer X"
        pref_match = re.search(r"\b(?:i like|i love|i prefer|i enjoy)\s+([^.,!?]+)", lowered)
        if pref_match:
            item = pref_match.group(1).strip()
            if len(item) > 2 and len(item) < 60:
                self.add_fact(user_name, "likes", item, confidence=0.9, subject_type="user")
                extracted.append(f"{user_name} likes {item}")

        # Pattern: "My name is X" / "Call me X"
        name_match = re.search(r"\b(?:my name is|call me|i am|i'm)\s+([A-Za-z]+)\b", text)
        if name_match:
            cand = name_match.group(1).strip()
            if cand.lower() not in {"sorry", "ready", "happy", "fine", "here", "just"}:
                self.add_fact(user_name, "is_named", cand, confidence=1.0, subject_type="user")
                extracted.append(f"{user_name} is_named {cand}")

        # Pattern: "I work on / building / developing X"
        work_match = re.search(r"\b(?:i work on|i am working on|i'm building|i'm developing|working on our)\s+([^.,!?]+)", lowered)
        if work_match:
            proj = work_match.group(1).strip()
            if len(proj) > 2 and len(proj) < 80:
                self.add_fact(user_name, "works_on", proj, confidence=0.85, subject_type="user", target_type="project")
                extracted.append(f"{user_name} works_on {proj}")

        return extracted


# ============================================================================
# Tier 4: Procedural Memory (Tool Recipes & Workflow Habits)
# ============================================================================

@dataclass
class ToolRecipe:
    tool_name: str
    task_pattern: str
    recommended_parameters: dict[str, Any]
    usage_count: int = 1
    success_count: int = 1

    @property
    def success_rate(self) -> float:
        return self.success_count / max(1, self.usage_count)


class ProceduralMemory:
    """Stores execution recipes, tool choices, and successful workflows."""

    def __init__(self) -> None:
        self.recipes: dict[str, ToolRecipe] = {
            "image_generate": ToolRecipe(
                tool_name="image_generate",
                task_pattern="image_generation",
                recommended_parameters={
                    "aspect_ratio": "1:1",
                    "enhance": True,
                    "quality": "hd",
                },
                usage_count=10,
                success_count=10,
            ),
            "web_search": ToolRecipe(
                tool_name="web_search",
                task_pattern="research",
                recommended_parameters={"freshness": "recent", "num_results": 5},
                usage_count=10,
                success_count=10,
            ),
            "code_edit": ToolRecipe(
                tool_name="code_edit",
                task_pattern="coding",
                recommended_parameters={"verify_tests": True, "lint_check": True},
                usage_count=5,
                success_count=5,
            ),
        }

    def record_execution(self, tool_name: str, success: bool, params: dict[str, Any] | None = None) -> None:
        if tool_name not in self.recipes:
            self.recipes[tool_name] = ToolRecipe(
                tool_name=tool_name,
                task_pattern=tool_name,
                recommended_parameters=params or {},
                usage_count=0,
                success_count=0,
            )
        recipe = self.recipes[tool_name]
        recipe.usage_count += 1
        if success:
            recipe.success_count += 1
            if params:
                recipe.recommended_parameters.update(params)

    def get_recipe(self, task_hint: str) -> ToolRecipe | None:
        lowered = task_hint.lower()
        for recipe in self.recipes.values():
            if (
                recipe.task_pattern in lowered
                or recipe.tool_name in lowered
                or any(w in lowered for w in recipe.task_pattern.split("_") if len(w) > 3)
                or any(w in lowered for w in recipe.tool_name.split("_") if len(w) > 3)
            ):
                return recipe
        return None


# ============================================================================
# Unified Advanced Memory Manager
# ============================================================================

class AdvancedMemoryManager:
    """Master orchestrator integrating Working, Episodic, Semantic, and Procedural Memory."""

    def __init__(self) -> None:
        self.working = WorkingMemory()
        self.episodic = EpisodicVectorStore()
        self.semantic = SemanticKnowledgeGraph()
        self.procedural = ProceduralMemory()

    def process_turn(
        self,
        user_id: str,
        conversation_id: str,
        user_text: str,
        assistant_text: str,
        importance: float = 1.0,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Record turn into Working, Episodic, and Semantic tiers."""
        # 1. Update Working Memory
        self.working.add_turn("user", user_text)
        self.working.add_turn("assistant", assistant_text)

        # 2. Extract and Consolidate Semantic Facts
        facts = self.semantic.consolidate_turn_text(user_text)

        # 3. Store in Episodic Vector Store
        episode_content = f"User: {user_text}\nHinaa: {assistant_text}"
        ep = self.episodic.record_episode(
            user_id=user_id,
            conversation_id=conversation_id,
            content=episode_content,
            importance=importance,
            metadata={"extracted_facts": facts, **(metadata or {})},
        )

        return {
            "episode_id": ep.id,
            "extracted_facts": facts,
            "working_turns": len(self.working.turns),
        }

    def assemble_memory_context(
        self,
        user_id: str,
        query: str,
        conversation_id: str | None = None,
    ) -> dict[str, Any]:
        """Synthesize relevant context from all memory tiers for prompt injection."""
        # 1. Recall relevant episodic memories via vector cosine similarity + decay
        episodes = self.episodic.recall(user_id=user_id, query=query, top_k=3)
        recalled_episodes = [ep.content for ep, _ in episodes]

        # 2. Recall semantic knowledge graph facts
        graph_facts = self.semantic.query_subgraph(query)

        # 3. Get relevant procedural recipes
        recipe = self.procedural.get_recipe(query)
        procedural_hint = (
            f"Recommended recipe for {recipe.tool_name}: {json.dumps(recipe.recommended_parameters)}"
            if recipe
            else None
        )

        return {
            "active_goal": self.working.get_goal(),
            "recalled_episodes": recalled_episodes,
            "graph_facts": graph_facts,
            "procedural_hint": procedural_hint,
        }


# Global singleton instance for easy service access
default_advanced_memory = AdvancedMemoryManager()
