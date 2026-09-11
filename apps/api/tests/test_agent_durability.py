from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import os
import tempfile
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hinaa_api.agent import AgentRuntime
from hinaa_api.agent.contracts import (
    AgentPlan,
    AgentRun,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
)
from hinaa_api.agent.persistence import AgentPersistenceService
from hinaa_api.agent.recovery import recover_run
from hinaa_api.errors import HinaaError
from hinaa_api.persistence.orm import Base


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    yield session_factory
    engine.dispose()
    try:
        os.remove(path)
    except OSError:
        pass


def test_process_restart_restores_runs_plans_steps_and_events(temp_db):
    # Server A: Create and populate runtime
    persistence_a = AgentPersistenceService(temp_db)
    rt_a = AgentRuntime(persistence=persistence_a)

    run = rt_a.create_run("build durable bridge", "user_alpha", conversation_id="conv-123")
    plan = AgentPlan(run_id=run.run_id, goal="build durable bridge")
    s0 = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="gather materials",
        description="acquire lumber and steel",
        operation_type=OperationType.RESPOND,
        status=StepState.COMPLETED,
    )
    s1 = PlanStep(
        plan_id=plan.plan_id,
        sequence=1,
        title="assemble structure",
        description="connect trusses",
        operation_type=OperationType.TOOL,
        tool_name="weld_tool",
        tool_parameters={"voltage": 220, "rod": "6013"},
        status=StepState.READY,
        dependencies=[s0.step_id],
    )
    plan.steps = [s0, s1]
    rt_a.plans[plan.plan_id] = plan
    persistence_a.save_plan(plan)

    rt_a._emit(run.run_id, "step.progress", step_id=s0.step_id, payload={"progress": 100})
    rt_a._emit(run.run_id, "tool.proposed", step_id=s1.step_id, payload={"tool": "weld_tool"})

    # Simulate Process Restart: Server B with completely fresh in-memory state
    persistence_b = AgentPersistenceService(temp_db)
    rt_b = AgentRuntime(persistence=persistence_b)

    # 1. Run restored
    reloaded_run = rt_b.get_run(run.run_id, "user_alpha")
    assert reloaded_run is not None
    assert reloaded_run.run_id == run.run_id
    assert reloaded_run.goal == "build durable bridge"
    assert reloaded_run.user_id == "user_alpha"
    assert reloaded_run.conversation_id == "conv-123"

    # 2. Plan restored
    reloaded_plan = rt_b.get_plan(run.run_id)
    assert reloaded_plan is not None
    assert reloaded_plan.plan_id == plan.plan_id
    assert len(reloaded_plan.steps) == 2

    # 3. Steps restored with full fidelity
    steps = rt_b.get_steps(run.run_id, "user_alpha")
    assert steps is not None
    assert len(steps) == 2
    assert steps[0].title == "gather materials"
    assert steps[0].status == StepState.COMPLETED
    assert steps[1].title == "assemble structure"
    assert steps[1].tool_name == "weld_tool"
    assert steps[1].tool_parameters == {"voltage": 220, "rod": "6013"}
    assert steps[1].status == StepState.READY
    assert steps[1].dependencies == [s0.step_id]

    # 4. Events restored in order
    events = rt_b.get_events(run.run_id, "user_alpha")
    assert events is not None
    assert len(events) >= 3  # agent.run.created + 2 emitted
    event_types = [e.event_type for e in events]
    assert "agent.run.created" in event_types
    assert "step.progress" in event_types
    assert "tool.proposed" in event_types


def test_process_restart_cancellation_persists(temp_db):
    persistence_a = AgentPersistenceService(temp_db)
    rt_a = AgentRuntime(persistence=persistence_a)
    run = rt_a.create_run("cancelable job", "user_alpha")

    # Process restart: Server B cancels the run
    persistence_b = AgentPersistenceService(temp_db)
    rt_b = AgentRuntime(persistence=persistence_b)
    cancelled = rt_b.cancel(run.run_id, "user_alpha")
    assert cancelled is not None
    assert cancelled.status == RunStatus.CANCELLED
    assert cancelled.cancellation_requested is True

    # Process restart: Server C inspects the run
    persistence_c = AgentPersistenceService(temp_db)
    rt_c = AgentRuntime(persistence=persistence_c)
    persisted_run = rt_c.get_run(run.run_id, "user_alpha")
    assert persisted_run is not None
    assert persisted_run.status == RunStatus.CANCELLED

    # Cancellation is idempotent
    second_cancel = rt_c.cancel(run.run_id, "user_alpha")
    assert second_cancel is not None
    assert second_cancel.status == RunStatus.CANCELLED


def test_process_restart_interrupted_recovery_and_resume(temp_db):
    persistence_a = AgentPersistenceService(temp_db)
    rt_a = AgentRuntime(persistence=persistence_a)
    run = rt_a.create_run("crash recovery", "user_alpha")
    run.status = RunStatus.EXECUTING
    persistence_a.save_run(run)

    plan = AgentPlan(run_id=run.run_id, goal="crash recovery")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="active step before crash",
        operation_type=OperationType.TOOL,
        tool_name="image_search",
        tool_parameters={"idempotent": True},
        status=StepState.RUNNING,
    )
    plan.steps = [step]
    rt_a.plans[plan.plan_id] = plan
    persistence_a.save_plan(plan)

    # Server B recovers the interrupted run
    persistence_b = AgentPersistenceService(temp_db)
    rt_b = AgentRuntime(persistence=persistence_b)
    recovered = rt_b.recover(run.run_id, "user_alpha")
    assert recovered is not None
    assert recovered.status == RunStatus.INTERRUPTED
    steps_b = rt_b.get_steps(run.run_id, "user_alpha")
    assert steps_b[0].status == StepState.INTERRUPTED

    # Server B resumes the run
    resumed = rt_b.resume(run.run_id, "user_alpha")
    assert resumed is not None
    assert resumed.status == RunStatus.EXECUTING
    steps_resumed = rt_b.get_steps(run.run_id, "user_alpha")
    assert steps_resumed[0].status == StepState.READY

    # Server C verifies persisted state after resume
    persistence_c = AgentPersistenceService(temp_db)
    rt_c = AgentRuntime(persistence=persistence_c)
    run_c = rt_c.get_run(run.run_id, "user_alpha")
    assert run_c.status == RunStatus.EXECUTING
    steps_c = rt_c.get_steps(run.run_id, "user_alpha")
    assert steps_c[0].status == StepState.READY


def test_process_restart_confirmation_approval_and_rejection(temp_db):
    persistence_a = AgentPersistenceService(temp_db)
    rt_a = AgentRuntime(persistence=persistence_a)
    run = rt_a.create_run("sensitive transaction", "user_alpha")
    run.status = RunStatus.AWAITING_CONFIRMATION
    persistence_a.save_run(run)

    plan = AgentPlan(run_id=run.run_id, goal="sensitive transaction")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="delete database records",
        operation_type=OperationType.TOOL,
        tool_name="sql_exec",
        requires_confirmation=True,
        status=StepState.AWAITING_CONFIRMATION,
    )
    plan.steps = [step]
    rt_a.plans[plan.plan_id] = plan
    persistence_a.save_plan(plan)

    # Server B confirms and approves
    persistence_b = AgentPersistenceService(temp_db)
    rt_b = AgentRuntime(persistence=persistence_b)
    confirmed = rt_b.confirm(run.run_id, step.step_id, "user_alpha", approved=True)
    assert confirmed is not None
    assert confirmed.status == RunStatus.EXECUTING
    steps_b = rt_b.get_steps(run.run_id, "user_alpha")
    assert steps_b[0].status == StepState.READY

    # Server C verifies persisted approval
    persistence_c = AgentPersistenceService(temp_db)
    rt_c = AgentRuntime(persistence=persistence_c)
    run_c = rt_c.get_run(run.run_id, "user_alpha")
    assert run_c.status == RunStatus.EXECUTING

    # Test rejection path on a second run
    run2 = rt_c.create_run("rejected run", "user_alpha")
    run2.status = RunStatus.AWAITING_CONFIRMATION
    persistence_c.save_run(run2)
    plan2 = AgentPlan(run_id=run2.run_id, goal="rejected run")
    step2 = PlanStep(
        plan_id=plan2.plan_id,
        sequence=0,
        title="dangerous op",
        operation_type=OperationType.TOOL,
        status=StepState.AWAITING_CONFIRMATION,
    )
    plan2.steps = [step2]
    rt_c.plans[plan2.plan_id] = plan2
    persistence_c.save_plan(plan2)

    rejected = rt_c.confirm(run2.run_id, step2.step_id, "user_alpha", approved=False)
    assert rejected.status == RunStatus.CANCELLED
    steps2 = rt_c.get_steps(run2.run_id, "user_alpha")
    assert steps2[0].status == StepState.CANCELLED


def test_cross_user_isolation_after_restart(temp_db):
    persistence_a = AgentPersistenceService(temp_db)
    rt_a = AgentRuntime(persistence=persistence_a)
    run = rt_a.create_run("private task", "user_alpha")

    # Server B query by user_beta
    persistence_b = AgentPersistenceService(temp_db)
    rt_b = AgentRuntime(persistence=persistence_b)

    assert rt_b.get_run(run.run_id, "user_beta") is None
    assert rt_b.get_steps(run.run_id, "user_beta") is None
    assert rt_b.get_events(run.run_id, "user_beta") is None
    assert rt_b.cancel(run.run_id, "user_beta") is None
    assert rt_b.resume(run.run_id, "user_beta") is None
    assert rt_b.confirm(run.run_id, "step-1", "user_beta", True) is None


def test_typed_tool_unavailable_error_persistence(temp_db):
    persistence = AgentPersistenceService(temp_db)

    async def throwing_executor(step: PlanStep):
        raise HinaaError("TOOL_UNAVAILABLE", f"Tool {step.tool_name} not found", status_code=404)

    rt = AgentRuntime(executor=throwing_executor, persistence=persistence, step_attempts=1)
    run = rt.create_run("execute missing tool", "user_alpha")
    plan = AgentPlan(run_id=run.run_id, goal="execute missing tool")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="call missing tool",
        operation_type=OperationType.TOOL,
        tool_name="nonexistent_tool",
        maximum_attempts=1,
    )
    plan.steps = [step]

    res = asyncio.run(rt.execute(run, plan=plan))
    assert res.status == RunStatus.FAILED
    assert res.failure_code == "TOOL_UNAVAILABLE"

    # Server B reloads: verify failure code was persisted in SQLite
    rt_b = AgentRuntime(persistence=persistence)
    reloaded = rt_b.get_run(run.run_id, "user_alpha")
    assert reloaded is not None
    assert reloaded.status == RunStatus.FAILED
    assert reloaded.failure_code == "TOOL_UNAVAILABLE"


def test_active_runs_listing(temp_db):
    persistence = AgentPersistenceService(temp_db)
    rt = AgentRuntime(persistence=persistence)

    r_queued = rt.create_run("q", "u1")
    r_exec = rt.create_run("e", "u1")
    r_exec.status = RunStatus.EXECUTING
    persistence.save_run(r_exec)

    r_comp = rt.create_run("c", "u1")
    r_comp.status = RunStatus.COMPLETED
    persistence.save_run(r_comp)

    r_fail = rt.create_run("f", "u1")
    r_fail.status = RunStatus.FAILED
    persistence.save_run(r_fail)

    active = persistence.list_active_runs()
    active_ids = {r.run_id for r in active}
    assert r_queued.run_id in active_ids
    assert r_exec.run_id in active_ids
    assert r_comp.run_id not in active_ids
    assert r_fail.run_id not in active_ids
