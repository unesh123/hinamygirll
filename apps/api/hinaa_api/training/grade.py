"""Outcome-based trajectory grading and DPO preference pair exporter."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class GradedTrajectory:
    goal: str
    status: str
    score: float
    response: str
    steps_count: int
    verified: bool


def grade_trajectory(trace: dict[str, Any]) -> GradedTrajectory:
    """Compute a normalized [0.0, 1.0] reward score from objective verification signals."""
    status = str(trace.get("status") or "unknown").lower()
    verified = bool(trace.get("verified", status == "completed"))
    steps = list(trace.get("steps") or [])
    failed_steps = sum(1 for s in steps if str(s.get("status") or "") == "failed")
    score = 0.0
    if verified and status == "completed":
        score = 1.0 - min(0.35, failed_steps * 0.08)
    elif status == "completed":
        score = 0.65 - min(0.25, failed_steps * 0.08)
    elif status in {"partial", "budget_exhausted"}:
        score = 0.25
    return GradedTrajectory(
        goal=str(trace.get("goal") or "").strip(),
        status=status,
        score=round(max(0.0, score), 4),
        response=str(trace.get("summary") or trace.get("response") or "").strip(),
        steps_count=len(steps),
        verified=verified,
    )


def export_dpo_pairs(
    traces: list[dict[str, Any]],
    out_path: str | Path,
    *,
    min_score_gap: float = 0.25,
) -> list[dict[str, Any]]:
    """Pair verified high-scoring runs with failed/inferior runs on the same goal."""
    by_goal: dict[str, list[GradedTrajectory]] = {}
    for raw in traces:
        g = grade_trajectory(raw)
        if not g.goal or not g.response:
            continue
        by_goal.setdefault(g.goal, []).append(g)

    pairs: list[dict[str, Any]] = []
    for goal, items in by_goal.items():
        items.sort(key=lambda x: x.score, reverse=True)
        best = items[0]
        worst = items[-1]
        if best.score - worst.score >= min_score_gap:
            pairs.append(
                {
                    "prompt": goal,
                    "chosen": best.response,
                    "rejected": worst.response,
                    "score_delta": round(best.score - worst.score, 4),
                    "metadata": {
                        "chosen_score": best.score,
                        "rejected_score": worst.score,
                    },
                }
            )

    target = Path(out_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8") as fh:
        for row in pairs:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return pairs
