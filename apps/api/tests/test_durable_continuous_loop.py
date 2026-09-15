"""Tests for C1 Durable Continuous Agent Loop (Directives §1–§9).

Verifies:
1. Autonomous loop driving multi-step DAG execution sequentially to completion.
2. Worker lease fencing token rejection for stale workers.
3. Lease expiration and lease extension.
4. Interruption recovery and restart safety without replaying finished steps.
"""

import asyncio
from datetime import UTC, datetime, timedelta
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from hinaa_api.agent.bridge import (
    DurableTaskBridge,
    LoopExecutionSummary,
    StepVerificationCondition,
    VerificationType,
)
from hinaa_api.agent.runtime import AgentRuntime
from hinaa_api.errors import HinaaError
from hinaa_api.persistence.orm import Base
from hinaa_api.persistence.task_service import TaskService


@pytest.fixture
def task_service():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    return TaskService(factory)


@pytest.fixture
def runtime():
    return AgentRuntime()


@pytest.fixture
def bridge(task_service, runtime):
    return DurableTaskBridge(task_service, runtime)


@pytest.mark.asyncio
async def test_autonomous_loop_sequential_dag(bridge, task_service):
    """3-step DAG (step1 -> step2 -> step3). Autonomous loop must execute in order."""
    steps = [
        {"id": "step_1", "title": "Analyze bug", "dependencies": []},
        {"id": "step_2", "title": "Apply patch", "dependencies": ["step_1"]},
        {"id": "step_3", "title": "Run regression tests", "dependencies": ["step_2"]},
    ]

    task_dict = task_service.create_task(
        owner_id="user_123",
        goal="Fix math calculation error",
        steps=steps,
    )
    task_id = task_dict["id"]

    executed_order: list[str] = []

    async def mock_executor(step: dict, context: dict) -> dict:
        step_id = step["id"]
        executed_order.append(step_id)
        assert context["taskId"] == task_id
        assert context["fencingToken"] >= 1
        return {"step": step_id, "status": "ok"}

    summary = await bridge.run_autonomous_loop(
        owner_id="user_123",
        task_id=task_id,
        worker_id="worker_alpha",
        executor=mock_executor,
    )

    assert summary.status == "completed"
    assert summary.completed_steps == 3
    assert executed_order == ["step_1", "step_2", "step_3"]

    # Verify task state in TaskService
    final_task = task_service.get_task("user_123", task_id)
    assert final_task["status"] == "completed"
    assert all(s["status"] == "completed" for s in final_task["steps"])


@pytest.mark.asyncio
async def test_worker_fence_rejection_stale_worker(bridge, task_service):
    """Worker 1 acquires lease (fencing_token=1).
    Worker 2 acquires lease (fencing_token=2).
    Worker 1 attempts to complete or fail a step with stale fencing token 1 -> rejected!
    """
    steps = [{"id": "s1", "title": "Work", "dependencies": []}]
    task = task_service.create_task("user_123", "Important task", steps=steps)
    task_id = task["id"]

    # Worker 1 claims
    claim1 = task_service.claim_task("user_123", task_id, worker_id="worker_1", lease_seconds=60)
    lease1 = claim1["lease"]["leaseId"]
    token1 = claim1["lease"]["fencingToken"]
    assert token1 == 1

    # Worker 2 claims (simulating worker 1 hung or timed out, force takeover)
    claim2 = task_service.claim_task("user_123", task_id, worker_id="worker_2", lease_seconds=60, force=True)
    lease2 = claim2["lease"]["leaseId"]
    token2 = claim2["lease"]["fencingToken"]
    assert token2 == 2

    # Worker 1 tries to complete step with stale token 1 -> STALE_WORKER_FENCE
    with pytest.raises(HinaaError) as exc_info:
        task_service.complete_step_with_lease(
            "user_123", task_id, "s1", lease_id=lease1, fencing_token=token1
        )
    assert exc_info.value.code == "STALE_WORKER_FENCE"

    # Worker 1 tries to fail step with stale token 1 -> STALE_WORKER_FENCE
    with pytest.raises(HinaaError) as exc_info2:
        task_service.fail_step_with_lease(
            "user_123", task_id, "s1", "error", lease_id=lease1, fencing_token=token1
        )
    assert exc_info2.value.code == "STALE_WORKER_FENCE"

    # Worker 2 (current fence holder) successfully completes step
    completed = task_service.complete_step_with_lease(
        "user_123", task_id, "s1", lease_id=lease2, fencing_token=token2
    )
    assert completed["status"] == "completed"


@pytest.mark.asyncio
async def test_lease_extension(task_service):
    """Extending lease pushes expiration forward without changing fencing token."""
    steps = [{"id": "s1", "title": "Long work", "dependencies": []}]
    task = task_service.create_task("user_123", "Long task", steps=steps)
    task_id = task["id"]

    claim = task_service.claim_task("user_123", task_id, worker_id="worker_slow", lease_seconds=30)
    initial_expiry = datetime.fromisoformat(claim["lease"]["leaseExpiresAt"])
    token = claim["lease"]["fencingToken"]
    lease_id = claim["lease"]["leaseId"]

    extended = task_service.extend_lease(
        "user_123", task_id, lease_id=lease_id, fencing_token=token, additional_seconds=120
    )
    new_expiry = datetime.fromisoformat(extended["lease"]["leaseExpiresAt"])
    assert new_expiry > initial_expiry
    assert extended["lease"]["fencingToken"] == token


@pytest.mark.asyncio
async def test_restart_recovery_and_resumption(bridge, task_service):
    """Task interrupted mid-execution recovers active steps and completes remaining steps."""
    steps = [
        {"id": "step_a", "title": "Done step", "dependencies": []},
        {"id": "step_b", "title": "Interrupted step", "dependencies": ["step_a"]},
        {"id": "step_c", "title": "Final step", "dependencies": ["step_b"]},
    ]
    task = task_service.create_task("user_123", "Recovery task", steps=steps)
    task_id = task["id"]

    # Claim and complete step_a
    claim = task_service.claim_task("user_123", task_id, worker_id="worker_1")
    task_service.complete_step_with_lease(
        "user_123",
        task_id,
        "step_a",
        lease_id=claim["lease"]["leaseId"],
        fencing_token=claim["lease"]["fencingToken"],
    )

    # Mark step_b as active (simulating crash while executing step_b)
    with task_service._factory() as session:
        step_row = task_service._step(session, task_id, "step_b")
        step_row.status = "active"
        session.commit()

    # Server restarts -> recover_interrupted_tasks
    recovered = task_service.recover_interrupted_tasks(owner_id="user_123")
    assert len(recovered) == 1
    rec_task = recovered[0]
    rec_b = next(s for s in rec_task["steps"] if s["id"] == "step_b")
    assert rec_b["status"] == "pending"
    assert rec_b["failureReason"] == "interrupted_by_server_restart"

    # Autonomous loop resumes task with new worker
    executed_steps: list[str] = []

    async def resume_executor(step: dict, context: dict) -> dict:
        executed_steps.append(step["id"])
        return {"status": "ok"}

    summary = await bridge.run_autonomous_loop(
        owner_id="user_123",
        task_id=task_id,
        worker_id="worker_recovered",
        executor=resume_executor,
    )

    assert summary.status == "completed"
    # Step A was already completed, so ONLY step B and C are executed!
    assert executed_steps == ["step_b", "step_c"]
