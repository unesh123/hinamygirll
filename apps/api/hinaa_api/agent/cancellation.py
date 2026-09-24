from __future__ import annotations
from .contracts import AgentRun, RunStatus


def request_cancellation(run: AgentRun, user_id: str | None = None) -> AgentRun | None:
    if user_id is not None and run.user_id != user_id:
        return None
    if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
        return run
    run.cancellation_requested = True
    run.status = RunStatus.CANCELLED
    return run


