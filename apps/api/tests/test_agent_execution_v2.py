from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hinaa_api.agent.bridge import (
    DurableTaskBridge,
    StepVerificationCondition,
    VerificationType,
)
from hinaa_api.agent.contracts import RunStatus, StepState
from hinaa_api.agent.runtime import AgentRuntime
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.persistence.orm import Base
from hinaa_api.persistence.task_service import TaskService


@pytest.fixture
def setup_services():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    mem_service = MemoryService(factory)
    task_service = TaskService(factory)
    user = mem_service.ensure_user("user_agent_exec_test")
    runtime = AgentRuntime()
    bridge = DurableTaskBridge(task_service, runtime)
    return user, task_service, runtime, bridge


def test_create_durable_agent_run(setup_services):
    user, task_service, runtime, bridge = setup_services

    task_dict, run, plan = bridge.create_durable_agent_run(
        owner_id=user.id,
        goal="Perform automated security audit on microservices",
        steps=[
            {"title": "Scan open ports", "position": 0},
            {"title": "Check CVE vulnerabilities", "position": 1},
        ],
    )

    assert task_dict["id"] == run.run_id
    assert run.status == RunStatus.EXECUTING
    assert run.total_steps == 2
    assert len(plan.steps) == 2
    assert plan.steps[0].title == "Scan open ports"
    assert plan.steps[1].title == "Check CVE vulnerabilities"


@pytest.mark.asyncio
async def test_execute_step_with_deterministic_verification(setup_services):
    user, task_service, runtime, bridge = setup_services

    task_dict, run, plan = bridge.create_durable_agent_run(
        owner_id=user.id,
        goal="Generate API client schema",
        steps=[
            {"title": "Fetch OpenAPI spec", "position": 0},
            {"title": "Validate schema keys", "position": 1},
        ],
    )

    step0_id = task_dict["steps"][0]["id"]
    step1_id = task_dict["steps"][1]["id"]

    # 1. Execute step 0 with NON_EMPTY verification
    async def fetch_spec(step):
        return {"spec": "openapi: 3.1.0", "artifacts": [{"id": "art_100", "filename": "openapi.json"}]}

    v_non_empty = StepVerificationCondition(verification_type=VerificationType.NON_EMPTY)
    completed_task, result = await bridge.execute_step(
        user.id, task_dict["id"], step0_id, executor=fetch_spec, verification=v_non_empty
    )

    assert completed_task["status"] == "active"
    assert completed_task["steps"][0]["status"] == "completed"
    assert completed_task["steps"][0]["outputArtifactIds"] == ["art_100"]

    # 2. Execute step 1 with REQUIRED_KEYS verification failure test
    async def bad_validate(step):
        return {"status": "ok"}  # Missing required key 'schema_version'

    v_keys = StepVerificationCondition(
        verification_type=VerificationType.REQUIRED_KEYS,
        required_keys=["status", "schema_version"],
    )

    with pytest.raises(ValueError, match="Missing required keys"):
        await bridge.execute_step(
            user.id, task_dict["id"], step1_id, executor=bad_validate, verification=v_keys
        )

    # Step 1 should now be recorded as failed in TaskService
    failed_state = task_service.get_task(user.id, task_dict["id"])
    assert failed_state["steps"][1]["attemptCount"] == 1

    # 3. Now execute step 1 with valid required keys
    async def good_validate(step):
        return {"status": "ok", "schema_version": "3.1.0"}

    completed_task2, result2 = await bridge.execute_step(
        user.id, task_dict["id"], step1_id, executor=good_validate, verification=v_keys
    )

    assert completed_task2["status"] == "completed"
    assert completed_task2["steps"][1]["status"] == "completed"


def test_resume_from_checkpoint_without_rerunning_completed_steps(setup_services):
    user, task_service, runtime, bridge = setup_services

    task_dict, run, plan = bridge.create_durable_agent_run(
        owner_id=user.id,
        goal="Multi-stage data pipeline",
        steps=[
            {"title": "Extract records", "position": 0},
            {"title": "Transform records", "position": 1},
            {"title": "Load to warehouse", "position": 2},
        ],
    )

    step0_id = task_dict["steps"][0]["id"]
    # Complete step 0
    task_service.complete_step(user.id, task_dict["id"], step0_id)

    # Create fresh runtime instance and resume
    new_runtime = AgentRuntime()
    new_bridge = DurableTaskBridge(task_service, new_runtime)

    resumed_run, resumed_plan = new_bridge.resume_from_checkpoint(user.id, task_dict["id"])

    assert resumed_run.run_id == task_dict["id"]
    assert resumed_run.completed_steps == 1
    assert resumed_plan.steps[0].status == StepState.COMPLETED
    assert resumed_plan.steps[1].status != StepState.COMPLETED


def test_steer_task_injection(setup_services):
    user, task_service, runtime, bridge = setup_services

    task_dict, run, plan = bridge.create_durable_agent_run(
        owner_id=user.id,
        goal="Generate frontend components",
        steps=[{"title": "Draft button component", "position": 0}],
    )

    steered = bridge.steer_task(
        user.id,
        task_dict["id"],
        "Ensure all components use Tailwind CSS classes and WCAG AA contrast",
    )

    assert steered["status"] == "active"
    metadata = task_service.get_task(user.id, task_dict["id"]).get("metadata") or {}
    assert "Tailwind CSS" in metadata.get("lastSteeringInstruction", "")
    assert any("Tailwind CSS" in c for c in metadata.get("constraints", []))
