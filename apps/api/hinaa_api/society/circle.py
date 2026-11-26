"""Maker -> Reviewer -> Verifier bounded quality circle."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

from .metrics import SocietyMetricsStore, get_society_metrics
from .roles import ReviewVerdict, VerificationVerdict, default_society_specs


@dataclass
class CircleOutcome:
    verified: bool
    rounds: int
    artifact: dict[str, Any]
    reviews: list[ReviewVerdict] = field(default_factory=list)
    verification: VerificationVerdict | None = None


MakerFn = Callable[[str, list[str]], Awaitable[dict[str, Any]]]
ReviewerFn = Callable[[dict[str, Any]], Awaitable[ReviewVerdict]]
VerifierFn = Callable[[dict[str, Any]], Awaitable[VerificationVerdict]]


class SocietyCircle:
    """Enforces independent review + verification before completing code/task output."""

    def __init__(
        self,
        *,
        maker: MakerFn,
        reviewer: ReviewerFn,
        verifier: VerifierFn,
        max_rounds: int = 3,
        metrics: SocietyMetricsStore | None = None,
    ) -> None:
        self.specs = default_society_specs()
        self.maker = maker
        self.reviewer = reviewer
        self.verifier = verifier
        self.max_rounds = max(1, max_rounds)
        self.metrics = metrics or get_society_metrics()

    async def run(self, goal: str) -> CircleOutcome:
        feedback: list[str] = []
        reviews: list[ReviewVerdict] = []
        caught_count = 0
        artifact: dict[str, Any] = {}
        verification: VerificationVerdict | None = None

        for round_idx in range(1, self.max_rounds + 1):
            artifact = await self.maker(goal, list(feedback))
            rev = await self.reviewer(artifact)
            reviews.append(rev)
            if rev.verdict != "PASS":
                caught_count += len(rev.findings) or 1
                feedback = list(rev.findings) or ["Reviewer requested changes."]
                if round_idx < self.max_rounds:
                    continue

            ver = await self.verifier(artifact)
            verification = ver
            if ver.verified:
                self.metrics.record_circle(
                    goal=goal,
                    verified=True,
                    rounds=round_idx,
                    reviewer_caught=caught_count,
                )
                return CircleOutcome(
                    verified=True,
                    rounds=round_idx,
                    artifact=artifact,
                    reviews=reviews,
                    verification=ver,
                )
            feedback = list(ver.failures) or ["Verification failed."]

        failures = verification.failures if verification else feedback
        self.metrics.record_circle(
            goal=goal,
            verified=False,
            rounds=self.max_rounds,
            reviewer_caught=caught_count,
            failures=failures,
        )
        return CircleOutcome(
            verified=False,
            rounds=self.max_rounds,
            artifact=artifact,
            reviews=reviews,
            verification=verification,
        )
