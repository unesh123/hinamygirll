from __future__ import annotations
from .contracts import AgentRun, AgentPlan, StepState, RunStatus


class StepScheduler:
    def next_ready(self, run: AgentRun, plan: AgentPlan) -> object | None:
        if run.cancellation_requested or run.status in {
            RunStatus.CANCELLED, RunStatus.FAILED, RunStatus.COMPLETED, RunStatus.INTERRUPTED
        }:
            return None
        done = {s.step_id for s in plan.steps if s.status == StepState.COMPLETED}
        failed = {s.step_id for s in plan.steps if s.status == StepState.FAILED and s.attempt_count >= s.maximum_attempts}

        for step in sorted(plan.steps, key=lambda s: s.sequence):
            if any(dep in failed for dep in step.dependencies):
                step.status = StepState.BLOCKED
                continue
            if step.status == StepState.PENDING and all(dep in done for dep in step.dependencies):
                if step.requires_confirmation:
                    step.status = StepState.AWAITING_CONFIRMATION
                    return None
                step.status = StepState.READY
                return step
            elif step.status == StepState.READY:
                return step
        return None


