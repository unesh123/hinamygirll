"""
HINAA OS — Reflective Voice & Metacognitive Explanation Contracts
Defines typed models, enums, dataclasses, and serialization for:
- Delivery intent routing
- Artifact understanding & evidence packs
- Metacognitive explanation planning & bounded self-model
- Spoken script composition & verification
- Exactly-once turn coordination & conversation topic memory
"""

from __future__ import annotations

import enum
import hashlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class DeliveryMode(str, enum.Enum):
    EXPLAIN_BRIEFLY = "EXPLAIN_BRIEFLY"          # ~20-45 seconds, 2-4 key points
    EXPLAIN_FULLY = "EXPLAIN_FULLY"              # Section-based walkthrough with transitions
    EXPLAIN_DIFFERENTLY = "EXPLAIN_DIFFERENTLY"  # New framing, analogy or example, same facts
    PERSPECTIVE_AND_CRITIQUE = "PERSPECTIVE_AND_CRITIQUE"  # Implications, tradeoffs, labeled interpretation
    TEACH_STEP_BY_STEP = "TEACH_STEP_BY_STEP"    # Pedagogical tutorial adapted to user pace
    DISCUSS = "DISCUSS"                          # Interactive two-way conversation
    READ_VERBATIM = "READ_VERBATIM"              # Exact word-for-word document narration
    VOICE_CHAT = "VOICE_CHAT"                    # General conversation dialogue


class ClaimPerspective(str, enum.Enum):
    SOURCE_SUPPORTED = "SOURCE_SUPPORTED"        # Directly backed by document source span/citation
    INFERENCE = "INFERENCE"                      # Logical deduction grounded in facts
    INTERPRETATION = "INTERPRETATION"            # Analytical perspective, tradeoff or critique
    NOT_ENOUGH_EVIDENCE = "NOT_ENOUGH_EVIDENCE"  # Acknowledged uncertainty or missing evidence


class TurnState(str, enum.Enum):
    CREATED = "CREATED"
    PLANNED = "PLANNED"
    QUEUED = "QUEUED"
    SYNTHESIZING = "SYNTHESIZING"
    PLAYING = "PLAYING"
    PLAYED = "PLAYED"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


@dataclass(slots=True)
class KeyClaim:
    claim_id: str
    factual_assertion: str
    source_span: str
    supporting_citation_ids: List[str] = field(default_factory=list)
    factual_confidence: float = 1.0
    conflicts: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "factual_assertion": self.factual_assertion,
            "source_span": self.source_span,
            "supporting_citation_ids": self.supporting_citation_ids,
            "factual_confidence": self.factual_confidence,
            "conflicts": self.conflicts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> KeyClaim:
        return cls(
            claim_id=data.get("claim_id", f"claim-{uuid.uuid4().hex[:8]}"),
            factual_assertion=data.get("factual_assertion", ""),
            source_span=data.get("source_span", ""),
            supporting_citation_ids=list(data.get("supporting_citation_ids", [])),
            factual_confidence=float(data.get("factual_confidence", 1.0)),
            conflicts=list(data.get("conflicts", [])),
        )


@dataclass(slots=True)
class ArtifactUnderstanding:
    artifact_id: str
    content_sha256: str
    content_type: str  # "research_report", "code_patch", "document", "image", "video", "task_receipt"
    version: int = 1
    access_scope: str = "tenant"
    tenant_id: str = "default"
    title: str = ""
    headings: List[str] = field(default_factory=list)
    section_summaries: Dict[str, str] = field(default_factory=dict)
    main_objectives: List[str] = field(default_factory=list)
    conclusions: List[str] = field(default_factory=list)
    key_claims: List[KeyClaim] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)
    unresolved_questions: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)
    code_receipts: Dict[str, Any] = field(default_factory=dict)
    media_receipts: Dict[str, Any] = field(default_factory=dict)
    raw_content: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "content_sha256": self.content_sha256,
            "content_type": self.content_type,
            "version": self.version,
            "access_scope": self.access_scope,
            "tenant_id": self.tenant_id,
            "title": self.title,
            "headings": self.headings,
            "section_summaries": self.section_summaries,
            "main_objectives": self.main_objectives,
            "conclusions": self.conclusions,
            "key_claims": [c.to_dict() for c in self.key_claims],
            "limitations": self.limitations,
            "unresolved_questions": self.unresolved_questions,
            "recommended_actions": self.recommended_actions,
            "code_receipts": self.code_receipts,
            "media_receipts": self.media_receipts,
            "raw_content": self.raw_content,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ArtifactUnderstanding:
        claims = [
            KeyClaim.from_dict(c) if isinstance(c, dict) else c
            for c in data.get("key_claims", [])
        ]
        return cls(
            artifact_id=data["artifact_id"],
            content_sha256=data.get("content_sha256", ""),
            content_type=data.get("content_type", "document"),
            version=int(data.get("version", 1)),
            access_scope=data.get("access_scope", "tenant"),
            tenant_id=data.get("tenant_id", "default"),
            title=data.get("title", ""),
            headings=list(data.get("headings", [])),
            section_summaries=dict(data.get("section_summaries", {})),
            main_objectives=list(data.get("main_objectives", [])),
            conclusions=list(data.get("conclusions", [])),
            key_claims=claims,
            limitations=list(data.get("limitations", [])),
            unresolved_questions=list(data.get("unresolved_questions", [])),
            recommended_actions=list(data.get("recommended_actions", [])),
            code_receipts=dict(data.get("code_receipts", {})),
            media_receipts=dict(data.get("media_receipts", {})),
            raw_content=data.get("raw_content", ""),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass(slots=True)
class ExplanationPlan:
    plan_id: str
    source_artifact_id: str
    source_sha256: str
    utterance_goal: str
    audience_level: str  # "general", "technical", "beginner", "executive"
    language: str        # "en", "ne", "mixed"
    delivery_mode: DeliveryMode
    time_budget_seconds: float
    selected_claim_ids: List[str] = field(default_factory=list)
    covered_section_ids: List[str] = field(default_factory=list)
    alternative_perspective: Optional[str] = None
    comparison_or_analogy: Optional[str] = None
    uncertainty_to_disclose: List[str] = field(default_factory=list)
    already_spoken_topic_ids: List[str] = field(default_factory=list)
    segment_plan: List[Dict[str, Any]] = field(default_factory=list)
    source_provenance: Dict[str, Any] = field(default_factory=dict)
    reason_for_mode: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "source_artifact_id": self.source_artifact_id,
            "source_sha256": self.source_sha256,
            "utterance_goal": self.utterance_goal,
            "audience_level": self.audience_level,
            "language": self.language,
            "delivery_mode": self.delivery_mode.value if isinstance(self.delivery_mode, DeliveryMode) else str(self.delivery_mode),
            "time_budget_seconds": self.time_budget_seconds,
            "selected_claim_ids": self.selected_claim_ids,
            "covered_section_ids": self.covered_section_ids,
            "alternative_perspective": self.alternative_perspective,
            "comparison_or_analogy": self.comparison_or_analogy,
            "uncertainty_to_disclose": self.uncertainty_to_disclose,
            "already_spoken_topic_ids": self.already_spoken_topic_ids,
            "segment_plan": self.segment_plan,
            "source_provenance": self.source_provenance,
            "reason_for_mode": self.reason_for_mode,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ExplanationPlan:
        mode = data.get("delivery_mode", DeliveryMode.EXPLAIN_BRIEFLY.value)
        if isinstance(mode, str):
            try:
                mode = DeliveryMode(mode)
            except ValueError:
                mode = DeliveryMode.EXPLAIN_BRIEFLY
        return cls(
            plan_id=data.get("plan_id", f"plan-{uuid.uuid4().hex[:8]}"),
            source_artifact_id=data.get("source_artifact_id", ""),
            source_sha256=data.get("source_sha256", ""),
            utterance_goal=data.get("utterance_goal", ""),
            audience_level=data.get("audience_level", "general"),
            language=data.get("language", "en"),
            delivery_mode=mode,
            time_budget_seconds=float(data.get("time_budget_seconds", 30.0)),
            selected_claim_ids=list(data.get("selected_claim_ids", [])),
            covered_section_ids=list(data.get("covered_section_ids", [])),
            alternative_perspective=data.get("alternative_perspective"),
            comparison_or_analogy=data.get("comparison_or_analogy"),
            uncertainty_to_disclose=list(data.get("uncertainty_to_disclose", [])),
            already_spoken_topic_ids=list(data.get("already_spoken_topic_ids", [])),
            segment_plan=list(data.get("segment_plan", [])),
            source_provenance=dict(data.get("source_provenance", {})),
            reason_for_mode=data.get("reason_for_mode", ""),
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass(slots=True)
class SpokenSegment:
    segment_id: str
    segment_index: int
    text: str
    perspectives: List[ClaimPerspective] = field(default_factory=list)
    expected_duration_seconds: float = 0.0
    idempotency_key: str = ""
    generation_id: int = 1
    state: TurnState = TurnState.CREATED
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "segment_index": self.segment_index,
            "text": self.text,
            "perspectives": [p.value if isinstance(p, ClaimPerspective) else str(p) for p in self.perspectives],
            "expected_duration_seconds": self.expected_duration_seconds,
            "idempotency_key": self.idempotency_key,
            "generation_id": self.generation_id,
            "state": self.state.value if isinstance(self.state, TurnState) else str(self.state),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SpokenSegment:
        persp_list = []
        for p in data.get("perspectives", []):
            if isinstance(p, ClaimPerspective):
                persp_list.append(p)
            elif isinstance(p, str):
                try:
                    persp_list.append(ClaimPerspective(p))
                except ValueError:
                    persp_list.append(ClaimPerspective.SOURCE_SUPPORTED)
        state = data.get("state", TurnState.CREATED.value)
        if isinstance(state, str):
            try:
                state = TurnState(state)
            except ValueError:
                state = TurnState.CREATED

        return cls(
            segment_id=data.get("segment_id", f"seg-{uuid.uuid4().hex[:8]}"),
            segment_index=int(data.get("segment_index", 0)),
            text=data.get("text", ""),
            perspectives=persp_list,
            expected_duration_seconds=float(data.get("expected_duration_seconds", 0.0)),
            idempotency_key=data.get("idempotency_key", ""),
            generation_id=int(data.get("generation_id", 1)),
            state=state,
            created_at=float(data.get("created_at", time.time())),
        )


@dataclass(slots=True)
class SpokenTopicRecord:
    record_id: str
    conversation_id: str
    artifact_id: str
    tenant_id: str = "default"
    claim_ids_explained: List[str] = field(default_factory=list)
    narrative_angle: str = ""
    examples_used: List[str] = field(default_factory=list)
    last_speech_turn: int = 0
    user_feedback: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "conversation_id": self.conversation_id,
            "artifact_id": self.artifact_id,
            "tenant_id": self.tenant_id,
            "claim_ids_explained": self.claim_ids_explained,
            "narrative_angle": self.narrative_angle,
            "examples_used": self.examples_used,
            "last_speech_turn": self.last_speech_turn,
            "user_feedback": self.user_feedback,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SpokenTopicRecord:
        return cls(
            record_id=data.get("record_id", f"rec-{uuid.uuid4().hex[:8]}"),
            conversation_id=data.get("conversation_id", ""),
            artifact_id=data.get("artifact_id", ""),
            tenant_id=data.get("tenant_id", "default"),
            claim_ids_explained=list(data.get("claim_ids_explained", [])),
            narrative_angle=data.get("narrative_angle", ""),
            examples_used=list(data.get("examples_used", [])),
            last_speech_turn=int(data.get("last_speech_turn", 0)),
            user_feedback=data.get("user_feedback"),
            timestamp=float(data.get("timestamp", time.time())),
        )


def compute_segment_idempotency_key(
    conversation_id: str,
    response_id: str,
    generation_id: int,
    segment_index: int,
    text: str,
) -> str:
    """Computes a deterministic, collision-resistant idempotency key for exactly-once audio playback."""
    clean_text = " ".join(text.strip().split())
    raw = f"{conversation_id}:{response_id}:{generation_id}:{segment_index}:{clean_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
