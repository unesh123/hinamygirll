"""Regression tests for workspace grep speed, full autonomy gates, background approval/steering, and Muse dual-brain."""

import asyncio
import json

import httpx
import pytest
from pydantic import SecretStr

from hinaa_api.agent.agentic_runner import (
    AgenticLoopRunner,
    AgenticRunResult,
    PendingApprovalRecord,
    _hash_args,
)
from hinaa_api.agent.live_agentic_service import (
    AgenticRunStore,
    PersistedAgenticRun,
    launch_background_agentic_job,
    steer_agentic_run,
)
from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService
from hinaa_api.tools.registry import registry
from hinaa_api.tools.workspace_coding_tools import WorkspaceGrepParams, workspace_grep_handler


@pytest.mark.asyncio
async def test_workspace_grep_skips_artifact_venv_and_data_directories(tmp_path) -> None:
    (tmp_path / "src").mkdir(parents=True)
    (tmp_path / "src" / "app.py").write_text("target_token = 42\n", encoding="utf-8")

    for skipped in (
        tmp_path / ".venv" / "lib.py",
        tmp_path / "renders" / "scene.html",
        tmp_path / "generated_videos" / "clip.html",
        tmp_path / "generated_images" / "meta.txt",
        tmp_path / "apps" / "api" / "hinaa_api" / "data" / "brain_outcomes.json",
    ):
        skipped.parent.mkdir(parents=True, exist_ok=True)
        skipped.write_text('{"target_token": true}\n', encoding="utf-8")

    res = await workspace_grep_handler(
        WorkspaceGrepParams(pattern="target_token", workspace_root=str(tmp_path))
    )
    assert res["status"] == "success"
    assert res["count"] == 1
    assert res["matches"][0]["file"] == "src/app.py"


@pytest.mark.asyncio
async def test_full_autonomy_permits_web_research_while_gating_external_side_effect(
    tmp_path, monkeypatch
) -> None:
    orig_web_handler = registry._handlers.get("web_search")

    async def _fake_web(_args):
        return {"status": "success", "results": [{"title": "Merlin UI", "url": "https://example.com"}]}

    if "web_search" in registry._handlers:
        registry._handlers["web_search"] = _fake_web

    monkeypatch.setenv("HINAA_FULL_AUTONOMY", "true")
    monkeypatch.setenv("HINAA_AUTO_APPROVE", "true")
    autonomy_settings = Settings(_env_file=None)
    assert autonomy_settings.full_autonomy is True
    assert autonomy_settings.auto_approve is True

    runner = AgenticLoopRunner(max_steps=4, workspace_root=str(tmp_path), settings=autonomy_settings)
    try:
        async def _web_planner(_transcript, step_num: int, images=None):
            if step_num == 1:
                return {"action": "call_tool", "tool": "web_search", "arguments": {"query": "Merlin AI UI"}}
            return {"action": "final", "summary": "Researched Merlin UI cleanly."}

        res_web = await runner.run(
            goal="Research Merlin UI",
            planner=_web_planner,
            allowed_tools={"web_search", "workspace_read_file"},
        )
        assert res_web.status == "completed"
        assert res_web.steps[0].tool == "web_search"

        if registry.get("mlai_run_routine") is not None:
            async def _external_planner(_transcript, _step_num: int, images=None):
                return {
                    "action": "call_tool",
                    "tool": "mlai_run_routine",
                    "arguments": {"routine": "external-webhook"},
                }

            res_ext = await runner.run(
                goal="Trigger external routine",
                planner=_external_planner,
                allowed_tools={"web_search", "mlai_run_routine"},
            )
            assert res_ext.status == "awaiting_approval"
            assert res_ext.pending_approval is not None
            assert res_ext.pending_approval.tool == "mlai_run_routine"
    finally:
        if orig_web_handler is not None:
            registry._handlers["web_search"] = orig_web_handler


@pytest.mark.asyncio
async def test_background_agentic_approve_steer_and_stream_endpoints(tmp_path, monkeypatch) -> None:
    runs_dir = tmp_path / "runs"
    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(runs_dir))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)

    seen_steers: list[str] = []

    def _fake_make_planner(**kwargs):
        async def _planner(transcript, step_num: int, images=None):
            for item in transcript:
                if "indigoglow" in str(item) and "indigoglow" not in seen_steers:
                    seen_steers.append("indigoglow")
            await asyncio.sleep(0.03)
            if step_num == 1:
                return {
                    "action": "call_tool",
                    "tool": "workspace_write_file",
                    "arguments": {
                        "file_path": "out/site.html",
                        "content": "<html><body><h1>Live</h1></body></html>",
                    },
                }
            return {"action": "final", "summary": "Built out/site.html after steer/approval."}

        return _planner

    monkeypatch.setattr("hinaa_api.agent.live_agentic_service.make_provider_planner", _fake_make_planner)

    app_settings = Settings(_env_file=None, provider_mode="mock", full_autonomy=True, auto_approve=True)

    # 1. launch_background_agentic_job + steer_agentic_run + /stream NDJSON
    rec = launch_background_agentic_job(
        goal="Build site.html in background",
        router=object(),
        settings=app_settings,
        provider_mode="mock",
        user_id="default_user",
        allowed_tools={"workspace_write_file", "workspace_read_file"},
        workspace_root=str(tmp_path),
        max_steps=4,
    )
    assert rec.result.status == "running"
    assert steer_agentic_run(rec.run_id, "Add indigoglow theme tokens") is True

    app = create_app(app_settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        stream_lines: list[dict] = []
        async with client.stream("GET", f"/api/v1/agent/agentic-runs/{rec.run_id}/stream") as resp:
            assert resp.status_code == 200
            async for line in resp.aiter_lines():
                if line and line.strip():
                    stream_lines.append(json.loads(line))
        ev_types = [item.get("type") for item in stream_lines]
        assert "agent.steered" in ev_types
        assert "agentic.finalized" in ev_types
        assert "indigoglow" in seen_steers

        # 2. awaiting_approval + POST /approve with background=True
        store = AgenticRunStore(runs_dir)
        args = {"file_path": "approved/app.html", "content": "<html><body>Approved</body></html>"}
        arg_hash = _hash_args("workspace_write_file", args)
        gated_rec = PersistedAgenticRun(
            run_id="run-bg-approve-1",
            user_id="default_user",
            goal="Write approved/app.html",
            provider_mode="mock",
            allowed_tools=["workspace_write_file", "workspace_read_file"],
            workspace_root=str(tmp_path),
            result=AgenticRunResult(
                run_id="run-bg-approve-1",
                status="awaiting_approval",
                summary="Awaiting approval for workspace_write_file",
                pending_approval=PendingApprovalRecord(
                    approval_id="appr-bg-test-1",
                    tool="workspace_write_file",
                    scope="approved/app.html",
                    arguments_hash=arg_hash,
                    arguments_preview=args,
                    reason="Confirm file write",
                    rollback_hint="Delete created file",
                ),
            ),
        )
        store.save(gated_rec)

        appr_resp = await client.post(
            "/api/v1/agent/agentic-runs/run-bg-approve-1/approve",
            json={"approved": True, "argumentsHash": arg_hash, "background": True},
            headers={"X-Hinaa-User-Id": "default_user"},
        )
        assert appr_resp.status_code == 200, appr_resp.text
        appr_payload = appr_resp.json()
        assert appr_payload["result"]["status"] == "running"

        final_events: list[dict] = []
        async with client.stream("GET", "/api/v1/agent/agentic-runs/run-bg-approve-1/stream") as resp2:
            assert resp2.status_code == 200
            async for line in resp2.aiter_lines():
                if line and line.strip():
                    final_events.append(json.loads(line))
        assert any(e.get("type") == "agentic.finalized" for e in final_events)


@pytest.mark.asyncio
async def test_muse_dual_brain_stream_turn_launches_background_and_steers(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)

    def _slow_planner(**_kwargs):
        async def _planner(_transcript, step_num: int, images=None):
            await asyncio.sleep(0.15)
            if step_num == 1:
                return {
                    "action": "call_tool",
                    "tool": "workspace_write_file",
                    "arguments": {"file_path": "web/index.html", "content": "<html><body><h1>Merlin</h1></body></html>"},
                }
            return {"action": "final", "summary": "Finished website."}

        return _planner

    monkeypatch.setattr("hinaa_api.agent.live_agentic_service.make_provider_planner", _slow_planner)

    service = ConversationService(
        Settings(
            _env_file=None,
            provider_mode="toptools",
            toptools_api_key=SecretStr("sk-toptools-test-12345"),
            full_autonomy=True,
            auto_approve=True,
        )
    )
    monkeypatch.setattr(service.router, "llm", lambda *_a, **_kw: service.router.mock_llm)

    captured_muse_contexts: list[str] = []
    orig_create_live_plan = service.create_live_plan

    async def _wrapped_create_live_plan(*args, **kwargs):
        captured_muse_contexts.append(str(kwargs.get("muse_context") or ""))
        return await orig_create_live_plan(*args, **kwargs)

    monkeypatch.setattr(service, "create_live_plan", _wrapped_create_live_plan)

    req1 = TurnRequest(
        sessionId="sess-muse-1",
        text="Build me a dark interactive AI chat website landing page locally",
        providerMode="toptools",
    )
    events1 = [
        json.loads(line)
        async for chunk in service.stream_turn(req1, "corr-muse-1", user_id="u1")
        for line in chunk.decode("utf-8").splitlines()
        if line.strip()
    ]
    types1 = [e.get("type") for e in events1]
    assert "agentic.background" in types1
    assert "plan" in types1
    assert any("Background Builder Brain" in ctx or "clarifying" in ctx.lower() for ctx in captured_muse_contexts)
    bg_ev = next(e for e in events1 if e.get("type") == "agentic.background")
    run_id = bg_ev["runId"]
    assert run_id

    # Steer the live running builder while Muse continues chatting
    req2 = TurnRequest(
        sessionId="sess-muse-1",
        text="Use emerald accents and a clean pricing grid",
        providerMode="toptools",
        activeAgentRunId=run_id,
    )
    events2 = [
        json.loads(line)
        async for chunk in service.stream_turn(req2, "corr-muse-2", user_id="u1")
        for line in chunk.decode("utf-8").splitlines()
        if line.strip()
    ]
    types2 = [e.get("type") for e in events2]
    assert "agent.steered" in types2
    assert "plan" in types2

    # Wait briefly so background builder finishes before tmp_path teardown
    await asyncio.sleep(0.4)


@pytest.mark.asyncio
async def test_confirmation_persists_before_event_and_recovers_interrupted_run(
    tmp_path, monkeypatch
) -> None:
    from hinaa_api.agent.live_agentic_service import run_agentic_job

    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)
    monkeypatch.setenv("HINAA_AUTO_APPROVE", "false")
    monkeypatch.setenv("HINAA_FULL_AUTONOMY", "false")

    store = AgenticRunStore(tmp_path / "runs")
    cmd_args = {"command": "echo hi", "cwd": str(tmp_path)}
    expected_hash = _hash_args("workspace_run_command", cmd_args)
    seen_pending_during_event: list[bool] = []

    def _gate_planner(**_kwargs):
        async def _planner(_transcript, _step_num: int, images=None):
            return {
                "action": "call_tool",
                "tool": "workspace_run_command",
                "arguments": dict(cmd_args),
                "rationale": "Run echo test",
            }
        return _planner

    monkeypatch.setattr("hinaa_api.agent.live_agentic_service.make_provider_planner", _gate_planner)

    async def _on_evt(evt_name: str, _payload: dict) -> None:
        if evt_name == "confirmation.required":
            saved = store.load("run-persist-race-1")
            seen_pending_during_event.append(
                bool(saved and saved.result.pending_approval and saved.result.pending_approval.arguments_hash == expected_hash)
            )

    service = ConversationService(Settings(_env_file=None, provider_mode="mock"))
    await run_agentic_job(
        goal="Run echo test",
        router=service.router,
        settings=Settings(_env_file=None, provider_mode="mock", auto_approve=False, full_autonomy=False),
        provider_mode="mock",
        allowed_tools={"workspace_run_command"},
        workspace_root=str(tmp_path),
        run_id="run-persist-race-1",
        store=store,
        on_event=_on_evt,
    )
    assert seen_pending_during_event == [True]

    # Interrupted running record recovery + completed 409 check
    store.save(
        PersistedAgenticRun(
            run_id="run-interrupted-1",
            goal="Interrupted build",
            provider_mode="mock",
            allowed_tools=["workspace_run_command"],
            approved_hashes=[],
            workspace_root=str(tmp_path),
            result=AgenticRunResult(run_id="run-interrupted-1", status="running", summary="Interrupted mid-step"),
        )
    )
    store.save(
        PersistedAgenticRun(
            run_id="run-done-1",
            goal="Finished build",
            provider_mode="mock",
            result=AgenticRunResult(run_id="run-done-1", status="completed", summary="All done"),
        )
    )

    monkeypatch.setattr(
        "hinaa_api.agent.live_agentic_service.launch_background_agentic_job",
        lambda **kw: PersistedAgenticRun(
            run_id=kw["run_id"],
            goal=kw["goal"],
            provider_mode=kw["provider_mode"],
            allowed_tools=sorted(kw["allowed_tools"]),
            approved_hashes=sorted(kw["approved_hashes"]),
            workspace_root=kw["workspace_root"],
            result=AgenticRunResult(run_id=kw["run_id"], status="running", summary="Resumed cleanly"),
        ),
    )
    app = create_app(Settings(_env_file=None, provider_mode="mock"))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        ok_resp = await client.post(
            "/api/v1/agent/agentic-runs/run-interrupted-1/approve",
            json={"approved": True, "argumentsHash": expected_hash, "background": True},
        )
        assert ok_resp.status_code == 200, ok_resp.text
        assert expected_hash in ok_resp.json()["approved_hashes"]

        conflict_resp = await client.post(
            "/api/v1/agent/agentic-runs/run-done-1/approve",
            json={"approved": True, "argumentsHash": expected_hash},
        )
        assert conflict_resp.status_code == 409
