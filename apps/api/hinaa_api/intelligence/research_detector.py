from __future__ import annotations

import re


_TEMPORAL_RESEARCH_RE = re.compile(
    r"\b(today|yesterday|this\s+week|current|currently|latest|recent|recently|breaking\s+news|what\s+happened\s+in|new\s+in\s+202[5-9]|price\s+of|stock\s+price|incident\s+in|earthquake\s+in|election\s+results)\b",
    re.I,
)

_FACTUAL_LOOKUP_RE = re.compile(
    r"\b(who\s+won|who\s+is\s+currently|what\s+is\s+the\s+latest|release\s+date\s+of|release\s+notes\s+for|documentation\s+for)\b",
    re.I,
)


class ResearchNeedDetector:
    """Detects when an incoming user query requires external web research without explicit /search commands."""

    @staticmethod
    def needs_research(query: str) -> tuple[bool, str | None]:
        cleaned = query.strip()
        lowered = cleaned.lower()

        # Check for temporal or real-time event markers
        if _TEMPORAL_RESEARCH_RE.search(lowered) or _FACTUAL_LOOKUP_RE.search(lowered):
            # Clean leading noise to produce a solid search query
            clean_q = re.sub(r"(?i)^(?:hey\s+)?(?:hinaa?|hina)?[,\s]*(?:can\s+you\s+)?(?:tell\s+me|find|search)?\s*", "", cleaned).strip(" ?,.!")
            return True, clean_q or cleaned

        return False, None
