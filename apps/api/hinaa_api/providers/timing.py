"""Sanitized monotonic timing stages for provider turns.

Never stores prompt text, secrets, or raw audio. Values are integer milliseconds
relative to the timer start (or absolute elapsed between marks when requested).
"""

from __future__ import annotations

from collections.abc import Callable
from time import perf_counter
from typing import Literal

TimingStage = Literal[
    "prompt_built",
    "provider_client_ready",
    "request_sent",
    "first_provider_event",
    "first_text_delta",
    "text_complete",
    "plan_parsed",
    "plan_validated",
]

STAGE_ORDER: tuple[TimingStage, ...] = (
    "prompt_built",
    "provider_client_ready",
    "request_sent",
    "first_provider_event",
    "first_text_delta",
    "text_complete",
    "plan_parsed",
    "plan_validated",
)


class ProviderTiming:
    def __init__(self, now: Callable[[], float] | None = None) -> None:
        self._now = now or perf_counter
        self._started = self._now()
        self._marks: dict[str, float] = {}

    def mark(self, stage: TimingStage) -> None:
        if stage not in self._marks:
            self._marks[stage] = self._now()

    def ms_since_start(self, stage: TimingStage) -> int | None:
        stamp = self._marks.get(stage)
        if stamp is None:
            return None
        return int((stamp - self._started) * 1000)

    def snapshot(self) -> dict[str, int]:
        """Return only observed stages as ms-from-start. Missing stages omitted."""
        out: dict[str, int] = {}
        for stage in STAGE_ORDER:
            value = self.ms_since_start(stage)
            if value is not None:
                out[stage] = value
        return out
