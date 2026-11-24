"""Phase 5: video by code — the user's correction, 2026-11-13.

Hina must NOT need a generative video model (fal.ai / Veo / Kling) to make
a video. The frontier model writes the video as code — a timeline of
scenes, text, timing and transitions — and local ffmpeg renders it into a
real MP4. No key, no credits. These tests render REAL videos with the
local ffmpeg and verify them with ffprobe: duration, resolution, codec,
real bytes. No fake headers, no placeholder frames.
"""
from __future__ import annotations

import asyncio
import io
import json
import shutil
import subprocess

import pytest
from PIL import Image

from hinaa_api.errors import HinaaError

pytestmark = pytest.mark.skipif(
    not shutil.which("ffmpeg") or not shutil.which("ffprobe"),
    reason="ffmpeg/ffprobe required for code video tests",
)

FAKE_MP4 = b"\x00\x00\x00\x18ftypisom" + b"\x00" * 2048


def _job(operation, timeline=None, prompt="test video"):
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
            operation=operation,
            prompt=prompt,
            duration_seconds=4,
            aspect_ratio="9:16",
            timeline_json=timeline,
        ),
        provider="code_video",
        created_at="2026-11-13T00:00:00Z",
        updated_at="2026-11-13T00:00:00Z",
    )


def _two_scene_timeline():
    return {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "scenes": [
            {
                "duration": 2.0,
                "background": "black",
                "texts": [
                    {"text": "Sometimes you gotta run", "start": 0.3, "end": 1.8,
                     "size": 72, "color": "white"}
                ],
                "transition": "cut",
            },
            {
                "duration": 2.0,
                "background": "#111827",
                "texts": [
                    {"text": "Before you can walk", "start": 0.3, "end": 1.8,
                     "size": 72, "color": "yellow"}
                ],
                "transition": "crossfade",
            },
        ],
    }


def _probe_bytes(data: bytes) -> dict:
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        f.write(data)
        path = Path(f.name)
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0",
         "-show_entries", "stream=codec_name,width,height",
         "-show_entries", "format=duration", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    info = json.loads(out.stdout or "{}")
    path.unlink()
    return info


def test_code_video_renders_a_real_mp4() -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    provider = CodeVideoProvider()
    assert provider.is_available()
    out = asyncio.run(provider.execute_job(_job(CreativeOperation.TIMELINE_EXPORT, _two_scene_timeline())))
    assert len(out) > 10_000, "rendered video is suspiciously small"
    assert b"ftyp" in out[:32]
    info = _probe_bytes(out)
    stream = info["streams"][0]
    assert stream["codec_name"] == "h264"
    assert stream["width"] == 1080 and stream["height"] == 1920
    assert abs(float(info["format"]["duration"]) - 4.0) < 0.6


def test_code_video_renders_image_background_with_motion() -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    import tempfile
    from pathlib import Path

    img = Image.new("RGB", (1080, 1920), color=(180, 30, 30))
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img.save(f, format="PNG")
        img_path = f.name
    try:
        timeline = {
            "width": 1080, "height": 1920, "fps": 30,
            "scenes": [
                {"duration": 2.0, "background": img_path,
                 "texts": [{"text": "Iron Man", "start": 0.2, "end": 1.8, "size": 96}],
                 "transition": "cut"},
            ],
        }
        out = asyncio.run(
            CodeVideoProvider().execute_job(_job(CreativeOperation.TEXT_TO_VIDEO, timeline))
        )
        assert len(out) > 10_000
        info = _probe_bytes(out)
        assert info["streams"][0]["width"] == 1080
        assert abs(float(info["format"]["duration"]) - 2.0) < 0.6
    finally:
        Path(img_path).unlink()


def test_code_video_rejects_invalid_timelines() -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    provider = CodeVideoProvider()
    for bad in (
        {},  # no timeline at all
        {"width": 1080, "height": 1920, "fps": 30, "scenes": []},  # no scenes
        {"width": 1080, "height": 1920, "fps": 30,
         "scenes": [{"duration": 61.0, "background": "black"}]},  # too long
        {"width": 1080, "height": 1920, "fps": 30,
         "scenes": [{"duration": 2.0, "background": "black",
                     "texts": [{"text": "  "}]}]},  # empty text
    ):
        with pytest.raises(HinaaError):
            asyncio.run(provider.execute_job(_job(CreativeOperation.TIMELINE_EXPORT, bad or None)))


def test_code_video_rejects_missing_background_image() -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    timeline = {
        "width": 1080, "height": 1920, "fps": 30,
        "scenes": [{"duration": 2.0, "background": "/no/such/image.png", "transition": "cut"}],
    }
    with pytest.raises(HinaaError) as excinfo:
        asyncio.run(CodeVideoProvider().execute_job(_job(CreativeOperation.TIMELINE_EXPORT, timeline)))
    assert excinfo.value.code == "CODE_VIDEO_BAD_BACKGROUND"


def test_timeline_job_routes_to_code_provider(monkeypatch) -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.fal_video_provider import get_video_provider

    def _settings(**overrides):
        from hinaa_api.config import Settings

        base = dict(
            HINAA_PROVIDER_MODE="mock",
            AZURE_SPEECH_KEY="", AZURE_SPEECH_REGION="", GEMINI_API_KEY="",
            _env_file=None,
        )
        base.update(overrides)
        return Settings(**base)

    monkeypatch.setattr("hinaa_api.config.get_settings", lambda: _settings())
    # A job WITH a timeline goes to code, even with no keys at all.
    assert get_video_provider(_job(CreativeOperation.TEXT_TO_VIDEO, _two_scene_timeline())).provider_id == "code_video"
    # A job WITHOUT a timeline falls through to the generative chain (stub here).
    assert get_video_provider(_job(CreativeOperation.TEXT_TO_VIDEO, None)).provider_id == "generative_video_neural"


def test_deterministic_renderer_fails_honestly_on_bad_ffmpeg() -> None:
    from hinaa_api.media.timeline_spec import DeterministicVideoRenderer, TimelineSpec

    renderer = DeterministicVideoRenderer()
    renderer.ffmpeg = "/nonexistent/ffmpeg"
    job = asyncio.run(renderer.render_timeline(TimelineSpec(), "testkey123456"))
    assert job.status == "failed"
    assert job.error
    # No fake 24-byte MP4 header was written as a success.
    assert not (renderer.output_root / job.id / "master.mp4").exists()
