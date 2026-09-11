from __future__ import annotations

import json
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.agent.contracts import RunStatus


def test_stream_turn_creates_and_completes_agent_run_when_enabled():
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_AGENT_RUNTIME_ENABLED=True,
        HINAA_VMC_PORT=0,
        _env_file=None,
    )
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    runtime = app.state.agent_runtime

    r = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "sess-stream-1",
            "text": "Tell me about Tokyo",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "mock",
        },
    )
    assert r.status_code == 200
    lines = [json.loads(line) for line in r.text.split("\n") if line.strip()]
    assert len(lines) > 0
    event_types = [line.get("type") for line in lines]
    assert "agent.run.created" in event_types
    assert "agent.plan.ready" in event_types
    assert "agent.step.started" in event_types
    assert "agent.step.completed" in event_types
    assert "agent.run.completed" in event_types

    # Verify AgentRun was created and tracked to COMPLETED
    runs = list(runtime.runs.values())
    assert len(runs) >= 1
    stream_run = next((run for run in runs if run.goal == "Tell me about Tokyo"), None)
    assert stream_run is not None
    assert stream_run.status == RunStatus.COMPLETED
    assert stream_run.started_at is not None
    assert stream_run.completed_at is not None

    # Verify persisted in SQLite
    if runtime.persistence:
        persisted = runtime.persistence.get_run(stream_run.run_id)
        assert persisted is not None
        assert persisted.status == RunStatus.COMPLETED
        assert persisted.completed_at is not None
        persisted_steps = runtime.get_steps(stream_run.run_id, stream_run.user_id)
        assert persisted_steps is not None
        assert len(persisted_steps) == 1
        assert persisted_steps[0].status.value == "completed"
        persisted_events = runtime.get_events(stream_run.run_id, stream_run.user_id)
        assert persisted_events is not None
        assert [event.event_type for event in persisted_events][-1] == "agent.run.completed"


def test_stream_turn_without_agent_runtime_enabled():
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_AGENT_RUNTIME_ENABLED=False,
        HINAA_VMC_PORT=0,
        _env_file=None,
    )
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "sess-stream-disabled",
            "text": "Hello without agent runtime",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "mock",
        },
    )
    assert r.status_code == 200
    lines = [json.loads(line) for line in r.text.split("\n") if line.strip()]
    assert any(line.get("type") == "plan" for line in lines)
