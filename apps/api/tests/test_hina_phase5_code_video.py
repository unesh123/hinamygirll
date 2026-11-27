"""Phase 5: video by code — FFmpeg timeline rendering with ffprobe QC verification."""
from __future__ import annotations

import asyncio
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


def test_code_video_renders_image_background_with_motion(tmp_path) -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    bg = tmp_path / "poster.png"
    Image.new("RGB", (640, 640), color=(28, 64, 128)).save(bg)
    timeline = {
        "width": 720,
        "height": 720,
        "fps": 24,
        "scenes": [
            {
                "duration": 1.5,
                "background": str(bg),
                "texts": [{"text": "Code Motion", "start": 0.1, "end": 1.4, "size": 48}],
                "transition": "cut",
            }
        ],
    }
    provider = CodeVideoProvider()
    out = asyncio.run(provider.execute_job(_job(CreativeOperation.TIMELINE_EXPORT, timeline)))
    info = _probe_bytes(out)
    assert info["streams"][0]["codec_name"] == "h264"
    assert info["streams"][0]["width"] == 720


def test_code_video_blocks_path_escape(tmp_path) -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.code_video_provider import CodeVideoProvider

    outside = tmp_path.anchor + "nonexistent_outside_root/secret.png"
    timeline = {
        "width": 320,
        "height": 320,
        "fps": 12,
        "scenes": [{"duration": 1.0, "background": outside}],
    }
    with pytest.raises(HinaaError) as exc:
        asyncio.run(CodeVideoProvider().execute_job(_job(CreativeOperation.TIMELINE_EXPORT, timeline)))
    assert exc.value.code == "CODE_VIDEO_BAD_BACKGROUND"


def test_get_video_provider_prefers_code_for_timeline() -> None:
    from hinaa_api.creative.models import CreativeOperation
    from hinaa_api.creative.providers.fal_video_provider import get_video_provider

    job = _job(CreativeOperation.TEXT_TO_VIDEO, _two_scene_timeline())
    assert get_video_provider(job).provider_id == "code_video"
