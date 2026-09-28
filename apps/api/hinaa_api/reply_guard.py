"""Self-check pass for a reply, before the user ever sees it.

"Her thinking needs to be perfect" starts with never shipping an obvious defect.
This guard is the last gate between the plan the brain produced and the text on
screen: it removes the generator's own diagnostics, closes a fence the model left
open, and refuses to send a reply that came out empty. It is deliberately
conservative — it repairs only what is provably wrong and records everything it
touched, so a rewrite can never silently change her meaning.

Pure functions only; no I/O, no network, so the policy is unit-testable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Lines the generator writes for *us*, never for him. They name an internal
# decision ("WHY DID HINA CONTINUE?") or a segment counter, and reading one is
# how a working reply looks broken.
_TRACE_LINE = re.compile(
    r"^\s*(?:WHY DID HINA (?:CONTINUE|STOP)\?|generation\s+\S+\s+used\s+\d+\s+segments|"
    r"seg\d+\s*:|depth floor\b|seam dedup\b)",
    re.IGNORECASE,
)

_EMPTY_REPLY = "I am here, but I lost that reply. Could you say it once more?"


@dataclass(frozen=True)
class GuardIssue:
    kind: str
    detail: str


@dataclass(frozen=True)
class GuardResult:
    text: str
    issues: tuple[GuardIssue, ...] = field(default_factory=tuple)

    @property
    def repaired(self) -> bool:
        return bool(self.issues)


_TOOL_MARKUP_RE = re.compile(
    r"<\|?\s*(?:(?:tool|function|b:tool)[_.:-]?calls?|calls?|invokes?|tool_call_argument|tool_call_section_begin|tool_call_section_end|arg|arg_name|arg_value|parameter|parameters)[^>]*>.*?</\|?\s*(?:(?:tool|function|b:tool)[_.:-]?calls?|calls?|invokes?|tool_call_argument|tool_call_section_begin|tool_call_section_end|arg|arg_name|arg_value|parameter|parameters)[^>]*>|"
    r"<\|?\s*(?:(?:tool|function|b:tool)[_.:-]?calls?|calls?|invokes?|tool_call_argument|tool_call_section_begin|tool_call_section_end|arg|arg_name|arg_value|parameter|parameters)[^>]*>",
    re.DOTALL | re.IGNORECASE,
)


def _strip_trace_lines(text: str) -> tuple[str, int]:
    kept: list[str] = []
    removed = 0
    for line in text.splitlines():
        if _TRACE_LINE.match(line):
            removed += 1
            continue
        kept.append(line)
    return "\n".join(kept), removed


def check_reply(
    text: str | None,
    *,
    user_text: str | None = None,
    language: str | None = None,
) -> GuardResult:
    """Return a sendable reply plus every issue that was found.

    ``language`` is accepted so callers can pass the turn language without the
    guard needing to guess it; this pass does not rewrite language because a
    bad detector would rewrite a correct answer.
    """
    issues: list[GuardIssue] = []
    original = (text or "").strip()

    if not original:
        return GuardResult(_EMPTY_REPLY, (GuardIssue("empty_reply", "the reply was empty"),))

    cleaned, removed = _strip_trace_lines(original)
    if removed:
        issues.append(GuardIssue("internal_trace", f"removed {removed} generator trace line(s)"))
    cleaned = cleaned.strip()

    if _TOOL_MARKUP_RE.search(cleaned):
        cleaned = _TOOL_MARKUP_RE.sub("", cleaned).strip()
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        issues.append(GuardIssue("tool_markup", "removed model invented tool-call markup"))

    # A fence the model opened and never closed makes the whole tail a code
    # block on screen; closing it is a repair, not a rewrite.
    if cleaned.count("```") % 2 == 1:
        cleaned = cleaned + "\n```"
        issues.append(GuardIssue("unbalanced_fence", "closed an unterminated code fence"))

    if not cleaned:
        return GuardResult(_EMPTY_REPLY, (GuardIssue("empty_reply", "the reply was only trace lines"),))

    if user_text and cleaned.strip() == user_text.strip():
        # A verbatim echo is worth flagging but not rewriting: a short question
        # can legitimately be repeated back.
        issues.append(GuardIssue("parrot", "the reply repeated the user's message verbatim"))

    return GuardResult(cleaned, tuple(issues))
