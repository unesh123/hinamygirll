from __future__ import annotations

import asyncio
import json
import time

import httpx
import pytest
from pydantic import BaseModel

from hinaa_api.agent.contracts import AgentPlan, OperationType, PlanStep, RunStatus
from hinaa_api.media import AssetStore
from hinaa_api.persistence.db import get_session_factory
from hinaa_api.persistence.orm import GenerationSet, ImageJob
from hinaa_api.prompts.response_modes import infer_response_mode, response_mode_layer
from hinaa_api.providers.magnific import MagnificProvider
from hinaa_api.config import Settings
from hinaa_api.tools.registry import registry, ToolDefinition


class EchoParams(BaseModel):
    query: str
    userId: str | None = None


PNG_DATA_URL = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII="


def _provider_with_transport(monkeypatch, tmp_path, handler):
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs))
    return MagnificProvider(
        Settings(
            MAGNIFIC_API_KEY="test-key",
            MAGNIFIC_POLL_SECONDS=0.001,
            MAGNIFIC_TIMEOUT_SECONDS=0.02,
            _env_file=None,
        ),
        asset_store=AssetStore(tmp_path),
    )


def test_idempotent_tool_result_survives_runtime_cache_reset(client, monkeypatch):
    calls = []
    async def handler(params: EchoParams):
        calls.append(params.query)
        return {"status": "success", "data": {"query": params.query}}
    monkeypatch.setitem(registry._handlers, "youtube_playback_request", handler)
    body = {"toolName": "youtube_playback_request", "parameters": {"query": "calm music"},
            "confirmed": True, "approvalSource": "user", "idempotencyKey": "one-request"}
    first = client.post("/v1/tools/execute", json=body)
    assert first.status_code == 200
    run_id = first.json()["runtimeRunId"]
    runtime = client.app.state.agent_runtime
    for _ in range(100):
        if runtime.runs[run_id].status == RunStatus.COMPLETED:
            break
        time.sleep(0.01)
    original_ids = [event.event_id for event in runtime.get_events(run_id, runtime.runs[run_id].user_id)]
    runtime.runs.clear()
    runtime.plans.clear()
    runtime.events.clear()
    repeated = client.post("/v1/tools/execute", json=body)
    assert repeated.status_code == 200
    assert repeated.json()["runtimeRunId"] == run_id
    assert calls == ["calm music"]
    persisted_events = client.get(f"/v1/agent/runs/{run_id}/events").json()
    assert [event["event_id"] for event in persisted_events["events"]] == original_ids
    assert client.get(f"/v1/agent/runs/{run_id}/events?after={persisted_events['cursor']}").json()["events"] == []
    body["parameters"]["query"] = "different"
    assert client.post("/v1/tools/execute", json=body).status_code == 409


def test_image_poll_is_owner_scoped(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "alice"}).json()["userId"]
    with get_session_factory(client.app.state.settings)() as session:
        session.add(GenerationSet(id="private-job", user_id=owner, prompt="portrait", workflow_mode="quality"))
        session.commit()
    assert client.get("/v1/tools/poll?job_id=private-job", headers={"X-HINAA-Dev-User": "alice"}).status_code == 200
    assert client.get("/v1/tools/poll?job_id=private-job", headers={"X-HINAA-Dev-User": "bob"}).status_code == 404


def test_runtime_project_resume_keeps_workspace_run_live(client):
    owner = client.get("/v1/workspace/identity").json()["userId"]
    project = client.post("/v1/projects", json={"title": "Resume Project", "description": ""}).json()
    runtime = client.app.state.agent_runtime
    run = runtime.create_run("Resume the canonical project work", owner, project_id=project["id"])
    run.status = RunStatus.INTERRUPTED
    runtime.persistence.save_run(run)
    workspace = client.app.state.workspace_service
    workspace.create_agent_run(owner, project["id"], run.goal, run_id=run.run_id)
    workspace.update_agent_run(owner, run.run_id, "waiting_approval")

    response = client.post(f"/v1/agent/runs/{run.run_id}/resume")
    assert response.status_code == 200
    assert response.json()["status"] == "executing"
    assert workspace.get_agent_run(owner, run.run_id)["status"] != "cancelled"


def test_saved_step_restores_idempotency_timeout_description_and_result(client):
    runtime = client.app.state.agent_runtime
    run = runtime.create_run("Restore work", "owner")
    step = PlanStep(plan_id="pending", sequence=0, title="Write", description="Preserved instructions",
                    operation_type=OperationType.TOOL, tool_name="pdf_generate", timeout_seconds=37,
                    result={"docId": "saved-doc"})
    plan = AgentPlan(run_id=run.run_id, goal=run.goal, steps=[step])
    step.plan_id = plan.plan_id
    runtime.persistence.save_plan(plan)
    restored = runtime.persistence.get_plan_by_run(run.run_id).steps[0]
    assert restored.idempotency_key == step.idempotency_key
    assert restored.description == step.description
    assert restored.timeout_seconds == 37
    assert restored.result == {"docId": "saved-doc"}


@pytest.mark.parametrize("text,mode", [
    ("latest information", "research"), ("create an assignment report", "academic"),
    ("generate a poster image", "creative"), ("create a PDF document", "professional"),
    ("open YouTube", "automation"), ("hey hina kaise ho", "conversation"),
])
def test_response_mode_routes_content_before_generic_action_verbs(text, mode):
    assert infer_response_mode(text) == mode
    assert "Romanized Hinglish" in response_mode_layer(mode)


@pytest.mark.asyncio
async def test_provider_unauthorized_is_not_healthy(monkeypatch):
    provider = MagnificProvider(Settings(MAGNIFIC_API_KEY="test-key", _env_file=None))
    original_client = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(401, json={"error": "unauthorized"}))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original_client(transport=transport, **kwargs))
    assert await provider.health_check() is False
    assert provider._headers()["x-magnific-api-key"] == "test-key"
    assert "Authorization" not in provider._headers()


def test_freepik_key_uses_freepik_base_and_header():
    provider = MagnificProvider(Settings(FREEPIK_API_KEY="freepik-key", MAGNIFIC_API_KEY=None, _env_file=None))
    assert provider._base_url() == "https://api.freepik.com"
    assert provider._headers()["x-freepik-api-key"] == "freepik-key"
    assert "x-magnific-api-key" not in provider._headers()


@pytest.mark.asyncio
async def test_magnific_still_image_uses_task_api(monkeypatch, tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}") if request.content else {}
        seen.append((request.method, request.url.path, body, dict(request.headers)))
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "task-1"}})
        return httpx.Response(200, json={"data": {"status": "COMPLETED", "image_url": PNG_DATA_URL}})

    provider = _provider_with_transport(monkeypatch, tmp_path, handler)
    result = await provider.generate_still_image("pink cyber anime companion", seed=42, model="flux-dev")
    assert result.asset_ref is not None
    assert result.task_id == "task-1"
    assert seen[0][1] == "/v1/ai/text-to-image/flux-dev"
    assert seen[1][1] == "/v1/ai/text-to-image/flux-dev/task-1"
    assert seen[0][3]["x-magnific-api-key"] == "test-key"


@pytest.mark.asyncio
async def test_magnific_upscale_media_result_uses_image_upscaler_task(monkeypatch, tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}") if request.content else {}
        seen.append((request.method, request.url.path, body))
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "upscale-1"}})
        return httpx.Response(200, json={"data": {"status": "COMPLETED", "image_url": PNG_DATA_URL}})

    provider = _provider_with_transport(monkeypatch, tmp_path, handler)
    result = await provider.upscale(image_ref=PNG_DATA_URL, scale=2, prompt="sharpen softly")
    assert result.asset_ref is not None
    assert result.provider == "magnific:upscale"
    assert seen[0][1] == "/v1/ai/image-upscaler"
    assert seen[0][2]["scale_factor"] == "2x"
    assert seen[1][1] == "/v1/ai/image-upscaler/upscale-1"


@pytest.mark.asyncio
async def test_magnific_relight_uses_image_relight_task(monkeypatch, tmp_path):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content or b"{}") if request.content else {}
        seen.append((request.method, request.url.path, body))
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "relight-1"}})
        return httpx.Response(200, json={"data": {"status": "COMPLETED", "image_url": PNG_DATA_URL}})

    provider = _provider_with_transport(monkeypatch, tmp_path, handler)
    result = await provider.relight(PNG_DATA_URL, "soft sakura studio light")
    assert result.asset_ref is not None
    assert result.task_id == "relight-1"
    assert seen[0][1] == "/v1/ai/image-relight"
    assert seen[0][2]["prompt"] == "soft sakura studio light"
    assert "lighting_prompt" not in seen[0][2]
    assert seen[1][1] == "/v1/ai/image-relight/relight-1"


@pytest.mark.asyncio
async def test_magnific_task_polling_does_not_finish_on_pending_preview(monkeypatch, tmp_path):
    poll_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal poll_count
        if request.method == "POST":
            return httpx.Response(200, json={"data": {"task_id": "task-preview"}})
        poll_count += 1
        if poll_count == 1:
            return httpx.Response(200, json={"data": {"status": "PROCESSING", "preview_url": PNG_DATA_URL}})
        return httpx.Response(200, json={"data": {"status": "COMPLETED", "image_url": PNG_DATA_URL}})

    provider = _provider_with_transport(monkeypatch, tmp_path, handler)
    result = await provider.generate_still_image("wait for real completion")
    assert result.asset_ref is not None
    assert poll_count == 2


@pytest.mark.parametrize("tool", ["browser_navigate", "file_read", "file_write", "app_launch", "clipboard_get", "clipboard_set", "screenshot"])
def test_private_and_external_tools_require_explicit_confirmation(tool):
    assert registry.get_tool(tool).requires_confirmation is True
