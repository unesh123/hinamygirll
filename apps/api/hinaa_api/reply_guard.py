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

_META_REASONING_LINE = re.compile(
    r"^\s*(?:"
    r"the (?:instructions|system prompt|developer instructions|prompt) (?:are|say|states?|requires?|dictates?|strictly)|"
    r"instructions (?:are|require|say|state)|"
    r"turn \d+\+?(?:\s+only)?\s*:|turn \d+\+? means|"
    r"unesh (?:just|is|has|asked|said|wants|did not|didn't)|"
    r"(?:the )?user (?:just|is|has|asked|said|wants|did not|didn't)|"
    r"i must (?:not )?(?:repeat|greet|answer|dive|respond|provide)|"
    r"i should (?:not )?(?:force-feed|repeat|ask|give|respond)|"
    r"my (?:persona|identity|character|task|goal) (?:is|requires)|"
    r"acting as (?:hina|hinaa|companion)|"
    r"character guidelines|"
    r"(?:his|the) active topic is|"
    r"(?:goal|plan|internal reasoning|reasoning|thinking|scratchpad)\s*:|"
    r"analyzing (?:user|the prompt|request|context)|"
    r"let (?:me|us) analyze|"
    r"current turn\s*:"
    r")\b",
    re.IGNORECASE,
)

_EMPTY_REPLY = "Hey babe! I'm right here with you. How can I help you right now?"


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


def _strip_meta_reflection(text: str) -> tuple[str, int]:
    """Strip leading or leaked system prompt reflections and meta-instructions."""
    if not text:
        return "", 0
    paragraphs = text.split("\n\n")
    kept_paras: list[str] = []
    removed = 0
    checking_leading = True

    for p in paragraphs:
        p_clean = p.strip()
        if not p_clean:
            continue
        is_reflection = False
        lines = [l.strip() for l in p_clean.splitlines() if l.strip()]
        if checking_leading:
            for line in lines:
                if _META_REASONING_LINE.search(line):
                    is_reflection = True
                    break
            if not is_reflection and re.search(
                r"(?i)\b(?:instructions are strict|system prompt says|turn 2\+ means|do not repeat a canned greeting)\b",
                p_clean,
            ):
                is_reflection = True

        if checking_leading and is_reflection:
            removed += 1
        else:
            checking_leading = False
            kept_lines = [l for l in p.splitlines() if not _META_REASONING_LINE.search(l.strip())]
            if len(kept_lines) < len(p.splitlines()):
                removed += len(p.splitlines()) - len(kept_lines)
            if kept_lines:
                kept_paras.append("\n".join(kept_lines))

    return "\n\n".join(kept_paras).strip(), removed


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

    # Strip thinking blocks
    cleaned = re.sub(r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^\s*<(?:think|thought)>[\s\S]*$", "", cleaned, flags=re.IGNORECASE)

    # Strip system prompt reflections / meta-instructions
    cleaned, meta_removed = _strip_meta_reflection(cleaned)
    if meta_removed:
        issues.append(GuardIssue("meta_reflection", f"removed {meta_removed} internal meta-reasoning item(s)"))
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
