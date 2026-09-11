from __future__ import annotations
from .contracts import AgentRun, AgentPlan, RunStatus, StepState


def recover_run(run: AgentRun, plan: AgentPlan | None = None) -> AgentRun:
    if run.status in {RunStatus.UNDERSTANDING, RunStatus.PLANNING, RunStatus.EXECUTING, RunStatus.VERIFYING}:
        run.status = RunStatus.INTERRUPTED
    if plan:
        for step in plan.steps:
            if step.status == StepState.RUNNING:
                step.status = StepState.INTERRUPTED
    return run


