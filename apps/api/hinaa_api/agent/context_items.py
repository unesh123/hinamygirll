"""HINAA Phase B2 — Context item model, trust/authority, and manifest.

Core security rule (directive §13): retrieved content is DATA. It never
promotes to instruction authority. Every context candidate carries an
explicit trust level and an instruction-authority flag; the prompt assembly
renders untrusted blocks inside untrusted tags so the model is told they are
data, not policy.

Directive §11/§12/§19/§20:
- ``ContextItem`` — one retrieval candidate with relevance/recency/importance/
  authority/affinity scoring inputs and provenance.
- ``ContextManifest`` — per-request ledger of what was included, excluded,
  compacted, retrieved, and pinned, with a full WHY trace for the developer
  inspector (directive §38: why-did-Hina-forget trace).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TrustLevel(str, Enum):
    """Where a piece of context came from — drives prompt-side trust tags."""

    SYSTEM = "system"                      # Tier 0: security/provider contract
    APPLICATION = "application"            # Tier 0/1: app-configured state
    USER_EXPLICIT = "user_explicit"        # Tier 1: the user said it now
    PROJECT_STATE = "project_state"        # Tier 2
    MEMORY = "memory"                      # Tier 4
    RAG = "rag"                            # Tier 5: untrusted external data
    WEB = "web"                            # Tier 5: untrusted external data
    EXTERNAL_DATA = "external_data"        # Tier 5: untrusted external data
    TOOL_OUTPUT = "tool_output"            # Tier 2/3: evidence, data-only
    HISTORY = "history"                    # Tier 3/6


class InstructionAuthority(str, Enum):
    """Instruction authority carried by a context block (P0.15 §5/§6)."""

    AUTHORITATIVE = "authoritative"        # System policies / security contract
    STANDARD = "standard"                  # Live user turn request
    NONE = "none"                          # External data, web, tool output, RAG


class PriorityTier(int, Enum):
    """Directive §14 — a lower tier may never displace unresolved higher tier."""

    TIER0_SECURITY = 0          # system/security/provider contract
    TIER1_LIVE_STATE = 1        # current message, active goal, corrections
    TIER2_EXECUTION = 2         # active task, checkpoint, project, assets
    TIER3_CONTINUITY = 3        # recent exact turns, tool observations
    TIER4_MEMORY = 4            # semantic/episodic/procedural memory
    TIER5_KNOWLEDGE = 5         # RAG, files, repository, external evidence
    TIER6_HISTORY = 6           # old conversations, archived artifacts


# Trust levels allowed to carry instruction authority. Everything else is
# DATA-ONLY and must be rendered as untrusted content in prompts.
INSTRUCTION_AUTHORITIES = frozenset(
    {TrustLevel.SYSTEM, TrustLevel.APPLICATION, TrustLevel.USER_EXPLICIT}
)


class ContextItem:
    """One context candidate with scoring inputs and provenance (§12)."""

    __slots__ = (
        "context_id",
        "source_type",
        "source_id",
        "text",
        "token_estimate",
        "relevance",
        "recency",
        "importance",
        "authority",
        "confidence",
        "task_affinity",
        "project_affinity",
        "entity_affinity",
        "trust",
        "tier",
        "required",
        "pinnable",
        "provenance",
        "created_at",
        "exclusion_reason",
    )

    def __init__(
        self,
        *,
        source_type: str,
        text: str,
        token_estimate: int,
        trust: TrustLevel = TrustLevel.HISTORY,
        tier: PriorityTier = PriorityTier.TIER3_CONTINUITY,
        source_id: str | None = None,
        relevance: float = 0.3,
        recency: float = 0.5,
        importance: float = 0.5,
        authority: float = 0.5,
        confidence: float = 0.8,
        task_affinity: float = 0.0,
        project_affinity: float = 0.0,
        entity_affinity: float = 0.0,
        required: bool = False,
        pinnable: bool = False,
        provenance: dict[str, Any] | None = None,
    ) -> None:
        self.context_id = self._derive_id(source_type, source_id, text)
        self.source_type = source_type
        self.source_id = source_id
        self.text = text
        self.token_estimate = max(1, token_estimate)
        self.relevance = relevance
        self.recency = recency
        self.importance = importance
        self.authority = authority
        self.confidence = confidence
        self.task_affinity = task_affinity
        self.project_affinity = project_affinity
        self.entity_affinity = entity_affinity
        self.trust = trust
        self.tier = tier
        self.required = required
        self.pinnable = pinnable
        self.provenance = provenance
        # B2.1 — why this item was excluded, set during compile overflow/gating.
        self.exclusion_reason: str | None = None
        self.created_at = time.time()

    @staticmethod
    def _derive_id(source_type: str, source_id: str | None, text: str) -> str:
        digest = hashlib.sha256(f"{source_type}:{source_id or ''}:{text[:256]}".encode("utf-8")).hexdigest()[:12]
        return f"ctx_{digest}"

    def can_carry_instructions(self) -> bool:
        """Security gate (§13): only SYSTEM/APPLICATION/USER_EXPLICIT may instruct."""
        return self.trust in INSTRUCTION_AUTHORITIES

    def base_score(self) -> float:
        """Multi-factor base score before source-specific adjustments (§21)."""
        score = (
            self.relevance * 0.30
            + self.recency * 0.15
            + self.importance * 0.20
            + self.authority * 0.25
            + (self.task_affinity + self.project_affinity + self.entity_affinity) * 0.10
        )
        return min(1.0, score) * self.confidence

    def to_manifest_entry(self, *, included: bool, reason: str) -> dict[str, Any]:
        """Manifest ledger entry with WHY included/excluded (§20)."""
        entry: dict[str, Any] = {
            "context_id": self.context_id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "tier": self.tier.value,
            "trust": self.trust.value,
            "token_estimate": self.token_estimate,
            "score": round(self.base_score(), 4),
            "included": included,
            "reason": reason,
        }
        if not included:
            # Never persist full text of excluded items (§52 privacy).
            entry["content_hash"] = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:12]
        return entry


class CompactionReason(str, Enum):
    NONE = "none"
    OVERFLOW = "overflow"
    SOURCE_BUDGET = "source_budget"
    PROFILE = "profile"


@dataclass
class ContextCompaction:
    """A recorded compaction: raw → compact form (§30)."""

    item: ContextItem
    compacted_text: str
    reason: CompactionReason
    original_tokens: int


class ManifestStatus(str, Enum):
    OK = "ok"
    PINNED_OVERFLOW = "pinned_overflow"   # pinned state alone exceeded budget
    FALLBACK_HOT = "fallback_hot"         # compilation failed → HOT context


@dataclass
class ContextManifest:
    """Per-request context ledger (§19). Developer-inspector visible."""

    request_id: str
    conversation_id: str | None
    profile: str
    allocations: dict[str, int]
    manifest_id: str = field(default_factory=lambda: f"cm_{int(time.time() * 1000):x}_{hashlib.sha1(str(time.time_ns()).encode()).hexdigest()[:8]}")
    included_items: list[dict[str, Any]] = field(default_factory=list)
    excluded_items: list[dict[str, Any]] = field(default_factory=list)
    compactions: list[dict[str, Any]] = field(default_factory=list)
    retrieval_queries: list[str] = field(default_factory=list)
    pinning_decisions: list[str] = field(default_factory=list)
    pinned_overflow: list[str] = field(default_factory=list)
    dedup_dropped: int = 0
    conflicts_resolved: list[dict[str, Any]] = field(default_factory=list)
    token_estimate: int = 0
    cacheable_prefix_tokens: int = 0
    output_reserve_tokens: int = 0
    model_context_limit: int = 0
    compile_ms: float = 0.0
    status: ManifestStatus = ManifestStatus.OK
    generated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "request_id": self.request_id,
            "conversation_id": self.conversation_id,
            "profile": self.profile,
            "status": self.status.value,
            "allocations": self.allocations,
            "token_estimate": self.token_estimate,
            "cacheable_prefix_tokens": self.cacheable_prefix_tokens,
            "output_reserve_tokens": self.output_reserve_tokens,
            "model_context_limit": self.model_context_limit,
            "compile_ms": round(self.compile_ms, 2),
            "included": self.included_items,
            "excluded": self.excluded_items,
            "compactions": self.compactions,
            "retrieval_queries": self.retrieval_queries,
            "pinning_decisions": self.pinning_decisions,
            "pinned_overflow": self.pinned_overflow,
            "dedup_dropped": self.dedup_dropped,
            "conflicts_resolved": self.conflicts_resolved,
            "generated_at": self.generated_at,
        }
