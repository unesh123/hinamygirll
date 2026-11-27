"""Regression tests for frame-by-frame video inspection, multi-file ingestion, new workspace tools, and multimodal Dual-Brain SORA builds."""

from __future__ import annotations

import asyncio
import base64
import io
import subprocess
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from hinaa_api.agent.live_agentic_service import (
    AgenticRunStore,
    _persist_attached_reference_files,
    launch_background_agentic_job,
    steer_agentic_run,
    subscribe_agentic_events,
)
from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.media.extractors import _get_ffmpeg_bin
from hinaa_api.media.video_inspector import VideoInspectFramesParams, video_inspect_frames_handler
from hinaa_api.models import TurnRequest
from hinaa_api.prompts.assembly import assemble_prompt
from hinaa_api.prompts.models import PromptInput
from hinaa_api.services import ConversationService
from hinaa_api.tools.code_animation_tool import WorkspaceVerifyHtmlParams, workspace_verify_html_handler
from hinaa_api.tools.workspace_coding_tools import (
    WorkspaceCheckpointParams,
    WorkspaceGitStatusDiffParams,
    WorkspaceMoveFileParams,
    workspace_checkpoint_handler,
    workspace_git_status_diff_handler,
    workspace_move_file_handler,
)

# 1x1 red PNG
_TINY_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
_TINY_PNG_DATA_URL = f"data:image/png;base64,{_TINY_PNG_B64}"


def _make_sample_mp4_bytes() -> bytes:
    ffmpeg = _get_ffmpeg_bin()
    import tempfile

    with tempfile.TemporaryDirectory(prefix="hinaa_test_mp4_") as td:
        out_mp4 = Path(td) / "sample.mp4"
        proc = subprocess.run(
            [
                ffmpeg,
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=0x111827:s=320x180:d=1.2",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(out_mp4),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=25,
        )
        assert proc.returncode == 0 and out_mp4.is_file()
        return out_mp4.read_bytes()


def _make_minimal_xlsx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"></Types>',
        )
        zf.writestr(
            "xl/sharedStrings.xml",
            '<?xml version="1.0" encoding="UTF-8"?><sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><si><t>Product</t></si><si><t>SORA</t></si></sst>',
        )
        zf.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="s"><v>1</v></c></row></sheetData></worksheet>',
        )
    return buf.getvalue()


@pytest.fixture
def test_client():
    app = create_app(Settings(provider_mode="mock", auth_enabled=False, _env_file=None))
    with TestClient(app) as client:
        yield client


def test_video_inspect_endpoint_and_all_file_extractors(test_client: TestClient) -> None:
    mp4_bytes = _make_sample_mp4_bytes()
    res = test_client.post(
        "/api/v1/media/inspect-video",
        files={"file": ("demo_ui.mp4", mp4_bytes, "video/mp4")},
        data={"start_sec": "0", "num_frames": "4"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["asset_id"]
    assert body["metadata"]["duration_seconds"] >= 0.8
    assert len(body["frames"]) == 4
    assert body["contact_sheet_asset_id"]
    assert str(body["contact_sheet_data_url"]).startswith("data:image/jpeg;base64,")
    assert "Video Frame-by-Frame Inspection" in body["summary"]

    # Code / Markdown / XLSX / ZIP extraction
    for fname, raw, mime, expected in (
        ("SORA_SPEC.md", b"# SORA Hub\nVite + React + Three.js", "text/markdown", "SORA Hub"),
        ("App.tsx", b"export function App(){ return <main>SORA</main>; }", "text/plain", "export function App"),
        ("catalog.xlsx", _make_minimal_xlsx_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "SORA"),
    ):
        ext_res = test_client.post("/api/v1/documents/extract", files={"file": (fname, raw, mime)})
        assert ext_res.status_code == 200, (fname, ext_res.text)
        assert expected in ext_res.json()["text"]

    # ZIP with nested .md snippet
    zbuf = io.BytesIO()
    with zipfile.ZipFile(zbuf, "w") as zf:
        zf.writestr("sora/README.md", "# SORA Architecture\nAnime hub spec")
    zres = test_client.post("/api/v1/documents/extract", files={"file": ("sora.zip", zbuf.getvalue(), "application/zip")})
    assert zres.status_code == 200
    assert "SORA Architecture" in zres.json()["text"]

    # Binary image/video rejected cleanly on document extract
    bad_mp4 = test_client.post("/api/v1/documents/extract", files={"file": ("clip.mp4", mp4_bytes, "video/mp4")})
    assert bad_mp4.status_code == 400


@pytest.mark.asyncio
async def test_video_inspect_frames_tool_handler(test_client: TestClient) -> None:
    mp4_bytes = _make_sample_mp4_bytes()
    up = test_client.post(
        "/api/v1/assets",
        files={"file": ("motion.mp4", mp4_bytes, "video/mp4")},
    )
    assert up.status_code in (200, 201)
    aid = up.json()["asset_id"]
    res = await video_inspect_frames_handler(VideoInspectFramesParams(asset_id=aid, num_frames=4))
    assert res["status"] == "success"
    assert len(res["frames"]) == 4
    preview_fp = Path(res["_vision_preview_path"])
    assert preview_fp.is_file()
    preview_fp.unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_workspace_move_git_status_and_checkpoint_roundtrip(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "old.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / ".env.local").write_text("SECRET_KEY=do_not_copy\n", encoding="utf-8")

    # 1. Checkpoint create (excludes .env.local)
    ckpt = await workspace_checkpoint_handler(
        WorkspaceCheckpointParams(action="create", label="before refactor", workspace_root=str(tmp_path))
    )
    assert ckpt["status"] == "success"
    cid = ckpt["checkpointId"]
    assert not (tmp_path / ".hina" / "checkpoints" / cid / "files" / ".env.local").exists()

    # 2. List checkpoints
    listed = await workspace_checkpoint_handler(
        WorkspaceCheckpointParams(action="list", workspace_root=str(tmp_path))
    )
    assert listed["status"] == "success"
    assert any(item["checkpointId"] == cid for item in listed["checkpoints"])

    # 3. Move file + sensitive/escape guard
    moved = await workspace_move_file_handler(
        WorkspaceMoveFileParams(source_path="src/old.py", dest_path="src/new.py", workspace_root=str(tmp_path))
    )
    assert moved["status"] == "success"
    assert not (tmp_path / "src" / "old.py").exists()
    assert (tmp_path / "src" / "new.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    blocked_move = await workspace_move_file_handler(
        WorkspaceMoveFileParams(source_path=".env.local", dest_path="src/leak.txt", workspace_root=str(tmp_path))
    )
    assert blocked_move["status"] == "error"

    # 4. Git status/diff inspection
    git_res = await workspace_git_status_diff_handler(
        WorkspaceGitStatusDiffParams(workspace_root=str(tmp_path))
    )
    assert git_res["status"] == "success"
    assert any("new.py" in entry for entry in git_res["changedEntries"])

    # 5. Checkpoint restore restores old.py cleanly
    restored = await workspace_checkpoint_handler(
        WorkspaceCheckpointParams(action="restore", checkpoint_id=cid, workspace_root=str(tmp_path))
    )
    assert restored["status"] == "success"
    assert (tmp_path / "src" / "old.py").read_text(encoding="utf-8") == "VALUE = 1\n"


@pytest.mark.asyncio
async def test_workspace_verify_html_mobile_viewport(tmp_path: Path) -> None:
    html_fp = tmp_path / "mobile_check.html"
    html_fp.write_text(
        "<!doctype html><html><body style='margin:0;background:#0f172a;color:#fff'><h1>SORA</h1><button>Explore</button></body></html>",
        encoding="utf-8",
    )
    res = await workspace_verify_html_handler(
        WorkspaceVerifyHtmlParams(file_path="mobile_check.html", mobile=True, wait_ms=300, workspace_root=str(tmp_path))
    )
    assert res["status"] == "success"
    assert res["mobile"] is True
    assert res["viewport"] == "390x844"
    assert res["horizontalOverflow"] is False
    assert res["interactiveCount"] >= 1
    assert res["headingCount"] >= 1
    preview = res.get("_vision_preview_path")
    if preview:
        Path(preview).unlink(missing_ok=True)


@pytest.mark.asyncio
async def test_sora_multiline_prompt_with_image_and_md_triggers_dual_brain_not_no_runner(tmp_path: Path, monkeypatch) -> None:
    from pydantic import SecretStr

    settings = Settings(
        provider_mode="toptools",
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        _env_file=None,
    )
    svc = ConversationService(settings=settings)
    captured: dict[str, object] = {}
    captured_muse_contexts: list[str] = []

    def _fake_launch(**kwargs):
        captured.update(kwargs)
        _persist_attached_reference_files(str(tmp_path), "run-sora-1", kwargs.get("attached_files"))
        from hinaa_api.agent.agentic_runner import AgenticRunResult
        from hinaa_api.agent.live_agentic_service import PersistedAgenticRun

        return PersistedAgenticRun(
            run_id=kwargs["run_id"],
            goal=kwargs["goal"],
            result=AgenticRunResult(run_id=kwargs["run_id"], status="running", summary="Started."),
        )

    sora_prompt = (
        "For the proper rebuild, build SORA now:\n\n"
        "Product: SORA — anime commerce + watch hub\n"
        "Stack: Vite/React, TypeScript, CSS, Three.js/WebGL\n"
        "Pages: command-center dashboard, storefront, product detail, watch page, cart drawer\n"
        "Files created in the workspace: package.json, src/, components, data, styles, 3D scene\n"
    )
    req = TurnRequest(
        sessionId="sess-sora-1",
        text=sora_prompt,
        providerMode="toptools",
        brainModel="Top-Tools-Ai-Pro",
        imageUrl=_TINY_PNG_DATA_URL,
        attachments=[
            {
                "filename": "SORA_PRD.md",
                "kind": "document",
                "mimeType": "text/markdown",
                "textExcerpt": "# SORA PRD\nObsidian black + cyan violet",
            }
        ],
    )

    orig_create_live_plan = svc.create_live_plan

    async def _wrapped_create_live_plan(*args, **kwargs):
        captured_muse_contexts.append(str(kwargs.get("muse_context") or ""))
        return await orig_create_live_plan(*args, **kwargs)

    monkeypatch.setattr("hinaa_api.agent.live_agentic_service.launch_background_agentic_job", _fake_launch)
    monkeypatch.setattr(svc.router, "llm", lambda *_a, **_kw: svc.router.mock_llm)
    monkeypatch.setattr(svc, "create_live_plan", _wrapped_create_live_plan)

    events = []
    async for chunk in svc.stream_turn(req, "corr-sora-1"):
        events.append(chunk)

    assert "allowed_tools" in captured
    allowed = captured["allowed_tools"]
    assert "design_website" not in allowed
    assert {"workspace_write_file", "workspace_checkpoint", "workspace_move_file", "video_inspect_frames"} <= set(allowed)
    assert len(captured.get("initial_images") or []) >= 1
    assert any(f.get("filename") == "SORA_PRD.md" for f in (captured.get("attached_files") or []))

    # Verify assembly never tells Brain #2 "No tools are available on this turn" during Muse Co-Build
    muse_ctx = captured_muse_contexts[0] if captured_muse_contexts else ""
    assert "WORKSPACE RUNNER IS ATTACHED" in muse_ctx
    pkg = assemble_prompt(
        PromptInput(
            companion_id="hinaa",
            interaction_mode="rest",
            user_text=sora_prompt,
            dialogue_state_block=muse_ctx,
            allowed_tools=(),
        )
    )
    assert "No tools are available on this turn" not in pkg.system_instruction
    assert "MUSE WORKSPACE RUNNER ATTACHED" in pkg.system_instruction


@pytest.mark.asyncio
async def test_background_progress_milestones_and_image_steer(tmp_path: Path) -> None:
    store = AgenticRunStore(tmp_path / "runs")
    step2_seen: dict[str, object] = {}
    entered_step2 = asyncio.Event()
    steer_sent = asyncio.Event()

    async def _fake_planner(transcript, step_num: int, images=None):
        if step_num == 1:
            return {
                "action": "call_tool",
                "tool": "workspace_write_file",
                "arguments": {"file_path": "sora/package.json", "content": '{"name":"sora"}', "overwrite": True},
            }
        if step_num == 2:
            entered_step2.set()
            await asyncio.wait_for(steer_sent.wait(), timeout=3.0)
            return {
                "action": "call_tool",
                "tool": "workspace_write_file",
                "arguments": {"file_path": "sora/index.html", "content": "<h1>SORA Ready at http://127.0.0.1:4173/</h1>", "overwrite": True},
            }
        step2_seen["images_count"] = len(images or [])
        step2_seen["transcript_text"] = str(transcript)
        return {"action": "final", "summary": "Built SORA at http://127.0.0.1:4173/ cleanly."}

    with patch("hinaa_api.agent.live_agentic_service.make_provider_planner", return_value=_fake_planner):
        rec = launch_background_agentic_job(
            goal="Build SORA storefront app",
            router=object(),
            settings=Settings(provider_mode="mock", _env_file=None),
            provider_mode="gemini",
            workspace_root=str(tmp_path),
            store=store,
            max_steps=4,
            initial_images=[("image/png", base64.b64decode(_TINY_PNG_B64))],
        )

        async def _consume():
            evts = []
            async for ev_name, payload in subscribe_agentic_events(rec.run_id, store=store):
                evts.append((ev_name, payload))
            return evts

        consumer = asyncio.create_task(_consume())
        await asyncio.wait_for(entered_step2.wait(), timeout=3.0)
        ok = steer_agentic_run(
            rec.run_id,
            "Use neon cyan glow",
            images=[("image/png", base64.b64decode(_TINY_PNG_B64))],
            attached_files=[{"filename": "THEME.md", "kind": "document", "textExcerpt": "# Cyan Theme"}],
            store=store,
        )
        assert ok is True
        steer_sent.set()
        events = await asyncio.wait_for(consumer, timeout=6.0)

    progress_events = [p for name, p in events if name == "agent.progress_update"]
    assert len(progress_events) >= 2
    assert any("sora/package.json" in (p.get("filesChanged") or []) for p in progress_events)
    finalized = [p for name, p in events if name == "agentic.finalized"]
    assert len(finalized) == 1
    assert "http://127.0.0.1:4173/" in (finalized[0].get("previewUrls") or [])
    assert step2_seen.get("images_count", 0) >= 1
    assert "LIVE IMAGES ATTACHED" in str(step2_seen.get("transcript_text") or "")
    assert "THEME.md" in str(step2_seen.get("transcript_text") or "")
