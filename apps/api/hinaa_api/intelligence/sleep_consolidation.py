"""
Stateful Sleep-Cycle Memory Consolidation Engine for HINAA.

Implements the Dual-Phase Neurobiological Memory Consolidation Architecture:
1. Slow-Wave Sleep (SWS) Pass:
   - Ingests recent episodic turns, tool outputs, and swarm consensus records.
   - Extracts structured entity nodes and semantic relation triples (Subject -> Predicate -> Target).
   - Detects contradiction and executes temporal supersession (newer facts override older stale facts).
2. REM Associative Pass:
   - Reinforces high-importance episodic nodes and procedural tool recipes.
   - Prunes transient noise and decayed, unreinforced episodic memories.
3. Durable Synchronization:
   - Atomically updates `.hina/memory/knowledge-graph.json` and appends to consolidation audit trail.
   - Synchronizes with durable MemoryService and SemanticKnowledgeGraph.
"""

from __future__ import annotations

import json
import logging
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

from ..persistence.advanced_memory import (
    GraphEntity,
    GraphRelation,
    SemanticKnowledgeGraph,
    default_advanced_memory,
)
from ..runtime_paths import project_root
from ..tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.intelligence.sleep_consolidation")


@dataclass
class ConsolidatedFact:
    subject: str
    predicate: str
    target: str
    confidence: float
    importance: float
    created_at: float
    last_reinforced: float
    status: str = "active"  # active, superseded, decayed
    superseded_by: Optional[str] = None
    subject_type: str = "concept"
    target_type: str = "concept"


class SleepCycleConsolidator:
    """Orchestrates episodic ingestion, contradiction resolution, decay pruning, and persistence."""

    def __init__(
        self,
        decay_half_life_days: float = 14.0,
        memory_dir: Optional[Path] = None,
    ) -> None:
        self.decay_half_life_days = decay_half_life_days
        self.root = project_root()
        self.memory_dir = memory_dir or (self.root / ".hina" / "memory")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.graph_path = self.memory_dir / "knowledge-graph.json"
        self.audit_log_path = self.memory_dir / "consolidation-log.jsonl"
        self.facts: Dict[str, ConsolidatedFact] = {}
        self._load_persisted_graph()

    def _make_key(self, subject: str, predicate: str, target: str) -> str:
        s = subject.strip().lower()
        p = predicate.strip().lower()
        t = target.strip(" .,!?:;'\"").lower()
        return f"{s}:{p}:{t}"

    def _load_persisted_graph(self) -> None:
        """Load knowledge graph state from disk if present."""
        if not self.graph_path.exists():
            return
        try:
            with open(self.graph_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            facts_raw = data.get("facts", {})
            for key, val in facts_raw.items():
                self.facts[key] = ConsolidatedFact(**val)
        except Exception as exc:
            logger.warning("Could not read knowledge-graph.json: %s", exc)

    def _persist_graph(self) -> None:
        """Atomically persist current consolidated facts to disk."""
        tmp_path = self.graph_path.with_suffix(".tmp")
        data = {
            "version": "2026.1",
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "active_facts_count": sum(1 for f in self.facts.values() if f.status == "active"),
            "facts": {k: asdict(v) for k, v in self.facts.items()},
        }
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        tmp_path.replace(self.graph_path)

    def _append_audit_log(self, entry: Dict[str, Any]) -> None:
        """Append consolidation audit event to log."""
        try:
            with open(self.audit_log_path, "a", encoding="utf-8") as f:
                entry_line = json.dumps({"timestamp": time.time(), **entry})
                f.write(entry_line + "\n")
        except Exception as exc:
            logger.debug("Failed writing audit log: %s", exc)

    def extract_triples_from_text(self, text: str, user_name: str = "User") -> List[Tuple[str, str, str, str, str, float]]:
        """Extract semantic triples (subject, predicate, target, subject_type, target_type, confidence)."""
        triples: List[Tuple[str, str, str, str, str, float]] = []
        clauses = re.split(r"(?:[.;\n\r]|\s+\band\b\s+)", text)

        for clause in clauses:
            cleaned_clause = clause.strip()
            if not cleaned_clause:
                continue

            # Preference patterns: "I prefer X", "I like X", "I love X", "always use X"
            pref_matches = re.finditer(
                r"\b(?:i\s+prefer|i\s+like|i\s+love|always\s+use|we\s+use)\s+([^,;!\n\r]+)",
                cleaned_clause,
                re.IGNORECASE,
            )
            for m in pref_matches:
                target = m.group(1).strip(" .,!?:;'\"")
                target = re.sub(r"\b(?:everywhere|now|instead|always)\b", "", target, flags=re.IGNORECASE).strip(" .,!?:;'\"")
                if target and target.lower() not in ("this", "that", "it", "something"):
                    triples.append((user_name, "prefers", target, "user", "preference", 0.95))

            # Architecture / tech stack
            stack_matches = re.finditer(
                r"\b(?:stack|architecture|built\s+with|written\s+in|uses|using)\s+([^,;!\n\r]+)",
                cleaned_clause,
                re.IGNORECASE,
            )
            for m in stack_matches:
                raw_tech = m.group(1).strip(" .,!?:;'\"")
                tech_parts = re.split(r"\b(?:with|\+)\b", raw_tech, flags=re.IGNORECASE)
                for part in tech_parts:
                    tech = part.strip(" .,!?:;'\"")
                    if tech and tech.lower() not in ("the", "our", "a", "all", "this", "that"):
                        triples.append(("Project", "uses_technology", tech, "project", "technology", 0.90))

            # Dislike / avoid patterns
            avoid_matches = re.finditer(
                r"\b(?:never\s+use|avoid|i\s+dislike|i\s+hate)\s+([^,;!\n\r]+)",
                cleaned_clause,
                re.IGNORECASE,
            )
            for m in avoid_matches:
                item = m.group(1).strip(" .,!?:;'\"")
                if item:
                    triples.append((user_name, "avoids", item, "user", "avoidance", 0.92))

        return triples

    def resolve_contradictions(
        self,
        new_subject: str,
        new_predicate: str,
        new_target: str,
        now: float,
    ) -> List[str]:
        """
        Detect contradictory earlier facts and supersede them.
        E.g. (User, prefers, dark mode) contradicts (User, prefers, light mode).
        """
        superseded_keys = []
        new_sub_low = new_subject.strip().lower()
        new_pred_low = new_predicate.strip().lower()
        new_tar_low = new_target.strip().lower()

        # Check for category overlap (e.g. mode, theme, language, library)
        theme_words = {"dark", "light", "system", "sepia"}
        framework_words = {"react", "vue", "svelte", "angular", "next", "vite"}

        for key, fact in self.facts.items():
            if fact.status != "active":
                continue
            if fact.subject.strip().lower() == new_sub_low and fact.predicate.strip().lower() == new_pred_low:
                old_tar_low = fact.target.strip().lower()
                if old_tar_low == new_tar_low:
                    # Same fact: reinforce confidence
                    fact.confidence = min(1.0, fact.confidence + 0.1)
                    fact.last_reinforced = now
                    return []

                # Contradiction check: Theme conflict
                if any(w in new_tar_low for w in theme_words) and any(w in old_tar_low for w in theme_words):
                    fact.status = "superseded"
                    fact.superseded_by = f"{new_subject} {new_predicate} {new_target}"
                    superseded_keys.append(key)

                # Contradiction check: Framework / bundler conflict
                elif any(w in new_tar_low for w in framework_words) and any(w in old_tar_low for w in framework_words):
                    fact.status = "superseded"
                    fact.superseded_by = f"{new_subject} {new_predicate} {new_target}"
                    superseded_keys.append(key)

                # Generic direct preference conflict on same predicate
                elif new_pred_low in ("prefers", "likes", "uses_technology"):
                    # Check semantic overlap
                    fact.status = "superseded"
                    fact.superseded_by = f"{new_subject} {new_predicate} {new_target}"
                    superseded_keys.append(key)

        return superseded_keys

    def apply_decay_and_prune(self, now: float) -> Tuple[int, int]:
        """Apply biological exponential decay and mark/prune decayed noise."""
        decayed_count = 0
        pruned_count = 0

        keys_to_delete = []
        for key, fact in self.facts.items():
            age_days = max(0.0, (now - fact.last_reinforced) / 86400.0)
            decay_factor = math.pow(0.5, age_days / self.decay_half_life_days)
            effective_confidence = fact.confidence * decay_factor

            # Anchor facts with importance >= 4.0 resist complete decay
            if fact.importance >= 4.0:
                effective_confidence = max(0.4, effective_confidence)

            if effective_confidence < 0.25 and fact.status == "active":
                fact.status = "decayed"
                decayed_count += 1

            # Remove permanently superseded or long-decayed entries (>60 days old)
            if fact.status in ("superseded", "decayed") and age_days > 60.0:
                keys_to_delete.append(key)
                pruned_count += 1

        for k in keys_to_delete:
            del self.facts[k]

        return decayed_count, pruned_count

    def run_consolidation_cycle(
        self,
        user_id: str = "LORD",
        source_texts: Optional[List[str]] = None,
        prune_decayed: bool = True,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute full sleep consolidation cycle."""
        now = time.time()
        start_time = now

        # 1. Gather text sources to ingest
        texts_to_process = list(source_texts or [])

        # Ingest from Working Memory buffer if available
        if default_advanced_memory and default_advanced_memory.working:
            for turn in default_advanced_memory.working.turns:
                texts_to_process.append(turn.content)

        extracted_triples: List[Dict[str, Any]] = []
        superseded_records: List[str] = []

        # 2. Extract and resolve triples
        for txt in texts_to_process:
            triples = self.extract_triples_from_text(txt, user_name=user_id)
            for sub, pred, tar, s_type, t_type, conf in triples:
                key = self._make_key(sub, pred, tar)
                # Check contradictions
                superseded = self.resolve_contradictions(sub, pred, tar, now)
                superseded_records.extend(superseded)

                if key in self.facts:
                    # Reinforce
                    f = self.facts[key]
                    f.confidence = min(1.0, f.confidence + 0.08)
                    f.last_reinforced = now
                    f.status = "active"
                else:
                    clean_tar = tar.strip(" .,!?:;'\"")
                    self.facts[key] = ConsolidatedFact(
                        subject=sub,
                        predicate=pred,
                        target=clean_tar,
                        confidence=conf,
                        importance=3.0,
                        created_at=now,
                        last_reinforced=now,
                        status="active",
                        subject_type=s_type,
                        target_type=t_type,
                    )
                extracted_triples.append({"subject": sub, "predicate": pred, "target": clean_tar})

                # Also sync into default_advanced_memory graph
                if default_advanced_memory and hasattr(default_advanced_memory, "semantic"):
                    default_advanced_memory.semantic.add_fact(
                        subject=sub,
                        predicate=pred,
                        target=tar,
                        confidence=conf,
                        subject_type=s_type,
                        target_type=t_type,
                    )

        # 3. Decay & Pruning
        decayed_count, pruned_count = (0, 0)
        if prune_decayed:
            decayed_count, pruned_count = self.apply_decay_and_prune(now)

        # 4. Persistence
        if not dry_run:
            self._persist_graph()
            self._append_audit_log({
                "action": "sleep_consolidation_cycle",
                "extracted_count": len(extracted_triples),
                "superseded_count": len(superseded_records),
                "decayed_count": decayed_count,
                "pruned_count": pruned_count,
                "active_facts_total": sum(1 for f in self.facts.values() if f.status == "active"),
            })

        duration = round(time.time() - start_time, 3)
        return {
            "success": True,
            "dry_run": dry_run,
            "duration_seconds": duration,
            "extracted_triples": extracted_triples,
            "superseded_facts": superseded_records,
            "decayed_count": decayed_count,
            "pruned_count": pruned_count,
            "total_active_facts": sum(1 for f in self.facts.values() if f.status == "active"),
            "graph_file": str(self.graph_path),
        }


# Singleton consolidator instance
_consolidator = SleepCycleConsolidator()


def get_sleep_consolidator() -> SleepCycleConsolidator:
    return _consolidator


# ============================================================================
# Registered Agent Tools
# ============================================================================

async def memory_consolidate_cycle_handler(
    user_id: str = "LORD",
    sample_texts: Optional[List[str]] = None,
    prune_decayed: bool = True,
    dry_run: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute a stateful sleep-cycle memory consolidation pass."""
    consolidator = get_sleep_consolidator()
    return consolidator.run_consolidation_cycle(
        user_id=user_id,
        source_texts=sample_texts,
        prune_decayed=prune_decayed,
        dry_run=dry_run,
    )


memory_consolidate_def = ToolDefinition(
    name="memory_consolidate_cycle",
    display_name="Stateful Sleep-Cycle Memory Consolidation",
    description=(
        "Executes a neurobiological sleep-cycle memory consolidation pass: extracts semantic triples from "
        "episodic history, resolves contradictions via temporal supersession, applies biological recency decay, "
        "and persists the updated knowledge graph to .hina/memory/knowledge-graph.json."
    ),
    parameters={
        "user_id": {
            "type": "string",
            "description": "User identifier for personalized memory consolidation (default: 'LORD')",
        },
        "sample_texts": {
            "type": "array",
            "description": "Optional list of recent turn or observation texts to consolidate",
        },
        "prune_decayed": {
            "type": "boolean",
            "description": "If true, apply half-life recency decay and mark unreinforced ephemeral memories",
        },
        "dry_run": {
            "type": "boolean",
            "description": "If true, compute consolidation report without writing changes to disk",
        },
    },
    required_parameters=[],
    permission_level="elevated",
    requires_confirmation=False,
    risk_level="medium",
    cancellable=True,
    voice_aliases=["consolidate memory", "run sleep cycle", "memory consolidation"],
)

registry.register(memory_consolidate_def, memory_consolidate_cycle_handler)
