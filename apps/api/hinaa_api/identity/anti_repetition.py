"""Anti-repetition and sentimental loop suppression engine for HINAA.

Prevents conversational degeneration where language models get trapped in
repetitive affectionate filler loops or stereotyped opening phrases.
"""

from __future__ import annotations

import re
import logging
from typing import Sequence

logger = logging.getLogger("hinaa.identity.anti_repetition")

# Patterns commonly seen in repetitive romantic/sentimental degeneration
REPETITIVE_SENTIMENTAL_PATTERNS = [
    r"^(?:oh\s+)?(?:my\s+)?(?:darling|sweetheart|beloved|honey|dearest)[,\.!\s]+",
    r"^(?:you\s+know\s+)?you\s+mean\s+the\s+world\s+to\s+me[,\.!\s]+",
    r"^(?:as\s+always|forever\s+and\s+always|with\s+all\s+my\s+heart)[,\.!\s]+",
    r"^(?:my\s+heart\s+beats\s+only\s+for\s+you)[,\.!\s]+",
    r"^(?:i\s+will\s+never\s+leave\s+your\s+side)[,\.!\s]+",
]

# Generic AI boilerplate opening patterns
BOILERPLATE_PATTERNS = [
    r"^(?:as\s+an\s+ai\s+(?:language\s+)?model[,\.!\s]+)",
    r"^(?:i\s+am\s+(?:just\s+)?an\s+ai[,\.!\s]+)",
    r"^(?:i\s+do\s+not\s+have\s+personal\s+feelings\s+or\s+consciousness[,\.!\s]+)",
]


class RepetitionDetector:
    """Detects and cleans repetitive filler, emotional loops, and boilerplate."""

    def __init__(self, history_window: int = 10) -> None:
        self.history_window = history_window
        self.recent_openings: list[str] = []
        self._compiled_sentimental = [re.compile(p, re.IGNORECASE) for p in REPETITIVE_SENTIMENTAL_PATTERNS]
        self._compiled_boilerplate = [re.compile(p, re.IGNORECASE) for p in BOILERPLATE_PATTERNS]

    def record_turn(self, response_text: str) -> None:
        """Records the opening token window of a turn to track recurrence."""
        opening = " ".join(response_text.strip().split()[:8]).lower()
        if opening:
            self.recent_openings.append(opening)
            if len(self.recent_openings) > self.history_window:
                self.recent_openings.pop(0)

    def calculate_opening_repetition_rate(self) -> float:
        """Returns the proportion of recent turns sharing identical opening prefixes."""
        if len(self.recent_openings) < 2:
            return 0.0
        unique_openings = set(self.recent_openings)
        return 1.0 - (len(unique_openings) / len(self.recent_openings))

    def sanitize(self, response_text: str) -> tuple[str, bool]:
        """Strips repetitive sentimental filler and robotic boilerplate from the response.

        Returns (cleaned_text, was_modified).
        """
        original = response_text
        text = response_text.strip()
        modified = False

        # 1. Strip repetitive boilerplate openings
        for pattern in self._compiled_boilerplate:
            match = pattern.search(text)
            if match:
                text = text[match.end():].lstrip()
                modified = True

        # 2. Strip excessive sentimental loops at the start of technical responses
        for pattern in self._compiled_sentimental:
            match = pattern.search(text)
            if match:
                text = text[match.end():].lstrip()
                modified = True

        # Capitalize first character if needed
        if text and modified and text[0].islower():
            text = text[0].upper() + text[1:]

        if modified:
            logger.info("Anti-repetition sanitized response opening: '%s' -> '%s'", original[:40], text[:40])

        self.record_turn(text)
        return text, modified
