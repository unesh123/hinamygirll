"""Phase 4: the $0 video route — Hugging Face Inference Providers.

The user has no money for fal.ai. Verified 2026-11-13: no major video API
offers a free tier (Gemini API Veo, fal.ai, Kling, Runway all bill from the
first call; Sora's API was discontinued 2026-09-24). The one real $0 route
is Hugging Face: a free personal token plus a small monthly Inference
Provider credit pool. This suite proves the free provider returns a real
MP4, fails honestly without a token, refuses non-MP4 bytes, and that the
provider priority is fal.ai (paid) > HF (free) > fail-closed stub.
"""
from __future__ import annotations

import asyncio

import pytest

from hinaa_api.errors import HinaaError

FAKE_MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 2048


def _settings(**overrides):
    from hinaa_api.config import Settings

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
        provider="hf_video",
        created_at="2026-11-13T00:00:00Z",
        updated_at="2026-11-13T00:00:00Z",
    )


class _FakeHfClient:
    def __init__(self, *, result=FAKE_MP4, calls=None):
        self._result = result
        self.calls = calls if calls is not None else {}

    def text_to_video(self, prompt, **kwargs):
        self.calls["prompt"] = prompt
        self.calls["model"] = kwargs.get("model")
        return self._result


def test_hf_provider_returns_a_real_mp4() -> None:
    from hinaa_api.creative.providers.hf_video_provider import HfVideoProvider

    calls: dict = {}
    provider = HfVideoProvider(
        api_key="hf_test_token",
        client_factory=lambda: _FakeHfClient(calls=calls),
    )
    assert provider.is_available()
    out = asyncio.run(provider.execute_job(_job()))
    assert out == FAKE_MP4
    assert calls["prompt"] == "a girl walking in a park at sunset"
    assert calls["model"] == "Wan-AI/Wan2.2-TI2V-5B"


def test_hf_provider_fails_closed_without_a_token() -> None:
    from hinaa_api.creative.providers.hf_video_provider import HfVideoProvider

    provider = HfVideoProvider(api_key="")
    assert not provider.is_available()
    with pytest.raises(HinaaError) as excinfo:
        asyncio.run(provider.execute_job(_job()))
    assert excinfo.value.code == "VIDEO_PROVIDER_NOT_CONFIGURED"


def test_hf_provider_refuses_non_mp4_bytes() -> None:
    from hinaa_api.creative.providers.hf_video_provider import HfVideoProvider

    provider = HfVideoProvider(
        api_key="hf_test_token",
        client_factory=lambda: _FakeHfClient(result=b"not a video at all"),
    )
    with pytest.raises(HinaaError) as excinfo:
        asyncio.run(provider.execute_job(_job()))
    assert excinfo.value.code == "HF_BAD_VIDEO"


def test_hf_provider_surfaces_upstream_failures() -> None:
    from hinaa_api.creative.providers.hf_video_provider import HfVideoProvider

    class _Boom:
        def text_to_video(self, *args, **kwargs):
            raise RuntimeError("429 rate limited: free pool exhausted")

    provider = HfVideoProvider(
        api_key="hf_test_token", client_factory=lambda: _Boom()
    )
    with pytest.raises(HinaaError) as excinfo:
        asyncio.run(provider.execute_job(_job()))
    assert excinfo.value.code == "HF_VIDEO_FAILED"


def test_provider_priority_fal_then_hf_then_stub(monkeypatch) -> None:
    from hinaa_api.creative.providers.fal_video_provider import get_video_provider

    # Neither key: the fail-closed stub.
    monkeypatch.setattr(
        "hinaa_api.config.get_settings", lambda: _settings()
    )
    assert get_video_provider().provider_id == "generative_video_neural"

    # Free HF token only: the free provider.
    monkeypatch.setattr(
        "hinaa_api.config.get_settings",
        lambda: _settings(HF_TOKEN="hf_test_token"),
    )
    assert get_video_provider().provider_id == "hf_video"

    # Paid fal key also set: fal wins.
    monkeypatch.setattr(
        "hinaa_api.config.get_settings",
        lambda: _settings(HF_TOKEN="hf_test_token", FAL_KEY="fal_test_key"),
    )
    assert get_video_provider().provider_id == "fal_video"


def test_video_status_names_the_free_route() -> None:
    from hinaa_api.capabilities import video_provider_status

    assert "HF_TOKEN" in video_provider_status(_settings())
    assert "Hugging Face" in video_provider_status(_settings(HF_TOKEN="hf_x"))
    assert "fal.ai" in video_provider_status(_settings(FAL_KEY="fal_x"))
