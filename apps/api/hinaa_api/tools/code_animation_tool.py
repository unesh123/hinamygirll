"""Code-to-MP4 Animation Studio Tool (`render_code_animation`).

Allows HINAA to author arbitrary HTML/CSS/SVG/Canvas animations OR structured
`timeline_json` scenes, render frames deterministically inside a network-isolated
headless Chromium browser via Playwright, mix & loudness-normalize optional
workspace/data audio to -14 LUFS via FFmpeg, verify stream integrity via
ffprobe, and store the resulting MP4 in `creative_asset_manager`.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ..creative.assets.manager import creative_asset_manager
from ..creative.models import CreativeOperation
from ..creative.providers.code_video_provider import (
    CodeVideoProvider,
    CodeVideoTimeline,
    _resolve_confined_media_path,
)
from ..errors import HinaaError
from .registry import RiskTier, ToolDefinition, ToolEffect, registry

_MAX_HTML_BYTES = 350_000


def _build_default_kinetic_html(title: str, subtitle: str, duration: float, width: int, height: int) -> str:
    safe_title = (title or "HINAA Kinetic").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_sub = (subtitle or "Rendered deterministically in code").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    width: {width}px; height: {height}px; overflow: hidden;
    background: radial-gradient(circle at 50% 42%, #1e1b4b 0%, #09090b 70%, #020617 100%);
    color: #f8fafc; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    display: flex; align-items: center; justify-content: center; position: relative;
  }}
  canvas {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
  .wrap {{ position: relative; z-index: 2; text-align: center; padding: 40px; max-width: 88%; }}
  .badge {{
    display: inline-block; letter-spacing: 0.28em; font-size: 13px; text-transform: uppercase;
    color: #38bdf8; border: 1px solid rgba(56,189,248,0.45); padding: 6px 14px; border-radius: 999px;
    margin-bottom: 22px; background: rgba(15,23,42,0.55);
  }}
  h1 {{
    font-size: clamp(32px, 6vw, 76px); font-weight: 800; line-height: 1.06;
    background: linear-gradient(135deg, #ffffff 15%, #38bdf8 55%, #f472b6 95%);
    -webkit-background-clip: text; color: transparent; letter-spacing: -0.02em;
  }}
  p {{ margin-top: 18px; font-size: clamp(16px, 2.4vw, 24px); color: #cbd5e1; opacity: 0.9; }}
</style>
</head>
<body>
  <canvas id="bg" width="{width}" height="{height}"></canvas>
  <div class="wrap" id="card">
    <div class="badge">HINAA STUDIO · CODE RENDER</div>
    <h1 id="headline">{safe_title}</h1>
    <p id="subline">{safe_sub}</p>
  </div>
  <script>
    const canvas = document.getElementById('bg');
    const ctx = canvas.getContext('2d');
    const total = {max(0.5, duration):.3f};
    const card = document.getElementById('card');
    function easeOutExpo(x) {{ return x >= 1 ? 1 : 1 - Math.pow(2, -10 * Math.max(0, x)); }}
    window.setAnimationTime = function(t) {{
      const p = Math.min(1, Math.max(0, t / total));
      const e = easeOutExpo(Math.min(1, t / Math.min(1.2, total * 0.45)));
      const fadeOut = p > 0.85 ? Math.max(0, (1 - p) / 0.15) : 1;
      card.style.opacity = String(e * fadeOut);
      card.style.transform = `translateY(${{(1 - e) * 34}}px) scale(${{0.94 + 0.06 * e}})`;
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      for (let i = 0; i < 28; i++) {{
        const angle = (i / 28) * Math.PI * 2 + p * Math.PI * 1.4;
        const radius = (canvas.width * 0.18) + (i % 4) * 38 + Math.sin(p * Math.PI * 4 + i) * 14;
        const x = canvas.width * 0.5 + Math.cos(angle) * radius;
        const y = canvas.height * 0.46 + Math.sin(angle) * radius * 0.72;
        ctx.beginPath();
        ctx.arc(x, y, 2.2 + (i % 3), 0, Math.PI * 2);
        ctx.fillStyle = i % 2 === 0 ? 'rgba(56,189,248,0.48)' : 'rgba(244,114,182,0.42)';
        ctx.fill();
      }}
    }};
    window.setAnimationTime(0);
  </script>
</body>
</html>"""


def _ffprobe_metadata(video_path: Path) -> dict[str, Any]:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise HinaaError("FFPROBE_MISSING", "ffprobe is required to verify rendered MP4 output.", 500, True)
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video_path)],
        capture_output=True, text=True, timeout=30,
    )
    if proc.returncode != 0:
        raise HinaaError("RENDER_QC_FAILED", f"ffprobe failed: {proc.stderr[-300:]}", 502, True)
    parsed = json.loads(proc.stdout or "{}")
    streams = parsed.get("streams") or []
    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if not v_stream:
        raise HinaaError("RENDER_QC_FAILED", "Rendered output has no video stream.", 502, True)
    fps_raw = str(v_stream.get("avg_frame_rate") or "0/1")
    if "/" in fps_raw:
        num, den = fps_raw.split("/", 1)
        fps_val = float(num) / max(1.0, float(den))
    else:
        fps_val = float(fps_raw or 0.0)
    raw_bytes = video_path.read_bytes()
    return {
        "size_bytes": len(raw_bytes),
        "duration_sec": float(parsed.get("format", {}).get("duration") or 0.0),
        "resolution": f"{v_stream.get('width')}x{v_stream.get('height')}",
        "width": int(v_stream.get("width") or 0),
        "height": int(v_stream.get("height") or 0),
        "fps": round(fps_val, 3),
        "video_codec": v_stream.get("codec_name"),
        "audio_codec": a_stream.get("codec_name") if a_stream else None,
        "audio_channels": int(a_stream.get("channels") or 0) if a_stream else 0,
        "checksum_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        "ffprobe_output": parsed,
    }


def _render_html_sync(
    *,
    html_code: str,
    width: int,
    height: int,
    fps: int,
    duration_seconds: float,
    audio_path: str | None,
    normalize_audio: bool,
) -> tuple[bytes, dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HinaaError("FFMPEG_MISSING", "ffmpeg is required to encode MP4 output.", 500, True)

    total_frames = max(2, int(round(duration_seconds * fps)))
    with tempfile.TemporaryDirectory(prefix="hinaa_code_anim_") as tmp:
        tmp_path = Path(tmp)
        html_file = tmp_path / "scene.html"
        html_file.write_text(html_code, encoding="utf-8")
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
                page = context.new_page()

                # Fail closed on outbound HTTP(S) inside rendered scene HTML to prevent SSRF/exfiltration
                def _route_guard(route: Any) -> None:
                    url = str(route.request.url or "").lower()
                    if url.startswith("file://") or url.startswith("data:") or url.startswith("blob:") or url.startswith("about:"):
                        route.continue_()
                    else:
                        route.abort()

                page.route("**/*", _route_guard)
                page.goto(html_file.as_uri(), wait_until="load", timeout=15_000)

                for idx in range(total_frames):
                    t_sec = idx / float(fps)
                    t_ms = t_sec * 1000.0
                    page.evaluate(
                        """([tSec, tMs]) => {
                            if (typeof window.setAnimationTime === 'function') {
                                window.setAnimationTime(tSec);
                            }
                            if (typeof document.getAnimations === 'function') {
                                for (const anim of document.getAnimations()) {
                                    try {
                                        anim.pause();
                                        anim.currentTime = tMs;
                                    } catch (_) {}
                                }
                            }
                        }""",
                        [t_sec, t_ms],
                    )
                    frame_path = frames_dir / f"frame_{idx:05d}.png"
                    page.screenshot(path=str(frame_path), type="png")
            finally:
                browser.close()

        raw_mp4 = tmp_path / "video_only.mp4"
        final_mp4 = tmp_path / "final.mp4"
        enc_cmd = [
            ffmpeg, "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.png"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(raw_mp4),
        ]
        enc_proc = subprocess.run(enc_cmd, capture_output=True, text=True, timeout=300)
        if enc_proc.returncode != 0:
            raise HinaaError("RENDER_FAILED", f"FFmpeg encode failed: {enc_proc.stderr[-400:]}", 502, True)

        if audio_path:
            resolved_audio = _resolve_confined_media_path(audio_path, code="BAD_AUDIO_PATH", label="Audio")
            mix_cmd = [
                ffmpeg, "-y",
                "-i", str(raw_mp4), "-i", str(resolved_audio),
                "-map", "0:v", "-map", "1:a",
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            ]
            if normalize_audio:
                mix_cmd.extend(["-filter:a", "loudnorm=I=-14:TP=-1.0:LRA=11"])
            mix_cmd.extend(["-shortest", "-movflags", "+faststart", "-t", f"{duration_seconds:.3f}", str(final_mp4)])
            mix_proc = subprocess.run(mix_cmd, capture_output=True, text=True, timeout=180)
            if mix_proc.returncode != 0:
                raise HinaaError("AUDIO_MIX_FAILED", f"FFmpeg audio mix failed: {mix_proc.stderr[-400:]}", 502, True)
        else:
            shutil.copyfile(raw_mp4, final_mp4)

        probe = _ffprobe_metadata(final_mp4)
        if probe["size_bytes"] < 1024:
            raise HinaaError("RENDER_QC_FAILED", "Encoded MP4 is suspiciously small.", 502, True)
        return final_mp4.read_bytes(), probe


class RenderCodeAnimationParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str = Field("HINAA Kinetic Animation", max_length=140, description="Title for the animation or asset.")
    subtitle: str = Field("Deterministic Code Render", max_length=240, description="Optional subtitle when auto-building kinetic HTML.")
    html_code: str | None = Field(None, max_length=_MAX_HTML_BYTES, description="Self-contained HTML/CSS/SVG/Canvas document using window.setAnimationTime(t) or CSS animations.")
    html_path: str | None = Field(None, max_length=500, description="Optional relative path to an existing workspace .html file to render into MP4.")
    timeline_json: dict[str, Any] | None = Field(None, description="Alternative CodeVideoTimeline JSON spec rendered via FFmpeg.")
    duration_seconds: float = Field(5.0, ge=0.5, le=30.0, description="Duration in seconds (0.5..30).")
    fps: int = Field(24, ge=1, le=60, description="Frames per second (1..60).")
    width: int = Field(1080, ge=64, le=1920, description="Output width in pixels.")
    height: int = Field(1920, ge=64, le=1920, description="Output height in pixels.")
    preview: bool = Field(False, description="When true, renders fast 480p@30fps draft for rapid approval.")
    audio_path: str | None = Field(None, max_length=500, description="Optional .mp3/.wav path inside workspace/data.")
    normalize_audio: bool = Field(True, description="Apply EBU R128 loudness normalization (-14 LUFS) to audio.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override for html_path.")
    userId: str = Field("default_user", max_length=120)


async def render_code_animation_handler(params: RenderCodeAnimationParams) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    width, height, fps = params.width, params.height, params.fps
    if params.preview:
        scale = min(480.0 / max(1, min(width, height)), 1.0)
        width = max(64, int(round((width * scale) / 2.0) * 2))
        height = max(64, int(round((height * scale) / 2.0) * 2))
        fps = min(fps, 30)

    if params.timeline_json:
        timeline = CodeVideoTimeline.model_validate({
            "width": width,
            "height": height,
            "fps": fps,
            "audio": params.audio_path,
            "normalize_audio": params.normalize_audio,
            **params.timeline_json,
        })
        prov = CodeVideoProvider()
        mp4_bytes = await asyncio.to_thread(prov.render_timeline, timeline)
        probe = dict(prov.last_probe or {})
        probe.setdefault("size_bytes", len(mp4_bytes))
        probe.setdefault("resolution", f"{width}x{height}")
        probe.setdefault("fps", fps)
        probe.setdefault("video_codec", probe.get("codec", "h264"))
        probe.setdefault("duration_sec", probe.get("duration", params.duration_seconds))
        renderer = "code_video_ffmpeg"
    else:
        html_doc = (params.html_code or "").strip()
        if not html_doc and params.html_path:
            from .workspace_coding_tools import _resolve_inside_workspace, _resolve_workspace_root

            ws_root = _resolve_workspace_root(params.workspace_root)
            try:
                html_target = _resolve_inside_workspace(ws_root, params.html_path)
            except ValueError as err:
                raise HinaaError("WORKSPACE_ESCAPE", str(err), 400, False) from err
            if not html_target.exists() or not html_target.is_file():
                raise HinaaError("HTML_PATH_NOT_FOUND", f"HTML file not found: {params.html_path}", 404, False)
            html_doc = html_target.read_text(encoding="utf-8", errors="replace")[:_MAX_HTML_BYTES]
        if not html_doc:
            html_doc = _build_default_kinetic_html(
                params.title, params.subtitle, params.duration_seconds, width, height
            )
        mp4_bytes, probe = await asyncio.to_thread(
            _render_html_sync,
            html_code=html_doc,
            width=width,
            height=height,
            fps=fps,
            duration_seconds=params.duration_seconds,
            audio_path=params.audio_path,
            normalize_audio=params.normalize_audio,
        )
        renderer = "playwright_chromium_ffmpeg"

    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", params.title.lower()).strip("_")[:36] or "animation"
    filename = f"{slug}_{uuid.uuid4().hex[:8]}.mp4"
    meta = await asyncio.to_thread(
        creative_asset_manager.store_asset,
        data=mp4_bytes,
        filename=filename,
        operation=CreativeOperation.TIMELINE_EXPORT,
        provider=renderer,
        model_version="1.0",
        tenant_id="default_tenant",
        user_id=params.userId or "default_user",
        prompt=params.title,
        duration_seconds=float(probe.get("duration_sec") or params.duration_seconds),
        fps=float(probe.get("fps") or fps),
    )
    completed_at = datetime.now(timezone.utc).isoformat()
    download_url = f"/v1/creative/assets/{meta.asset_id}/download"
    return {
        "status": "success",
        "stage": "preview_render" if params.preview else "final_render",
        "renderer": renderer,
        "asset_id": meta.asset_id,
        "filename": meta.filename,
        "download_url": download_url,
        "url": download_url,
        "mime_type": "video/mp4",
        "output": {
            "asset_id": meta.asset_id,
            "download_url": download_url,
            "size_bytes": meta.file_size_bytes,
            "duration_sec": meta.duration_seconds,
            "resolution": f"{meta.width}x{meta.height}",
            "fps": meta.fps,
            "video_codec": probe.get("video_codec") or meta.codec or "h264",
            "audio_codec": probe.get("audio_codec"),
            "audio_channels": probe.get("audio_channels", 0),
            "loudness_lufs": -14.0 if (params.audio_path and params.normalize_audio) else None,
            "checksum_sha256": meta.sha256_hash,
        },
        "started_at": started_at,
        "completed_at": completed_at,
    }


render_code_animation_def = ToolDefinition(
    name="render_code_animation",
    display_name="Studio: Render Code Animation (Playwright + FFmpeg)",
    description=(
        "Render custom HTML/CSS/SVG/Canvas animations (using window.setAnimationTime(t) or CSS keyframes) "
        "or CodeVideoTimeline JSON directly to a ffprobe-verified H.264 MP4 asset with optional -14 LUFS audio mixing. "
        "Runs network-isolated locally with zero paid video API credits."
    ),
    parameters={
        "title": {"type": "string", "description": "Title for the rendered video."},
        "subtitle": {"type": "string", "description": "Subtitle used when auto-building kinetic HTML."},
        "html_code": {"type": "string", "description": "Optional self-contained HTML animation document."},
        "html_path": {"type": "string", "description": "Optional relative path to a workspace HTML file to render."},
        "timeline_json": {"type": "object", "description": "Optional CodeVideoTimeline JSON scene specification."},
        "duration_seconds": {"type": "number", "description": "Video length in seconds (0.5..30)."},
        "fps": {"type": "integer", "description": "Frames per second (1..60)."},
        "width": {"type": "integer", "description": "Pixel width."},
        "height": {"type": "integer", "description": "Pixel height."},
        "preview": {"type": "boolean", "description": "Fast 480p preview render before final export."},
        "audio_path": {"type": "string", "description": "Optional workspace/data .mp3/.wav audio file."},
        "normalize_audio": {"type": "boolean", "description": "Normalize audio track to -14 LUFS (EBU R128)."},
        "workspace_root": {"type": "string", "description": "Optional workspace root override for html_path."},
    },
    required_parameters=[],
    requires_confirmation=False,
    risk_level="medium",
    risk_tier=RiskTier.TIER_1_REVERSIBLE,
    tool_effect=ToolEffect.MUTATE_WORKSPACE,
    audit_category="media",
    timeout_seconds=300,
    is_long_running=True,
    is_concurrency_safe=False,
    max_retries=0,
)

registry.register(render_code_animation_def, render_code_animation_handler)
