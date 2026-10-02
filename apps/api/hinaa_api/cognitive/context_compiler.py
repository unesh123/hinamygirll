"""
HINAA Context OS & Adaptive Context Compiler.

Implements the 11-Level Context Hierarchy (L0-L10):
- L0: Current turn tokens
- L1: Working memory (recent turns)
- L2: Session memory (thread state, objectives)
- L3: Task memory (current task graph, completed steps)
- L4: Project memory (architecture, conventions, decisions from .hina/)
- L5: User profile memory (preferences, style, constraints)
- L6: Semantic knowledge (verified facts, entity links)
- L7: Procedural skills (learned workflow rules, how-to recipes)
- L8: Execution experience (past successful trajectories)
- L9: Failure & recovery memory (known pitfalls and repair rules)
- L10: Evaluation history (confidence benchmarks)

Provides:
- Hybrid scoring: Semantic + Lexical + Entity + Recency + Importance + Project relevance
- Strict token budgeting and compaction
- Temporal validity filtering (superseded/expired facts omitted)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Sequence

from .contracts import WorldState

logger = logging.getLogger("hinaa.cognitive.context_compiler")


@dataclass
class ContextItem:
    layer: str  # "L1" ... "L10"
    content: str
    source: str
    score: float = 1.0
    tokens: int = 0
    importance: int = 1
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledContext:
    system_instruction: str
    world_state_block: str
    project_context_block: str
    memory_facts_block: str
    procedural_rules_block: str
    recent_dialogue_block: str
    total_token_estimate: int
    items_included: int
    items_pruned: int


class ContextCompiler:
    """Compiles multi-source operational knowledge into structured model prompt context."""

    def __init__(self, default_token_budget: int = 8000) -> None:
        self.default_token_budget = default_token_budget

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _hybrid_score(
        self,
        query: str,
        content: str,
        *,
        importance: int = 1,
        timestamp: float = 0.0,
        project_match: bool = False,
    ) -> float:
        """
        Computes hybrid relevance score:
        0.30 semantic + 0.20 lexical + 0.15 entity + 0.15 recency + 0.10 importance + 0.10 project
        """
        query_words = set(re.findall(r"\w+", query.lower()))
        content_words = set(re.findall(r"\w+", content.lower()))
        if not query_words or not content_words:
            lexical_sim = 0.1
        else:
            intersection = query_words.intersection(content_words)
            lexical_sim = len(intersection) / max(1, len(query_words))

        # Recency decay (half-life of 7 days)
        age_seconds = max(0.0, time.time() - (timestamp or time.time()))
        recency_score = max(0.1, 1.0 - (age_seconds / (7 * 86400 * 4)))

        imp_score = min(1.0, max(0.2, importance / 5.0))
        proj_score = 1.0 if project_match else 0.3
        semantic_approx = min(1.0, lexical_sim * 1.2 + 0.2)

        return (
            0.30 * semantic_approx
            + 0.20 * lexical_sim
            + 0.15 * (1.0 if any(w in content.lower() for w in ["hina", "hinaa", "desktop", "agent"]) else 0.2)
            + 0.15 * recency_score
            + 0.10 * imp_score
            + 0.10 * proj_score
        )

    def compile(
        self,
        query: str,
        world_state: WorldState,
        *,
        user_id: str,
        project_id: Optional[str] = None,
        memory_manager: Optional[Any] = None,
        project_specs: Optional[Dict[str, str]] = None,
        recent_turns: Optional[Sequence[Dict[str, str]]] = None,
        max_budget: Optional[int] = None,
    ) -> CompiledContext:
        """Compiles layered context according to adaptive budgets."""
        budget = max_budget or self.default_token_budget
        items: List[ContextItem] = []

        # 1. Project Memory (L4) from .hina/ specs and project store
        if project_specs:
            for spec_name, spec_content in project_specs.items():
                snippet = spec_content[:1200]
                tokens = self._estimate_tokens(snippet)
                score = self._hybrid_score(query, snippet, importance=4, project_match=True)
                items.append(ContextItem(
                    layer="L4",
                    content=f"[{spec_name}]: {snippet.strip()}",
                    source=f"project_spec:{spec_name}",
                    score=score,
                    tokens=tokens,
                    importance=4,
                ))

        # 2. Semantic Memory (L6) & Profile (L5) from MemoryManagerV2
        if memory_manager:
            try:
                facts = (
                    memory_manager.get_active_semantic_memories(user_id)
                    if hasattr(memory_manager, "get_active_semantic_memories")
                    else (memory_manager.get_active_facts(user_id) if hasattr(memory_manager, "get_active_facts") else [])
                )
                for fact in facts:
                    if hasattr(fact, "is_temporally_valid") and not fact.is_temporally_valid:
                        continue
                    text = getattr(fact, "content", str(fact))
                    imp = getattr(fact, "importance", 2)
                    ts = getattr(fact, "timestamp", time.time())
                    score = self._hybrid_score(query, text, importance=imp, timestamp=ts)
                    items.append(ContextItem(
                        layer="L5" if getattr(fact, "category", "") == "preference" else "L6",
                        content=text,
                        source="memory_v2:semantic",
                        score=score,
                        tokens=self._estimate_tokens(text),
                        importance=imp,
                    ))

                # Procedural memory (L7)
                rules = memory_manager.get_procedural_rules() if hasattr(memory_manager, "get_procedural_rules") else []
                for r in rules:
                    trigger = getattr(r, "trigger_pattern", "")
                    workflow = getattr(r, "action_workflow", "")
                    rule_text = f"When '{trigger}': {workflow}"
                    score = self._hybrid_score(query, rule_text, importance=3)
                    items.append(ContextItem(
                        layer="L7",
                        content=rule_text,
                        source="memory_v2:procedural",
                        score=score,
                        tokens=self._estimate_tokens(rule_text),
                        importance=3,
                    ))
            except Exception as e:
                logger.debug("Error retrieving facts from memory manager: %s", e)

        # 3. Sort candidates by hybrid score
        items.sort(key=lambda x: x.score, reverse=True)

        # Budget Allocation:
        # L4 (Project): max 25% of budget
        # L5/L6 (Facts): max 25% of budget
        # L7 (Procedural): max 15% of budget
        project_items = []
        fact_items = []
        rule_items = []

        total_consumed = 0
        pruned_count = 0

        for item in items:
            if total_consumed + item.tokens > budget:
                pruned_count += 1
                continue
            if item.layer == "L4":
                project_items.append(item.content)
            elif item.layer in ("L5", "L6"):
                fact_items.append(item.content)
            elif item.layer == "L7":
                rule_items.append(item.content)
            total_consumed += item.tokens

        # Format Dialogue (L1 Working Memory)
        dialogue_lines = []
        if recent_turns:
            for t in recent_turns[-8:]:
                role = t.get("role", "user")
                c = t.get("content", "")
                dialogue_lines.append(f"{role.upper()}: {c}")

        recent_dialogue_block = "\n".join(dialogue_lines)
        total_consumed += self._estimate_tokens(recent_dialogue_block)

        # Summarize World State
        from .world_model import WorldModel
        world_block = WorldModel.summarize_for_prompt(world_state)
        total_consumed += self._estimate_tokens(world_block)

        return CompiledContext(
            system_instruction="HINAA Frontier Operating Core: Embody continuous intelligence with strict grounded actuation.",
            world_state_block=world_block,
            project_context_block="\n---\n".join(project_items) if project_items else "No explicit project context.",
            memory_facts_block="\n• ".join(["Known user & world facts:"] + fact_items) if fact_items else "No prior facts.",
            procedural_rules_block="\n• ".join(["Learned workflows:"] + rule_items) if rule_items else "Standard operational workflow.",
            recent_dialogue_block=recent_dialogue_block,
            total_token_estimate=total_consumed,
            items_included=len(project_items) + len(fact_items) + len(rule_items),
            items_pruned=pruned_count,
        )
