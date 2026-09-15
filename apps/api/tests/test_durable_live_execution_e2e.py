"""test_durable_live_execution_e2e.py — Durable Live Execution & Recovery Verification

Verifies:
1. POST /v1/tools/execute creates durable tasks, steps, checkpoints, and events in SQLite.
2. Idempotency: Duplicate calls with the same key return cached result without re-execution.
3. Idempotency Conflict: Same key with altered parameters returns 409 IDEMPOTENCY_CONFLICT.
4. Interruption & Restart Recovery: In-flight active tasks/steps recover cleanly to waiting_user on server restart.
"""
from __future__ import annotations

import time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.persistence.orm import (
    DurableTask,
    DurableTaskStep,
    DurableTaskCheckpoint,
    DurableTaskEvent,
)
from hinaa_api.persistence.db import get_session_factory
from hinaa_api.tools.registry import registry


@pytest.fixture
def durable_client(tmp_path):
    db_path = tmp_path / "durable_e2e.db"
    settings = Settings(
        HINAA_DATABASE_URL=f"sqlite:///{db_path}",
        HINAA_AUTH_MODE="dev",
        HINAA_DEV_AUTH_SUBJECT="test-durable-user",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_PROVIDER_MODE="mock",
        HINAA_AGENT_RUNTIME_ENABLED=True,
    )
    app = create_app(settings)
    client = TestClient(app)
    return client, settings


def test_durable_tool_execution_creates_sqlite_records(durable_client, monkeypatch):
    """Executing a tool over HTTP must record durable tasks, steps, checkpoints, and events."""
    client, settings = durable_client
    call_count = []

    async def mock_echo(params):
        call_count.append(params.get("message"))
        return {"echo": params.get("message"), "status": "success"}

    from hinaa_api.tools.registry import ToolDefinition
    tool_def = ToolDefinition(
        name="diagnostic_echo",
        display_name="Diagnostic Echo",
        description="Echo diagnostic message",
        parameters={"message": {"type": "string", "description": "message"}},
        required_parameters=["message"],
        requires_confirmation=False,
    )
    monkeypatch.setitem(registry._tools, "diagnostic_echo", tool_def)
    monkeypatch.setitem(registry._handlers, "diagnostic_echo", mock_echo)

    body = {
        "toolName": "diagnostic_echo",
        "parameters": {"message": "hello durable world"},
        "confirmed": True,
        "approvalSource": "standing-consent",
        "idempotencyKey": "durable-key-001",
        "conversationId": "conv-durable-123",
    }

    resp = client.post("/v1/tools/execute", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert "runtimeRunId" in data
    run_id = data["runtimeRunId"]

    # Verify SQLite records created by DurableTaskBridge & TaskService
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        # 1. Durable Task
        task = session.scalar(select(DurableTask).where(DurableTask.id == run_id))
        assert task is not None, f"DurableTask row with id {run_id} was not found in SQLite"
        assert task.status == "completed"
        assert task.conversation_id == "conv-durable-123"

        # 2. Durable Step
        steps = session.scalars(select(DurableTaskStep).where(DurableTaskStep.task_id == run_id)).all()
        assert len(steps) >= 1
        assert steps[0].status == "completed"

        # 3. Checkpoints
        checkpoints = session.scalars(
            select(DurableTaskCheckpoint).where(DurableTaskCheckpoint.task_id == run_id)
        ).all()
        assert len(checkpoints) >= 1

        # 4. Append-only Events
        events = session.scalars(
            select(DurableTaskEvent).where(DurableTaskEvent.task_id == run_id).order_by(DurableTaskEvent.sequence)
        ).all()
        event_types = [e.event_type for e in events]
        assert "TASK_CREATED" in event_types
        assert "STEP_COMPLETED" in event_types
        assert "TASK_COMPLETED" in event_types


def test_durable_tool_idempotency_and_conflict(durable_client, monkeypatch):
    """Submitting the exact same idempotencyKey returns cached result; differing params return 409."""
    client, settings = durable_client
    calls = []

    async def mock_echo(params):
        calls.append(params.get("message"))
        return {"echo": params.get("message"), "status": "success"}

    from hinaa_api.tools.registry import ToolDefinition
    tool_def = ToolDefinition(
        name="diagnostic_echo",
        display_name="Diagnostic Echo",
        description="Echo diagnostic message",
        parameters={"message": {"type": "string", "description": "message"}},
        required_parameters=["message"],
        requires_confirmation=False,
    )
    monkeypatch.setitem(registry._tools, "diagnostic_echo", tool_def)
    monkeypatch.setitem(registry._handlers, "diagnostic_echo", mock_echo)

    body = {
        "toolName": "diagnostic_echo",
        "parameters": {"message": "idempotent query"},
        "confirmed": True,
        "approvalSource": "standing-consent",
        "idempotencyKey": "idem-key-999",
    }

    # 1. First execution
    resp1 = client.post("/v1/tools/execute", json=body)
    assert resp1.status_code == 200
    run_id1 = resp1.json()["runtimeRunId"]
    assert len(calls) == 1

    # 2. Duplicate execution with identical key & params
    resp2 = client.post("/v1/tools/execute", json=body)
    assert resp2.status_code == 200
    assert resp2.json()["runtimeRunId"] == run_id1
    # Handler should NOT have been invoked a second time
    assert len(calls) == 1

    # 3. Conflicting execution with same key but different parameters
    conflicting_body = {
        "toolName": "diagnostic_echo",
        "parameters": {"message": "different query entirely"},
        "confirmed": True,
        "approvalSource": "standing-consent",
        "idempotencyKey": "idem-key-999",
    }
    resp3 = client.post("/v1/tools/execute", json=conflicting_body)
    assert resp3.status_code == 409


def test_interrupted_tasks_recovery_on_server_restart(durable_client):
    """In-flight tasks interrupted by a crash/restart must recover to waiting_user state with checkpoint."""
    import json
    client, settings = durable_client
    task_service = client.app.state.task_service
    owner = "test-durable-user"

    # Simulate an in-flight task that was running when server abruptly stopped
    task_data = task_service.create_task(
        owner_id=owner,
        goal="Simulate in-flight task",
        task_id="interrupted-task-001",
        steps=[{"title": "Running step", "status": "active"}],
    )
    # Put task in active status
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        task = session.scalar(select(DurableTask).where(DurableTask.id == "interrupted-task-001"))
        task.status = "active"
        session.commit()

    # Simulate server restart by running recover_interrupted_tasks()
    recovered = task_service.recover_interrupted_tasks(owner)
    assert len(recovered) >= 1
    rec_task = next(t for t in recovered if t["id"] == "interrupted-task-001")
    assert rec_task["status"] == "waiting_user"

    # Verify latest checkpoint in DB has reason restart_recovery
    with session_factory() as session:
        checkpoints = session.scalars(
            select(DurableTaskCheckpoint)
            .where(DurableTaskCheckpoint.task_id == "interrupted-task-001")
            .order_by(DurableTaskCheckpoint.version.desc())
        ).all()
        assert any(
            json.loads(cp.state_json or "{}").get("checkpointReason") == "restart_recovery"
            for cp in checkpoints
        )
