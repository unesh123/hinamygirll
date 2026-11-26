"""Core invariants and actual Chromium/FFmpeg checks, isolated from app-wide fixtures.

pytest --confcutdir=tests/motion_studio tests/motion_studio
"""
# ruff: noqa: S603, S607

import asyncio
import hashlib
import os
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest
from PIL import Image
from pydantic import ValidationError

from hinaa_api.motion_studio import MotionComposition, compile_composition
from hinaa_api.motion_studio.analysis import analyze_audio, analyze_reference


def composition(**layer):
    return MotionComposition(scenes=[{"duration": 2, "layers": [{"text": "MOVE", **layer}]}])


@pytest.mark.parametrize(
    "bad",
    [
        {"start": 2},
        {"end": 0.1, "start": 0.2},
        {"x": float("nan")},
        {"motion": "imaginary_preset"},
        {"keyframes": [{"time": 1}, {"time": 0}]},
        {"unit_times": [0.3, 0.1]},
        {"unit_times": [float("nan")]},
    ],
)
def test_rejects_broken_timing_and_nonfinite_motion(bad):
    with pytest.raises(ValidationError):
        composition(**bad)


def test_composition_duration_and_accents_are_bounded():
    with pytest.raises(ValidationError):
        MotionComposition(scenes=[{"duration": 20, "layers": [{"text": "A"}]}] * 2)
    with pytest.raises(ValidationError):
        MotionComposition(scenes=[{"duration": 2, "layers": [{"text": "A"}]}], accents=[2])


def test_script_text_is_data_and_media_is_confined(tmp_path):
    doc = compile_composition(
        composition(text="</script><script>window.PWNED=1</script>"), tmp_path
    )
    assert "</script><script>window.PWNED" not in doc
    assert "\\u003c/script" in doc
    outside = tmp_path.parent / "outside.png"
    Image.new("RGB", (20, 20), "red").save(outside)
    (tmp_path / "link.png").symlink_to(outside)
    for path in ("../outside.png", "link.png", "https://example.com/photo.png"):
        with pytest.raises(ValueError):
            compile_composition(composition(kind="image", path=path), tmp_path)


@pytest.fixture
def page():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        exe = Path(pw.chromium.executable_path)
        system = (
            os.environ.get("HINAA_CHROMIUM_EXECUTABLE")
            or shutil.which("chromium")
            or shutil.which("google-chrome")
        )
        if not exe.exists() and not system:
            pytest.skip("Chromium required")
        browser = pw.chromium.launch(**({"executable_path": system} if system else {}))
        pg = browser.new_page(viewport={"width": 360, "height": 640})
        yield pg
        browser.close()


def test_frame_clock_deterministic_and_nepali_shaping(page, tmp_path):
    doc = compile_composition(
        composition(text="नेपालको कथा", motion="letter_stagger"), tmp_path, 360, 640
    )
    errors = []
    page.on("pageerror", lambda err: errors.append(str(err)))
    page.set_content(doc)
    page.evaluate("async()=>await window.setAnimationTime(.8)")
    a = page.screenshot()
    page.evaluate("async()=>await window.setAnimationTime(.2)")
    b = page.screenshot()
    page.evaluate("async()=>await window.setAnimationTime(.8)")
    assert page.screenshot() == a
    assert a != b
    assert page.evaluate('units("नेपालको कथा",false).length') == 2
    assert errors == []


def test_layer_order_and_aspect_ratio_preserved(page, tmp_path):
    Image.new("RGB", (200, 100), (30, 170, 60)).save(tmp_path / "wide.png")
    spec = MotionComposition(
        scenes=[
            {
                "duration": 2,
                "layers": [
                    {"kind": "text", "text": "HIDDEN", "motion": "none"},
                    {"kind": "image", "path": "wide.png", "size": 1, "height": 1, "fit": "contain"},
                ],
            }
        ]
    )
    page.set_content(compile_composition(spec, tmp_path, 360, 640))
    page.evaluate("async()=>await window.setAnimationTime(1)")
    color = page.evaluate("Array.from(main.getImageData(180,320,1,1).data)")
    assert color[:3] == [30, 170, 60]
    # A 2:1 source remains 2:1, so the top is the scene background.
    assert page.evaluate("Array.from(main.getImageData(180,100,1,1).data)")[:3] == [12, 16, 25]


def test_all_motion_and_transition_presets_render(page, tmp_path):
    motions = [
        "none",
        "mask_rise",
        "word_reveal",
        "letter_stagger",
        "tracking",
        "perspective",
        "slash",
        "blur_rise",
        "typewriter",
        "scale_pop",
    ]
    transitions = ["cut", "crossfade", "wipe", "diagonal", "whip", "iris"]
    scenes = [
        {"duration": 1, "transition": transitions[i % 6], "layers": [{"text": "TEST", "motion": m}]}
        for i, m in enumerate(motions)
    ]
    spec = MotionComposition(scenes=scenes)
    page.set_content(compile_composition(spec, tmp_path, 360, 640))
    for i in range(len(motions)):
        for t in (i + 0.1, i + 0.8):
            page.evaluate("async t=>await window.setAnimationTime(t)", t)
            assert page.evaluate("main.getImageData(0,0,1,1).data[3]") == 255


def test_video_frames_are_sought_before_capture(page, tmp_path):
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg required")
    video = tmp_path / "colors.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=red:s=64x64:d=0.5:r=10",
            "-f",
            "lavfi",
            "-i",
            "color=blue:s=64x64:d=0.5:r=10",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-pix_fmt",
            "yuv420p",
            str(video),
        ],
        check=True,
    )
    spec = composition(kind="video", path="colors.mp4", size=1, height=1)
    page.set_content(compile_composition(spec, tmp_path, 360, 640))
    page.evaluate("async()=>await window.setAnimationTime(.2)")
    red = page.evaluate("Array.from(main.getImageData(180,320,1,1).data)")
    page.evaluate("async()=>await window.setAnimationTime(.8)")
    blue = page.evaluate("Array.from(main.getImageData(180,320,1,1).data)")
    assert red[0] > 200 and red[2] < 20
    assert blue[2] > 200 and blue[0] < 20
    page.evaluate("async()=>await window.setAnimationTime(.2)")
    assert page.evaluate("Array.from(main.getImageData(180,320,1,1).data)") == red


def write_audio(path, seconds=2, clicks=True):
    rate = 22050
    t = np.arange(int(rate * seconds)) / rate
    a = np.zeros(len(t))
    if clicks:
        for onset in (0.3, 0.8, 1.3):
            dt = t - onset
            a += np.where(
                (dt >= 0) & (dt < 0.1),
                0.7 * np.sin(2 * np.pi * 120 * dt) * np.exp(-np.maximum(0, dt) * 45),
                0,
            )
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(rate)
        f.writeframes((a * 32767).astype("<i2").tobytes())


def test_audio_analysis_measures_transients_not_a_fake_grid(tmp_path):
    p = tmp_path / "beats.wav"
    write_audio(p)
    result = analyze_audio(p, 0, 2)
    for expected in (0.3, 0.8, 1.3):
        assert min(abs(t - expected) for t in result["accents"]) < 0.07
    silent = tmp_path / "silent.wav"
    write_audio(silent, clicks=False)
    assert analyze_audio(silent, 0, 2)["accents"] == []
    with pytest.raises(ValueError):
        analyze_audio(p, 10, 2)


def test_reference_analysis_reports_real_cut_candidates(tmp_path):
    p = tmp_path / "reference.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=white:s=64x64:d=1:r=8",
            "-f",
            "lavfi",
            "-i",
            "color=black:s=64x64:d=1:r=8",
            "-filter_complex",
            "[0:v][1:v]concat=n=2:v=1:a=0",
            "-pix_fmt",
            "yuv420p",
            str(p),
        ],
        check=True,
    )
    result = analyze_reference(p, 2)
    assert any(abs(t - 1) < 0.15 for t in result["candidate_cuts"])
    assert result["width"] == 64


def test_actual_hina_tool_exports_audio_and_editable_source(tmp_path, monkeypatch):
    # Import the real handler, registry and asset manager; never substitute a fake renderer.
    os.environ["HINAA_DATA_DIR"] = str(tmp_path / "data")
    import hinaa_api.tools.code_animation_tool as tool
    from hinaa_api.creative.assets.manager import CreativeAssetManager
    from hinaa_api.tools.code_animation_tool import (
        RenderCodeAnimationParams,
        render_code_animation_handler,
    )

    manager = CreativeAssetManager(tmp_path / "assets")
    monkeypatch.setattr(tool, "creative_asset_manager", manager)
    audio = tmp_path / "song.wav"
    write_audio(audio)
    params = RenderCodeAnimationParams(
        title="Real compositor test",
        workspace_root=str(tmp_path),
        composition_json=composition().model_dump(),
        audio_path="song.wav",
        fps=12,
        width=360,
        height=640,
        audio_preset="none",
    )
    result = asyncio.run(render_code_animation_handler(params))
    assert result["renderer"] == "hina_motion_studio_local"
    assert result["output"]["audio_codec"] == "aac"
    assert result["output"]["fps"] == 12
    assert result["external_video_api_calls"] == 0
    assert abs(result["output"]["duration_sec"] - 2) < 0.1
    raw = manager.get_asset_bytes(result["asset_id"], "default_tenant")
    assert hashlib.sha256(raw).hexdigest() == result["output"]["checksum_sha256"]
    source = tmp_path / result["source_project"]["composition"]
    assert MotionComposition.model_validate_json(source.read_text()).duration == 2
    assert result["analysis"]["audio"]["accents"]


def test_inspection_has_no_render_side_effect(tmp_path, monkeypatch):
    import hinaa_api.tools.code_animation_tool as tool
    from hinaa_api.tools.code_animation_tool import (
        RenderCodeAnimationParams,
        render_code_animation_handler,
    )

    def forbidden(**kwargs):
        pytest.fail("inspection must not invoke a renderer")

    monkeypatch.setattr(tool, "_render_html_sync", forbidden)
    result = asyncio.run(
        render_code_animation_handler(
            RenderCodeAnimationParams(inspect_only=True, workspace_root=str(tmp_path))
        )
    )
    assert result["rendered"] is False
    assert result["stage"] == "media_analysis"
    assert "scenes" in result["composition_schema"]["properties"]


def test_source_audio_trim_keeps_pitch_and_video_duration(tmp_path):
    from hinaa_api.tools.code_animation_tool import _render_html_sync

    rate = 22050
    t = np.arange(rate * 3) / rate
    signal = 0.35 * np.sin(2 * np.pi * np.where(t < 1, 220, 660) * t)
    song = tmp_path / "two-tones.wav"
    with wave.open(str(song), "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes((signal * 32767).astype("<i2").tobytes())
    doc = compile_composition(composition(), tmp_path, 180, 320)
    data, metadata = _render_html_sync(
        html_code=doc,
        width=180,
        height=320,
        fps=12,
        duration_seconds=1,
        audio_path=str(song),
        audio_start_seconds=1.1,
        normalize_audio=False,
        audio_preset="none",
    )
    video = tmp_path / "trim.mp4"
    video.write_bytes(data)
    pcm = subprocess.run(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(video),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(rate),
            "-f",
            "f32le",
            "pipe:1",
        ],
        capture_output=True,
        check=True,
    ).stdout
    a = np.frombuffer(pcm, dtype="<f4")[: rate // 2]
    peak = np.fft.rfftfreq(len(a), 1 / rate)[np.argmax(np.abs(np.fft.rfft(a)))]
    assert abs(peak - 660) < 5
    assert abs(metadata["duration_sec"] - 1) < 0.1


def test_short_audio_and_ambiguous_inputs_fail_before_render(tmp_path, monkeypatch):
    import hinaa_api.tools.code_animation_tool as tool
    from hinaa_api.errors import HinaaError
    from hinaa_api.tools.code_animation_tool import (
        RenderCodeAnimationParams,
        render_code_animation_handler,
    )

    def forbidden(**kwargs):
        pytest.fail("invalid input must fail before invoking Chromium")

    monkeypatch.setattr(tool, "_render_html_sync", forbidden)
    song = tmp_path / "short.wav"
    write_audio(song, seconds=1)
    with pytest.raises(HinaaError, match="shorter"):
        asyncio.run(
            render_code_animation_handler(
                RenderCodeAnimationParams(
                    workspace_root=str(tmp_path),
                    composition_json=composition().model_dump(),
                    audio_path="short.wav",
                )
            )
        )
    with pytest.raises(HinaaError, match="Use one"):
        asyncio.run(
            render_code_animation_handler(
                RenderCodeAnimationParams(
                    workspace_root=str(tmp_path),
                    composition_json=composition().model_dump(),
                    html_code="<html></html>",
                )
            )
        )
