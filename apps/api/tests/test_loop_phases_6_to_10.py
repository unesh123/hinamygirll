"""Integration & unit verification for Loop Harness Phases 6 to 10."""

from __future__ import annotations

import asyncio
import io
import json
import sys
import time
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from hinaa_api.config import get_settings
from hinaa_api.harness.agent_step import LLMAgentStep, LoopProvider, resolve_approval
from hinaa_api.harness.loop_engine import EvidenceReceipt, LoopTaskSpec
from hinaa_api.harness.loop_events import EVENT_BUS
from hinaa_api.main import create_app
from hinaa_api.response_protocol import (
    ChartBlock,
    ImageGalleryBlock,
    MetricGridBlock,
    MetricItem,
    ResponseDocument,
)


def _provider(protocol: str = "openai") -> LoopProvider:
    return LoopProvider(
        name="test-mock",
        protocol=protocol,
        base_url="https://mock.invalid/v1",
        api_key="dummy-key",
        model="mock-model",
    )


def _step_for(
    tmp_path: Path,
    replies: list[str],
    calls: list[dict],
    *,
    protocol: str = "openai",
    require_human_approval: bool = False,
) -> LLMAgentStep:
    idx = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal idx
        payload = json.loads(request.content.decode("utf-8"))
        calls.append(payload)
        reply = replies[min(idx, len(replies) - 1)]
        idx += 1
        if protocol == "anthropic":
            return httpx.Response(200, json={"content": [{"type": "text", "text": reply}], "usage": {"input_tokens": 10, "output_tokens": 10}})
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": reply}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LLMAgentStep(
        provider=_provider(protocol),
        workspace_dir=tmp_path,
        trace_path=tmp_path / "state" / "t_trace.jsonl",
        state_dir=tmp_path / "state",
        client=client,
        require_human_approval=require_human_approval,
    )


def _spec(tmp_path: Path, task_id: str = "loop_p610") -> LoopTaskSpec:
    return LoopTaskSpec(
        task_id=task_id,
        goal_title="Verify phases 6-10",
        verification_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
        workspace_dir=str(tmp_path),
        max_turns=3,
    )


def test_phase6_build_website_tool_emits_preview_ready(tmp_path, monkeypatch):
    import hinaa_api.foundry.service as foundry_mod
    from hinaa_api.foundry.service import FoundryService

    monkeypatch.setattr(foundry_mod, "_FOUNDRY_SINGLETON", FoundryService(db_path=tmp_path / "f.db"))
    calls: list[dict] = []
    # Without confirm=True -> blocked
    bad_reply = json.dumps({"thought": "build", "actions": [{"type": "build_website", "brief": "Kuro Coffee in Kyoto"}]})
    step = _step_for(tmp_path, [bad_reply], calls)
    res_bad = asyncio.run(step.run(_spec(tmp_path, "loop_site_bad"), 1, None))
    assert res_bad.outcomes[0].status == "blocked"

    # With confirm=True -> applied + preview_ready SSE event
    good_reply = json.dumps(
        {"thought": "build site", "actions": [{"type": "build_website", "brief": "Kuro Coffee in Kyoto", "confirm": True}]}
    )
    step2 = _step_for(tmp_path, [good_reply], calls)
    res_ok = asyncio.run(step2.run(_spec(tmp_path, "loop_site_ok"), 1, None))
    assert res_ok.outcomes[0].status == "applied"
    detail = json.loads(res_ok.outcomes[0].detail)
    assert detail["preview_url"].startswith("/api/v1/foundry/sites/site_")
    ev_types = [e["event_type"] for e in EVENT_BUS.history("loop_site_ok")]
    assert "preview_ready" in ev_types


def test_phase6_run_dev_server_gates_and_cleanup(tmp_path, monkeypatch):
    calls: list[dict] = []
    reply = json.dumps(
        {
            "thought": "serve",
            "actions": [{"type": "run_dev_server", "command": f"{sys.executable} -m http.server 3008", "port": 3008, "confirm": True}],
        }
    )
    monkeypatch.delenv("HINAA_LOOP_ALLOW_COMMANDS", raising=False)
    step = _step_for(tmp_path, [reply], calls)
    res_blocked = asyncio.run(step.run(_spec(tmp_path, "loop_srv_blk"), 1, None))
    assert res_blocked.outcomes[0].status == "blocked"

    # When enabled inside workspace, spawns bounded server and terminates cleanly in aclose()
    monkeypatch.setenv("HINAA_LOOP_ALLOW_COMMANDS", "1")
    step2 = _step_for(tmp_path, [reply], calls)

    async def _go():
        try:
            return await step2.run(_spec(tmp_path, "loop_srv_ok"), 1, None)
        finally:
            await step2.aclose()

    res_ok = asyncio.run(_go())
    assert res_ok.outcomes[0].status == "applied"
    info = json.loads(res_ok.outcomes[0].detail)
    assert info["preview_url"] == "http://127.0.0.1:3008/"
    assert not step2._spawned_servers


def test_phase7_media_attachments_endpoint_and_loop_tools(tmp_path, monkeypatch):
    import hinaa_api.routers.loop_router as loop_router_mod
    from hinaa_api.harness.loop_engine import LoopEngine

    engine = LoopEngine(base_dir=tmp_path / "loop_state")
    monkeypatch.setattr(loop_router_mod, "_loop_engine", engine)

    img_buf = io.BytesIO()
    Image.new("RGB", (64, 48), color=(30, 120, 210)).save(img_buf, format="PNG")
    png_bytes = img_buf.getvalue()

    app = create_app(get_settings())
    with TestClient(app) as client:
        up1 = client.post(
            "/api/loop/loop_media1/attachments",
            files={"file": ("mockup.png", png_bytes, "image/png")},
        )
        assert up1.status_code == 200
        media = up1.json()["media"]
        assert media["width"] == 64 and media["height"] == 48
        assert "stored_path" not in media

        # Duplicate binary upload dedupes cleanly to the same media_id
        up2 = client.post(
            "/api/loop/loop_media1/attachments",
            files={"file": ("mockup_copy.png", png_bytes, "image/png")},
        )
        assert up2.status_code == 200
        assert up2.json()["media"]["media_id"] == media["media_id"]

        listed = client.get("/api/loop/loop_media1/attachments")
        assert listed.status_code == 200
        assert len(listed.json()["attachments"]) == 1

        # Invalid task_id blocked
        assert client.get("/api/loop/bad..id/attachments").status_code == 400

    # Tool inspection reads derived metadata into agent context
    calls: list[dict] = []
    replies = [
        json.dumps(
            {
                "thought": "inspect attached media",
                "actions": [
                    {"type": "list_media"},
                    {"type": "describe_media", "media_id": media["media_id"]},
                ],
            }
        )
    ]
    step = LLMAgentStep(
        provider=_provider(),
        workspace_dir=tmp_path,
        trace_path=engine.base_dir / "loop_media1_trace.jsonl",
        state_dir=engine.base_dir,
        client=httpx.AsyncClient(
            transport=httpx.MockTransport(
                lambda r: (
                    calls.append(json.loads(r.content.decode("utf-8"))),
                    httpx.Response(
                        200,
                        json={"choices": [{"message": {"role": "assistant", "content": replies[0]}}], "usage": {"prompt_tokens": 10, "completion_tokens": 10}},
                    ),
                )[1]
            )
        ),
    )
    res = asyncio.run(step.run(_spec(tmp_path, "loop_media1"), 1, None))
    assert all(o.status == "applied" for o in res.outcomes)
    assert media["media_id"] in res.outcomes[0].detail
    assert '"width": 64' in res.outcomes[1].detail


def test_phase8_prompt_budgeter_digest_document_vision_and_provenance(tmp_path):
    # 1. Middle-out compaction
    huge_mid = "M" * 60_000
    parts = ["Goal: TOP_ANCHOR", "Constraint: STAY", huge_mid, "Failure: TAIL_ANCHOR", "Obs: LAST"]
    compacted = LLMAgentStep._budget_prompt(parts, max_chars=4_000)
    assert len(compacted) <= 4_000
    assert "TOP_ANCHOR" in compacted
    assert "TAIL_ANCHOR" in compacted
    assert "truncated middle" in compacted

    # 2. digest_document scans huge workspace file cleanly
    big_doc = tmp_path / "manual.md"
    lines = ["# Overview\nIntro text\n"] + [f"Line {i} standard\n" for i in range(500)] + ["## Auth Setup\nUse OAuth2 token refresh cleanly\n"]
    big_doc.write_text("".join(lines), encoding="utf-8")

    calls: list[dict] = []
    # Also test vision attachment gets attached to OpenAI chat/completions call
    snap = tmp_path / "snap.png"
    Image.new("RGB", (20, 20), color=(255, 0, 0)).save(snap, format="PNG")
    reply = json.dumps(
        {"thought": "digest manual", "actions": [{"type": "digest_document", "path": "manual.md", "query": "oauth2", "max_chunks": 3}]}
    )
    step = _step_for(tmp_path, [reply], calls)
    step._pending_vision_images.append(snap)
    res = asyncio.run(step.run(_spec(tmp_path, "loop_p8"), 1, None))
    assert res.outcomes[0].status == "applied"
    assert "OAuth2" in res.outcomes[0].detail
    user_content = calls[0]["messages"][1]["content"]
    assert isinstance(user_content, list)
    assert any(part.get("type") == "image_url" for part in user_content)
    assert step._pending_vision_images == []

    # 3. ResponseDocument provenance gate
    doc = ResponseDocument(
        response_id="resp_1",
        blocks=[
            MetricGridBlock(id="m1", items=[MetricItem(label="Latency", value=42, source_ref="src_real")]),
            ChartBlock(id="c1", title="Latency", dataset_ref="ds_real", points=[{"x": 1, "y": 2}]),
            ImageGalleryBlock(id="g1", asset_refs=["med_fake"]),
        ],
    )
    errs = doc.validate_provenance(verified_assets={"med_real"}, verified_datasets={"ds_real"}, verified_sources={"src_real"})
    assert errs == ["unverified gallery asset_ref: 'med_fake'"]


def test_phase9_human_approval_gate_diff_review_and_resume(tmp_path, monkeypatch):
    import hinaa_api.routers.loop_router as loop_router_mod
    from hinaa_api.harness.loop_engine import LoopEngine

    calls: list[dict] = []
    write_reply = json.dumps(
        {
            "thought": "write file with human gate",
            "actions": [{"type": "write_file", "path": "ok.txt", "content": "approved!\n", "confirm": True}],
        }
    )
    review_reply = json.dumps(
        {"approved": True, "severity": "none", "findings": [], "summary": "Diff looks clean."}
    )
    step = _step_for(tmp_path, [write_reply, review_reply], calls, require_human_approval=True)
    spec = _spec(tmp_path, "loop_appr_1")

    async def _drive_approval():
        run_coro = asyncio.create_task(step.run(spec, 1, None))
        # Wait briefly for approval_required event to publish its server-computed approval_id
        approval_id = None
        for _ in range(40):
            for ev in EVENT_BUS.history("loop_appr_1"):
                if ev["event_type"] == "approval_required":
                    approval_id = ev["data"]["approval_id"]
                    break
            if approval_id:
                break
            await asyncio.sleep(0.05)
        assert approval_id and approval_id.startswith("appr_")
        assert resolve_approval("loop_appr_1", approval_id, True) is True
        return await run_coro

    result = asyncio.run(_drive_approval())
    assert result.actions_applied == 1
    assert (tmp_path / "ok.txt").read_text(encoding="utf-8") == "approved!\n"

    # Fresh-context diff review
    verdict = asyncio.run(step.run_diff_review(spec))
    assert verdict["approved"] is True
    assert any(ev["event_type"] == "turn_reviewed" for ev in EVENT_BUS.history("loop_appr_1"))

    # HTTP /approve rejects unknown approval_id cleanly (409) & /resume restarts from persisted spec
    engine = LoopEngine(base_dir=tmp_path / "loop_state2")
    monkeypatch.setattr(loop_router_mod, "_loop_engine", engine)
    monkeypatch.setattr(loop_router_mod, "_task_reports", {})
    app = create_app(get_settings())
    with TestClient(app) as client:
        assert client.post("/api/loop/loop_unknown/approve", json={"approval_id": "appr_fake", "approved": True}).status_code == 409
        started = client.post(
            "/api/loop/start",
            json={
                "goal_title": "Pause and resume test",
                "verification_command": [sys.executable, "-c", "import time; time.sleep(0.8)"],
                "max_turns": 2,
                "workspace_dir": str(tmp_path),
            },
        )
        tid = started.json()["task_id"]
        client.post(f"/api/loop/pause/{tid}")
        time.sleep(0.1)
        resumed = client.post(f"/api/loop/resume/{tid}", json={"max_turns": 1})
        assert resumed.status_code == 200
        assert resumed.json()["task_id"] == tid
        client.post(f"/api/loop/stop/{tid}")


def test_phase10_ssrf_allowlist_and_secret_scrubbing(tmp_path, monkeypatch):
    calls: list[dict] = []
    fake_secret = "sk-proj-AAAABBBBCCCCDDDDEEEEFFFF11112222"
    actions = [
        {"type": "fetch_url", "url": "http://169.254.169.254/latest/meta-data/"},
        {"type": "fetch_url", "url": "http://127.0.0.1:8000/internal"},
        {"type": "fetch_url", "url": "http://10.0.0.5/secret"},
        {"type": "fetch_url", "url": "http://localhost/admin"},
    ]
    reply = json.dumps({"thought": f"Using Bearer secret_tok_{fake_secret} to debug", "actions": actions})
    step = _step_for(tmp_path, [reply], calls)
    res = asyncio.run(step.run(_spec(tmp_path, "loop_sec"), 1, None))
    assert len(res.outcomes) == 4
    for outcome in res.outcomes:
        assert outcome.status == "blocked"
        assert "ssrf blocked" in outcome.detail

    # Trace file & SSE stream must NOT contain raw key
    trace_raw = (tmp_path / "state" / "t_trace.jsonl").read_text(encoding="utf-8")
    assert fake_secret not in trace_raw
    assert "[REDACTED]" in trace_raw

    # Egress allowlist rejects external domain outside allowlist
    monkeypatch.setenv("HINAA_LOOP_EGRESS_ALLOWLIST", "docs.python.org")
    reply2 = json.dumps({"thought": "fetch disallowed", "actions": [{"type": "fetch_url", "url": "https://example.org/data"}]})
    step2 = _step_for(tmp_path, [reply2], calls)
    res2 = asyncio.run(step2.run(_spec(tmp_path, "loop_egress"), 1, None))
    assert res2.outcomes[0].status == "blocked"
    assert "HINAA_LOOP_EGRESS_ALLOWLIST" in res2.outcomes[0].detail
