"""Private, deterministic text polishing for HINAA.

This module is deliberately not an AI-detector evasion tool.  It improves
readability while preserving facts and protecting Markdown code, links, quotes,
numbers, and the user-selected Hindi/English content from rewrite rules.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Literal

HumanizerStyle = Literal["natural", "warm", "professional", "concise"]

_MAX_TEXT_LENGTH = 60_000
_PROTECTED_TOKEN = re.compile(
    r"```[\s\S]*?```|`[^`\n]+`|https?://[^\s)\]>]+|\[[^\]]+\]\([^)]*\)"
    r"|(?:mailto:)?[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}"
    r"|\b[A-Z]:\\[^\s<>|?*]+|(?<!\w)/(?:[\w.@+-]+/)*[\w.@+-]+"
    r"|\[(?:\d{1,3}|[A-Za-z][^\]\n]{0,44})\]",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True)
class HumanizerResult:
    text: str
    style: HumanizerStyle
    route: str
    externalTextTransfer: bool
    changes: tuple[str, ...]
    originalCharacterCount: int
    outputCharacterCount: int
    protectedSegmentCount: int
    protectedCharacterCount: int

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _normalise_prose(segment: str, style: HumanizerStyle) -> tuple[str, set[str]]:
    changes: set[str] = set()
    # Preserve Markdown structure and quoted lines. Only regular prose lines are
    # changed, keeping a pasted document's headings, lists, tables and quotes intact.
    output: list[str] = []
    for original_line in segment.splitlines(keepends=True):
        newline = "\n" if original_line.endswith("\n") else ""
        line = original_line.rstrip("\n")
        stripped = line.strip()
        if not stripped or re.match(r"^\s*(?:#{1,6}\s|[-*+]\s|\d+[.)]\s|>|\|)", line):
            output.append(line + newline)
            continue
        cleaned = re.sub(r"[ \t]{2,}", " ", line)
        if cleaned != line:
            changes.add("Normalized extra spacing")
        line = cleaned

        # These substitutions are intentionally small, fact-neutral, and applied
        # only in normal prose. They never invent detail or alter protected spans.
        substitutions: list[tuple[str, str, str]] = [
            (r"\bIt is important to note that\s*", "", "Removed empty filler"),
            (r"\bIn order to\b", "To", "Simplified wording"),
            (r"\butilize\b", "use", "Simplified wording"),
            (r"\bcommence\b", "start", "Simplified wording"),
            (r"\ba variety of\b", "several", "Simplified wording"),
            (r"\bdue to the fact that\b", "because", "Simplified wording"),
            (r"\bat this point in time\b", "now", "Simplified wording"),
        ]
        if style in {"natural", "warm", "concise"}:
            substitutions.extend([
                (r"\bAdditionally\b", "Also", "Smoothed transitions"),
                (r"\bFurthermore\b", "Also", "Smoothed transitions"),
            ])
        if style == "concise":
            substitutions.extend([
                (r"\bPlease note that\s*", "", "Removed empty filler"),
                (r"\bIt should be noted that\s*", "", "Removed empty filler"),
            ])
        if style == "warm":
            substitutions.append((r"\bYou should\b", "You can", "Softened directive tone"))

        for pattern, replacement, change in substitutions:
            updated = re.sub(pattern, replacement, line, flags=re.IGNORECASE)
            if updated != line:
                changes.add(change)
                line = updated
        line = re.sub(r" {2,}", " ", line).strip() if line.strip() else line
        output.append(line + newline)
    return "".join(output), changes


def humanize_text(text: str, style: HumanizerStyle = "natural") -> HumanizerResult:
    """Polish text locally while retaining protected technical and factual spans."""
    if style not in {"natural", "warm", "professional", "concise"}:
        raise ValueError("style must be natural, warm, professional, or concise")
    if not isinstance(text, str):
        raise ValueError("text must be a string")
    if not text.strip():
        raise ValueError("text is required")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(f"text must be at most {_MAX_TEXT_LENGTH:,} characters")

    pieces: list[str] = []
    changes: set[str] = set()
    position = 0
    protected_segment_count = 0
    protected_character_count = 0
    for protected in _PROTECTED_TOKEN.finditer(text):
        prose, prose_changes = _normalise_prose(text[position:protected.start()], style)
        pieces.append(prose)
        protected_text = protected.group(0)
        pieces.append(protected_text)
        protected_segment_count += 1
        protected_character_count += len(protected_text)
        changes.update(prose_changes)
        position = protected.end()
    prose, prose_changes = _normalise_prose(text[position:], style)
    pieces.append(prose)
    changes.update(prose_changes)

    polished = "".join(pieces).strip()
    if not polished:
        polished = text.strip()
    if polished != text.strip() and not changes:
        changes.add("Polished spacing and formatting")
    if protected_segment_count:
        changes.add("Protected technical spans and citations")
    if not changes:
        changes.add("Preserved the original wording because no safe local edit was needed")

    return HumanizerResult(
        text=polished,
        style=style,
        route="local-deterministic",
        externalTextTransfer=False,
        changes=tuple(sorted(changes)),
        originalCharacterCount=len(text),
        outputCharacterCount=len(polished),
        protectedSegmentCount=protected_segment_count,
        protectedCharacterCount=protected_character_count,
    )
