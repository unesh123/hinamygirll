"""Tests for TokenRouter gateway, dynamic model discovery, verify_matrix, motion presets, and audio beats."""
from __future__ import annotations

import io
import json
import math
import wave
from unittest.mock import AsyncMock

import httpx
import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from pydantic import SecretStr

from hinaa_api.agent.agentic_runner import AgenticLoopRunner
from hinaa_api.capabilities import build_capability_registry
from hinaa_api.config import Settings
from hinaa_api.creative.audio_beats import detect_beats_wav
from hinaa_api.creative.motion_presets import PRESET_NAMES, apply_preset, apply_preset_sequence
from hinaa_api.errors import HinaaError
from hinaa_api.evaluation.verify_matrix import get_matrix_status, record_check, reset_matrix
from hinaa_api.main import create_app
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.reachability import GatewayModelsOutcome, probe_gateway_models, reset_models_cache
from hinaa_api.services import ProviderRouter


def test_tokenrouter_settings_and_router_enforcement():
    cfg = Settings(
        tokenrouter_api_key=SecretStr("sk-tokenrouter-test-12345"),
        tokenrouter_base_url="https://api.tokenrouter.com/v1",
        tokenrouter_model="deepseek/deepseek-chat",
        tokenrouter_allowed_models_raw="deepseek/deepseek-chat,deepseek/deepseek-reasoner",
        primary_brain="tokenrouter",
        _env_file=None,
    )
    assert cfg.tokenrouter_configured is True
    assert cfg.active_tokenrouter_base_url == "https://api.tokenrouter.com/v1"
    assert cfg.active_tokenrouter_model == "deepseek/deepseek-chat"
    assert cfg.resolve_tokenrouter_model("deepseek/deepseek-reasoner") == "deepseek/deepseek-reasoner"

    mode, reason = cfg.resolve_primary_brain()
    assert mode == "tokenrouter"
    assert "selected" in reason

    router = ProviderRouter(cfg)
    provider = router.llm("tokenrouter")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.id == "tokenrouter"
    assert provider.model == "deepseek/deepseek-chat"

    with pytest.raises(HinaaError) as exc:
        router.llm("tokenrouter", brain_model="blocked-model")
    assert exc.value.code == "PROVIDER_MODEL_NOT_ALLOWED"
    assert exc.value.status_code == 422


def test_tokenrouter_capabilities_and_dynamic_models(monkeypatch):
    monkeypatch.setattr(
        "hinaa_api.main.probe_gateway_models",
        AsyncMock(
            return_value=GatewayModelsOutcome(
                True,
                3,
                "ok",
                "Catalog serving 3 models.",
                model_ids=("deepseek/deepseek-chat", "deepseek/deepseek-reasoner", "anthropic/claude-opus-4.5"),
            )
        ),
    )
    settings = Settings(
        environment="development",
        auth_mode="dev",
        toptools_api_key=SecretStr("sk-toptools-test-12345"),
        toptools_base_url="https://top-tools-ai.com/api/v1",
        tokenrouter_api_key=SecretStr("sk-tokenrouter-test-12345"),
        tokenrouter_base_url="https://api.tokenrouter.com/v1",
        tokenrouter_model="deepseek/deepseek-chat",
        tokenrouter_allowed_models_raw="deepseek/deepseek-chat,deepseek/deepseek-reasoner,*",
        visible_providers_raw="toptools,tokenrouter,local",
        primary_brain="tokenrouter",
        _env_file=None,
    )
    reg = build_capability_registry(settings)
    assert reg.default_brain == "deepseek/deepseek-chat"
    tr_models = {m.id: m for m in reg.models if m.provider == "tokenrouter"}
    assert "deepseek/deepseek-chat" in tr_models
    assert tr_models["deepseek/deepseek-chat"].vision is False

    with TestClient(create_app(settings)) as client:
        caps = client.get("/api/v1/capabilities").json()
        pmap = {p["id"]: p for p in caps["providers"]}
        assert "tokenrouter" in pmap
        assert pmap["tokenrouter"]["name"] == "TokenRouter"
        model_ids = {m["id"] for m in caps["models"] if m["provider"] == "tokenrouter"}
        assert "anthropic/claude-opus-4.5" in model_ids

        prov_map = {p["id"]: p for p in client.get("/api/v1/providers").json()}
        assert "tokenrouter" in prov_map
        assert prov_map["tokenrouter"]["state"] == "healthy"
        assert "model:anthropic/claude-opus-4.5" in prov_map["tokenrouter"]["capabilities"]


async def test_probe_gateway_models_surfaces_ip_not_allowed_403(monkeypatch):
    reset_models_cache()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            return httpx.Response(
                403,
                content=json.dumps({"error": {"code": "IP_NOT_ALLOWED", "message": "Forbidden."}}).encode(),
                request=httpx.Request("GET", url),
            )

    monkeypatch.setattr(httpx, "AsyncClient", _FakeClient)
    outcome = await probe_gateway_models("https://api.tokenrouter.com/v1", api_key="sk-test", use_cache=False)
    assert outcome.serving is False
    assert outcome.reason == "http_403"
    assert "IP_NOT_ALLOWED" in outcome.detail


def test_verify_matrix_persistence_roundtrip(tmp_path):
    matrix_path = tmp_path / "verify_matrix.json"
    record_check("frontend/sora", "tsc", True, "0 errors", path=matrix_path)
    record_check("frontend/sora", "mobile_390x844", False, "Overflow on header", path=matrix_path)
    status = get_matrix_status(path=matrix_path)
    assert status["total"] == 2
    assert status["passed"] == 1
    assert status["failed"] == 1
    assert status["allPassed"] is False
    assert status["failedChecks"] == ["frontend/sora:mobile_390x844"]

    record_check("frontend/sora", "mobile_390x844", True, "Fixed overflow", path=matrix_path)
    status_after = get_matrix_status(path=matrix_path)
    assert status_after["allPassed"] is True
    reset_matrix(path=matrix_path)
    assert not matrix_path.exists()


def test_motion_presets_modify_pixels_deterministically():
    from PIL import ImageDraw

    base = Image.new("RGB", (96, 64), (24, 28, 48))
    draw = ImageDraw.Draw(base)
    draw.rectangle([18, 12, 78, 52], fill=(80, 140, 220), outline=(240, 240, 255), width=2)
    draw.ellipse([36, 20, 60, 44], fill=(220, 70, 130))
    base_arr = np.asarray(base)
    for preset in PRESET_NAMES:
        out = apply_preset(base, preset, progress=0.5, intensity=1.0)
        assert out.size == base.size
        assert not np.array_equal(np.asarray(out), base_arr), preset
    seq = apply_preset_sequence([base, base.copy(), base.copy()], "orbit")
    assert len(seq) == 3


def test_audio_beats_detects_synthetic_120_bpm_clicks():
    sr = 22050
    dur = 4.0
    n = int(sr * dur)
    samples = np.zeros(n, dtype=np.float32)
    # 120 BPM = 0.5s beat interval
    for beat_sec in (0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5):
        idx = int(beat_sec * sr)
        t = np.arange(800, dtype=np.float32) / sr
        samples[idx : idx + 800] = np.sin(2.0 * math.pi * 880.0 * t) * np.exp(-t * 35.0) * 0.9

    pcm = np.clip(samples * 32767.0, -32768, 32767).astype("<i2")
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())

    result = detect_beats_wav(buf.getvalue())
    assert 116.0 <= result["bpm"] <= 124.0
    assert len(result["beat_times_sec"]) >= 5


async def test_agentic_runner_marks_verified_on_disk(tmp_path):
    real_file = tmp_path / "real.txt"
    real_file.write_text("hello", encoding="utf-8")

    calls = 0

    async def _planner(transcript, step, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return json.dumps({
                "action": "call_tool",
                "tool": "workspace_read_file",
                "arguments": {"file_path": "real.txt"},
            })
        return json.dumps({"action": "final", "summary": "Done"})

    runner = AgenticLoopRunner(workspace_root=str(tmp_path), max_steps=4)
    fake_artifacts = [
        {"kind": "diff", "filePath": "real.txt", "tool": "workspace_write_file"},
        {"kind": "diff", "filePath": "phantom.txt", "tool": "workspace_write_file"},
    ]
    runner._verify_artifacts_on_disk(fake_artifacts)
    assert fake_artifacts[0]["verifiedOnDisk"] is True
    assert fake_artifacts[1]["verifiedOnDisk"] is False
    res = await runner.run(goal="read real.txt", planner=_planner)
    assert res.status == "completed"


@pytest.mark.asyncio
async def test_workspace_read_file_resolves_hina_refs_and_cancel_route(tmp_path):
    from hinaa_api.agent.agentic_runner import AgenticRunResult
    from hinaa_api.agent.live_agentic_service import AgenticRunStore, PersistedAgenticRun, _persist_attached_reference_files
    from hinaa_api.tools.workspace_coding_tools import WorkspaceReadFileParams, workspace_read_file_handler

    notes = _persist_attached_reference_files(
        str(tmp_path),
        "run-ref-test",
        [{"filename": "sora_spec.md", "kind": "text", "mimeType": "text/markdown", "textExcerpt": "# SORA Hub\nNeon obsidian"}],
    )
    assert "sora_spec.md" in notes
    assert "Neon obsidian" in notes

    read_res = await workspace_read_file_handler(
        WorkspaceReadFileParams(file_path="sora_spec.md", workspace_root=str(tmp_path))
    )
    assert read_res["status"] == "success"
    assert "Neon obsidian" in read_res["content"]

    # /api/v1/agent/runs/{run_id}/cancel should delegate cleanly to awaiting_approval agentic runs
    store = AgenticRunStore(tmp_path / "runs")
    store.save(
        PersistedAgenticRun(
            run_id="run-cancel-test",
            goal="test cancel",
            result=AgenticRunResult(run_id="run-cancel-test", status="awaiting_approval", summary="Wait"),
        )
    )
    settings = Settings(environment="development", auth_mode="dev", _env_file=None)
    import os

    prev = os.environ.get("HINAA_AGENTIC_RUNS_DIR")
    os.environ["HINAA_AGENTIC_RUNS_DIR"] = str(tmp_path / "runs")
    try:
        from hinaa_api.agent import live_agentic_service

        live_agentic_service._STORE_SINGLETON = None
        with TestClient(create_app(settings)) as client:
            resp = client.post("/api/v1/agent/runs/run-cancel-test/cancel")
            assert resp.status_code == 200
            assert resp.json()["status"] == "cancelled"
    finally:
        live_agentic_service._STORE_SINGLETON = None
        if prev is None:
            os.environ.pop("HINAA_AGENTIC_RUNS_DIR", None)
        else:
            os.environ["HINAA_AGENTIC_RUNS_DIR"] = prev
