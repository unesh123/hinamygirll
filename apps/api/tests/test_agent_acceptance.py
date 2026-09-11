from __future__ import annotations

import asyncio
import json
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.agent import AgentRuntime
from hinaa_api.agent.contracts import (
    AgentPlan,
    AgentRun,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
)
from hinaa_api.agent.recovery import recover_run


@pytest.fixture
def client_and_runtime():
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        GROQ_API_KEY="",
        OPENAI_API_KEY="",
        AGENT_ROUTER_API_KEY="",
        CX_GATEWAY_API_KEY="",
        ELEVENLABS_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_VMC_PORT=0,
        HINAA_AGENT_RUNTIME_ENABLED=True,
        _env_file=None,
    )
    app = create_app(settings)
    client = TestClient(app, raise_server_exceptions=False)
    runtime: AgentRuntime = app.state.agent_runtime
    return client, runtime


# 1. Existing simple conversation stream
def test_01_existing_conversation_stream(client_and_runtime):
    client, _ = client_and_runtime
    r = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "sess-accept-1",
            "text": "Hello HINAA",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "mock",
        },
    )
    assert r.status_code == 200
    lines = [line.strip() for line in r.text.split("\n") if line.strip()]
    assert len(lines) > 0


# 2. Feature-flag-disabled fallback
def test_02_feature_flag_disabled_fallback():
    rt_disabled = AgentRuntime(enabled=False)
    run_dis = rt_disabled.create_run("fallback test", "u1")
    run_dis_res = asyncio.run(rt_disabled.execute(run_dis))
    assert run_dis_res.status == RunStatus.QUEUED


# 3. Feature-flag-enabled simple runtime turn
def test_03_feature_flag_enabled_simple_turn():
    async def simple_exec(step):
        return {"msg": "done"}

    rt_enabled = AgentRuntime(enabled=True, executor=simple_exec)
    run_en = rt_enabled.create_run("simple turn", "u1")
    run_en_res = asyncio.run(rt_enabled.execute(run_en))
    assert run_en_res.status == RunStatus.COMPLETED


# 4. Multi-step fixture run (DAG order)
def test_04_multi_step_fixture_run():
    trace = []

    async def multi_exec(step):
        trace.append(step.title)
        return {"step": step.title}

    rt_multi = AgentRuntime(executor=multi_exec)
    run_m = rt_multi.create_run("dag run", "u1")
    plan_m = AgentPlan(run_id=run_m.run_id, goal="dag")
    s0 = PlanStep(plan_id=plan_m.plan_id, sequence=0, title="step0", operation_type=OperationType.RESPOND)
    s1 = PlanStep(plan_id=plan_m.plan_id, sequence=1, title="step1", operation_type=OperationType.RESPOND, dependencies=[s0.step_id])
    plan_m.steps = [s0, s1]
    res_m = asyncio.run(rt_multi.execute(run_m, plan=plan_m))
    assert res_m.status == RunStatus.COMPLETED
    assert trace == ["step0", "step1"]


# 5. Run retrieval
def test_05_run_retrieval(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("retrieval test", "local-dev-user")
    r = client.get(f"/v1/agent/runs/{run.run_id}")
    assert r.status_code == 200
    data = r.json()
    assert data["run_id"] == run.run_id


# 6. Step retrieval
def test_06_step_retrieval(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("steps test", "local-dev-user")
    plan = AgentPlan(run_id=run.run_id, goal="steps test")
    step = PlanStep(plan_id=plan.plan_id, sequence=0, title="first step", operation_type=OperationType.RESPOND)
    plan.steps = [step]
    runtime.plans[plan.plan_id] = plan
    if runtime.persistence:
        runtime.persistence.save_plan(plan)

    r = client.get(f"/v1/agent/runs/{run.run_id}/steps")
    assert r.status_code == 200
    steps = r.json().get("steps", [])
    assert len(steps) >= 1
    assert steps[0]["title"] == "first step"


# 7. Ordered event retrieval
def test_07_ordered_event_retrieval(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("events test", "local-dev-user")
    runtime._emit(run.run_id, "step.progress", payload={"action": "step1"})
    runtime._emit(run.run_id, "step.progress", payload={"action": "step2"})

    r = client.get(f"/v1/agent/runs/{run.run_id}/events")
    assert r.status_code == 200
    events = r.json().get("events", [])
    seqs = [e["sequence"] for e in events]
    assert seqs == list(range(1, len(events) + 1))


# 8. Queued cancellation
def test_08_queued_cancellation(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("cancel queued", "local-dev-user")
    r = client.post(f"/v1/agent/runs/{run.run_id}/cancel")
    assert r.status_code == 200
    assert r.json().get("status") == "cancelled"


# 9. Repeated cancellation (idempotent)
def test_09_repeated_cancellation(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("repeat cancel", "local-dev-user")
    r1 = client.post(f"/v1/agent/runs/{run.run_id}/cancel")
    assert r1.status_code == 200
    r2 = client.post(f"/v1/agent/runs/{run.run_id}/cancel")
    assert r2.status_code == 200
    assert r2.json().get("idempotent") is True


# 10. Confirmation-required pause
def test_10_confirmation_required_pause(client_and_runtime):
    _, runtime = client_and_runtime
    run = runtime.create_run("pause test", "local-dev-user")
    plan = AgentPlan(run_id=run.run_id, goal="pause")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="critical action",
        operation_type=OperationType.RESPOND,
        requires_confirmation=True,
    )
    plan.steps = [step]
    res = asyncio.run(runtime.execute(run, plan=plan))
    assert res.status == RunStatus.AWAITING_CONFIRMATION


# 11. Interrupted-run inspection
def test_11_interrupted_run_inspection(client_and_runtime):
    _, runtime = client_and_runtime
    run = runtime.create_run("interrupt test", "local-dev-user")
    run.status = RunStatus.EXECUTING
    recovered = recover_run(run)
    assert recovered.status == RunStatus.INTERRUPTED


# 12. Safe recovery path
def test_12_safe_recovery_path(client_and_runtime):
    client, runtime = client_and_runtime
    run = runtime.create_run("resume test", "local-dev-user")
    run.status = RunStatus.INTERRUPTED
    if runtime.persistence:
        runtime.persistence.save_run(run)

    r = client.post(f"/v1/agent/runs/{run.run_id}/resume")
    assert r.status_code == 200
    assert r.json().get("status") == "executing"


# 13. Existing conversation routes
def test_13_existing_conversation_routes(client_and_runtime):
    client, _ = client_and_runtime
    r = client.get("/health/live")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert data.get("service") == "hinaa-api"


# 14. Existing generated-image fixture routes
def test_14_existing_generated_image_routes(client_and_runtime, tmp_path, monkeypatch):
    """Image route serves a file from the images store.
    We create a minimal 1×1 white JPEG in the correct store directory so the
    test is self-contained regardless of which CWD pytest uses.
    """
    client, _ = client_and_runtime
    image_id = "056e086c693e4951bce9105a149d5e30"

    # Locate the image store relative to CWD (same logic as main.py)
    from pathlib import Path
    store = Path("apps/api/data/images").resolve()
    store.mkdir(parents=True, exist_ok=True)
    fixture = store / f"{image_id}.jpg"

    # Minimal valid JPEG header (1×1 white pixel)
    MINIMAL_JPEG = bytes([
        0xFF, 0xD8, 0xFF, 0xE0, 0x00, 0x10, 0x4A, 0x46, 0x49, 0x46, 0x00, 0x01,
        0x01, 0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00, 0xFF, 0xDB, 0x00, 0x43,
        0x00, 0x08, 0x06, 0x06, 0x07, 0x06, 0x05, 0x08, 0x07, 0x07, 0x07, 0x09,
        0x09, 0x08, 0x0A, 0x0C, 0x14, 0x0D, 0x0C, 0x0B, 0x0B, 0x0C, 0x19, 0x12,
        0x13, 0x0F, 0x14, 0x1D, 0x1A, 0x1F, 0x1E, 0x1D, 0x1A, 0x1C, 0x1C, 0x20,
        0x24, 0x2E, 0x27, 0x20, 0x22, 0x2C, 0x23, 0x1C, 0x1C, 0x28, 0x37, 0x29,
        0x2C, 0x30, 0x31, 0x34, 0x34, 0x34, 0x1F, 0x27, 0x39, 0x3D, 0x38, 0x32,
        0x3C, 0x2E, 0x33, 0x34, 0x32, 0xFF, 0xC0, 0x00, 0x0B, 0x08, 0x00, 0x01,
        0x00, 0x01, 0x01, 0x01, 0x11, 0x00, 0xFF, 0xC4, 0x00, 0x1F, 0x00, 0x00,
        0x01, 0x05, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
        0x09, 0x0A, 0x0B, 0xFF, 0xC4, 0x00, 0xB5, 0x10, 0x00, 0x02, 0x01, 0x03,
        0x03, 0x02, 0x04, 0x03, 0x05, 0x05, 0x04, 0x04, 0x00, 0x00, 0x01, 0x7D,
        0xFF, 0xDA, 0x00, 0x08, 0x01, 0x01, 0x00, 0x00, 0x3F, 0x00, 0xFB, 0xDE,
        0xFF, 0xD9,
    ])

    created = not fixture.exists()
    if created:
        fixture.write_bytes(MINIMAL_JPEG)
    try:
        r = client.get(f"/v1/generated-images/{image_id}")
        assert r.status_code == 200, f"Expected 200 got {r.status_code}. CWD: {Path.cwd()}, Store: {store}"
        assert "image" in r.headers.get("content-type", "")
    finally:
        if created and fixture.exists():
            fixture.unlink()



# 15. Video request rejection with HTTP 403
def test_15_video_request_rejection_http_403(client_and_runtime):
    client, _ = client_and_runtime
    r = client.post(
        "/v1/creative/jobs",
        json={
            "model": "magnific-video",
            "prompt": "forbidden video creation",
        },
    )
    assert r.status_code == 403
    assert r.json().get("code") == "VIDEO_GENERATION_FORBIDDEN"


# 16. Response-secret inspection
def test_16_response_secret_inspection():
    rt = AgentRuntime()
    run = rt.create_run("secret test", "u1")
    rt._emit(
        run.run_id,
        "test.event",
        payload={
            "api_key": "sk-proj-testkey12345678",
            "auth": "Bearer secret-val-1234567890",
            "password": "supersecretpassword",
        },
    )
    events = rt.get_events(run.run_id, "u1")
    last_event = events[-1]
    payload = last_event.payload
    assert "[REDACTED]" in payload["api_key"]
    assert "[REDACTED]" in payload["auth"]
    assert "[REDACTED]" in payload["password"]


# 17. Backward-compatible final response fields
def test_17_backward_compatible_response_fields(client_and_runtime):
    client, _ = client_and_runtime
    r = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "sess-compat-1",
            "text": "Hello backward compat",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "mock",
        },
    )
    assert r.status_code == 200
    lines = [json.loads(line) for line in r.text.split("\n") if line.strip()]
    plan_event = next((e for e in lines if e.get("type") == "plan"), None)
    assert plan_event is not None
    plan = plan_event.get("plan", {})
    for field in ["displayText", "spokenText", "language", "emotion", "performance"]:
        assert field in plan, f"Field '{field}' missing from turn plan response"
