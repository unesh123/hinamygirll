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


@pytest.mark.asyncio
async def test_long_motion_title_and_kinetic_song_prompt_never_502(tmp_path, monkeypatch) -> None:
    from hinaa_api.tools.motion_video_tool import MotionVideoParams

    # Long >120 char multi-line titles must clamp cleanly instead of raising HTTP 502 ValidationError
    mv = MotionVideoParams(
        title="There are my conversations with Hina.\n" + ("X" * 260),
        scenes=[{"title": "Intro", "subtitle": "Kinetic", "duration": 2.0, "layout": "orbit"}],
    )
    assert len(mv.title) <= 120
    assert mv.title.startswith("There are my conversations")

    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    monkeypatch.setattr("hinaa_api.agent.live_agentic_service._STORE_SINGLETON", None)
    service = ConversationService(Settings(_env_file=None, provider_mode="mock"))

    # Long kinetic-typography prompt containing "song" must auto-route to agentic loop (not blocked by song guard)
    long_prompt = (
        "There are my conversations with Hina. " + ("Context line. " * 12) +
        "Now create a kinetic typography MP4 video tightly synced to the song with layered motion and glow."
    )
    req_kin = TurnRequest(sessionId="sess-kin-1", text=long_prompt, providerMode="mock")
    ev_kin = [
        json.loads(line)
        async for chunk in service.stream_turn(req_kin, "corr-kin-1", user_id="u1")
        for line in chunk.decode("utf-8").splitlines()
        if line.strip()
    ]
    assert "agent.step.started" in [e.get("type") for e in ev_kin]

    # Capability inquiry and pure song playback stay off the auto-agentic loop
    for non_ag_prompt in ("What kind of videos can you make?", "Play a chill song on spotify"):
        req_plain = TurnRequest(sessionId="sess-plain-1", text=non_ag_prompt, providerMode="mock")
        ev_plain = [
            json.loads(line)
            async for chunk in service.stream_turn(req_plain, "corr-plain-1", user_id="u1")
            for line in chunk.decode("utf-8").splitlines()
            if line.strip()
        ]
        assert "agent.step.started" not in [e.get("type") for e in ev_plain]

    # Follow-up "now try again" resolves prior kinetic/MP4 goal from history & ignores stale refusal
    req_retry = TurnRequest(
        sessionId="sess-retry-1",
        text="now try again",
        providerMode="mock",
        history=[
            {"role": "user", "content": "Create a kinetic typography MP4 video synced to the song"},
            {"role": "assistant", "content": "No render tool is available to me on this turn; I can't render or attach the MP4."},
        ],
    )
    ev_retry = [
        json.loads(line)
        async for chunk in service.stream_turn(req_retry, "corr-retry-1", user_id="u1")
        for line in chunk.decode("utf-8").splitlines()
        if line.strip()
    ]
    assert "agent.step.started" in [e.get("type") for e in ev_retry]


def test_format_agentic_markdown_handles_string_output_without_crashing() -> None:
    from hinaa_api.agent.agentic_runner import AgenticRunResult
    from hinaa_api.agent.live_agentic_service import format_agentic_markdown

    res = AgenticRunResult(
        run_id="run-fmt-1",
        status="completed",
        summary="Rendered clip cleanly.",
        artifacts=[
            {
                "kind": "video",
                "download_url": "/v1/creative/assets/asset-xyz/download",
                "output": "neon.mp4",
            }
        ],
    )
    md = format_agentic_markdown(res)
    assert "/v1/creative/assets/asset-xyz/download" in md


@pytest.mark.asyncio
async def test_agentic_runner_timeout_error_has_descriptive_message(monkeypatch) -> None:
    from hinaa_api.agent.agentic_runner import AgenticLoopRunner

    runner = AgenticLoopRunner(max_steps=2, per_tool_timeout_seconds=1.0)

    async def _raise_empty_timeout(*_args, **_kwargs):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(runner, "_invoke_tool", _raise_empty_timeout)

    step_calls = {"n": 0}

    async def _planner(_transcript, step_num: int) -> str:
        step_calls["n"] = step_num
        if step_num == 1:
            return json.dumps({
                "action": "call_tool",
                "tool": "workspace_list_dir",
                "arguments": {},
                "rationale": "Test timeout recovery",
            })
        return json.dumps({"action": "final", "summary": "Recovered after timeout"})

    res = await runner.run(goal="Test timeout", planner=_planner, allowed_tools={"workspace_list_dir"})
    assert res.status == "completed"
    assert len(res.steps) == 1
    assert res.steps[0].status == "failed"
    assert res.steps[0].error and "timed out" in res.steps[0].error.lower()


def test_build_compact_tool_prompt_marks_final_render_ready() -> None:
    from hinaa_api.agent.live_agentic_service import build_compact_tool_prompt

    preview_prompt = build_compact_tool_prompt(
        {"render_code_animation"},
        [{"role": "tool_observation", "tool": "render_code_animation", "observation": {"status": "success", "stage": "preview_render", "download_url": "/v1/creative/assets/a1/download"}}],
        2,
        6,
    )
    assert "Verified Asset Ready" not in preview_prompt

    final_prompt = build_compact_tool_prompt(
        {"render_code_animation"},
        [{"role": "tool_observation", "tool": "render_code_animation", "observation": {"status": "success", "stage": "final_render", "download_url": "/v1/creative/assets/a2/download"}}],
        2,
        6,
    )
    assert "Verified Asset Ready: /v1/creative/assets/a2/download" in final_prompt


@pytest.mark.asyncio
async def test_services_routes_bug_inspection_and_webpage_builds_into_agentic(monkeypatch, tmp_path) -> None:
    from hinaa_api.config import get_settings
    from hinaa_api.models import TurnRequest
    from hinaa_api.services import ConversationService

    monkeypatch.setenv("HINAA_AGENTIC_RUNS_DIR", str(tmp_path / "runs"))
    import hinaa_api.agent.live_agentic_service as las
    las._STORE_SINGLETON = None
    service = ConversationService(get_settings())

    for prompt in (
        "Inspect why CreativeAssetManager loses metadata on restart and explain the line numbers cleanly.",
        "Build me a high-level interactive 3D solar system webpage with live orbits and controls, then verify it renders cleanly.",
        "Create a 6-second 1080p (1920x1080) kinetic motion-graphics MP4 reel using StudioFX showcasing BUILD BEYOND.",
    ):
        req = TurnRequest(sessionId="sess-auto-route", text=prompt, providerMode="mock")
        events = [
            json.loads(line)
            async for chunk in service.stream_turn(req, f"corr-{hash(prompt) & 0xffff}", user_id="u1")
            for line in chunk.decode("utf-8").splitlines()
            if line.strip()
        ]
        types = [e.get("type") for e in events]
        assert "agentic.started" in types, f"Expected agentic execution for {prompt!r}, got {types}"
        plan_ev = next(e for e in events if e.get("type") == "plan")
        assert plan_ev.get("provider") != "deterministic-intent"


@pytest.mark.asyncio
async def test_agentic_runner_parallel_batch_and_subagent_and_vision(tmp_path) -> None:
    from PIL import Image
    from hinaa_api.agent.agentic_runner import AgenticLoopRunner

    (tmp_path / "alpha.txt").write_text("alpha-data\n", encoding="utf-8")
    (tmp_path / "beta.txt").write_text("beta-data\n", encoding="utf-8")
    preview_file = tmp_path / "shot.jpg"
    Image.new("RGB", (64, 64), (20, 120, 240)).save(preview_file, format="JPEG")

    from hinaa_api.tools.registry import RiskTier, ToolDefinition, ToolEffect, registry

    if registry.get("_test_vision_emit") is None:
        async def _emit_vis(_args):
            return {"status": "success", "_vision_preview_path": str(preview_file)}

        registry.register(
            ToolDefinition(
                name="_test_vision_emit",
                display_name="Test Vision Emit",
                description="Emit synthetic preview path.",
                parameters={},
                required_parameters=[],
                is_read_only=True,
                is_concurrency_safe=True,
                requires_confirmation=False,
                risk_tier=RiskTier.TIER_0_READ_ONLY,
                effect=ToolEffect.READ,
            ),
            _emit_vis,
        )

    runner = AgenticLoopRunner(max_steps=5, workspace_root=str(tmp_path))
    seen_images: list[int] = []

    async def _planner(transcript, step_num: int, images=None) -> str:
        if images:
            seen_images.append(len(images))
        # Handle isolated subagent child call cleanly
        if transcript and "[Subagent Role:" in str(transcript[0].get("content", "")):
            if step_num == 1:
                return json.dumps({
                    "action": "call_tool",
                    "tool": "workspace_glob",
                    "arguments": {"pattern": "*.txt"},
                })
            return json.dumps({"action": "final", "summary": "Subagent found alpha.txt and beta.txt"})

        if step_num == 1:
            # Parallel XML read batch + subagent + vision producer
            return (
                '<tool name="workspace_read_file" file_path="alpha.txt" start_line="1" end_line="5"></tool>\n'
                '<tool name="workspace_read_file" file_path="beta.txt" start_line="1" end_line="5"></tool>\n'
                '<tool name="_test_vision_emit"></tool>'
            )
        if step_num == 2:
            return json.dumps({
                "action": "call_tool",
                "tool": "workspace_spawn_subagent",
                "arguments": {"role": "File Checker", "task": "List txt files"},
            })
        return json.dumps({"action": "final", "summary": "Parallel + vision + subagent succeeded"})

    try:
        res = await runner.run(
            goal="Inspect files cleanly",
            planner=_planner,
            allowed_tools={"workspace_read_file", "workspace_glob", "workspace_spawn_subagent", "_test_vision_emit"},
        )
        assert res.status == "completed"
        assert seen_images == [1]
        assert not preview_file.exists()  # temp preview cleaned up after reading bytes
        assert len(res.steps) == 4
        assert res.steps[3].tool == "workspace_spawn_subagent"
        assert res.steps[3].observation["summary"] == "Subagent found alpha.txt and beta.txt"
    finally:
        registry._tools.pop("_test_vision_emit", None)
        registry._handlers.pop("_test_vision_emit", None)


@pytest.mark.asyncio
async def test_workspace_background_process_and_loopback_verify(tmp_path) -> None:
    import socket
    from hinaa_api.tools.code_animation_tool import WorkspaceVerifyUrlParams, workspace_verify_url_handler
    from hinaa_api.tools.workspace_coding_tools import (
        WorkspaceProcessLogsParams,
        WorkspaceStartProcessParams,
        WorkspaceStopProcessParams,
        workspace_process_logs_handler,
        workspace_start_process_handler,
        workspace_stop_process_handler,
    )

    (tmp_path / "index.html").write_text(
        "<!DOCTYPE html><html><body style='background:#0b1120;color:#fff'><h1>Live Local App</h1></body></html>",
        encoding="utf-8",
    )
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    free_port = sock.getsockname()[1]
    sock.close()

    started = await workspace_start_process_handler(
        WorkspaceStartProcessParams(
            command=f"python -m http.server {free_port} --bind 127.0.0.1",
            ready_port=free_port,
            ready_wait_ms=5000,
            workspace_root=str(tmp_path),
        )
    )
    assert started["status"] == "success"
    assert started["listening"] is True
    pid = started["processId"]
    try:
        # Reject non-loopback SSRF URLs cleanly
        bad_url = await workspace_verify_url_handler(WorkspaceVerifyUrlParams(url="https://example.com/"))
        assert bad_url["status"] == "error"
        assert bad_url["code"] == "LOOPBACK_ONLY_BLOCKED"

        logs = await workspace_process_logs_handler(WorkspaceProcessLogsParams(process_id=pid, tail=20))
        assert logs["status"] == "success"
        assert logs["running"] is True

        try:
            verified = await workspace_verify_url_handler(
                WorkspaceVerifyUrlParams(url=f"http://127.0.0.1:{free_port}/index.html", wait_ms=300)
            )
            assert verified["status"] == "success"
            assert verified["httpStatus"] == 200
            assert verified["hasVisualRender"] is True
        finally:
            pass
    finally:
        stopped = await workspace_stop_process_handler(WorkspaceStopProcessParams(process_id=pid))
        assert stopped["status"] == "success"
        assert stopped["running"] is False


def test_build_compact_tool_prompt_builds_scratchpad_digest_for_long_transcripts() -> None:
    from hinaa_api.agent.live_agentic_service import build_compact_tool_prompt

    transcript: list[dict] = [{"role": "user", "content": "Build big app"}]
    for i in range(1, 14):
        transcript.append({
            "role": "tool_observation",
            "step": i,
            "tool": "workspace_read_file",
            "observation": {
                "status": "success",
                "filePath": f"src/mod_{i}.py",
                "startLine": 1,
                "endLine": 120,
                "content": "x" * 3500,
            },
        })
    prompt = build_compact_tool_prompt({"workspace_read_file"}, transcript, 14, 16)
    assert "[Rolling Workspace Scratchpad" in prompt
    assert "read `src/mod_1.py` L1-120" in prompt


def test_motion_and_render_params_coerce_llm_aliases() -> None:
    from pydantic import ValidationError
    from hinaa_api.creative.motion import MotionScene
    from hinaa_api.tools.code_animation_tool import RenderCodeAnimationParams
    from hinaa_api.tools.motion_video_tool import MotionVideoParams

    # Regression for LLM passing duration/description keys instead of subtitle/title
    mv = MotionVideoParams.model_validate({
        "title": "Kinetic Typography Reel",
        "scenes": [
            {"duration": 4, "description": "Near-black editorial title reveal"},
            "Second Beat Drop",
        ],
    })
    assert mv.scenes[0].subtitle == "Near-black editorial title reveal"
    assert mv.scenes[0].title == "Scene 1"
    assert mv.scenes[1].title == "Second Beat Drop"
    with pytest.raises(ValidationError):
        MotionScene(title="Bad", accent="javascript:alert(1)")

    rp = RenderCodeAnimationParams.model_validate({
        "prompt": "Kinetic Typography Reel\nNeon beat drop showcase",
        "html": "<html><body><canvas></canvas></body></html>",
        "duration": 6,
        "width": 1081,
        "height": 721,
    })
    assert rp.duration_seconds == 6.0
    assert rp.html_code == "<html><body><canvas></canvas></body></html>"
    assert rp.width == 1080 and rp.height == 720


def test_build_agentic_tool_schemas_and_messages_pairs() -> None:
    from hinaa_api.agent.live_agentic_service import build_agentic_messages, build_agentic_tool_schemas

    schemas = build_agentic_tool_schemas({"workspace_read_file", "workspace_delete_file"})
    names = {s["function"]["name"] for s in schemas}
    assert names == {"workspace_read_file", "workspace_delete_file"}

    msgs = build_agentic_messages(
        {"workspace_read_file"},
        [
            {"role": "user", "content": "Inspect app.py"},
            {
                "role": "tool_observation",
                "step": 1,
                "call_id": "call_1_0",
                "tool": "workspace_read_file",
                "arguments": {"file_path": "app.py"},
                "observation": {"status": "success", "filePath": "app.py"},
            },
        ],
        2,
        16,
    )
    assert msgs[0]["role"] == "user"
    assert msgs[1]["role"] == "assistant" and msgs[1]["tool_calls"][0]["id"] == "call_1_0"
    assert msgs[2]["role"] == "tool" and msgs[2]["tool_call_id"] == "call_1_0"


@pytest.mark.asyncio
async def test_openai_native_tool_calls_and_gateway_fallback(monkeypatch) -> None:
    import contextlib
    import httpx
    from hinaa_api.providers.openai_llm import OpenAILLMProvider

    adapter = OpenAILLMProvider(
        key="sk-test",
        model="deepseek/deepseek-v4.1-flash",
        base_url="https://api.example.com/v1",
        provider_id="custom",
    )
    payloads_seen: list[dict] = []

    class _FakeClient:
        async def post(self, _url, headers=None, json=None):
            payloads_seen.append(dict(json or {}))
            if "tools" in (json or {}):
                # 1st test triggers native tool_calls response unless fallback flag set
                if headers is not None and len(payloads_seen) == 1:
                    return httpx.Response(
                        200,
                        json={
                            "choices": [{
                                "message": {
                                    "content": "",
                                    "tool_calls": [{
                                        "id": "tc_1",
                                        "type": "function",
                                        "function": {
                                            "name": "workspace_glob",
                                            "arguments": "{\"pattern\": \"*.py\"}",
                                        },
                                    }],
                                }
                            }]
                        },
                    )
                return httpx.Response(400, json={"error": {"message": "tools unsupported"}})
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "{\"action\": \"final\", \"summary\": \"ok\"}"}}]},
            )

    @contextlib.asynccontextmanager
    async def _fake_pool():
        yield _FakeClient()

    monkeypatch.setattr("hinaa_api.providers.openai_llm._pooled_client", _fake_pool)

    schemas = [{"type": "function", "function": {"name": "workspace_glob", "parameters": {"type": "object"}}}]
    res1 = await adapter.complete_raw_agentic(
        system_prompt="sys",
        user_prompt="flat",
        tool_schemas=schemas,
        messages=[{"role": "user", "content": "hi"}],
    )
    parsed1 = json.loads(res1)
    assert parsed1["action"] == "call_tool"
    assert parsed1["tool"] == "workspace_glob"
    assert parsed1["arguments"] == {"pattern": "*.py"}

    # Second call simulates 400 on `tools` and proves seamless fallback to prompt mode
    res2 = await adapter.complete_raw_agentic(
        system_prompt="sys",
        user_prompt="flat",
        tool_schemas=schemas,
        messages=[{"role": "user", "content": "hi"}],
    )
    assert json.loads(res2)["action"] == "final"
    assert "tools" not in payloads_seen[-1]


@pytest.mark.asyncio
async def test_agentic_runner_rejects_step1_planning_monologue_and_executes_tool(tmp_path) -> None:
    calls = 0

    async def _planner(_transcript, step_num: int):
        nonlocal calls
        calls += 1
        if step_num == 1:
            return "Let me first check the workspace and write out a quick sample:\n```html\n<div>unclosed"
        if step_num == 2:
            return {
                "action": "call_tool",
                "tool": "workspace_write_file",
                "arguments": {"file_path": "out.html", "content": "<!doctype html><html><body>OK</body></html>"},
            }
        return {"action": "final", "summary": "Wrote out.html cleanly."}

    runner = AgenticLoopRunner(max_steps=5, workspace_root=str(tmp_path))
    res = await runner.run(goal="Build out.html webpage", planner=_planner)
    assert res.status == "completed"
    assert calls == 3
    assert res.files_changed == ["out.html"]
    assert (tmp_path / "out.html").exists()


@pytest.mark.asyncio
async def test_openai_reasoning_only_without_tool_call_never_leaks_prose(monkeypatch) -> None:
    import contextlib
    import httpx
    from hinaa_api.providers.openai_llm import OpenAILLMProvider

    adapter = OpenAILLMProvider(key="sk-test", model="deepseek-v4-1-flash-1017", base_url="https://api.example.com/v1", provider_id="custom")

    class _ReasoningClient:
        async def post(self, _url, headers=None, json=None):
            return httpx.Response(
                200,
                json={"choices": [{"message": {"content": "", "reasoning_content": "Let me think through step 1..."}}]},
            )

    @contextlib.asynccontextmanager
    async def _fake_pool():
        yield _ReasoningClient()

    monkeypatch.setattr("hinaa_api.providers.openai_llm._pooled_client", _fake_pool)
    out = await adapter.complete_raw_agentic(system_prompt="sys", user_prompt="flat")
    assert out == ""
