from __future__ import annotations

import os
import subprocess
import tempfile
import pytest

from hinaa_api.media.extractors import (
    _get_ffmpeg_bin,
    extract_audio_metadata,
    extract_video_metadata_and_keyframes,
)
from hinaa_api.media.resolver import _extract_media_text


@pytest.fixture(scope="module")
def sample_media_files():
    ffmpeg_bin = _get_ffmpeg_bin()
    temp_dir = tempfile.mkdtemp(prefix="hinaa_test_media_")

    video_path = os.path.join(temp_dir, "sample.mp4")
    # Generate a lightweight 2-second 320x240 MP4
    cmd_video = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=10",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        video_path,
    ]
    subprocess.run(cmd_video, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    audio_path = os.path.join(temp_dir, "sample.wav")
    # Generate a lightweight 1-second sine wave WAV
    cmd_audio = [
        ffmpeg_bin, "-y",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        audio_path,
    ]
    subprocess.run(cmd_audio, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

    yield {"video_path": video_path, "audio_path": audio_path, "temp_dir": temp_dir}

    # Cleanup
    import shutil
    shutil.rmtree(temp_dir, ignore_errors=True)


def test_extract_video_metadata_and_keyframes(sample_media_files):
    video_path = sample_media_files["video_path"]
    with open(video_path, "rb") as f:
        video_bytes = f.read()

    res = extract_video_metadata_and_keyframes(video_bytes, max_frames=3)
    assert res["status"] == "success"
    assert res["duration_seconds"] >= 1.5
    assert res["resolution"] == "320x240"
    assert len(res["keyframe_paths"]) > 0
    assert "Video Intelligence Analysis" in res["timeline_summary"]

    for kf in res["keyframe_paths"]:
        assert os.path.exists(kf)
        assert os.path.getsize(kf) > 0


def test_extract_audio_metadata(sample_media_files):
    audio_path = sample_media_files["audio_path"]
    with open(audio_path, "rb") as f:
        audio_bytes = f.read()

    res = extract_audio_metadata(audio_bytes)
    assert res["status"] == "success"
    assert res["duration_seconds"] >= 0.8
    assert res["sample_rate"] == 44100
    assert "Audio Intelligence Analysis" in res["summary"]


def test_media_resolver_video_audio_routing(sample_media_files):
    video_path = sample_media_files["video_path"]
    with open(video_path, "rb") as f:
        v_bytes = f.read()
    v_summary = _extract_media_text(v_bytes, "video/mp4", "clip.mp4")
    assert v_summary is not None
    assert "Video Intelligence Analysis" in v_summary

    audio_path = sample_media_files["audio_path"]
    with open(audio_path, "rb") as f:
        a_bytes = f.read()
    a_summary = _extract_media_text(a_bytes, "audio/wav", "voice.wav")
    assert a_summary is not None
    assert "Audio Intelligence Analysis" in a_summary
