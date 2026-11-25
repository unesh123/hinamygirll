"""Tests for `render_code_animation` Playwright + FFmpeg + ffprobe studio tool."""
from __future__ import annotations

import asyncio
import shutil

import pytest

from hinaa_api.tools.code_animation_tool import (
    RenderCodeAnimationParams,
    _build_default_kinetic_html,
    render_code_animation_handler,
)


def _has_render_toolchain() -> bool:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        return False
    try:
        from pathlib import Path
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            return Path(pw.chromium.executable_path).exists()
    except Exception:
        return False


def test_default_kinetic_html_escapes_title() -> None:
    doc = _build_default_kinetic_html("<script>alert(1)</script>", "Sub & More", 3.0, 480, 640)
    assert "<script>alert(1)</script>" not in doc
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in doc
    assert "Sub &amp; More" in doc
    assert "window.setAnimationTime" in doc


@pytest.mark.asyncio
async def test_render_code_animation_preview_via_timeline(monkeypatch, tmp_path) -> None:
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        pytest.skip("ffmpeg/ffprobe required")
    from hinaa_api.creative.assets.manager import CreativeAssetManager

    mgr = CreativeAssetManager(tmp_path / "assets")
    monkeypatch.setattr("hinaa_api.tools.code_animation_tool.creative_asset_manager", mgr)

    res = await render_code_animation_handler(
        RenderCodeAnimationParams(
            title="Preview Scene",
            duration_seconds=1.5,
            fps=24,
            width=1080,
            height=1920,
            preview=True,
            timeline_json={
                "scenes": [
                    {
                        "duration": 1.5,
                        "background": "#0f172a",
                        "texts": [{"text": "HINAA Preview", "start": 0.1, "end": 1.4, "size": 36, "color": "white"}],
                    }
                ]
            },
        )
    )
    assert res["status"] == "success"
    assert res["stage"] == "preview_render"
    assert res["output"]["resolution"] == "480x854"
    assert res["output"]["video_codec"] == "h264"
    assert res["download_url"].startswith("/v1/creative/assets/")
    assert len(mgr.get_asset_bytes(res["asset_id"], "default_tenant") or b"") > 5000


@pytest.mark.asyncio
async def test_render_code_animation_html_playwright_ffmpeg_e2e(monkeypatch, tmp_path) -> None:
    if not await asyncio.to_thread(_has_render_toolchain):
        pytest.skip("Playwright Chromium + ffmpeg + ffprobe required")
    from hinaa_api.creative.assets.manager import CreativeAssetManager

    mgr = CreativeAssetManager(tmp_path / "assets")
    monkeypatch.setattr("hinaa_api.tools.code_animation_tool.creative_asset_manager", mgr)

    custom_html = """<!DOCTYPE html>
<html><body style="margin:0;background:#111;color:#fff;display:flex;align-items:center;justify-content:center;width:320px;height:320px;font-family:sans-serif">
  <div id="box" style="font-size:28px;font-weight:700">HELLO</div>
  <script>
    window.setAnimationTime = function(t) {
      document.getElementById('box').style.transform = 'translateX(' + Math.round(t * 20) + 'px)';
    };
  </script>
</body></html>"""

    res = await render_code_animation_handler(
        RenderCodeAnimationParams(
            title="Kinetic Test",
            html_code=custom_html,
            duration_seconds=1.0,
            fps=12,
            width=320,
            height=320,
        )
    )
    assert res["status"] == "success"
    assert res["renderer"] == "playwright_chromium_ffmpeg"
    assert res["output"]["resolution"] == "320x320"
    assert res["output"]["video_codec"] == "h264"
    assert abs(res["output"]["duration_sec"] - 1.0) < 0.35
    assert res["output"]["checksum_sha256"]
    assert res["output"]["size_bytes"] > 2000
