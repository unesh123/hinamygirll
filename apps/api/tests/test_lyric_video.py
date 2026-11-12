"""Lyric-video generator: spec, timing, scenes, HTML safety and a real render."""
# ruff: noqa: E501, S603, S607

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageChops
from pydantic import ValidationError

from hinaa_api.creative.lyric_video import (
    SCENE_PRESETS,
    LyricVideoSpec,
    build_html,
    build_page_data,
    pick_scene,
    render_lyric_video,
    resolve_timeline,
    tools_available,
)
from hinaa_api.creative.lyric_video.jobs import LyricVideoService
from hinaa_api.creative.models import JobState
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.tools import registry

needs_render = pytest.mark.skipif(not tools_available(), reason="Chromium/ffmpeg unavailable")


def _spec(**kw) -> LyricVideoSpec:
    kw.setdefault("lines", [{"text": "one"}, {"text": "two"}])
    return LyricVideoSpec(**kw)


def _sine(path: Path, seconds: float = 3.0) -> str:
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", str(path)],
            check=True,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        import struct
        sample_rate = 8000
        num_samples = int(sample_rate * seconds)
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF", 36 + num_samples, b"WAVE",
            b"fmt ", 16, 1, 1, sample_rate, sample_rate, 1, 8,
            b"data", num_samples,
        )
        path.write_bytes(header + b"\x80" * num_samples)
    return str(path)


def _probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(out.stdout)


def _frame(video: Path, t: float, dest: Path) -> Image.Image:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(t), "-i", str(video), "-frames:v", "1", str(dest)], check=True)
    return Image.open(dest).convert("RGB")


# ---- spec & timing ---------------------------------------------------------------------

def test_spec_defaults_and_validation(tmp_path):
    s = _spec()
    assert (s.aspect, s.fps, s.draft) == ("9:16", 30, False)
    assert s.size == (1080, 1920)
    assert _spec(aspect="16:9").size == (1920, 1080)
    assert _spec(aspect="1:1", draft=True).size == (540, 540)
    with pytest.raises(ValidationError):
        _spec(lines=[])
    with pytest.raises(ValidationError):
        _spec(aspect="4:3")
    with pytest.raises(ValidationError):
        _spec(lines=[{"text": "x", "start": 2, "end": 1}])
    with pytest.raises(ValidationError):
        _spec(lines=[{"text": "x", "scene": "nope"}])
    with pytest.raises(ValidationError):
        _spec(lines=[{"text": "   "}])
    with pytest.raises(ValidationError):
        _spec(palette={"accent": "pink"})
    with pytest.raises(ValidationError):
        _spec(audio_path=str(tmp_path / "missing.mp3"))
    bad = tmp_path / "a.ogg"
    bad.write_bytes(b"x")
    with pytest.raises(ValidationError):
        _spec(audio_path=str(bad))
    with pytest.raises(ValidationError):
        _spec(unknown_field=1)


def test_auto_timing_without_audio_is_three_seconds_per_line():
    lines, total = resolve_timeline(_spec(lines=[{"text": "a"}, {"text": "b"}, {"text": "c"}]))
    assert total == 9.0
    assert [(ln.start, ln.end) for ln in lines] == [(0, 3), (3, 6), (6, 9)]


def test_auto_timing_distributes_over_audio_duration():
    lines, total = resolve_timeline(_spec(lines=[{"text": "a"}, {"text": "b"}, {"text": "c"}, {"text": "d"}]), 10.0)
    assert total == 10.0
    assert [ln.start for ln in lines] == [0, 2.5, 5.0, 7.5]
    assert lines[-1].end == 10.0


def test_explicit_timing_fills_gaps_and_clips_to_audio():
    spec = _spec(lines=[{"text": "a", "start": 1, "end": 2}, {"text": "b"}, {"text": "c", "start": 6}])
    lines, total = resolve_timeline(spec)
    assert (lines[0].start, lines[0].end) == (1, 2)
    assert (lines[1].start, lines[1].end) == (2, 6)  # open end runs to next start
    assert (lines[2].start, lines[2].end) == (6, 9)  # default 3s tail
    assert total == 9
    lines, total = resolve_timeline(spec, 7.0)
    assert total == 7.0 and lines[-1].end == 7.0


# ---- scenes -----------------------------------------------------------------------------

def test_scene_auto_assignment_is_valid_varied_and_never_repeats():
    texts = ["Daada pari kaanchi nachi", "Piratiko yaadma hasi", "Paaderoko pani chiso maya", "Baderai rakhana man ta"] * 3
    lines, _ = resolve_timeline(_spec(lines=[{"text": t} for t in texts]))
    scenes = [ln.scene for ln in lines]
    assert set(scenes) <= set(SCENE_PRESETS)
    assert len(set(scenes)) >= 4
    assert all(a != b for a, b in zip(scenes, scenes[1:], strict=False))


def test_scene_keywords_and_explicit_override():
    assert pick_scene("under the moon tonight", 0, None) == "starry-night-flags"
    assert pick_scene("snow is falling", 0, None) == "snow-window"
    assert pick_scene("zzz", 7, None) in SCENE_PRESETS
    lines, _ = resolve_timeline(_spec(lines=[{"text": "snow", "scene": "love-burst"}]))
    assert lines[0].scene == "love-burst"


# ---- HTML safety ------------------------------------------------------------------------

def test_html_escapes_lyric_text_and_title():
    evil = '</script><script>window.__pwned=1</script><img src=x onerror=alert(1)> & "q" \u2028'
    spec = _spec(title=evil, lines=[{"text": evil}], stickers=[{"text": "</script><b>x</b>&", "at": 0}])
    html = build_html(build_page_data(spec))
    assert "<img src=x" not in html
    assert "</script><script>window" not in html
    # only the template's own two <script> blocks may exist
    assert len(re.findall(r"<script\b", html)) == 2
    payload = re.search(r'id="spec">(.*?)</script>', html, re.S).group(1)
    assert "<" not in payload and ">" not in payload and "\u2028" not in payload
    assert json.loads(payload)["lines"][0]["text"] == evil.strip()
    # lyrics reach the DOM through textContent, never innerHTML
    assert "ln.text" in html and "innerHTML = ln.text" not in html


@needs_render
def test_malicious_text_does_not_execute(tmp_path):
    from playwright.sync_api import sync_playwright

    evil = '<img src=x onerror="window.__pwned=1"><script>window.__pwned=1</script>'
    page_file = tmp_path / "p.html"
    page_file.write_text(build_html(build_page_data(_spec(lines=[{"text": evil}]))), encoding="utf-8")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(page_file.as_uri())
        page.wait_for_function("window.__ready === true")
        page.evaluate("window.__setFrame(20)")
        assert page.evaluate("window.__pwned === undefined")
        assert page.evaluate("document.querySelectorAll('.word img').length") == 0
        browser.close()


# ---- registration & API -----------------------------------------------------------------

def test_tool_registered_without_confirmation():
    tool = registry.get_tool("create_lyric_video")
    assert tool is not None
    assert tool.risk_level == "medium" and tool.requires_confirmation is False
    assert "lines" in tool.required_parameters


def test_endpoint_requires_auth_and_validates(settings, tmp_path):
    from tests.test_clerk_auth import _keys, _settings

    _private, public = _keys()
    with TestClient(create_app(_settings(tmp_path, public)), base_url="http://127.0.0.1:8000") as anon:
        assert anon.post("/v1/creative/lyric-video", json={"lines": [{"text": "x"}]}).status_code == 401
        assert anon.get("/v1/creative/lyric-video/job-lv-x").status_code == 401
    with TestClient(create_app(settings), base_url="http://127.0.0.1:8000", headers={"X-HINAA-Dev-User": "t"}) as c:
        assert c.post("/v1/creative/lyric-video", json={"lines": []}).status_code == 422
        assert c.post("/v1/creative/lyric-video", json={"lines": [{"text": "x"}], "aspect": "2:1"}).status_code == 422
        assert c.get("/v1/creative/lyric-video/job-lv-missing").status_code == 404


async def test_service_rejects_paths_outside_allowed_roots(tmp_path):
    audio = _sine(tmp_path / "a.wav", 1)
    svc = LyricVideoService(allowed_roots=[tmp_path / "allowed"])
    with pytest.raises(HinaaError) as exc:
        await svc.submit(_spec(audio_path=audio))
    assert exc.value.status_code == 403


# ---- real render ------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    if not tools_available():
        pytest.skip("Chromium/ffmpeg unavailable")
    d = tmp_path_factory.mktemp("lv")
    spec = LyricVideoSpec(
        title="Test", draft=True, audio_path=_sine(d / "tone.wav", 3.0),
        lines=[{"text": "Daada pari kaanchi nachi"}, {"text": "Baderai rakhana man ta"}],
        stickers=[{"text": "wait for the promise", "at": 0.5}],
    )
    progress: list[float] = []
    out = d / "out.mp4"
    result = render_lyric_video(spec, out, lambda p, _l: progress.append(p))
    return d, out, result, progress


@needs_render
def test_real_render_outputs_valid_mp4(rendered):
    _d, out, result, progress = rendered
    assert out.exists() and out.stat().st_size > 5_000
    info = _probe(out)
    video = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert next(s for s in info["streams"] if s["codec_type"] == "audio")["codec_name"] == "aac"
    assert (video["width"], video["height"]) == (540, 960)
    assert video["codec_name"] == "h264" and video["pix_fmt"] == "yuv420p"
    assert abs(float(info["format"]["duration"]) - 3.0) <= 0.25
    assert result["frames"] == 90
    assert progress == sorted(progress) and progress[-1] == 100.0


@needs_render
def test_real_render_frames_from_different_lines_differ(rendered):
    d, out, *_ = rendered
    a = _frame(out, 1.0, d / "a.png")
    b = _frame(out, 2.4, d / "b.png")
    assert a.size == b.size == (540, 960)
    diff = ImageChops.difference(a, b)
    changed = sum(1 for px in diff.getdata() if max(px) > 24)
    assert changed > 0.05 * a.size[0] * a.size[1]


@needs_render
def test_render_is_deterministic(tmp_path):
    spec = _spec(draft=True, lines=[{"text": "same", "start": 0, "end": 1}])
    paths = [tmp_path / "1.mp4", tmp_path / "2.mp4"]
    for p in paths:
        render_lyric_video(spec, p)
    f1, f2 = (_frame(p, 0.5, tmp_path / f"{p.stem}.png") for p in paths)
    diff = ImageChops.difference(f1, f2)
    big = sum(1 for px in diff.getdata() if max(px) > 40)
    assert big < 0.001 * f1.size[0] * f1.size[1]  # same frame; allow raster/codec edge noise


@needs_render
async def test_job_lifecycle_completes_and_stores_asset(tmp_path):
    import hinaa_api.creative.lyric_video.jobs as jobs_mod
    from hinaa_api.creative.assets.manager import CreativeAssetManager

    mgr = CreativeAssetManager(storage_root=tmp_path / "assets")
    original = jobs_mod.creative_asset_manager
    jobs_mod.creative_asset_manager = mgr
    try:
        svc = LyricVideoService(allowed_roots=[tmp_path])
        job = await svc.submit(_spec(draft=True, lines=[{"text": "hi", "start": 0, "end": 1}]), tenant_id="t1")
        await svc.wait(job.job_id)
        assert job.state == JobState.COMPLETED and job.progress_percent == 100.0
        path = mgr.get_asset_path(job.asset["asset_id"], "t1")
        assert path and path.suffix == ".mp4" and path.stat().st_size > 1000
        with pytest.raises(HinaaError):
            svc.get(job.job_id, "other-tenant")
    finally:
        jobs_mod.creative_asset_manager = original


@needs_render
async def test_job_cancel_stops_render_and_leaves_no_output(tmp_path):
    import hinaa_api.creative.lyric_video.jobs as jobs_mod
    from hinaa_api.creative.assets.manager import CreativeAssetManager

    mgr = CreativeAssetManager(storage_root=tmp_path / "assets")
    original = jobs_mod.creative_asset_manager
    jobs_mod.creative_asset_manager = mgr
    try:
        svc = LyricVideoService(allowed_roots=[tmp_path])
        job = await svc.submit(_spec(draft=True, lines=[{"text": "long", "start": 0, "end": 30}]), tenant_id="t1")
        await svc.cancel(job.job_id, "t1")
        await svc.wait(job.job_id)
        assert job.state == JobState.CANCELLED
        assert job.asset is None
        assert list((tmp_path / "assets").rglob("*.mp4")) == []
    finally:
        jobs_mod.creative_asset_manager = original
