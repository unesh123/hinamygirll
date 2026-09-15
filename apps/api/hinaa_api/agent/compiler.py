"""HINAA Phase B2 — Hierarchical Context Compiler V3.

ONE canonical model-context construction path (directive §10). Every route —
chat turn, agent runtime, tool summaries — converges here. The compiler:

1. Routes the turn via ``MemoryQueryRouter`` (profile + retrieval routes).
2. Converts candidates into ``ContextItem``s with explicit trust levels,
   priority tiers, and provenance (§12–§13).
3. Pins unresolved live state (§15), deduplicates facts (§22), resolves
   conflicts by precedence: latest explicit user correction > active goal >
   project state > recent turn > memory > RAG (§23).
4. Allocates the token budget per profile with an output-token reserve
   (§33), applies intelligent overflow (§34: drop expired → rank → compact
   → trim low tiers — never random mid-truncation), and records every
   include/exclude decision into a ``ContextManifest`` (§19–§20).

The legacy ``compile(...)`` signature is preserved so existing callers and
tests keep working; the manifest is available via ``result.manifest``.
"""

from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Sequence

from .context_items import (
    CompactionReason,
    ContextCompaction,
    ContextItem,
    ContextManifest,
    InstructionAuthority,
    ManifestStatus,
    PriorityTier,
    TrustLevel,
)
from .context_profiles import (
    ContextProfile,
    DEFAULT_OUTPUT_RESERVE_TOKENS,
    MemoryQueryRouter,
    compute_input_budget,
    effective_budgets,
)


@dataclass
class CompiledContextFingerprint:
    """Deterministic hash fingerprint of semantic context blocks (P0.15 §4)."""
    manifest_id: str
    item_hashes: list[str]
    combined_hash: str
    token_sum: int

    @classmethod
    def compute(cls, manifest: ContextManifest) -> CompiledContextFingerprint:
        hashes: list[str] = []
        token_sum = 0
        for item in sorted(
            manifest.included_items or [],
            key=lambda x: (str(x.get("source_type") or ""), str(x.get("source_id") or "")),
        ):
            st = str(item.get("source_type") or "")
            sid = str(item.get("source_id") or "")
            tok = int(item.get("tokens") or item.get("token_estimate") or 0)
            token_sum += tok
            h = hashlib.sha256(f"{st}:{sid}:{tok}".encode("utf-8")).hexdigest()[:16]
            hashes.append(h)
        combined = hashlib.sha256(":".join(hashes).encode("utf-8")).hexdigest()
        return cls(
            manifest_id=manifest.manifest_id,
            item_hashes=hashes,
            combined_hash=combined,
            token_sum=token_sum,
        )


def estimate_tokens(text: str) -> int:
    """Estimate token count (approx 4 chars per token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


@dataclass
class CompiledContextBlock:
    source_type: str
    source_id: str | None
    content: str
    score: float
    token_estimate: int
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CompiledPromptContext:
    system_prefix: str
    active_task_block: str | None
    project_block: str | None
    memory_blocks: list[CompiledContextBlock]
    dialogue_messages: list[dict[str, Any]]
    total_tokens: int
    cache_fingerprint: str
    manifest: ContextManifest | None = None
    dialogue_state_block: str | None = None
    live_web_block: str | None = None
    manifest_fingerprint: str = ""

    def to_assembled_prompt(self, user_prompt: str) -> str:
        """Render the fully compiled context into a single structured prompt."""
        sections = [self.system_prefix]

        if self.project_block:
            sections.append(f"\n## Active Project\n{self.project_block}")

        if self.active_task_block:
            sections.append(f"\n## Active Durable Task\n{self.active_task_block}")

        if self.memory_blocks:
            mem_lines = [f"- [{b.source_type}] {b.content}" for b in self.memory_blocks]
            sections.append("\n## Context & Memory\n" + "\n".join(mem_lines))

        sections.append(f"\n## User Request\n{user_prompt}")
        return "\n\n".join(sections)


# Directive §23 — conflict resolution precedence (lower number wins).
_SOURCE_PRECEDENCE: dict[str, int] = {
    "user_correction": 0,
    "hard_constraint": 1,
    "goal": 1,
    "project": 2,
    "recent_turn": 3,
    "entity": 4,
    "asset": 4,
    "memory": 5,
    "episodic": 5,
    "summary": 6,
    "rag": 7,
    "web": 7,
    "tool_result": 3,
    "history": 8,
}

# Normalized fact extraction for dedup/conflict (§22): lowercase, strip
# articles/punct, keep content words. "The DB is PostgreSQL." → "db postgresql".
_STOPWORDS = frozenset(
    {"the", "a", "an", "is", "are", "was", "were", "be", "been", "it", "its",
     "of", "to", "for", "and", "or", "in", "on", "with", "by", "at", "as",
     "that", "this", "these", "those", "we", "our", "us"}
)


def _normalize_fact(text: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return " ".join(w for w in words if w not in _STOPWORDS)


def _fact_signature(text: str) -> str | None:
    """Signature for dedup: normalized first ~12 content words of a fact."""
    norm = _normalize_fact(text)
    if len(norm) < 8:
        return None
    return " ".join(norm.split()[:12])


_TRUST_BY_SOURCE: dict[str, tuple[TrustLevel, PriorityTier]] = {
    "system": (TrustLevel.SYSTEM, PriorityTier.TIER0_SECURITY),
    "security": (TrustLevel.SYSTEM, PriorityTier.TIER0_SECURITY),
    "application": (TrustLevel.APPLICATION, PriorityTier.TIER0_SECURITY),
    "dialogue_state": (TrustLevel.APPLICATION, PriorityTier.TIER1_LIVE_STATE),
    "user_message": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "user_correction": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "hard_constraint": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "goal": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "pending_question": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "pending_confirmation": (TrustLevel.USER_EXPLICIT, PriorityTier.TIER1_LIVE_STATE),
    "project": (TrustLevel.PROJECT_STATE, PriorityTier.TIER2_EXECUTION),
    "durable_task": (TrustLevel.PROJECT_STATE, PriorityTier.TIER2_EXECUTION),
    "checkpoint": (TrustLevel.PROJECT_STATE, PriorityTier.TIER2_EXECUTION),
    "asset": (TrustLevel.PROJECT_STATE, PriorityTier.TIER2_EXECUTION),
    "entity": (TrustLevel.MEMORY, PriorityTier.TIER4_MEMORY),
    "memory": (TrustLevel.MEMORY, PriorityTier.TIER4_MEMORY),
    "episodic": (TrustLevel.MEMORY, PriorityTier.TIER4_MEMORY),
    "summary": (TrustLevel.MEMORY, PriorityTier.TIER4_MEMORY),
    "recent_turn": (TrustLevel.HISTORY, PriorityTier.TIER3_CONTINUITY),
    "message": (TrustLevel.HISTORY, PriorityTier.TIER3_CONTINUITY),
    "tool_result": (TrustLevel.TOOL_OUTPUT, PriorityTier.TIER3_CONTINUITY),
    "rag": (TrustLevel.RAG, PriorityTier.TIER5_KNOWLEDGE),
    "web": (TrustLevel.WEB, PriorityTier.TIER5_KNOWLEDGE),
    "external_data": (TrustLevel.EXTERNAL_DATA, PriorityTier.TIER5_KNOWLEDGE),
    "document_context": (TrustLevel.EXTERNAL_DATA, PriorityTier.TIER5_KNOWLEDGE),
    "repository": (TrustLevel.RAG, PriorityTier.TIER5_KNOWLEDGE),
    "history": (TrustLevel.HISTORY, PriorityTier.TIER6_HISTORY),
}

_REQUIRED_SOURCES = frozenset(
    {
        "user_message", "user_correction", "hard_constraint", "goal",
        "dialogue_state", "pending_question", "pending_confirmation", "system", "security",
    }
)


class ContextCompiler:
    """Multi-factor Context Compiler with prompt-cache optimization,

    trust-tiered ranking, token budgeting with output reserve, fact dedup,
    conflict resolution, and a full ContextManifest decision trace.
    """

    def __init__(self, max_tokens: int = 8192, *, model_context_limit: int | None = None) -> None:
        self.max_tokens = max(64, max_tokens)
        # Directive §33: input budget = model limit − output reserve − margin.
        self.model_context_limit = model_context_limit
        self.output_reserve = DEFAULT_OUTPUT_RESERVE_TOKENS
        self.router = MemoryQueryRouter()
        self._last_manifest: ContextManifest | None = None

    # ------------------------------------------------------------------
    # Scoring (kept for backward compatibility with existing tests)
    # ------------------------------------------------------------------
    def calculate_score(
        self,
        item_text: str,
        source_type: str,
        query: str,
        age_turns: int = 0,
        affinity: bool = False,
    ) -> float:
        """Multi-factor score: relevance * recency * authority * affinity."""
        authority_map = {
            "checkpoint": 1.0,
            "durable_task": 1.0,
            "project": 0.85,
            "entity": 0.75,
            "memory": 0.70,
            "summary": 0.75,
            "tool_result": 0.65,
            "message": 0.60,
        }
        authority = authority_map.get(source_type, 0.50)
        recency = 1.0 / (1.0 + 0.15 * max(0, age_turns))

        q_words = set(re.findall(r"\w+", query.lower()))
        item_words = set(re.findall(r"\w+", item_text.lower()))
        if q_words and item_words:
            overlap = len(q_words & item_words)
            relevance = min(1.0, 0.2 + 0.8 * (overlap / max(1, len(q_words))))
        else:
            relevance = 0.3

        affinity_mult = 1.25 if affinity else 1.0
        score = (relevance * 0.35 + recency * 0.25 + authority * 0.40) * affinity_mult
        return round(min(1.0, score), 4)

    # ------------------------------------------------------------------
    # Main compile — legacy signature preserved
    # ------------------------------------------------------------------
    def compile(
        self,
        system_identity: str,
        user_query: str,
        *,
        active_project: dict[str, Any] | None = None,
        active_task_checkpoint: dict[str, Any] | None = None,
        memories: Sequence[dict[str, Any]] | None = None,
        entities: Sequence[dict[str, Any]] | None = None,
        history: Sequence[dict[str, Any]] | None = None,
        summary: str | None = None,
        tool_results: Sequence[dict[str, Any]] | None = None,
        cross_session_evidence: Sequence[Any] | None = None,
        # --- B2 additions (all optional; defaults keep legacy behavior) ---
        user_corrections: Sequence[str] | None = None,
        hard_constraints: Sequence[str] | None = None,
        active_goal: str | None = None,
        pending_questions: Sequence[str] | None = None,
        rag_results: Sequence[dict[str, Any]] | None = None,
        dialogue_state: str | None = None,
        live_search_evidence: Sequence[Any] | None = None,
        approved_memories: Sequence[str] | None = None,
        attached_documents: Sequence[Any] | None = None,
        request_id: str = "compiled",
        conversation_id: str | None = None,
        profile: ContextProfile | str | None = None,
        domain: str | None = None,
        model_context_limit: int | None = None,
    ) -> CompiledPromptContext:
        started = time.perf_counter()
        query_text = user_query or ""

        # 1. Route the turn → profile (§18, §16). FAST keeps hot state only.
        decision = self.router.route(
            query_text,
            has_active_task=active_task_checkpoint is not None,
            has_active_project=active_project is not None,
            domain_hint=domain,
            explicit_profile=profile,
        )
        profile = decision.profile
        is_fast = profile is ContextProfile.FAST

        # 2. Budget (§33): reserve output space before allocating input.
        limit = model_context_limit or self.model_context_limit or self.max_tokens * 4
        input_budget = min(self.max_tokens, compute_input_budget(limit, expected_output_tokens=self.output_reserve))
        if input_budget <= 0:
            input_budget = self.max_tokens

        prefix = system_identity.strip()
        prefix_tokens = estimate_tokens(prefix)
        remaining_budget = max(0, input_budget - prefix_tokens - estimate_tokens(query_text))

        # 3. Build ContextItems from every source (§11–§12).
        candidates: list[ContextItem] = []

        def _add(
            source_type: str,
            text: str,
            *,
            source_id: str | None = None,
            affinity: bool = False,
            required: bool | None = None,
            age_turns: int = 0,
        ) -> None:
            text = (text or "").strip()
            if not text:
                return
            trust, tier = _TRUST_BY_SOURCE.get(source_type, (TrustLevel.HISTORY, PriorityTier.TIER6_HISTORY))
            is_req = required if required is not None else (source_type in _REQUIRED_SOURCES)
            score = self.calculate_score(text, source_type, query_text, age_turns=age_turns, affinity=affinity)
            candidates.append(
                ContextItem(
                    source_type=source_type,
                    text=text,
                    token_estimate=estimate_tokens(text),
                    trust=trust,
                    tier=tier,
                    source_id=source_id,
                    relevance=score,
                    recency=max(0.0, 1.0 / (1.0 + 0.15 * age_turns)),
                    importance=0.9 if is_req else 0.5,
                    authority=trust.value in ("system", "application", "user_explicit") and 0.95 or 0.6,
                    confidence=0.9,
                    task_affinity=0.2 if affinity else 0.0,
                    required=is_req,
                    pinnable=tier.value <= PriorityTier.TIER2_EXECUTION.value,
                    provenance={"source": source_type, "age_turns": age_turns},
                )
            )

        if is_fast:
            # Directive §39: trivial turn → hot state only. No memory/RAG/
            # history ranking, no heavy retrieval — BUT hot continuity is kept:
            # recent exact turns + live control state, or "yes" answers nothing.
            hot_messages: list[dict[str, Any]] = []
            if history:
                hot_budget = min(remaining_budget, 1024)
                used = 0
                for turn in list(history)[-8:]:
                    content = (turn.get("content") or "").strip()
                    if not content:
                        continue
                    cost = estimate_tokens(content)
                    if used + cost > hot_budget:
                        break
                    used += cost
                    hot_messages.append({
                        "role": turn.get("role", "user"),
                        "content": content,
                    })
            manifest = self._new_manifest(
                request_id, conversation_id, profile, input_budget, prefix_tokens,
                compile_start=started, decision=decision,
            )
            manifest.retrieval_queries = []
            total = prefix_tokens + estimate_tokens(query_text) + sum(
                estimate_tokens(m["content"]) for m in hot_messages
            )
            # Manifest records hot continuity inclusions (§19: manifest = reality).
            for m in hot_messages:
                manifest.included_items.append({
                    "source_type": "recent_turn",
                    "source_id": None,
                    "context_id": None,
                    "included": True,
                    "tokens": estimate_tokens(m["content"]),
                    "reason": "FAST profile — hot continuity (last turns kept)",
                })
            self._last_manifest = manifest
            return CompiledPromptContext(
                system_prefix=prefix,
                active_task_block=None,
                project_block=None,
                memory_blocks=[],
                dialogue_messages=hot_messages,
                total_tokens=total,
                cache_fingerprint=hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:16],
                manifest=manifest,
            )

        # Tier 1 — live control state (pinned, never compacted §15).
        if dialogue_state:
            _add("dialogue_state", dialogue_state, required=True, affinity=True)
        for corr in user_corrections or ():
            _add("user_correction", corr)
        for con in hard_constraints or ():
            _add("hard_constraint", con)
        if active_goal:
            _add("goal", active_goal)
        for pq in pending_questions or ():
            _add("pending_question", pq)

        # Tier 2 — execution state.
        project_str = None
        if active_project:
            p_name = active_project.get("name", "Current Project")
            p_desc = active_project.get("description", "")
            project_str = f"**{p_name}**: {p_desc}".strip()
            _add("project", project_str, affinity=True)
        task_str = None
        if active_task_checkpoint:
            t_title = active_task_checkpoint.get("title") or active_task_checkpoint.get("task_id", "Task")
            t_status = active_task_checkpoint.get("status", "running")
            t_step = active_task_checkpoint.get("current_step") or active_task_checkpoint.get("progress", "")
            task_str = f"Task: {t_title} [{t_status}] - Step: {t_step}".strip()
            _add("checkpoint", task_str, affinity=True, required=True)

        # Tier 3 — immediate continuity.
        recent_turns: list[dict[str, Any]] = []
        if history:
            for idx, turn in enumerate(history):
                content = turn.get("content", "")
                if content:
                    item_age = len(history) - idx
                    _add("recent_turn", content, source_id=turn.get("id"), age_turns=item_age)
                    # Preserve role + exact order index for serialization (§4).
                    if candidates:
                        candidates[-1].provenance["turn_index"] = idx
                        candidates[-1].provenance["role"] = turn.get("role", "user")

        # Tier 4 — durable relevant memory.
        if summary:
            _add("summary", summary, affinity=True, age_turns=1)
        for ent in entities or ():
            name = ent.get("name", "")
            ent_summary = ent.get("summary") or ent.get("description", "")
            _add("entity", f"{name}: {ent_summary}", source_id=ent.get("id"))
        for mem in memories or ():
            _add("memory", mem.get("content", ""), source_id=mem.get("id"))
        for i, app_mem in enumerate(approved_memories or ()):
            _add("application", app_mem, source_id=f"approved_{i}", affinity=True)

        # Tier 5 — knowledge (RAG: DATA ONLY, never instruction authority §13).
        for tr in tool_results or ():
            text = str(tr.get("output") or tr.get("result") or tr)
            _add("tool_result", text, source_id=tr.get("id"))
        for ev in cross_session_evidence or ():
            ev_content = getattr(ev, "content", str(ev))
            ev_type = getattr(ev, "source_type", "memory")
            ev_id = getattr(ev, "source_id", None)
            trust, tier = _TRUST_BY_SOURCE.get(ev_type, (TrustLevel.MEMORY, PriorityTier.TIER4_MEMORY))
            score = self.calculate_score(ev_content, ev_type, query_text)
            candidates.append(
                ContextItem(
                    source_type=ev_type,
                    text=ev_content,
                    token_estimate=estimate_tokens(ev_content),
                    trust=trust,
                    tier=tier,
                    source_id=ev_id,
                    relevance=score,
                    recency=0.6,
                    importance=0.6,
                    authority=0.6,
                    confidence=0.8,
                    required=False,
                    pinnable=False,
                    provenance={"source": "cross_session"},
                )
            )
        for rag in rag_results or ():
            _add("rag", str(rag.get("content") or rag.get("text") or rag), source_id=rag.get("id"))

        from hinaa_api.grounding.citations import ExternalEvidence
        for i, ev in enumerate(live_search_evidence or ()):
            if hasattr(ev, "to_envelope"):
                text_block = ev.to_envelope()
                sid = getattr(ev, "source_id", f"src_{i}")
            elif isinstance(ev, dict):
                sid = str(ev.get("source_id") or ev.get("id") or f"src_{i}")
                raw = str(ev.get("snippet") or ev.get("content") or ev)
                text_block = ExternalEvidence(source_id=sid, raw_content=raw).to_envelope()
            else:
                raw = str(ev)
                sid = f"src_{i}"
                text_block = ExternalEvidence(source_id=sid, raw_content=raw).to_envelope()
            _add("web", text_block, source_id=sid, affinity=True)

        for i, doc in enumerate(attached_documents or ()):
            extracted = getattr(doc, "extracted_text", None) or (doc.get("extracted_text") if isinstance(doc, dict) else str(doc))
            fn = getattr(doc, "filename", None) or (doc.get("filename") if isinstance(doc, dict) else f"doc_{i}")
            if extracted:
                _add("document_context", str(extracted), source_id=str(fn), affinity=True)

        # 4. Dedup (§22) — same fact from many sources collapses to one.
        kept: list[ContextItem] = []
        seen_signatures: dict[str, ContextItem] = {}
        dedup_dropped = 0
        for item in candidates:
            sig = _fact_signature(item.text)
            if sig:
                prior = seen_signatures.get(sig)
                if prior is not None:
                    # Prefer higher authority then lower precedence index.
                    if (_SOURCE_PRECEDENCE.get(item.source_type, 9), item.trust.value) < (
                        _SOURCE_PRECEDENCE.get(prior.source_type, 9), prior.trust.value
                    ):
                        kept.remove(prior)
                        kept.append(item)
                        seen_signatures[sig] = item
                    dedup_dropped += 1
                    continue
                seen_signatures[sig] = item
            kept.append(item)

        # 5. Conflict resolution (§23) — conflicting facts: precedence wins,
        #    loser excluded with a recorded reason; ambiguity is preserved
        #    when precedence ties (do not invent consensus).
        by_fact: dict[str, list[ContextItem]] = {}
        conflicts_resolved: list[dict[str, Any]] = []
        final_items: list[ContextItem] = []
        for item in kept:
            sig = _fact_signature(item.text)
            if not sig:
                final_items.append(item)
                continue
            bucket = by_fact.setdefault(sig, [])
            if bucket:
                # Conflict candidates: same signature, different claims.
                conflicts_resolved.append({
                    "fact": sig,
                    "kept": {"source": item.source_type, "id": item.context_id},
                    "dropped": {"source": bucket[-1].source_type, "id": bucket[-1].context_id},
                    "policy": "latest_explicit_correction_over_memory" if item.source_type == "user_correction" else "precedence",
                })
                bucket.append(item)
            else:
                bucket.append(item)
            final_items.append(item)

        # 6. Overflow strategy (§34) — never truncate mid-text randomly.
        #    Order: required/pinned first → dedup done → rank rest → compact
        #    oversized → drop lowest-tier extras.
        def _sort_key(item: ContextItem) -> tuple[int, float, str]:
            return (item.tier.value, -item.base_score(), item.context_id)

        required_items = [i for i in final_items if i.required]
        optional_items = sorted((i for i in final_items if not i.required), key=_sort_key)

        included: list[ContextItem] = []
        excluded: list[ContextItem] = []
        compactions: list[ContextCompaction] = []
        budget_left = remaining_budget

        # B2.1 §36 — relevance gating (HOT/WARM/COLD, §9). Including every-
        # thing that merely *fits* is how 120 unrelated anime turns leak into
        # a "continue the Nova auth task" request. The gate runs regardless
        # of budget pressure: lexical relevance vs the query + hot recency
        # decides candidate worthiness; budget decides capacity. Keep (a)
        # required/pinned items, (b) query-relevant items, (c) hot recent
        # turns — drop cold noise with a manifest reason.
        # NOTE: item.relevance is the fused multi-factor score (authority+
        # recency dominate), so the gate uses direct lexical overlap instead.
        _RELEVANCE_FLOOR = 0.34  # ≥ 2 of 5+ query words matched
        _HOT_RECENCY_FLOOR = 0.45  # ≈ the newest 6 turns of the working set
        # Content words only — "what exactly did I say about PostgreSQL?" must
        # score on "postgresql", not be diluted by interrogative stopwords.
        _GATE_STOPWORDS = frozenset({
            "what", "exactly", "did", "do", "does", "i", "me", "my", "we", "us",
            "you", "it", "this", "that", "these", "those", "the", "a", "an",
            "is", "are", "was", "were", "be", "been", "to", "of", "in", "on",
            "for", "with", "and", "or", "about", "how", "why", "when", "where",
            "which", "who", "can", "could", "would", "should", "please", "say",
            "said", "tell", "ask", "use", "using", "make", "made", "get", "got",
        })
        _gate_words = set(re.findall(r"\w+", query_text.lower())) - _GATE_STOPWORDS
        kept_optional: list[ContextItem] = []
        for item in optional_items:
            if item.required:
                kept_optional.append(item)
                continue
            item_words = set(re.findall(r"\w+", item.text.lower()))
            lexical = (
                len(_gate_words & item_words) / max(1, len(_gate_words))
                if _gate_words and item_words
                else 0.0
            )
            if lexical >= _RELEVANCE_FLOOR or item.recency >= _HOT_RECENCY_FLOOR:
                kept_optional.append(item)
            else:
                item.exclusion_reason = "Cold/no-relevant content — below §36 gate"
                excluded.append(item)
        optional_items = kept_optional

        for item in required_items:
            if item.token_estimate <= budget_left:
                included.append(item)
                budget_left -= item.token_estimate
            else:
                # Compact required oversized items (§30) but keep the fact.
                compact = self._compact_item(item, budget_left)
                if compact is not None:
                    included.append(compact[0])
                    compactions.append(compact[1])
                    budget_left -= compact[0].token_estimate
                else:
                    excluded.append(item)

        for item in optional_items:
            if item.token_estimate <= budget_left:
                included.append(item)
                budget_left -= item.token_estimate
            else:
                compact = self._compact_item(item, budget_left)
                if compact is not None:
                    included.append(compact[0])
                    compactions.append(compact[1])
                    budget_left -= compact[0].token_estimate
                else:
                    excluded.append(item)

        # 7. Legacy output shapes (backward compatible).
        memory_blocks = [
            CompiledContextBlock(
                source_type=i.source_type,
                source_id=i.source_id,
                content=i.text,
                score=round(i.base_score(), 4),
                token_estimate=i.token_estimate,
                metadata={**i.provenance, "trust": i.trust.value},
            )
            for i in included
            if i.source_type not in ("recent_turn", "message", "checkpoint", "project", "user_correction", "hard_constraint", "goal")
        ]
        # Restore original conversation order by recorded turn index (exact,
        # robust to duplicate turn text — no content-equality ordering).
        turn_messages: list[tuple[int, dict[str, Any]]] = [
            (
                i.provenance.get("turn_index", 0),
                {"role": i.provenance.get("role", "user"), "content": i.text},
            )
            for i in included
            if i.source_type in ("recent_turn", "message")
        ]
        turn_messages.sort(key=lambda pair: pair[0])
        dialogue_messages = [m for _, m in turn_messages]

        user_correction_block = "\n".join(
            f"IMPORTANT — user correction: {i.text}"
            for i in included
            if i.source_type == "user_correction"
        )
        constraint_block = "\n".join(
            f"HARD CONSTRAINT: {i.text}"
            for i in included
            if i.source_type == "hard_constraint"
        )
        goal_block = "\n".join(
            f"ACTIVE GOAL: {i.text}"
            for i in included
            if i.source_type == "goal"
        )
        prefix_parts = [prefix]
        if constraint_block:
            prefix_parts.append(constraint_block)
        if user_correction_block:
            prefix_parts.append(user_correction_block)
        if goal_block:
            prefix_parts.append(goal_block)
        final_prefix = "\n".join(prefix_parts)

        total_tokens = (
            estimate_tokens(final_prefix)
            + (estimate_tokens(project_str) if project_str else 0)
            + (estimate_tokens(task_str) if task_str else 0)
            + sum(b.token_estimate for b in memory_blocks)
            + sum(estimate_tokens(m.get("content", "")) for m in dialogue_messages)
            + estimate_tokens(query_text)
        )

        # 8. Manifest (§19–§20).
        manifest = self._new_manifest(
            request_id, conversation_id, profile, input_budget, prefix_tokens,
            compile_start=started, decision=decision,
        )
        manifest.allocations = {
            k: int(remaining_budget * share)
            for k, share in effective_budgets(profile, domain=domain).items()
        }
        for item in included:
            manifest.included_items.append(
                item.to_manifest_entry(included=True, reason=self._why_included(item, decision))
            )
        for item in excluded:
            manifest.excluded_items.append(
                item.to_manifest_entry(included=False, reason=self._why_excluded(item))
            )
        manifest.compactions = [
            {
                "context_id": c.item.context_id,
                "source_type": c.item.source_type,
                "reason": c.reason.value,
                "original_tokens": c.original_tokens,
                "compacted_tokens": estimate_tokens(c.compacted_text),
            }
            for c in compactions
        ]
        manifest.dedup_dropped = dedup_dropped
        manifest.conflicts_resolved = conflicts_resolved
        manifest.token_estimate = total_tokens
        manifest.output_reserve_tokens = self.output_reserve
        manifest.model_context_limit = limit
        manifest.cacheable_prefix_tokens = prefix_tokens
        manifest.compile_ms = (time.perf_counter() - started) * 1000
        self._last_manifest = manifest

        dialogue_state_included = next((i.text for i in included if i.source_type == "dialogue_state"), None)
        web_blocks = [i.text for i in included if i.source_type in ("web", "external_data")]
        live_web_included = "\n\n".join(web_blocks) if web_blocks else None
        fingerprint = CompiledContextFingerprint.compute(manifest)

        return CompiledPromptContext(
            system_prefix=final_prefix,
            active_task_block=task_str,
            project_block=project_str,
            memory_blocks=memory_blocks,
            dialogue_messages=dialogue_messages,
            total_tokens=total_tokens,
            cache_fingerprint=hashlib.sha256(final_prefix.encode("utf-8")).hexdigest()[:16],
            manifest=manifest,
            dialogue_state_block=dialogue_state_included,
            live_web_block=live_web_included,
            manifest_fingerprint=fingerprint.combined_hash,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _compact_item(self, item: ContextItem, budget_left: int) -> tuple[ContextItem, ContextCompaction] | None:
        """Structured compaction (§30): head/tail keep, never blind mid-cut."""
        if budget_left < 24:
            return None
        max_chars = budget_left * 4
        marker = "\n...[compacted]...\n"
        body_budget = max_chars - len(marker)
        head = body_budget // 2
        tail = body_budget - head
        compact_text = f"{item.text[:head]}{marker}{item.text[-tail:]}" if item.text[-tail:] else item.text[:body_budget]
        compact_item = ContextItem(
            source_type=item.source_type,
            text=compact_text,
            token_estimate=estimate_tokens(compact_text),
            trust=item.trust,
            tier=item.tier,
            source_id=item.source_id,
            relevance=item.relevance,
            recency=item.recency,
            importance=item.importance,
            authority=item.authority,
            confidence=item.confidence,
            required=item.required,
            provenance={**item.provenance, "compacted": True},
        )
        return compact_item, ContextCompaction(
            item=item,
            compacted_text=compact_text,
            reason=CompactionReason.OVERFLOW,
            original_tokens=item.token_estimate,
        )

    @staticmethod
    def _why_included(item: ContextItem, decision: Any) -> str:
        if item.required:
            return "Required live state — pinned (§15)"
        if item.source_type in ("project", "checkpoint"):
            return "Active task/project state — execution tier"
        if item.source_type == "recent_turn":
            return "Recent exact turn — continuity tier"
        if item.source_type in ("web", "external_data"):
            return "Live web evidence — UNTRUSTED data block (§16)"
        if item.source_type == "rag":
            return "Retrieved evidence — data only"
        return f"Ranked {round(item.base_score(), 2)} ≥ budget fit ({decision.profile.value})"

    @staticmethod
    def _why_excluded(item: ContextItem) -> str:
        if item.trust in (TrustLevel.RAG, TrustLevel.WEB):
            return "Untrusted external data — low relevance or budget"
        if item.tier.value >= PriorityTier.TIER6_HISTORY.value:
            return "Cold history — not required by this turn"
        return "Token budget — ranked below included items"

    def _new_manifest(
        self,
        request_id: str,
        conversation_id: str | None,
        profile: ContextProfile,
        input_budget: int,
        prefix_tokens: int,
        *,
        compile_start: float,
        decision: Any,
    ) -> ContextManifest:
        return ContextManifest(
            request_id=request_id,
            conversation_id=conversation_id,
            profile=profile.value,
            allocations={},
            token_estimate=0,
            cacheable_prefix_tokens=prefix_tokens,
            output_reserve_tokens=self.output_reserve,
            model_context_limit=input_budget + self.output_reserve,
            compile_ms=(time.perf_counter() - compile_start) * 1000,
            retrieval_queries=[decision.reason],
        )

    @property
    def last_manifest(self) -> ContextManifest | None:
        return self._last_manifest


# ============================================================================
# B2.1 — CompiledContextPackage (directive §4) — the canonical contract between
# context SELECTION (ContextCompiler) and context SERIALIZATION (providers).
# Provider adapters consume this package; they must never retrieve context.
# ============================================================================


class CompiledContextPackage:
    """The single canonical model-context contract (directive §4).

    Everything the provider needs to serialize a request lives here. Provider
    formatters transform this package into OpenAI/Claude/Gemini/Groq message
    shapes — they may re-shape, never re-select.

    Semantic zones (§4): system_context (trusted policy), live_state (pinned
    dialogue control state), memory_context (application-trusted facts),
    conversation_context (untrusted recent turns), tool_context (data-only
    observations), rag_context (data-only external evidence).
    """

    __slots__ = (
        "manifest_id",
        "profile",
        "system_context",
        "live_state",
        "memory_context",
        "conversation_context",
        "tool_context",
        "rag_context",
        "user_text",
        "token_counts",
        "provenance",
    )

    def __init__(
        self,
        *,
        manifest: ContextManifest,
        profile: str,
        system_context: str,
        live_state: str = "",
        memory_context: tuple[str, ...] = (),
        conversation_context: tuple[tuple[str, str], ...] = (),
        tool_context: tuple[str, ...] = (),
        rag_context: tuple[str, ...] = (),
        user_text: str = "",
    ) -> None:
        self.manifest_id = manifest.manifest_id
        self.profile = profile
        self.system_context = system_context
        self.live_state = live_state
        self.memory_context = memory_context
        self.conversation_context = conversation_context
        self.tool_context = tool_context
        self.rag_context = rag_context
        self.user_text = user_text
        self.token_counts: dict[str, int] = {
            "system": estimate_tokens(system_context),
            "live_state": estimate_tokens(live_state),
            "memory": sum(estimate_tokens(m) for m in memory_context),
            "conversation": sum(estimate_tokens(f"{r}: {c}") for r, c in conversation_context),
            "tool": sum(estimate_tokens(t) for t in tool_context),
            "rag": sum(estimate_tokens(r) for r in rag_context),
            "user": estimate_tokens(user_text),
        }
        self.provenance: dict[str, Any] = {
            "profile": profile,
            "zones": list(self.token_counts.keys()),
        }


# ============================================================================
# B2.1 — ContextIntegrityVerifier (directive §12) — debug-only guard proving
# the manifest matches the actual provider payload.
# ============================================================================


class ContextIntegrityVerifier:
    """Verify CompiledContextPackage against its ContextManifest (§12).

    Flags: MISSING_SELECTED_ITEM, UNDECLARED_CONTEXT, TOKEN_BUDGET_MISMATCH.
    Only runs in debug/tests — zero cost on the hot path when not invoked.
    """

    @staticmethod
    def verify(package: CompiledContextPackage, manifest: ContextManifest) -> dict[str, Any]:
        issues: list[dict[str, Any]] = []

        included = manifest.included_items or []
        # Manifest entries may use either "tokens" (service-added entries) or
        # "token_estimate" (compiler entries).
        def _entry_tokens(entry: dict[str, Any]) -> int:
            return int(entry.get("tokens") or entry.get("token_estimate") or 0)

        included_tokens = sum(_entry_tokens(i) for i in included)

        # Payload zones that exist but have no manifest entry (UNDECLARED_CONTEXT).
        declared_zone_tokens: dict[str, int] = {
            "system": package.token_counts.get("system", 0),
            "user": package.token_counts.get("user", 0),
        }
        for item in included:
            st = item.get("source_type", "")
            if st in ("recent_turn", "message", "history"):
                declared_zone_tokens["conversation"] = declared_zone_tokens.get("conversation", 0) + _entry_tokens(item)
            elif st in ("memory", "entity", "summary", "episodic"):
                declared_zone_tokens["memory"] = declared_zone_tokens.get("memory", 0) + _entry_tokens(item)
            elif st == "tool_result":
                declared_zone_tokens["tool"] = declared_zone_tokens.get("tool", 0) + _entry_tokens(item)
            elif st in ("rag", "web", "repository"):
                declared_zone_tokens["rag"] = declared_zone_tokens.get("rag", 0) + _entry_tokens(item)

        if getattr(package, "live_state", None) and "live_state" not in declared_zone_tokens:
            issues.append({
                "type": "UNDECLARED_CONTEXT",
                "zone": "live_state",
                "detail": "live_state present in payload but not declared in manifest",
            })
        if getattr(package, "memory_context", None) and declared_zone_tokens.get("memory", 0) == 0:
            issues.append({
                "type": "UNDECLARED_CONTEXT",
                "zone": "memory",
                "detail": "memory context present but manifest records no memory items",
            })
        if getattr(package, "tool_context", None) and declared_zone_tokens.get("tool", 0) == 0:
            issues.append({
                "type": "UNDECLARED_CONTEXT",
                "zone": "tool",
                "detail": "tool observations present but manifest records no tool items",
            })
        if getattr(package, "rag_context", None) and declared_zone_tokens.get("rag", 0) == 0:
            issues.append({
                "type": "UNDECLARED_CONTEXT",
                "zone": "rag",
                "detail": "rag context present but manifest records no rag items",
            })

        # Check DUPLICATED_CONTEXT across zones
        for zone_name, items in [
            ("memory", getattr(package, "memory_context", None) or ()),
            ("tool", getattr(package, "tool_context", None) or ()),
            ("rag", getattr(package, "rag_context", None) or ()),
        ]:
            seen_items: set[str] = set()
            for itm in items:
                norm_itm = itm.strip()
                if norm_itm in seen_items:
                    issues.append({
                        "type": "DUPLICATED_CONTEXT",
                        "zone": zone_name,
                        "detail": f"duplicate content detected in {zone_name} context: {norm_itm[:60]!r}",
                    })
                seen_items.add(norm_itm)

        # Check TRUST_ESCALATION: external untrusted data marked trusted
        for item in included:
            st = item.get("source_type", "")
            tl = item.get("trust_level", "")
            if st in ("rag", "web", "tool_result", "external_doc") and tl in ("trusted", "TrustLevel.TRUSTED"):
                issues.append({
                    "type": "TRUST_ESCALATION",
                    "zone": st,
                    "detail": f"external untrusted source {item.get('id')} escalated to trusted",
                })

        # Check STALE_CONTEXT: out-of-sync or stale context items
        for item in included:
            if item.get("is_stale") or item.get("stale"):
                issues.append({
                    "type": "STALE_CONTEXT",
                    "zone": item.get("source_type", "unknown"),
                    "detail": f"stale context item {item.get('id')} included without archival note",
                })

        # Payload conversation vs declared (SELECTED_NOT_SENT / MISSING_SELECTED_ITEM).
        payload_conv_tokens = package.token_counts.get("conversation", 0)
        declared_conv = declared_zone_tokens.get("conversation", 0)
        if declared_conv > 0 and payload_conv_tokens == 0:
            issues.append({
                "type": "SELECTED_NOT_SENT",
                "zone": "conversation",
                "detail": f"manifest declares {declared_conv} conversation tokens absent from payload",
            })
            issues.append({
                "type": "MISSING_SELECTED_ITEM",
                "zone": "conversation",
                "detail": f"manifest declares {declared_conv} conversation tokens absent from payload",
            })

        # Budget & accounting guard (TOKEN_ACCOUNTING_MISMATCH / TOKEN_BUDGET_MISMATCH)
        total_payload = sum(package.token_counts.values())
        budget = manifest.model_context_limit - manifest.output_reserve_tokens
        if budget > 0 and total_payload > budget:
            issues.append({
                "type": "TOKEN_BUDGET_MISMATCH",
                "zone": "payload",
                "detail": f"payload {total_payload}t exceeds input budget {budget}t",
            })
            issues.append({
                "type": "TOKEN_ACCOUNTING_MISMATCH",
                "zone": "payload",
                "detail": f"payload {total_payload}t exceeds input budget {budget}t",
            })

        fingerprint = CompiledContextFingerprint.compute(manifest)
        return {
            "ok": not issues,
            "manifest_id": manifest.manifest_id,
            "package_manifest_id": package.manifest_id,
            "fingerprint": fingerprint.combined_hash,
            "issues": issues,
        }


# Canonical alias conforming to Directive §14
ContextPayloadIntegrityVerifier = ContextIntegrityVerifier
