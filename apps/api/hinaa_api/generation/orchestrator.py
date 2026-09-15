"""Provider-neutral generation orchestration (Phase B1.1).

Continuation policy lives HERE, not in any provider. Providers expose only
normalized streaming metadata (chunk events + finish reason); the orchestrator
decides continue / dedup / finalize / truncate.

Directive §1–§3 honored:
- ``GenerationFinishReason`` — normalized provider finish reasons; policy
  operates only on normalized values.
- ``GenerationProviderCapabilities`` — honest per-adapter capability profile.
- ``GenerationOrchestrator`` — the ONE continuation engine, shared by every
  provider (Gemini, Groq, OpenAI-compatible, agent-router).
"""

from __future__ import annotations

import inspect
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from .continuation import (
    ContinuationStatus,
    GenerationContinuationState,
    SeamGuard,
    detect_continuation_need,
    run_consistency_pass,
)

__all__ = [
    "GenerationFinishReason",
    "GenerationProviderCapabilities",
    "ProviderSegmentStream",
    "SegmentResult",
    "SegmentTraceRecord",
    "GenerationTrace",
    "GenerationOrchestrator",
    "OrchestratorOutcome",
    "OPENAI_FINISH_REASON_MAP",
    "GEMINI_FINISH_REASON_MAP",
    "map_finish_reason",
]


class GenerationFinishReason(str, Enum):
    """Normalized finish reasons (directive §2).

    Continuation policy operates ONLY on these values, never on raw
    provider strings. Semantics:
    - MAX_TOKENS / LENGTH + unfinished structure → continuation
    - STOP + structurally complete → no continuation
    - CONTENT_FILTER → never blindly continue (report + finalize)
    - TOOL_CALL → hand over to the tool runtime (no text continuation)
    - ERROR → preserve completed text, classify failure
    """

    STOP = "STOP"
    MAX_TOKENS = "MAX_TOKENS"
    LENGTH = "LENGTH"
    CONTENT_FILTER = "CONTENT_FILTER"
    TOOL_CALL = "TOOL_CALL"
    ERROR = "ERROR"
    CONTINUE = "CONTINUE"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


# Raw finish-reason strings → normalized enum. Covers OpenAI-compatible
# (openai/groq/agent-router/custom gateways) and Google Gemini shapes.
OPENAI_FINISH_REASON_MAP: dict[str, GenerationFinishReason] = {
    "stop": GenerationFinishReason.STOP,
    "length": GenerationFinishReason.LENGTH,
    "max_tokens": GenerationFinishReason.MAX_TOKENS,
    "tool_calls": GenerationFinishReason.TOOL_CALL,
    "function_call": GenerationFinishReason.TOOL_CALL,
    "content_filter": GenerationFinishReason.CONTENT_FILTER,
    "error": GenerationFinishReason.ERROR,
    "cancelled": GenerationFinishReason.CANCELLED,
    "other": GenerationFinishReason.UNKNOWN,
    "continue": GenerationFinishReason.CONTINUE,
}

GEMINI_FINISH_REASON_MAP: dict[str, GenerationFinishReason] = {
    "STOP": GenerationFinishReason.STOP,
    "MAX_TOKENS": GenerationFinishReason.MAX_TOKENS,
    "SAFETY": GenerationFinishReason.CONTENT_FILTER,
    "RECITATION": GenerationFinishReason.CONTENT_FILTER,
    "LANGUAGE": GenerationFinishReason.CONTENT_FILTER,
    "CONTINUE": GenerationFinishReason.CONTINUE,
    "OTHER": GenerationFinishReason.UNKNOWN,
    "MALFORMED_FUNCTION_CALL": GenerationFinishReason.UNKNOWN,
}


def map_finish_reason(raw: str | None, *, family: str = "openai") -> GenerationFinishReason:
    """Normalize a provider-specific finish reason string.

    Case-insensitive with cross-family fallback: uppercase OpenAI-style
    values (some gateways emit 'MAX_TOKENS') and lowercase Gemini-style
    values both normalize correctly.
    """
    if not raw:
        return GenerationFinishReason.UNKNOWN
    primary = GEMINI_FINISH_REASON_MAP if family == "gemini" else OPENAI_FINISH_REASON_MAP
    secondary = OPENAI_FINISH_REASON_MAP if family == "gemini" else GEMINI_FINISH_REASON_MAP
    for table in (primary, secondary):
        for candidate in (raw, raw.lower(), raw.upper()):
            if candidate in table:
                return table[candidate]
    return GenerationFinishReason.UNKNOWN


class GenerationProviderCapabilities:
    """What one provider adapter can honestly support (directive §3).

    The capability registry must reflect the ACTUAL adapter — e.g. the
    OpenAI-compatible `_stream_text` today yields text deltas without
    surfacing finish reasons, so `supports_finish_reason` is False until
    that adapter is upgraded; continuation then falls back to structure-
    only detection instead of pretending to know the finish reason.
    """

    def __init__(
        self,
        *,
        provider_id: str,
        supports_streaming: bool = True,
        supports_finish_reason: bool = True,
        supports_max_output_tokens: bool = True,
        supports_structured_output: bool = True,
        supports_tool_calls: bool = True,
        max_output_tokens: int | None = None,
        maximum_context: int | None = None,
        continuation_supported: bool = True,
    ) -> None:
        self.provider_id = provider_id
        self.supports_streaming = supports_streaming
        self.supports_finish_reason = supports_finish_reason
        self.supports_max_output_tokens = supports_max_output_tokens
        self.supports_structured_output = supports_structured_output
        self.supports_tool_calls = supports_tool_calls
        self.max_output_tokens = max_output_tokens
        self.maximum_context = maximum_context
        self.continuation_supported = continuation_supported

    def as_dict(self) -> dict[str, object]:
        return {
            "provider_id": self.provider_id,
            "supports_streaming": self.supports_streaming,
            "supports_finish_reason": self.supports_finish_reason,
            "supports_max_output_tokens": self.supports_max_output_tokens,
            "supports_structured_output": self.supports_structured_output,
            "supports_tool_calls": self.supports_tool_calls,
            "max_output_tokens": self.max_output_tokens,
            "maximum_context": self.maximum_context,
            "continuation_supported": self.continuation_supported,
        }


class ProviderSegmentStream(Protocol):
    """One continuation round's streaming source.

    Implementations yield sanitized text deltas and record the provider's
    finish reason (raw string) into ``finish_reason_holder["value"]`` when
    the underlying stream ends. The orchestrator owns all policy.
    """

    @property
    def finish_reason_holder(self) -> dict[str, str | None]: ...

    def __aiter__(self) -> AsyncIterator[str]: ...


@dataclass
class SegmentResult:
    """What one segment produced (evidence for tests and metrics)."""

    text: str
    finish_reason: GenerationFinishReason
    events: int = 0
    deduped_chars: int = 0


@dataclass
class SegmentTraceRecord:
    """Diagnostic trace record for one generation segment (P0.14 §7)."""

    segment_number: int
    finish_reason: str
    characters: int
    seam_overlap_removed: int
    continuation_decision: bool
    decision_reason: str
    decision_evidence: dict[str, object]
    explanation: str  # "WHY DID HINA CONTINUE?" or "WHY DID HINA STOP?"
    sections_completed: list[str] = field(default_factory=list)
    remaining_sections: list[str] = field(default_factory=list)


@dataclass
class GenerationTrace:
    """Audit & inspection trace for segmented long-form generation (P0.14 §6–§7)."""

    generation_id: str
    provider: str = ""
    model: str = ""
    requested_max_segments: int = 0
    effective_max_segments: int = 0
    requested_max_continuations: int = 0
    effective_max_continuations: int = 0
    char_budget: int = 0
    total_characters: int = 0
    total_segments: int = 0
    total_seam_deduped_chars: int = 0
    final_status: str = ""
    segments: list[SegmentTraceRecord] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "generation_id": self.generation_id,
            "provider": self.provider,
            "model": self.model,
            "requested_max_segments": self.requested_max_segments,
            "effective_max_segments": self.effective_max_segments,
            "requested_max_continuations": self.requested_max_continuations,
            "effective_max_continuations": self.effective_max_continuations,
            "char_budget": self.char_budget,
            "total_characters": self.total_characters,
            "total_segments": self.total_segments,
            "total_seam_deduped_chars": self.total_seam_deduped_chars,
            "final_status": self.final_status,
            "segments": [
                {
                    "segment_number": s.segment_number,
                    "finish_reason": s.finish_reason,
                    "characters": s.characters,
                    "seam_overlap_removed": s.seam_overlap_removed,
                    "continuation_decision": s.continuation_decision,
                    "decision_reason": s.decision_reason,
                    "decision_evidence": s.decision_evidence,
                    "explanation": s.explanation,
                    "sections_completed": s.sections_completed,
                    "remaining_sections": s.remaining_sections,
                }
                for s in self.segments
            ],
        }


class GenerationOrchestrator:
    """Shared continuation engine used by ALL providers (directive §1).

    Usage: the provider builds a fresh segment stream per round (first call
    streams the user's request; continuation rounds resume from the tail).
    The orchestrator consumes deltas, suppresses seam overlap on later
    segments, decides continuation from normalized finish reasons +
    structural detection, and finalizes with the consistency pass.
    """

    def __init__(
        self,
        *,
        max_continuations: int,
        char_budget: int,
        generation_id: str = "orchestrated",
        planned_sections: tuple[str, ...] = (),
        provider: str = "",
        model: str = "",
        requested_max_continuations: int | None = None,
    ) -> None:
        self.max_continuations = max_continuations
        self.char_budget = char_budget
        self.planned_sections = planned_sections
        self.provider = provider
        self.model = model
        req_cont = (
            requested_max_continuations
            if requested_max_continuations is not None
            else max_continuations
        )
        self.trace = GenerationTrace(
            generation_id=generation_id,
            provider=provider,
            model=model,
            requested_max_segments=req_cont + 1,
            effective_max_segments=max_continuations + 1,
            requested_max_continuations=req_cont,
            effective_max_continuations=max_continuations,
            char_budget=char_budget,
        )
        self.state = GenerationContinuationState(
            generation_id=generation_id,
            max_segments=max_continuations + 1,
            char_budget=char_budget,
        )
        self.deduped_total = 0
        self.segment_results: list[SegmentResult] = []

    async def run(
        self,
        *,
        first_segment_stream: AsyncIterator[str],
        first_finish_reason_holder: dict[str, str | None],
        continuation_stream_factory: Callable[[str], tuple[AsyncIterator[str], dict[str, str | None]]] | None,
        emit_delta: Callable[[str], Awaitable[None]],
        sanitize: Callable[[str], str] = lambda s: s,
        gemini_family: bool = False,
    ) -> "OrchestratorOutcome":
        family = "gemini" if gemini_family else "openai"
        chunks: list[str] = []
        emitted_chunks: list[str] = []
        segment_chars = 0
        segment_no = 0
        seam_guard = SeamGuard()

        while True:
            if segment_no == 0:
                deltas = first_segment_stream
                holder = first_finish_reason_holder
            else:
                if continuation_stream_factory is None:
                    break  # provider cannot continue — honest stop
                prior = "".join(chunks)
                seam_guard.reset_for_segment(prior)
                result = continuation_stream_factory(prior)
                if inspect.isawaitable(result):
                    result = await result
                deltas, holder = result

            events = 0
            async for raw in deltas:
                delta = sanitize(raw)
                if not delta:
                    continue
                remaining = self.char_budget - len("".join(chunks))
                if remaining <= 0:
                    break
                delta = delta[:remaining]
                chunks.append(delta)
                segment_chars += len(delta)
                events += 1
                if segment_no == 0:
                    await emit_delta(delta)
                    emitted_chunks.append(delta)
                else:
                    emit_text = seam_guard.feed(delta)
                    if emit_text:
                        await emit_delta(emit_text)
                        emitted_chunks.append(emit_text)

            if segment_no > 0:
                flush = seam_guard.finish_segment()
                if flush:
                    await emit_delta(flush)
                    emitted_chunks.append(flush)
                self.deduped_total += seam_guard.deduped_chars

            self.state.register_segment(segment_chars)
            raw_reason = (holder or {}).get("value")
            reason = map_finish_reason(raw_reason, family=family)
            self.segment_results.append(
                SegmentResult(text="".join(chunks), finish_reason=reason, events=events)
            )
            segment_chars = 0
            segment_no += 1

            # Policy (§2): normalized reasons drive continuation.
            joined = "".join(chunks)
            if reason in {GenerationFinishReason.CONTENT_FILTER, GenerationFinishReason.TOOL_CALL}:
                # Never blindly continue past a filter; tool calls hand over.
                self.state.status = (
                    ContinuationStatus.CANCELLED
                    if reason is GenerationFinishReason.TOOL_CALL
                    else ContinuationStatus.COMPLETED
                )
                break
            if reason is GenerationFinishReason.ERROR:
                # Preserve completed text; classify as FAILED but keep output.
                self.state.status = ContinuationStatus.FAILED
                break

            decision = detect_continuation_need(
                text=joined,
                finish_reason=reason.value,
                char_budget=self.char_budget,
                segment_number=segment_no,
                max_segments=self.state.max_segments,
                planned_sections=self.planned_sections,
            )

            explanation = (
                f"WHY DID HINA CONTINUE? -> {decision.reason}"
                if decision.continue_needed
                else f"WHY DID HINA STOP? -> {decision.reason}"
            )
            self.trace.segments.append(
                SegmentTraceRecord(
                    segment_number=segment_no,
                    finish_reason=reason.value,
                    characters=len(joined),
                    seam_overlap_removed=seam_guard.deduped_chars if segment_no > 1 else 0,
                    continuation_decision=decision.continue_needed,
                    decision_reason=decision.reason,
                    decision_evidence=decision.evidence.as_dict() if hasattr(decision.evidence, "as_dict") else {},
                    explanation=explanation,
                    sections_completed=[s for s in self.planned_sections if s not in getattr(decision.evidence, "remaining_sections", ())],
                    remaining_sections=list(getattr(decision.evidence, "remaining_sections", ())),
                )
            )

            if not decision.continue_needed:
                self.state.status = decision.status
                break
            self.state.status = ContinuationStatus.ACTIVE

        answer = "".join(chunks).strip()
        emitted = "".join(emitted_chunks).strip()
        # Canonical text is what the USER SAW (deduped); raw model text is
        # retained for diagnostics only. Consistency runs on canonical.
        consistency = run_consistency_pass(emitted, apply_repairs=True)

        self.trace.total_characters = len(consistency.text)
        self.trace.total_segments = segment_no
        self.trace.total_seam_deduped_chars = self.deduped_total
        self.trace.final_status = self.state.status.value

        return OrchestratorOutcome(
            text=consistency.text,
            raw_text=answer,
            status=self.state.status,
            segments=segment_no,
            deduped_chars=self.deduped_total,
            consistency_issues=[
                {"kind": i.kind, "detail": i.detail, "repaired": i.repaired}
                for i in consistency.issues
            ],
            segment_finish_reasons=[
                r.finish_reason.value for r in self.segment_results
            ],
            trace=self.trace,
        )


@dataclass
class OrchestratorOutcome:
    text: str
    raw_text: str
    status: ContinuationStatus
    segments: int
    deduped_chars: int
    consistency_issues: list[dict[str, object]] = field(default_factory=list)
    segment_finish_reasons: list[str] = field(default_factory=list)
    trace: GenerationTrace | None = None
