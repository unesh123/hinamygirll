"""Long-horizon checkpointed marathon runner with hard cost/wall-clock/step budgets."""

from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from ..society.metrics import SocietyMetricsStore, get_society_metrics


@dataclass(frozen=True)
class MarathonBudget:
    max_wall_seconds: float = 3600.0
    max_cost_usd: float = 5.0
    max_steps: int = 100


@dataclass
class MarathonCheckpoint:
    run_id: str
    goal: str
    step_index: int = 0
    elapsed_seconds: float = 0.0
    cost_usd: float = 0.0
    status: str = "running"  # running | paused_budget | completed | failed
    pause_reason: str | None = None
    notes: list[str] = field(default_factory=list)


StepExecutor = Callable[[MarathonCheckpoint], Awaitable[dict[str, Any]]]


class MarathonRunner:
    """Executes long multi-step runs with atomic disk checkpoints and hard budget pauses."""

    def __init__(
        self,
        *,
        checkpoint_dir: str | Path,
        budget: MarathonBudget | None = None,
        metrics: SocietyMetricsStore | None = None,
    ) -> None:
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.budget = budget or MarathonBudget()
        self.metrics = metrics or get_society_metrics()

    def _cp_path(self, run_id: str) -> Path:
        return self.checkpoint_dir / f"{run_id}.json"

    def save_checkpoint(self, cp: MarathonCheckpoint) -> Path:
        p = self._cp_path(cp.run_id)
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(cp), indent=2), encoding="utf-8")
        os.replace(tmp, p)
        return p

    def load_checkpoint(self, run_id: str) -> MarathonCheckpoint | None:
        p = self._cp_path(run_id)
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return MarathonCheckpoint(**data)

    async def run(
        self,
        *,
        run_id: str,
        goal: str,
        executor: StepExecutor,
        now_fn: Callable[[], float] = time.monotonic,
    ) -> MarathonCheckpoint:
        cp = self.load_checkpoint(run_id) or MarathonCheckpoint(run_id=run_id, goal=goal)
        if cp.status == "completed":
            return cp
        cp.status = "running"
        cp.pause_reason = None
        start_wall = now_fn() - cp.elapsed_seconds

        while True:
            cp.elapsed_seconds = max(0.0, now_fn() - start_wall)
            if cp.step_index >= self.budget.max_steps:
                cp.status = "paused_budget"
                cp.pause_reason = f"Step budget reached ({self.budget.max_steps})"
                self.save_checkpoint(cp)
                self.metrics.record_counter("marathons_paused", 1)
                return cp
            if cp.elapsed_seconds >= self.budget.max_wall_seconds:
                cp.status = "paused_budget"
                cp.pause_reason = f"Wall-clock budget exceeded ({self.budget.max_wall_seconds}s)"
                self.save_checkpoint(cp)
                self.metrics.record_counter("marathons_paused", 1)
                return cp
            if cp.cost_usd >= self.budget.max_cost_usd:
                cp.status = "paused_budget"
                cp.pause_reason = f"Cost budget exceeded (${self.budget.max_cost_usd:.2f})"
                self.save_checkpoint(cp)
                self.metrics.record_counter("marathons_paused", 1)
                return cp

            step_res = await executor(cp)
            cp.step_index += 1
            cp.cost_usd += float(step_res.get("cost_usd", 0.0))
            if step_res.get("note"):
                cp.notes.append(str(step_res["note"]))
            if step_res.get("done"):
                cp.status = "completed"
                cp.elapsed_seconds = max(0.0, now_fn() - start_wall)
                self.save_checkpoint(cp)
                self.metrics.record_counter("marathons_completed", 1)
                return cp
            self.save_checkpoint(cp)
