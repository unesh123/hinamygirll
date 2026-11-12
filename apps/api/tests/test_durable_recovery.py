from __future__ import annotations

import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hinaa_api.agent.contracts import (
    AgentPlan,
    AgentRun,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
)
from hinaa_api.agent.persistence import AgentPersistenceService
from hinaa_api.agent.runtime import AgentRuntime
from hinaa_api.persistence.orm import Base


@pytest.fixture
def persistence_fixture():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    service = AgentPersistenceService(session_factory)
    return service


def test_durable_task_recovery_flow(persistence_fixture):
    persistence = persistence_fixture
    runtime = AgentRuntime(persistence=persistence)

    # 1. Create a run and plan
    run = AgentRun(
        run_id="run_durable_101",
        user_id="user_nepal",
        goal="Build fullstack portfolio website",
        status=RunStatus.EXECUTING,
    )
    plan = AgentPlan(
        plan_id="plan_101",
        run_id=run.run_id,
        goal=run.goal,
        version=1,
        steps=[
            PlanStep(
                step_id="step_1",
                plan_id="plan_101",
                sequence=0,
                title="Initialize Vite app",
                operation_type=OperationType.TOOL,
                tool_name="write_file",
                status=StepState.COMPLETED,
            ),
            PlanStep(
                step_id="step_2",
                plan_id="plan_101",
                sequence=1,
                title="Run test suite",
                operation_type=OperationType.TOOL,
                tool_name="run_pytest",
                status=StepState.RUNNING,
            ),
        ],
    )

    persistence.save_run(run)
    persistence.save_plan(plan)

    # 2. Simulate process crash / server restart
    fresh_runtime = AgentRuntime(persistence=persistence)

    # In-memory runtime starts empty
    assert fresh_runtime.runs == {}

    # Startup auto-recovery scans database
    recovered_runs = fresh_runtime.recover_all_interrupted_runs()
    assert len(recovered_runs) == 1
    recovered = recovered_runs[0]
    assert recovered.run_id == "run_durable_101"
    assert recovered.status == RunStatus.INTERRUPTED

    # Check step status in DB
    step_2 = persistence.get_step("step_2")
    assert step_2 is not None
    assert step_2.status == StepState.INTERRUPTED

    # Step 1 remained completed
    step_1 = persistence.get_step("step_1")
    assert step_1.status == StepState.COMPLETED

    # 3. Resume run
    resumed = fresh_runtime.resume("run_durable_101", "user_nepal")
    assert resumed.status == RunStatus.EXECUTING

    # Step 2 transitioned to READY
    step_2_resumed = persistence.get_step("step_2")
    assert step_2_resumed.status == StepState.READY
