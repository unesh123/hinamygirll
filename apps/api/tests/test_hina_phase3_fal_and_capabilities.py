"""Phase 3: real video via fal.ai, capability-registry truth, frontier brain.

The three gaps the user asked to close:
1. Video: Hina could never return a real MP4 (stub failed closed, Veo
   adapter faked a 24-byte header). The fal.ai provider must submit, poll,
   and download a real MP4 — and fail honestly without a key.
2. Capability truth: build_capability_registry existed but nothing in the
   chat path ever called it, so the prompt claimed the full catalogue. The
   self-state layer must now read from the registry.
3. Frontier brain: HINAA_PRIMARY_BRAIN must select a frontier provider when
   its key is configured, and visibly stay on the pinned Qwen gateway when
   it is not — never a silent downgrade.
"""
from __future__ import annotations

import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError

FAKE_MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 2048
ENDPOINT = "fal-ai/kling-video/v3/pro/text-to-video"


def _settings(**overrides):
    base = dict(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        _env_file=None,
    )
    base.update(overrides)
    return Settings(**base)


def _job(prompt: str = "a girl walking in a park at sunset"):
    from hinaa_api.creative.models import (
        CreativeJobRecord,
        CreativeJobSpec,
        CreativeOperation,
    )

    return CreativeJobRecord(
        job_id="job-1",
        tenant_id="t1",
        user_id="u1",
        trace_id="trace-1",
        spec=CreativeJobSpec(
            operation=CreativeOperation.TEXT_TO_VIDEO,
            prompt=prompt,
            duration_seconds=5,
            aspect_ratio="9:16",
        ),
        provider="fal_video",
        created_at="2026-11-13T00:00:00Z",
        updated_at="2026-11-13T00:00:00Z",
    )


def _fal_handler(calls: dict, *, fail_status: bool = False, bad_video: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if request.method == "POST" and "queue.fal.run" in url:
            assert request.headers["Authorization"] == "Key test-fal-key"
            return httpx.Response(
                200,
                json={
                    "request_id": "req-1",
                    "status_url": "https://queue.fal.run/x/requests/req-1/status",
                    "response_url": "https://queue.fal.run/x/requests/req-1",
                    "cancel_url": "https://queue.fal.run/x/requests/req-1/cancel",
                },
            )
        if "status" in url:
            calls["status"] = calls.get("status", 0) + 1
            if fail_status and calls["status"] >= 1:
                return httpx.Response(200, json={"status": "FAILED"})
            if calls["status"] == 1:
                return httpx.Response(200, json={"status": "IN_PROGRESS"})
            return httpx.Response(200, json={"status": "COMPLETED"})
        if "requests/req-1" in url:
            return httpx.Response(
                200,
                json={"video": {"url": "https://storage.example/output.mp4", "content_type": "video/mp4"}},
            )
        if "storage.example" in url:
            return httpx.Response(200, content=b"not a video at all" if bad_video else FAKE_MP4)
        raise AssertionError(f"unexpected request: {request.method} {url}")

    return handler


async def _run(provider, job):
    return await provider.execute_job(job)


def test_fal_provider_returns_a_real_mp4() -> None:
    from hinaa_api.creative.providers.fal_video_provider import FalVideoProvider

    calls: dict = {}
    provider = FalVideoProvider(
        api_key="test-fal-key",
        endpoint=ENDPOINT,
        transport=httpx.MockTransport(_fal_handler(calls)),
        poll_interval_seconds=0.001,
    )
    assert provider.is_available()
    out = __import__("asyncio").run(_run(provider, _job()))
    assert out == FAKE_MP4
    assert calls["status"] >= 2  # polled at least once while in progress


def test_fal_provider_fails_closed_without_a_key() -> None:
    from hinaa_api.creative.providers.fal_video_provider import FalVideoProvider

    provider = FalVideoProvider(api_key="", endpoint=ENDPOINT)
    assert not provider.is_available()
    with pytest.raises(HinaaError) as excinfo:
        __import__("asyncio").run(_run(provider, _job()))
    assert excinfo.value.code == "VIDEO_PROVIDER_NOT_CONFIGURED"


def test_fal_provider_rejects_a_failed_job() -> None:
    from hinaa_api.creative.providers.fal_video_provider import FalVideoProvider

    calls: dict = {}
    provider = FalVideoProvider(
        api_key="test-fal-key",
        endpoint=ENDPOINT,
        transport=httpx.MockTransport(_fal_handler(calls, fail_status=True)),
        poll_interval_seconds=0.001,
    )
    with pytest.raises(HinaaError) as excinfo:
        __import__("asyncio").run(_run(provider, _job()))
    assert excinfo.value.code == "FAL_JOB_FAILED"


def test_fal_provider_refuses_non_mp4_bytes() -> None:
    from hinaa_api.creative.providers.fal_video_provider import FalVideoProvider

    calls: dict = {}
    provider = FalVideoProvider(
        api_key="test-fal-key",
        endpoint=ENDPOINT,
        transport=httpx.MockTransport(_fal_handler(calls, bad_video=True)),
        poll_interval_seconds=0.001,
    )
    with pytest.raises(HinaaError) as excinfo:
        __import__("asyncio").run(_run(provider, _job()))
    assert excinfo.value.code == "FAL_BAD_VIDEO"


def test_fal_provider_rejects_a_veo31_endpoint() -> None:
    """Veo 3.1 dies on fal on 17 Nov 2026 — the default must never be it."""
    from hinaa_api.config import Settings as _S

    settings = _settings()
    assert "veo3.1" not in settings.fal_video_endpoint
    assert settings.fal_video_endpoint == ENDPOINT


def test_primary_brain_stays_on_qwen_without_a_key() -> None:
    settings = _settings(HINAA_PRIMARY_BRAIN="claude")
    mode, reason = settings.resolve_primary_brain()
    assert mode == "xkiro"
    assert "not configured" in reason
    assert "Qwen" in reason


def test_primary_brain_uses_a_configured_frontier_key() -> None:
    settings = _settings(
        HINAA_PRIMARY_BRAIN="claude",
        HINAA_CLAUDE_API_KEY="sk-ant-test-key",
    )
    mode, reason = settings.resolve_primary_brain()
    assert mode == "claude"
    assert "key configured" in reason


def test_registry_reports_the_brain_choice_and_video_status() -> None:
    from hinaa_api.capabilities import build_capability_registry, video_provider_status

    plain = _settings()
    registry = build_capability_registry(plain)
    assert "not configured" in video_provider_status(plain)
    assert registry.primary_brain_reason == ""

    asked = _settings(HINAA_PRIMARY_BRAIN="claude")
    registry2 = build_capability_registry(asked)
    assert "staying on the pinned Qwen" in registry2.primary_brain_reason
    assert registry2.default_brain == "qwen/qwen3.8-max:free"


def test_self_state_layer_tells_the_truth(monkeypatch) -> None:
    from hinaa_api.prompts.assembly import _self_state_layer

    settings = _settings()
    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: settings)
    out = _self_state_layer(voice=True)
    assert "fully equipped with advanced capabilities" not in out
    assert "autonomous browser execution" not in out
    assert "Video generation: not configured" in out
    assert "No tools are available on this turn" in out
    assert "Never claim browser execution" in out
