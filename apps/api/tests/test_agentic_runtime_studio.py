"""Integration & unit tests for AgenticLoopRunner, CodingService durability, and Studio routing."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys

import pytest

from hinaa_api.agent.agentic_runner import AgenticLoopRunner
from hinaa_api.agent.live_agentic_service import AgenticRunStore, run_agentic_job
from hinaa_api.coding.models import CodingTaskSpec, CodingTaskState
from hinaa_api.coding.service import CodingService
from hinaa_api.models import TurnRequest
from hinaa_api.config import Settings
from hinaa_api.services import ConversationService, ProviderRouter
from hinaa_api.tools import load_all_tools
from hinaa_api.tools.intent_gate import sanction_tools

load_all_tools()


@pytest.mark.asyncio
async def test_agentic_runner_multi_step_read_edit_verify_and_secret_scrub(tmp_path) -> None:
    target = tmp_path / "calc.py"
    target.write_text("# leak_hint: mlai_sk_testsecret123456\ndef mul(a, b):\n    return a + b\n", encoding="utf-8")

    decisions = [
        {"action": "call_tool", "tool": "workspace_glob", "arguments": {"pattern": "*.py"}},
        {"action": "call_tool", "tool": "workspace_read_file", "arguments": {"file_path": "calc.py"}},
        {
            "action": "call_tool",
            "tool": "workspace_edit_file",
            "arguments": {
                "file_path": "calc.py",
                "target_content": "return a + b",
                "replacement_content": "return a * b",
            },
        },
        {"action": "final", "summary": "Fixed mul() in calc.py."},
    ]

    async def planner(_transcript, step_num):
        return decisions[step_num - 1]

    runner = AgenticLoopRunner(max_steps=6, workspace_root=str(tmp_path))
    res = await runner.run(goal="Fix calc.py", planner=planner)
    assert res.status == "completed"
    assert res.steps_executed == 3
    assert res.files_changed == ["calc.py"]
    assert any(a["kind"] == "diff" for a in res.artifacts)
    assert "return a * b" in target.read_text(encoding="utf-8")
    read_obs = res.steps[1].observation.get("content", "")
    assert "[REDACTED]" in read_obs
    assert "mlai_sk_testsecret123456" not in json.dumps(res.model_dump())


@pytest.mark.asyncio
async def test_agentic_runner_pauses_on_confirmation_required_tool(tmp_path) -> None:
    async def planner(_transcript, _step):
        return {
            "action": "call_tool",
            "tool": "mlai_run_routine",
            "arguments": {"routine_id": "routine-123"},
            "rationale": "Trigger cloud routine",
        }

    runner = AgenticLoopRunner(max_steps=4, workspace_root=str(tmp_path))
    res = await runner.run(goal="Trigger ML AI routine", planner=planner)
    assert res.status == "awaiting_approval"
    assert res.pending_approval is not None
    assert res.pending_approval.tool == "mlai_run_routine"
    assert res.pending_approval.arguments_hash


@pytest.mark.asyncio
async def test_agentic_runner_blocks_repeated_failure_and_denies_out_of_scope(tmp_path) -> None:
    calls = 0

    async def planner(_transcript, step_num):
        nonlocal calls
        calls += 1
        if step_num == 1:
            return {"action": "call_tool", "tool": "shell_run", "arguments": {"command": "echo hi"}}
        return {"action": "call_tool", "tool": "workspace_read_file", "arguments": {"file_path": "missing.py"}}

    runner = AgenticLoopRunner(max_steps=6, max_consecutive_failures=2, workspace_root=str(tmp_path))
    res = await runner.run(
        goal="Try denied and missing file",
        planner=planner,
        allowed_tools={"workspace_read_file"},
    )
    assert res.status == "blocked"
    assert calls == 3
    assert res.steps[0].observation["code"] == "TOOL_NOT_PERMITTED"


def test_intent_gate_routes_code_animation_instead_of_image() -> None:
    s = sanction_tools("Render a 5s MP4 animation in code via Playwright + FFmpeg")
    assert "render_code_animation" in s.allowed
    assert s.parameters["render_code_animation"]["duration_seconds"] == 5.0
    assert "image_generate" not in s.allowed

    s_prev = sanction_tools("Create a 480p preview kinetic typography MP4 animation")
    assert "render_code_animation" in s_prev.allowed
    assert s_prev.parameters["render_code_animation"]["preview"] is True


@pytest.mark.asyncio
async def test_stream_turn_agentic_mode_persists_run_and_emits_events(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)
    service = ConversationService(Settings(_env_file=None, provider_mode="mock"))
    req = TurnRequest(
        sessionId="sess-ag-1",
        text="Inspect Python files in workspace",
        providerMode="mock",
        agenticMode=True,
    )
    events = []
    async for chunk in service.stream_turn(req, "corr-ag-1", user_id="u1"):
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events.append(json.loads(line))
    ev_types = [e.get("type") for e in events]
    assert "agent.step.started" in ev_types
    assert "tool.started" in ev_types
    assert "tool.completed" in ev_types
    assert "plan" in ev_types
    assert "run.completed" in ev_types
    loaded = AgenticRunStore(tmp_path / "runs").load("corr-ag-1")
    assert loaded is not None
    assert loaded.result.status == "completed"


@pytest.mark.asyncio
async def test_coding_service_persists_across_restart_and_executes_goal(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "t@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True, capture_output=True)
    (repo / "math_mod.py").write_text("def sq(x):\n    return x\n", encoding="utf-8")
    (repo / "test_math_mod.py").write_text("from math_mod import sq\n\ndef test_sq():\n    assert sq(4) == 16\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    store_dir = tmp_path / "coding_store"
    svc1 = CodingService(storage_dir=store_dir)
    spec = CodingTaskSpec(task_id="task-dur-01", workspace_path=str(repo), objective="Fix sq()")
    loop = svc1.create_task(spec)

    async def planner(_transcript, step_num):
        if step_num == 1:
            return {
                "action": "call_tool",
                "tool": "workspace_edit_file",
                "arguments": {
                    "file_path": "math_mod.py",
                    "target_content": "return x",
                    "replacement_content": "return x * x",
                },
            }
        return {"action": "final", "summary": "Updated sq() cleanly."}

    st = await loop.execute_goal(planner=planner, test_command=[sys.executable, "-m", "pytest", "test_math_mod.py", "-q"], use_worktree=False)
    assert st.state == CodingTaskState.COMPLETED
    assert st.files_changed == ["math_mod.py"]
    assert st.verification_evidence

    # Simulate process restart with a fresh CodingService reading same storage_dir
    svc2 = CodingService(storage_dir=store_dir)
    recovered_status = svc2.get_task("task-dur-01")
    assert recovered_status is not None
    assert recovered_status.state == CodingTaskState.COMPLETED
    assert recovered_status.files_changed == ["math_mod.py"]
    assert any(t.task_id == "task-dur-01" for t in svc2.list_tasks())
    assert len(svc2.get_events("task-dur-01")) >= 3


@pytest.mark.asyncio
async def test_run_agentic_job_approval_resume_roundtrip(tmp_path, monkeypatch) -> None:
    settings = Settings(_env_file=None, provider_mode="mock")
    router = ProviderRouter(settings)
    store = AgenticRunStore(tmp_path / "runs")

    # Verify approval gate blocks external mlai_run_routine then resumes when bound hash is approved
    executed: list[str] = []

    async def _fake_routine(params):
        rid = getattr(params, "routine_id", None) if not isinstance(params, dict) else params.get("routine_id")
        executed.append(str(rid))
        return {"status": "success", "routineId": rid}

    runner = AgenticLoopRunner(max_steps=4, workspace_root=str(tmp_path))

    async def routine_planner(_transcript, step_num):
        if step_num == 1:
            return {"action": "call_tool", "tool": "mlai_run_routine", "arguments": {"routine_id": "rt-99"}}
        return {"action": "final", "summary": "Routine dispatched."}

    first = await runner.run(goal="Trigger rt-99", planner=routine_planner)
    assert first.status == "awaiting_approval"
    assert first.pending_approval is not None
    bound_hash = first.pending_approval.arguments_hash

    from hinaa_api.tools import registry as _reg
    orig = _reg.get_handler("mlai_run_routine")
    _reg._handlers["mlai_run_routine"] = _fake_routine
    try:
        resumed = await runner.run(goal="Trigger rt-99", planner=routine_planner, approved_hashes={bound_hash})
    finally:
        if orig is not None:
            _reg._handlers["mlai_run_routine"] = orig
    assert resumed.status == "completed"
    assert executed == ["rt-99"]

    # Persist through run_agentic_job in mock mode
    rec = await run_agentic_job(
        goal="Inspect workspace",
        router=router,
        settings=settings,
        provider_mode="mock",
        store=store,
        run_id="ag-persist-1",
    )
    assert store.load("ag-persist-1") is not None
    assert rec.result.status == "completed"

    # Test cancel roundtrip through durable CodingService
    svc = CodingService(storage_dir=tmp_path / "cs")
    sp = CodingTaskSpec(task_id="task-cancel-01", workspace_path=str(tmp_path), objective="Cancelled test")
    lp = svc.create_task(sp)
    lp.status.state = CodingTaskState.EXECUTING
    svc._persist_task_record(sp.task_id, sp, lp.status)
    svc2 = CodingService(storage_dir=tmp_path / "cs")
    rehydrated = svc2.resume_task("task-cancel-01")
    assert rehydrated is not None
    assert svc2.cancel_task("task-cancel-01") is True
    assert svc2.get_task("task-cancel-01").state == CodingTaskState.CANCELLED


@pytest.mark.asyncio
async def test_workspace_write_list_dir_run_command_and_html_video_markdown(tmp_path, monkeypatch) -> None:
    import shutil
    from hinaa_api.agent.live_agentic_service import format_agentic_markdown
    from hinaa_api.tools.workspace_coding_tools import (
        WorkspaceListDirParams,
        WorkspaceRunCommandParams,
        WorkspaceWriteFileParams,
        is_safe_verify_command,
        workspace_list_dir_handler,
        workspace_run_command_handler,
        workspace_write_file_handler,
    )

    ws = str(tmp_path)
    # 1. Sensitive dotfiles must be blocked
    blocked = await workspace_write_file_handler(
        WorkspaceWriteFileParams(file_path=".env.local", content="SECRET=abc", workspace_root=ws)
    )
    assert blocked["code"] == "SENSITIVE_PATH_BLOCKED"

    # 2. Broken Python file must be rejected before disk write
    bad_py = await workspace_write_file_handler(
        WorkspaceWriteFileParams(file_path="broken.py", content="def f(:\n  pass\n", workspace_root=ws)
    )
    assert bad_py["code"] == "SYNTAX_ERROR"
    assert not (tmp_path / "broken.py").exists()

    # 3. Valid full-page HTML + Python test file + safe command run via AgenticLoopRunner
    from hinaa_api.creative.assets.manager import CreativeAssetManager

    mgr = CreativeAssetManager(tmp_path / "assets")
    monkeypatch.setattr("hinaa_api.tools.code_animation_tool.creative_asset_manager", mgr)

    html_doc = """<!DOCTYPE html>
<html><body style="margin:0;background:#09090b;color:#fff;width:320px;height:320px;display:flex;align-items:center;justify-content:center">
  <h1 id="t">HINAA</h1>
  <script>window.setAnimationTime = (t) => { document.getElementById('t').style.opacity = String(0.5 + 0.5*Math.sin(t)); };</script>
</body></html>"""

    steps = [
        {
            "action": "call_tool",
            "tool": "workspace_write_file",
            "arguments": {"file_path": "exports/hero.html", "content": html_doc},
        },
        {
            "action": "call_tool",
            "tool": "workspace_write_file",
            "arguments": {
                "file_path": "test_mod.py",
                "content": "def add(a, b):\n    return a + b\n\ndef test_add():\n    assert add(2, 3) == 5\n",
            },
        },
        {"action": "call_tool", "tool": "workspace_list_dir", "arguments": {"subpath": "."}},
        {"action": "call_tool", "tool": "workspace_run_command", "arguments": {"command": "pytest test_mod.py -q"}},
    ]
    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        steps.append({
            "action": "call_tool",
            "tool": "render_code_animation",
            "arguments": {"title": "Hero From HTML", "html_path": "exports/hero.html", "duration_seconds": 1.0, "fps": 10, "width": 320, "height": 320},
        })
    steps.append({"action": "final", "summary": "Built exports/hero.html and verified test_mod.py."})

    async def planner(_t, step_num):
        return steps[step_num - 1]

    runner = AgenticLoopRunner(max_steps=8, workspace_root=ws)
    res = await runner.run(goal="Build full HTML and run pytest", planner=planner)
    assert res.status == "completed", res
    assert "exports/hero.html" in res.files_changed
    assert "test_mod.py" in res.files_changed
    md = format_agentic_markdown(res)
    assert "```html" in md
    assert "```diff" in md
    assert "pytest test_mod.py -q" in md

    # 4. Unsafe command requires explicit approval gate
    assert is_safe_verify_command("pytest test_mod.py -q") is True
    assert is_safe_verify_command("git status") is True
    assert is_safe_verify_command("pip install evil") is False
    assert is_safe_verify_command("pytest; rm -rf /") is False

    async def unsafe_cmd_planner(_t, _s):
        return {"action": "call_tool", "tool": "workspace_run_command", "arguments": {"command": "pip install something"}}

    gated = await runner.run(goal="Install package", planner=unsafe_cmd_planner)
    assert gated.status == "awaiting_approval"
    assert gated.pending_approval and gated.pending_approval.tool == "workspace_run_command"


@pytest.mark.asyncio
async def test_stream_turn_auto_activates_agentic_on_html_video_and_skips_for_greeting(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)
    service = ConversationService(Settings(_env_file=None, provider_mode="mock"))

    # Auto-activates when agenticMode is None on full-page HTML/code creation prompt
    req_auto = TurnRequest(
        sessionId="sess-auto-1",
        text="Create a full-page HTML landing page and run pytest",
        providerMode="mock",
    )
    events_auto = []
    async for chunk in service.stream_turn(req_auto, "corr-auto-1", user_id="u1"):
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events_auto.append(json.loads(line))
    assert "agent.step.started" in [e.get("type") for e in events_auto]

    # Casual chat stays on fast single-turn path (no agentic runner)
    req_chat = TurnRequest(sessionId="sess-chat-1", text="Hey Hina how are you today?", providerMode="mock")
    events_chat = []
    async for chunk in service.stream_turn(req_chat, "corr-chat-1", user_id="u1"):
        for line in chunk.decode("utf-8").splitlines():
            if line.strip():
                events_chat.append(json.loads(line))
    assert "agent.step.started" not in [e.get("type") for e in events_chat]


@pytest.mark.asyncio
async def test_agentic_runner_xml_raw_tool_and_truncated_json_retry(tmp_path) -> None:
    calls = 0

    async def planner(transcript, step_num):
        nonlocal calls
        calls += 1
        if step_num == 1:
            # Truncated JSON must trigger retry observation instead of returning raw JSON as final summary
            return '{"action": "call_tool", "tool": "workspace_write_file", "arguments": {"file_path": "a.html", "content": "<html>unclosed'
        if step_num == 2:
            assert transcript[-1]["result"]["code"] == "TOOL_FORMAT_ERROR"
            return '<tool name="workspace_write_file" path="exports/raw_scene.html">\n<!DOCTYPE html><html><body>"Raw quotes"\nLine2</body></html>\n</tool>'
        return {"action": "final", "summary": "Wrote exports/raw_scene.html cleanly via XML."}

    runner = AgenticLoopRunner(max_steps=5, workspace_root=str(tmp_path))
    res = await runner.run(goal="Create raw HTML page", planner=planner)
    assert res.status == "completed"
    assert res.files_changed == ["exports/raw_scene.html"]
    assert '"Raw quotes"' in (tmp_path / "exports" / "raw_scene.html").read_text(encoding="utf-8")
    assert calls == 3
