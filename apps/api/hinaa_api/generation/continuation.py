"""Coherent long-form generation engine (Phase B1).

This module is the *connective intelligence* behind multi-segment output.
It replaces the naive "ask the model to continue" loop with:

1. ``GenerationContinuationState`` — structured state for one generation
   (sections, segment bookkeeping, counters, status).
2. ``detect_continuation_need`` — decides whether another segment is
   actually required using finish reasons and structural signals, NOT
   merely "we hit a token cap".
3. ``SeamGuard`` / ``seam_dedup`` — removes exact/normalized overlap at
   segment boundaries so continuation never duplicates text.
4. ``run_consistency_pass`` — final structural verification/repair of the
   concatenated output (open fences, placeholders, duplicated headings).

Design rules honored here (directive §2–§6, §37, §55):
- Canonical text is NEVER modified during streaming; display repair is a
  renderer concern.
- The consistency pass only repairs *unambiguous* defects (an unclosed
  code fence at the end of a COMPLETED generation) and always reports
  everything it finds.
- Failure keeps completed text; continuation state can be resumed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "word_count",
    "ContinuationStatus",
    "ContinuationReason",
    "ContinuationNeeded",
    "ContinuationEvidence",
    "ContinuationDecision",
    "GenerationContinuationState",
    "strip_trailing_completion_decorations",
    "detect_continuation_need",
    "normalize_for_comparison",
    "seam_dedup",
    "SeamGuard",
    "ConsistencyIssue",
    "ConsistencyReport",
    "run_consistency_pass",
]


def word_count(text: str) -> int:
    """Words of written substance in a draft — the unit the depth contract uses.

    Whitespace-split, so Markdown table pipes and fences cost little: a table
    heavy report counts close to what a reader would call its length.
    """
    return len(text.split())


class ContinuationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    COMPLETED = "COMPLETED"
    TRUNCATED = "TRUNCATED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ContinuationReason(str, Enum):
    """Why another segment is (or is not) required."""

    FINISH_REASON_MAX_TOKENS = "finish_reason_max_tokens"
    INCOMPLETE_SENTENCE = "incomplete_sentence"
    INCOMPLETE_PARAGRAPH = "incomplete_paragraph"
    OPEN_CODE_FENCE = "open_code_fence"
    OPEN_JSON_STRUCTURE = "open_json_structure"
    INCOMPLETE_TABLE = "incomplete_table"
    UNFINISHED_SECTION = "unfinished_section"
    MISSING_REQUESTED_SECTIONS = "missing_requested_sections"
    DEPTH_CONTRACT_UNMET = "depth_contract_unmet"
    NONE = "none"


@dataclass
class ContinuationNeeded:
    reason: ContinuationReason
    detail: str = ""


@dataclass
class ContinuationEvidence:
    """Detailed evidence supporting a continuation or completion decision (P0.14 §4)."""

    max_tokens: bool = False
    natural_stop: bool = False
    mid_sentence: bool = False
    mid_word: bool = False
    open_fence: bool = False
    open_json: bool = False
    incomplete_table: bool = False
    remaining_sections: tuple[str, ...] = ()
    conversational_closing: bool = False
    trailing_decorations: str = ""
    shallow_vs_contract: bool = False
    words_short: int = 0

    def as_dict(self) -> dict[str, object]:
        return {
            "max_tokens": self.max_tokens,
            "natural_stop": self.natural_stop,
            "mid_sentence": self.mid_sentence,
            "mid_word": self.mid_word,
            "open_fence": self.open_fence,
            "open_json": self.open_json,
            "incomplete_table": self.incomplete_table,
            "remaining_sections": list(self.remaining_sections),
            "conversational_closing": self.conversational_closing,
            "trailing_decorations": self.trailing_decorations,
            "shallow_vs_contract": self.shallow_vs_contract,
            "words_short": self.words_short,
        }


@dataclass
class ContinuationDecision:
    continue_needed: bool
    reasons: tuple[ContinuationNeeded, ...] = ()
    status: ContinuationStatus = ContinuationStatus.COMPLETED
    confidence: float = 1.0
    provider_finish_reason: str | None = None
    evidence: ContinuationEvidence = field(default_factory=ContinuationEvidence)
    reason: str = ""

    @property
    def should_continue(self) -> bool:
        return self.continue_needed

    @property
    def reason_ids(self) -> tuple[str, ...]:
        return tuple(r.reason.value for r in self.reasons)


@dataclass
class GenerationContinuationState:
    """Durable state for one long generation (directive §3)."""

    generation_id: str
    conversation_id: str = ""
    output_type: str = "text"
    objective: str = ""

    completed_sections: list[str] = field(default_factory=list)
    current_section: str = ""
    remaining_sections: list[str] = field(default_factory=list)

    facts_introduced: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)

    segment_number: int = 0
    max_segments: int = 5
    token_count: int = 0
    character_count: int = 0
    char_budget: int = 200_000

    status: ContinuationStatus = ContinuationStatus.ACTIVE

    def register_segment(self, segment_chars: int, segment_tokens: int = 0) -> None:
        self.segment_number += 1
        self.character_count += segment_chars
        self.token_count += segment_tokens

    def can_continue(self) -> bool:
        return (
            self.status == ContinuationStatus.ACTIVE
            and self.segment_number < self.max_segments
            and self.character_count < self.char_budget
        )


# ---------------------------------------------------------------------------
# Structural detection
# ---------------------------------------------------------------------------

_MID_WORD_RE = re.compile(r"[A-Za-z\u0900-\u097F]$")
_STRUCTURAL_TAIL_RE = re.compile(
    r"(?:\n#{1,6}\s+[^\n]*$|\n(?:[-*+]|\d+\.)\s*$|\n>\s*$)"
)
_TERMINAL_PUNCT_RE = re.compile(r"[.!?:;\u0964\u0965]\s*$")


def _count_unbalanced(text: str) -> tuple[int, int]:
    """(open code fences, net JSON brace depth) heuristic counts."""
    fence_count = text.count("```")
    # Ignore fenced content when counting braces: JSON inside code blocks
    # is legitimately balanced by the fence, not by brace matching alone.
    outside = []
    in_fence = False
    for line in text.split("\n"):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            outside.append(line)
    outside_text = "\n".join(outside)
    depth = outside_text.count("{") - outside_text.count("}")
    return fence_count % 2, depth


def _looks_like_incomplete_table(text: str) -> bool:
    """A Markdown table row without a trailing pipe is a mid-row stop."""
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return False
    last = lines[-1].strip()
    if not (last.startswith("|") or "|" in last):
        return False
    has_header_sep = any(
        re.match(r"^\s*\|?[\s:|-]+\|[\s:|-]*$", ln) for ln in lines[-6:]
    )
    return has_header_sep and not last.endswith("|")


_DECORATIVE_TRAILING_RE = re.compile(
    r"[\s\"'”’\)\]\}*_`\uFE0F\u2600-\u27BF\U0001F300-\U0001FAFF]+$"
)
_CONVERSATIONAL_CLOSING_RE = re.compile(
    r"(?:say the word|let me know|feel free|hope this helps|ask away|ready when you are|take care|just ping me|which (?:direction|angle|part|option)|what do you think)[^\n]*$",
    re.IGNORECASE,
)


def strip_trailing_completion_decorations(text: str) -> tuple[str, str]:
    """Remove purely decorative presentation characters from text tail for detection only (P0.14 §3).

    Does NOT modify canonical generated text. Preserves mathematics, currency,
    arrows, units, and semantic Unicode punctuation.
    Returns (cleaned_tail, stripped_decorations).
    """
    match = _DECORATIVE_TRAILING_RE.search(text)
    if not match:
        return text, ""
    return text[: match.start()], match.group(0)


def detect_continuation_need(
    *,
    text: str,
    finish_reason: str | None = None,
    char_budget: int = 150_000,
    segment_number: int = 1,
    max_segments: int = 10,
    planned_sections: tuple[str, ...] = (),
    remaining_sections: tuple[str, ...] = (),
    min_words: int = 0,
) -> ContinuationDecision:
    """Decide whether generation must continue using strict finish-reason precedence (P0.14 §1–§5).

    Precedence Hierarchy:
    1. CONTENT_FILTER / SAFETY: Never continue, stop immediately.
    2. TOOL_CALL: Tool execution handover, stop continuation.
    3. ERROR / CANCELLED: Stop with failed/cancelled status.
    4. Hard Budgets (segment_number >= max_segments, len(text) >= char_budget): TRUNCATED.
    5. MAX_TOKENS / LENGTH: Authoritative signal that provider reached output token limit.
    6. Structured Output Plan Completeness: If planned/remaining sections are missing,
       continuation MUST trigger regardless of conversational closing phrases.
    7. Structural Incompleteness: Mid-word, open fences, open JSON, incomplete table.
    7b. Depth Contract: written text below the word count the response-depth
        prompt promised (min_words). A clean stop at a third of the promised
        report is a finished-looking outline, not a deliverable — expand it.
    8. Terminal Punctuation / Conversational Closing: LOW-STRENGTH evidence; confirms
       completion only if natural stop, no open structures, and all planned sections exist.
    """
    evidence = ContinuationEvidence()
    reasons: list[ContinuationNeeded] = []

    # 1. Content Filter / Safety Stop
    if finish_reason in {"CONTENT_FILTER", "content_filter", "safety", "SAFETY"}:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.COMPLETED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="content filter safety stop",
        )

    # 2. Tool Call
    if finish_reason in {"TOOL_CALL", "tool_calls", "function_call"}:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.COMPLETED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="tool call handover",
        )

    # 3. Error / Cancelled
    if finish_reason in {"ERROR", "error", "cancelled", "CANCELLED"}:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.FAILED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="provider error or cancellation",
        )

    # 4. Hard Budgets
    if segment_number >= max_segments:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.TRUNCATED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="max segments budget reached",
        )
    if len(text) >= char_budget:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.TRUNCATED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="character budget reached",
        )

    tail = text.rstrip()
    if not tail:
        return ContinuationDecision(
            continue_needed=False,
            reasons=(),
            status=ContinuationStatus.COMPLETED,
            confidence=1.0,
            provider_finish_reason=finish_reason,
            evidence=evidence,
            reason="empty text",
        )

    # 5. Authoritative provider MAX_TOKENS / LENGTH
    is_max_tokens = finish_reason in {"MAX_TOKENS", "max_tokens", "length", "LENGTH"}
    if is_max_tokens:
        evidence.max_tokens = True
        reasons.append(
            ContinuationNeeded(
                ContinuationReason.FINISH_REASON_MAX_TOKENS,
                "provider stopped at the output token cap",
            )
        )

    # 6. Structured Output Plan Completeness (Directive §5: Output Plan is stronger than punctuation)
    if remaining_sections:
        normalized = normalize_for_comparison(text)
        missing_remaining = [
            s for s in remaining_sections
            if normalize_for_comparison(s) not in normalized
        ]
        if missing_remaining:
            evidence.remaining_sections = tuple(missing_remaining)
            reasons.append(
                ContinuationNeeded(
                    ContinuationReason.MISSING_REQUESTED_SECTIONS,
                    "remaining planned sections absent: " + ", ".join(missing_remaining[:5]),
                )
            )

    if planned_sections:
        normalized = normalize_for_comparison(text)
        missing_planned = [
            section
            for section in planned_sections
            if normalize_for_comparison(section) not in normalized
        ]
        if missing_planned and (reasons or is_max_tokens):
            if not any(r.reason == ContinuationReason.MISSING_REQUESTED_SECTIONS for r in reasons):
                evidence.remaining_sections = tuple(missing_planned)
                reasons.append(
                    ContinuationNeeded(
                        ContinuationReason.MISSING_REQUESTED_SECTIONS,
                        "planned sections absent: " + ", ".join(missing_planned[:5]),
                    )
                )

    # 7. Structural Incompleteness
    if _MID_WORD_RE.search(tail):
        evidence.mid_word = True
        reasons.append(
            ContinuationNeeded(ContinuationReason.INCOMPLETE_SENTENCE, "ends mid-word")
        )

    open_fences, brace_depth = _count_unbalanced(text)
    if open_fences:
        evidence.open_fence = True
        reasons.append(
            ContinuationNeeded(ContinuationReason.OPEN_CODE_FENCE, "odd number of ``` fences")
        )
    if brace_depth > 0:
        evidence.open_json = True
        reasons.append(
            ContinuationNeeded(
                ContinuationReason.OPEN_JSON_STRUCTURE,
                f"unbalanced braces outside code fences (depth {brace_depth})",
            )
        )

    if _looks_like_incomplete_table(text):
        evidence.incomplete_table = True
        reasons.append(
            ContinuationNeeded(ContinuationReason.INCOMPLETE_TABLE, "last table row unfinished")
        )

    if _STRUCTURAL_TAIL_RE.search(tail):
        reasons.append(
            ContinuationNeeded(
                ContinuationReason.INCOMPLETE_PARAGRAPH, "ends on an open Markdown construct"
            )
        )

    # 7b. Depth contract: the prompt told the model how long this answer had to
    # be. A clean stop well under that floor is the failure the old detector
    # could not see, because nothing was *broken* — it was just thin.
    written_words = word_count(tail)
    if min_words > 0 and written_words < min_words and not reasons:
        evidence.shallow_vs_contract = True
        evidence.words_short = min_words - written_words
        reasons.append(
            ContinuationNeeded(
                ContinuationReason.DEPTH_CONTRACT_UNMET,
                f"{written_words:,} words written against a {min_words:,} word depth floor",
            )
        )

    # 8. Terminal Punctuation & Conversational Closing (Low-strength evidence)
    cleaned_tail, stripped_decorations = strip_trailing_completion_decorations(tail)
    evidence.trailing_decorations = stripped_decorations

    is_closing = bool(_CONVERSATIONAL_CLOSING_RE.search(tail))
    evidence.conversational_closing = is_closing

    has_terminal_punct = bool(cleaned_tail and _TERMINAL_PUNCT_RE.search(cleaned_tail))
    if not has_terminal_punct and not evidence.mid_word:
        # If closing phrase matched, it can only confirm completion when NO stronger reason exists
        if is_closing:
            # Closing confirmed only when natural stop, no missing sections, no max tokens, no open fence
            if not is_max_tokens and not evidence.remaining_sections and not open_fences and brace_depth == 0:
                pass  # Weak evidence confirms natural completion
            else:
                evidence.mid_sentence = True
        else:
            evidence.mid_sentence = True
            reasons.append(
                ContinuationNeeded(
                    ContinuationReason.INCOMPLETE_SENTENCE, "no terminal punctuation"
                )
            )

    if finish_reason in {"STOP", "stop"}:
        evidence.natural_stop = True

    should_continue = bool(reasons)
    status = ContinuationStatus.ACTIVE if should_continue else ContinuationStatus.COMPLETED
    reason_desc = (
        "; ".join(r.detail for r in reasons)
        if reasons
        else "all planned sections and structures complete with natural stop"
    )
    confidence = 0.95 if should_continue else 1.0

    return ContinuationDecision(
        continue_needed=should_continue,
        reasons=tuple(reasons),
        status=status,
        confidence=confidence,
        provider_finish_reason=finish_reason,
        evidence=evidence,
        reason=reason_desc,
    )


# ---------------------------------------------------------------------------
# Seam deduplication (directive §5)
# ---------------------------------------------------------------------------

_WORD_RE = re.compile(r"[\w\u0900-\u097F']+", re.UNICODE)


def normalize_for_comparison(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)
    lowered = re.sub(r"[^\w\u0900-\u097F ]", "", lowered)
    return lowered.strip()


def seam_dedup(previous_tail: str, next_segment: str, *, min_words: int = 3) -> str:
    """Remove the overlap between the end of ``previous_tail`` and the start
    of ``next_segment``.

    Compares at word granularity after normalization so punctuation and
    whitespace differences don't defeat matching. Only overlaps of at
    least ``min_words`` are removed to avoid eating legitimate short
    repetitions (e.g. a heading repeated deliberately).
    """
    prev_words = _WORD_RE.findall(previous_tail.lower())
    next_words = _WORD_RE.findall(next_segment.lower())
    if not prev_words or not next_words:
        return next_segment

    max_k = min(len(prev_words), len(next_words))
    best_k = 0
    for k in range(min_words, max_k + 1):
        if prev_words[-k:] == next_words[:k]:
            best_k = k
    if best_k < min_words:
        return next_segment

    # Drop the matched word prefix from the *original* segment text.
    pattern = re.compile(
        r"^[\s\S]{0,80}?"  # tolerate tiny non-word prefixes (whitespace, bullets)
        + r"[\s]*".join(re.escape(w) for w in next_words[:best_k]),
        re.IGNORECASE,
    )
    match = pattern.match(next_segment)
    if match:
        remainder = next_segment[match.end():]
        # Consume an orphaned punctuation run (e.g. the duplicated sentence's
        # period) into a single boundary space, but PRESERVE a leading space
        # when the join is mid-sentence: previous text '...tier stores' plus
        # remainder ' recent turns' must join as 'stores recent', and
        # '...answers.' plus remainder '. Next…' must join as 'answers. Next'.
        remainder = re.sub(r"^\s*[.,;:!?\u0964\u0965]+\s*", " ", remainder, count=1)
        # The previous segment ended a sentence (terminal punct or newline):
        # the seam must not weld the next sentence onto the period.
        if previous_tail.rstrip() and previous_tail.rstrip()[-1:] in ".!?\u0964\u0965\n":
            remainder = remainder.lstrip()
        return remainder
    # Fallback: rebuild from words (loses formatting only in the seam).
    rebuilt = " ".join(next_words[best_k:])
    if previous_tail and previous_tail[-1:] not in ("", " ", "\n", ".", "!", "?", ":", ";"):
        rebuilt = " " + rebuilt
    return rebuilt


class SeamGuard:
    """Streams continuation segments while suppressing seam overlap.

    Continuation rounds hold back a small prefix buffer until it is large
    enough to test against the previous segment's tail (overlap can only
    exist at the very start of a segment). Once resolved — overlap found
    and stripped, or proven absent — deltas stream through untouched.
    """

    RESOLVE_WINDOW_CHARS = 600

    def __init__(self, previous_tail: str = "", *, min_words: int = 3) -> None:
        self.previous_tail = previous_tail[-800:]
        self.min_words = min_words
        self._buffer: list[str] = []
        self._resolved = False
        self.deduped_chars = 0

    @property
    def resolved(self) -> bool:
        return self._resolved

    def reset_for_segment(self, previous_tail: str) -> None:
        self.previous_tail = previous_tail[-800:]
        self._buffer = []
        self._resolved = False

    def feed(self, delta: str) -> str:
        """Return the emit-safe text for this delta ('' while buffering)."""
        if self._resolved:
            return delta
        self._buffer.append(delta)
        buffered = "".join(self._buffer)
        if len(buffered) < self.RESOLVE_WINDOW_CHARS and len(self.previous_tail) >= 40:
            return ""
        return self._resolve(buffered)

    def finish_segment(self) -> str:
        """Flush any residual buffer at segment end (after dedup)."""
        if self._resolved:
            return ""
        buffered = "".join(self._buffer)
        self._buffer = []
        self._resolved = True
        return self._resolve(buffered) if buffered else ""

    def _resolve(self, buffered: str) -> str:
        self._resolved = True
        self._buffer = []
        cleaned = seam_dedup(self.previous_tail, buffered, min_words=self.min_words)
        self.deduped_chars = len(buffered) - len(cleaned)
        return cleaned


# ---------------------------------------------------------------------------
# Final consistency pass (directive §6, §37, §39)
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(
    r"\[(?:TODO|TBD|INSERT|PLACEHOLDER|LOREM)[^\]]*\]|<(?:TODO|TBD|PLACEHOLDER)[^>]*>",
    re.IGNORECASE,
)
_HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)


@dataclass
class ConsistencyIssue:
    kind: str
    detail: str
    repaired: bool = False


@dataclass
class ConsistencyReport:
    issues: list[ConsistencyIssue] = field(default_factory=list)
    text: str = ""

    @property
    def clean(self) -> bool:
        return not self.issues

    @property
    def unrepaired(self) -> list[ConsistencyIssue]:
        return [i for i in self.issues if not i.repaired]


def run_consistency_pass(text: str, *, apply_repairs: bool = True) -> ConsistencyReport:
    """Verify structural consistency of a completed long output.

    Repairs ONLY unambiguous defects when ``apply_repairs`` is true:
    - an unclosed code fence at end-of-generation (closing it is correct
      because generation is complete);
    - trailing mid-word/mid-sentence fragments on the final line are left
      in place (reported, never silently rewritten — §37 canonical rule).

    Everything else (duplicated headings, placeholders, open JSON) is
    reported unrepaired for upstream decisions.
    """
    issues: list[ConsistencyIssue] = []
    repaired_text = text

    open_fences, brace_depth = _count_unbalanced(text)
    if open_fences:
        detail = "odd number of code fences at end of generation"
        if apply_repairs:
            repaired_text = repaired_text.rstrip() + "\n```"
            issues.append(ConsistencyIssue("OPEN_CODE_FENCE", detail, repaired=True))
        else:
            issues.append(ConsistencyIssue("OPEN_CODE_FENCE", detail, repaired=False))

    if brace_depth > 0:
        issues.append(
            ConsistencyIssue(
                "OPEN_JSON_STRUCTURE",
                f"unbalanced braces outside code fences (depth {brace_depth})",
                repaired=False,
            )
        )

    headings = [normalize_for_comparison(h) for h in _HEADING_RE.findall(text)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for h in headings:
        if h and h in seen and h not in duplicates:
            duplicates.append(h)
        seen.add(h)
    for dup in duplicates:
        issues.append(
            ConsistencyIssue("DUPLICATED_HEADING", f"heading repeated: {dup[:80]}", repaired=False)
        )

    for match in _PLACEHOLDER_RE.finditer(text):
        issues.append(
            ConsistencyIssue(
                "PLACEHOLDER_TEXT", f"placeholder found: {match.group(0)[:60]}", repaired=False
            )
        )

    tail = repaired_text.rstrip()
    if tail and _MID_WORD_RE.search(tail):
        issues.append(
            ConsistencyIssue(
                "TRAILING_MID_WORD",
                "generation ends mid-word — likely truncated by budget, not repaired",
                repaired=False,
            )
        )

    return ConsistencyReport(issues=issues, text=repaired_text)
