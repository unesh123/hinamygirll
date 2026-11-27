"""Code-to-MP4 Animation Studio Tool (`render_code_animation`).

Allows HINAA to author arbitrary HTML/CSS/SVG/Canvas animations OR structured
`timeline_json` scenes, render frames deterministically inside a network-isolated
headless Chromium browser via Playwright, mix & loudness-normalize optional
workspace/data audio to -14 LUFS via FFmpeg, verify stream integrity via
ffprobe, and store the resulting MP4 in `creative_asset_manager`.
"""

from __future__ import annotations

import array
import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import uuid
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    safe_title = (title or "HINAA KINETIC").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    safe_sub = (subtitle or "STUDIO MOTION RENDER").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    words = [w for w in re.split(r"\s+", safe_title) if w][:5] or ["HINAA", "MOTION"]
    words_json = json.dumps(words)
    sub_json = json.dumps(safe_sub)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{
    width: {width}px; height: {height}px; overflow: hidden;
    background: #04050b; color: #f8fafc;
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
  }}
  canvas {{ position: absolute; inset: 0; width: 100%; height: 100%; display: block; }}
</style>
</head>
<body>
  <canvas id="stage" width="{width}" height="{height}"></canvas>
  <script>
    const cv = document.getElementById('stage');
    const ctx = cv.getContext('2d');
    const W = cv.width, H = cv.height, T = {max(0.5, duration):.3f};
    const WORDS = {words_json};
    const SUB = {sub_json};
    function spring(t, t0) {{
      const x = Math.max(0, t - t0);
      if (x <= 0) return 0;
      return 1 - Math.exp(-9.5 * x) * Math.cos(14.0 * x);
    }}
    function clamp01(v) {{ return Math.max(0, Math.min(1, v)); }}
    function easeOutExpo(x) {{ const c = clamp01(x); return c >= 1 ? 1 : 1 - Math.pow(2, -10 * c); }}
    function hash(n) {{ const s = Math.sin(n * 127.1 + 311.7) * 43758.5453; return s - Math.floor(s); }}
    window.setAnimationTime = function(t) {{
      const p = clamp01(t / T);
      const beatFrac = (t * 2.0) % 1.0;
      const beatPulse = Math.exp(-6.5 * beatFrac);
      const dropImpact = Math.exp(-13.0 * Math.max(0, t - 0.12)) + Math.exp(-12.0 * Math.max(0, (t % 2.0)));
      const shakeX = Math.sin(t * 78.0) * dropImpact * 4.5;
      const shakeY = Math.cos(t * 64.0) * dropImpact * 3.0;
      const camScale = 1.0 + 0.045 * beatPulse + 0.075 * Math.sin(p * Math.PI);
      ctx.save();
      ctx.fillStyle = '#04050b';
      ctx.fillRect(0, 0, W, H);
      const rg = ctx.createRadialGradient(W * 0.5, H * 0.44, 10, W * 0.5, H * 0.44, Math.max(W, H) * 0.72);
      rg.addColorStop(0, `rgba(56, 189, 248, ${{0.22 + 0.16 * beatPulse}})`);
      rg.addColorStop(0.45, 'rgba(139, 92, 246, 0.12)');
      rg.addColorStop(1, 'rgba(4, 5, 11, 0)');
      ctx.fillStyle = rg;
      ctx.fillRect(0, 0, W, H);

      ctx.translate(W * 0.5 + shakeX, H * 0.5 + shakeY);
      ctx.scale(camScale, camScale);
      ctx.rotate(Math.sin(p * Math.PI * 2) * 0.016);
      ctx.translate(-W * 0.5, -H * 0.5);

      // Perspective synth floor & parallax atmospheric bokeh depth
      ctx.strokeStyle = `rgba(56, 189, 248, ${{0.11 + 0.09 * beatPulse}})`;
      ctx.lineWidth = 1;
      const horizon = H * 0.69;
      for (let i = -9; i <= 9; i++) {{
        ctx.beginPath();
        ctx.moveTo(W * 0.5 + i * W * 0.028, horizon);
        ctx.lineTo(W * 0.5 + i * W * 0.23, H + 40);
        ctx.stroke();
      }}
      for (let i = 0; i < 68; i++) {{
        const z = ((hash(i) + t * (0.24 + 0.22 * hash(i + 9))) % 1.0);
        const px = W * 0.5 + (hash(i + 20) - 0.5) * W * (0.36 + z * 1.15);
        const py = H * 0.45 + (hash(i + 40) - 0.5) * H * (0.36 + z * 0.92);
        const r = i % 11 === 0 ? (10 + z * 28) : (1.0 + z * 3.4);
        ctx.beginPath();
        ctx.arc(px, py, r, 0, Math.PI * 2);
        ctx.fillStyle = i % 11 === 0
          ? (i % 2 === 0 ? 'rgba(56,189,248,0.06)' : 'rgba(244,114,182,0.06)')
          : (i % 3 === 0 ? `rgba(244,114,182,${{0.18 + z * 0.5}})` : `rgba(125,211,252,${{0.15 + z * 0.5}})`);
        ctx.fill();
      }}

      // Orbital reticle rings behind primary headline
      const minDim = Math.min(W, H);
      ctx.save();
      ctx.translate(W * 0.5, H * 0.45);
      ctx.rotate(t * 0.42);
      ctx.strokeStyle = `rgba(56,189,248,${{0.16 + 0.14 * beatPulse}})`;
      ctx.lineWidth = 1.5;
      ctx.setLineDash([minDim * 0.06, minDim * 0.03]);
      ctx.beginPath();
      ctx.arc(0, 0, minDim * (0.31 + 0.02 * beatPulse), 0, Math.PI * 2);
      ctx.stroke();
      ctx.rotate(-t * 0.78);
      ctx.strokeStyle = 'rgba(244,114,182,0.16)';
      ctx.setLineDash([minDim * 0.025, minDim * 0.04]);
      ctx.beginPath();
      ctx.arc(0, 0, minDim * 0.24, 0, Math.PI * 2);
      ctx.stroke();
      ctx.restore();

      // Editorial top pill + directional mask-wiped headline stack
      const baseSize = Math.round(minDim * (WORDS.length >= 4 ? 0.082 : 0.098));
      const lineStep = baseSize * 1.1;
      const totalH = WORDS.length * lineStep;
      const startY = H * 0.46 - totalH * 0.5 + baseSize * 0.54;
      const badgeP = easeOutExpo(t * 2.2);
      ctx.save();
      ctx.globalAlpha = badgeP;
      ctx.fillStyle = 'rgba(15, 23, 42, 0.72)';
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.lineWidth = 1.2;
      const bw = Math.min(W * 0.54, minDim * 0.42), bh = Math.max(24, Math.round(minDim * 0.04));
      const bx = W * 0.5 - bw * 0.5, by = startY - baseSize * 0.85 - bh - 12;
      ctx.beginPath();
      ctx.roundRect(bx, by, bw, bh, bh * 0.5);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = '#7dd3fc';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.font = `700 ${{Math.max(10, Math.round(bh * 0.42))}}px "Segoe UI", system-ui, sans-serif`;
      ctx.fillText('STUDIO KINETIC SEQUENCE', W * 0.5, by + bh * 0.52);
      ctx.restore();

      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      WORDS.forEach((word, idx) => {{
        const sp = spring(t, idx * 0.22 + 0.06);
        const maskP = easeOutExpo((t - idx * 0.20) * 1.85);
        const dir = idx % 2 === 0 ? -1 : 1;
        const offsetX = (1 - sp) * dir * W * 0.24;
        const y = startY + idx * lineStep;
        const rgbSplit = (beatPulse * 6.5 + dropImpact * 5.0) * sp;
        ctx.save();
        ctx.beginPath();
        ctx.rect(0, y - lineStep * 0.54, W * (0.1 + 0.9 * maskP), lineStep * 1.08);
        ctx.clip();
        ctx.globalAlpha = clamp01(sp);
        ctx.font = `900 ${{baseSize}}px "Segoe UI", system-ui, sans-serif`;
        if (rgbSplit > 0.6) {{
          ctx.fillStyle = 'rgba(244, 63, 94, 0.58)';
          ctx.fillText(word, W * 0.5 + offsetX - rgbSplit, y);
          ctx.fillStyle = 'rgba(34, 211, 238, 0.58)';
          ctx.fillText(word, W * 0.5 + offsetX + rgbSplit, y);
        }}
        ctx.fillStyle = idx === 1 ? '#38bdf8' : (idx === 3 ? '#f472b6' : '#f8fafc');
        ctx.fillText(word, W * 0.5 + offsetX, y);
        ctx.restore();
      }});

      // Animated gradient accent divider + tracked subtitle
      const ruleY = startY + totalH - baseSize * 0.14;
      const ruleP = easeOutExpo((t - 0.35) * 1.6);
      const rw = minDim * 0.44 * ruleP;
      if (rw > 2) {{
        const lg = ctx.createLinearGradient(W * 0.5 - rw * 0.5, ruleY, W * 0.5 + rw * 0.5, ruleY);
        lg.addColorStop(0, '#38bdf8');
        lg.addColorStop(1, '#ec4899');
        ctx.fillStyle = lg;
        ctx.fillRect(W * 0.5 - rw * 0.5, ruleY, rw, 3);
      }}
      const subAlpha = clamp01((t - 0.48) * 1.8);
      ctx.globalAlpha = subAlpha;
      ctx.fillStyle = '#cbd5e1';
      ctx.font = `600 ${{Math.round(minDim * 0.025)}}px "Segoe UI", system-ui, sans-serif`;
      ctx.fillText(SUB.toUpperCase(), W * 0.5, ruleY + Math.round(minDim * 0.048));
      ctx.restore();

      // Viewfinder HUD brackets & broadcast timeline bar
      const pad = Math.round(minDim * 0.045), bLen = Math.round(minDim * 0.032);
      ctx.strokeStyle = 'rgba(148, 163, 184, 0.42)';
      ctx.lineWidth = 2;
      [[pad, pad, 1, 1], [W - pad, pad, -1, 1], [pad, H - pad, 1, -1], [W - pad, H - pad, -1, -1]].forEach(([cx, cy, dx, dy]) => {{
        ctx.beginPath();
        ctx.moveTo(cx + dx * bLen, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * bLen);
        ctx.stroke();
      }});
      ctx.fillStyle = 'rgba(255,255,255,0.16)';
      ctx.fillRect(W * 0.08, H - 30, W * 0.84, 3);
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(W * 0.08, H - 30, W * 0.84 * p, 3);
    }};
    window.setAnimationTime(0);
  </script>
</body>
</html>"""


def _synthesize_studio_audio_wav(out_wav: Path, duration_seconds: float, preset: str = "kinetic_pulse") -> None:
    """Synthesize deterministic beat-locked stereo PCM SFX + warm harmonic bed."""
    sr = 44100
    n_samples = max(sr // 2, int(round(max(0.5, duration_seconds) * sr)))
    p_name = (preset or "kinetic_pulse").strip().lower()
    if p_name == "auto":
        p_name = "kinetic_pulse"
    bpm = 128.0 if p_name == "cyber_bass" else 90.0 if p_name == "minimal_clean" else 120.0
    beat_sec = 60.0 / bpm
    buf = array.array("h", [0] * (n_samples * 2))
    two_pi = 2.0 * math.pi
    inv_sr = 1.0 / sr
    pad_freqs = (130.81, 196.00, 293.66) if p_name != "cyber_bass" else (110.0, 164.81, 220.0)

    for i in range(n_samples):
        t = i * inv_sr
        beat_idx = int(t / beat_sec)
        bt = t - beat_idx * beat_sec
        # Kick / low impact every beat (stronger on downbeat every 4 beats)
        kick_env = math.exp(-bt * (18.0 if p_name == "minimal_clean" else 13.0))
        kick_freq = 44.0 + 78.0 * math.exp(-bt * 28.0)
        kick = math.sin(two_pi * kick_freq * bt) * kick_env * (0.48 if beat_idx % 4 == 0 else 0.34)
        # Tight offbeat click / hat transient
        half_bt = (t + beat_sec * 0.5) % beat_sec
        tick_env = math.exp(-half_bt * 85.0)
        tick = math.sin(two_pi * 3400.0 * half_bt + math.sin(two_pi * 1700.0 * t)) * tick_env * (0.06 if p_name == "minimal_clean" else 0.11)
        # Atmospheric warm harmonic shimmer
        shimmer = 0.0
        for fi, freq in enumerate(pad_freqs):
            shimmer += math.sin(two_pi * freq * t + 0.35 * math.sin(two_pi * (0.25 + fi * 0.11) * t))
        pad = (shimmer / len(pad_freqs)) * 0.14
        # Smooth fade-in and fade-out
        env_master = min(1.0, t / 0.06) * min(1.0, max(0.0, (duration_seconds - t) / 0.28))
        l_val = (kick + pad + tick * 0.85) * env_master
        r_val = (kick + pad * 0.96 - tick * 0.85) * env_master
        buf[2 * i] = max(-32767, min(32767, int(l_val * 28000)))
        buf[2 * i + 1] = max(-32767, min(32767, int(r_val * 28000)))

    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(buf.tobytes())


def _check_rendered_frames_qc(frames_dir: Path, total_frames: int) -> dict[str, Any]:
    """Verify rendered keyframes are non-blank and record visual motion metrics."""
    from PIL import Image, ImageChops, ImageStat

    sample_indices = sorted({max(0, min(total_frames - 1, int(total_frames * frac))) for frac in (0.15, 0.5, 0.85)})
    samples: list[Image.Image] = []
    peak_stddev = 0.0
    for idx in sample_indices:
        fp = frames_dir / f"frame_{idx:05d}.jpg"
        if not fp.is_file():
            continue
        with Image.open(fp) as im:
            rgb = im.convert("RGB")
            rgb.load()
            samples.append(rgb)
            st = ImageStat.Stat(rgb)
            peak_stddev = max(peak_stddev, max(st.stddev))

    if samples and peak_stddev < 2.0:
        raise HinaaError(
            "RENDER_QC_FAILED",
            "Rendered HTML animation produced blank/solid frames with no visible graphics.",
            422,
            True,
        )
    motion_delta = 0.0
    if len(samples) >= 2:
        diff = ImageChops.difference(samples[0], samples[-1])
        motion_delta = sum(ImageStat.Stat(diff).mean) / 3.0
    return {
        "sampled_frames": len(samples),
        "peak_luma_stddev": round(peak_stddev, 2),
        "motion_delta": round(motion_delta, 2),
    }


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


def _launch_studio_browser(pw: Any) -> Any:
    options: dict[str, Any] = {"headless": True}
    configured = os.environ.get("HINAA_CHROMIUM_EXECUTABLE", "").strip()
    if configured:
        if not Path(configured).is_file():
            raise HinaaError("CHROMIUM_MISSING", "Configured Chromium executable does not exist", 500, True)
        options["executable_path"] = configured
    elif not Path(pw.chromium.executable_path).is_file():
        system = shutil.which("chromium") or shutil.which("google-chrome")
        if system:
            options["executable_path"] = system
    return pw.chromium.launch(**options)


_STUDIO_FX_SCRIPT = """<script>
(function () {
  if (window.StudioFX) return;
  function spring(t, t0, stiffness, damping) {
    const dt = Math.max(0, t - (t0 || 0));
    if (dt <= 0) return 0;
    const k = stiffness || 140;
    const d = damping || 14;
    return 1 - Math.exp(-d * dt * 0.65) * Math.cos(Math.sqrt(k) * dt);
  }
  function easeOutExpo(x) {
    const c = Math.max(0, Math.min(1, x));
    return c >= 1 ? 1 : 1 - Math.pow(2, -10 * c);
  }
  function easeInOutCubic(x) {
    const c = Math.max(0, Math.min(1, x));
    return c < 0.5 ? 4 * c * c * c : 1 - Math.pow(-2 * c + 2, 3) / 2;
  }
  function beat(t, bpm) {
    const b = ((Math.max(0, t) * (bpm || 120)) / 60);
    const index = Math.floor(b);
    const frac = b - index;
    return { index, frac, pulse: Math.exp(-6.5 * frac), bar: Math.floor(index / 4), isDrop: index % 4 === 0 && frac < 0.35 };
  }
  function hash(n) {
    const s = Math.sin(n * 127.1 + 311.7) * 43758.5453123;
    return s - Math.floor(s);
  }
  function drawGlow(ctx, x, y, r, color) {
    const g = ctx.createRadialGradient(x, y, 0, x, y, r);
    g.addColorStop(0, color || 'rgba(56,189,248,0.28)');
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fill();
  }
  function drawStarfield(ctx, w, h, t, count, colA, colB) {
    const n = count || 70;
    for (let i = 0; i < n; i++) {
      const z = (hash(i) + t * (0.22 + 0.25 * hash(i + 7))) % 1.0;
      const px = w * 0.5 + (hash(i + 19) - 0.5) * w * (0.35 + z * 1.15);
      const py = h * 0.48 + (hash(i + 37) - 0.5) * h * (0.35 + z * 0.95);
      ctx.beginPath();
      ctx.arc(px, py, 0.9 + z * 3.2, 0, Math.PI * 2);
      ctx.fillStyle = (i % 3 === 0 ? colB : colA) || 'rgba(125,211,252,0.55)';
      ctx.globalAlpha = 0.2 + z * 0.7;
      ctx.fill();
    }
    ctx.globalAlpha = 1;
  }
  function drawPerspectiveGrid(ctx, w, h, t, strokeStyle, horizonRatio) {
    const hor = h * (horizonRatio || 0.66);
    ctx.save();
    ctx.strokeStyle = strokeStyle || 'rgba(56,189,248,0.16)';
    ctx.lineWidth = 1;
    for (let i = -9; i <= 9; i++) {
      ctx.beginPath();
      ctx.moveTo(w * 0.5 + i * w * 0.028, hor);
      ctx.lineTo(w * 0.5 + i * w * 0.23, h + 40);
      ctx.stroke();
    }
    const scroll = (t * 0.65) % 1.0;
    for (let r = 0; r < 8; r++) {
      const p = Math.pow((r + scroll) / 8, 1.8);
      const y = hor + (h - hor) * p;
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(w, y);
      ctx.stroke();
    }
    ctx.restore();
  }
  function drawSweepFlare(ctx, w, h, progress, color) {
    if (progress <= 0 || progress >= 1) return;
    const x = -w * 0.25 + progress * w * 1.5;
    ctx.save();
    const lg = ctx.createLinearGradient(x - w * 0.12, 0, x + w * 0.12, h);
    lg.addColorStop(0, 'rgba(255,255,255,0)');
    lg.addColorStop(0.5, color || 'rgba(255,255,255,0.22)');
    lg.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = lg;
    ctx.fillRect(0, 0, w, h);
    ctx.restore();
  }
  function drawChromaticText(ctx, text, x, y, splitPx, color, font, align) {
    ctx.save();
    if (font) ctx.font = font;
    ctx.textAlign = align || 'center';
    ctx.textBaseline = 'middle';
    const sp = splitPx || 0;
    if (sp > 0.5) {
      ctx.fillStyle = 'rgba(244,63,94,0.55)';
      ctx.fillText(text, x - sp, y);
      ctx.fillStyle = 'rgba(34,211,238,0.55)';
      ctx.fillText(text, x + sp, y);
    }
    ctx.fillStyle = color || '#f8fafc';
    ctx.fillText(text, x, y);
    ctx.restore();
  }
  function maskRevealText(ctx, text, x, y, progress, color, font, align, slidePx) {
    const p = easeOutExpo(progress);
    if (p <= 0.01) return;
    ctx.save();
    if (font) ctx.font = font;
    ctx.textAlign = align || 'center';
    ctx.textBaseline = 'middle';
    const sz = parseInt((font || '48px').match(/(\\d+)px/)?.[1] || '48', 10);
    const clipH = sz * 1.45;
    ctx.beginPath();
    ctx.rect(0, y - clipH * 0.5, (ctx.canvas?.width || 1920), clipH * p);
    ctx.clip();
    ctx.globalAlpha = Math.min(1, p * 1.15);
    ctx.fillStyle = color || '#f8fafc';
    ctx.fillText(text, x, y + (1 - p) * (slidePx ?? sz * 0.45));
    ctx.restore();
  }
  function drawBokehField(ctx, w, h, t, count, colA, colB) {
    const n = count || 18;
    ctx.save();
    for (let i = 0; i < n; i++) {
      const x = ((hash(i * 3 + 1) + Math.sin(t * (0.2 + 0.15 * hash(i)) + i) * 0.08) * w);
      const y = ((hash(i * 7 + 2) + Math.cos(t * (0.18 + 0.12 * hash(i + 5)) + i) * 0.08) * h);
      const r = (0.018 + 0.045 * hash(i + 11)) * Math.min(w, h);
      drawGlow(ctx, x, y, r, (i % 2 === 0 ? colA : colB) || (i % 2 === 0 ? 'rgba(56,189,248,0.16)' : 'rgba(244,114,182,0.14)'));
    }
    ctx.restore();
  }
  function drawKineticRule(ctx, x1, y1, x2, y2, progress, color, lineWidth) {
    const p = easeOutExpo(progress);
    if (p <= 0.01) return;
    ctx.save();
    ctx.strokeStyle = color || '#38bdf8';
    ctx.lineWidth = lineWidth || 3;
    ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x1 + (x2 - x1) * p, y1 + (y2 - y1) * p);
    ctx.stroke();
    ctx.restore();
  }
  function drawHUDCorners(ctx, w, h, pad, size, color, alpha) {
    const p = pad || 36, s = size || 24;
    ctx.save();
    ctx.globalAlpha = alpha ?? 0.45;
    ctx.strokeStyle = color || '#94a3b8';
    ctx.lineWidth = 2;
    [[p, p, 1, 1], [w - p, p, -1, 1], [p, h - p, 1, -1], [w - p, h - p, -1, -1]].forEach(([cx, cy, dx, dy]) => {
      ctx.beginPath();
      ctx.moveTo(cx + dx * s, cy); ctx.lineTo(cx, cy); ctx.lineTo(cx, cy + dy * s);
      ctx.stroke();
    });
    ctx.restore();
  }
  function cameraShake(t, dropTimes, amp) {
    let sx = 0, sy = 0;
    const a = amp || 8;
    for (const d of (dropTimes || [0])) {
      const dt = t - d;
      if (dt >= 0 && dt < 0.45) {
        const dec = Math.exp(-15 * dt);
        sx += Math.sin(dt * 72) * a * dec;
        sy += Math.cos(dt * 63) * a * 0.7 * dec;
      }
    }
    return { x: sx, y: sy };
  }
  function graphemes(text) {
    if (typeof Intl !== 'undefined' && typeof Intl.Segmenter === 'function') {
      return Array.from(new Intl.Segmenter(undefined, { granularity: 'grapheme' }).segment(String(text || '')), (s) => s.segment);
    }
    return String(text || '').split(/\\s+/);
  }
  window.StudioFX = {
    spring, easeOutExpo, easeInOutCubic, beat, hash,
    drawGlow, drawStarfield, drawBokehField, drawPerspectiveGrid,
    drawSweepFlare, drawChromaticText, maskRevealText, drawKineticRule,
    drawHUDCorners, cameraShake, graphemes,
  };
})();
</script>"""


def _inject_studio_fx(html_code: str) -> str:
    if "</head>" in html_code:
        return html_code.replace("</head>", f"{_STUDIO_FX_SCRIPT}\n</head>", 1)
    if "<body" in html_code:
        idx = html_code.find("<body")
        return html_code[:idx] + _STUDIO_FX_SCRIPT + "\n" + html_code[idx:]
    return _STUDIO_FX_SCRIPT + "\n" + html_code


def _save_vision_storyboard(frames_dir: Path, total_frames: int) -> str | None:
    """Create a 2x2 contact-sheet JPEG under `.hina/previews/` for multimodal vision self-review."""
    try:
        from PIL import Image

        from ..runtime_paths import project_root

        previews_dir = project_root() / ".hina" / "previews"
        previews_dir.mkdir(parents=True, exist_ok=True)
        indices = [
            max(0, min(total_frames - 1, int(total_frames * frac)))
            for frac in (0.10, 0.35, 0.65, 0.90)
        ]
        tiles: list[Image.Image] = []
        tw, th = 420, 260
        for idx in indices:
            fp = frames_dir / f"frame_{idx:05d}.jpg"
            if fp.is_file():
                with Image.open(fp) as im:
                    rgb = im.convert("RGB")
                    rgb.thumbnail((tw, th))
                    tile = Image.new("RGB", (tw, th), (8, 10, 18))
                    tile.paste(rgb, ((tw - rgb.width) // 2, (th - rgb.height) // 2))
                    tiles.append(tile)
        if not tiles:
            return None
        sheet = Image.new("RGB", (tw * 2, th * 2), (6, 8, 14))
        for i, tile in enumerate(tiles[:4]):
            sheet.paste(tile, ((i % 2) * tw, (i // 2) * th))
        out_path = previews_dir / f"sb_{uuid.uuid4().hex[:10]}.jpg"
        sheet.save(out_path, format="JPEG", quality=82)
        return str(out_path)
    except Exception:
        return None


def _render_html_sync(
    *,
    html_code: str,
    width: int,
    height: int,
    fps: int,
    duration_seconds: float,
    audio_path: str | None,
    normalize_audio: bool,
    audio_preset: str = "auto",
    audio_start_seconds: float = 0.0,
) -> tuple[bytes, dict[str, Any]]:
    from playwright.sync_api import sync_playwright

    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise HinaaError("FFMPEG_MISSING", "ffmpeg is required to encode MP4 output.", 500, True)

    total_frames = max(2, int(round(duration_seconds * fps)))
    injected_html = _inject_studio_fx(html_code)
    with tempfile.TemporaryDirectory(prefix="hinaa_code_anim_") as tmp:
        tmp_path = Path(tmp)
        html_file = tmp_path / "scene.html"
        html_file.write_text(injected_html, encoding="utf-8")
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as pw:
            browser = _launch_studio_browser(pw)
            try:
                context = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=1)
                page = context.new_page()
                page_errors: list[str] = []
                page.on("pageerror", lambda err: page_errors.append(str(err)))

                # Fail closed on outbound HTTP(S) inside rendered scene HTML to prevent SSRF/exfiltration
                def _route_guard(route: Any) -> None:
                    url = str(route.request.url or "").lower()
                    if url.startswith("file://") or url.startswith("data:") or url.startswith("blob:") or url.startswith("about:"):
                        route.continue_()
                    else:
                        route.abort()

                page.route("**/*", _route_guard)
                page.goto(html_file.as_uri(), wait_until="load", timeout=15_000)
                page.evaluate("async () => { if (window.__motionReady) await window.__motionReady; await document.fonts.ready; }")

                for idx in range(total_frames):
                    t_sec = idx / float(fps)
                    t_ms = t_sec * 1000.0
                    page.evaluate(
                        """async ([tSec, tMs]) => {
                            if (typeof window.setAnimationTime === 'function') {
                                await window.setAnimationTime(tSec);
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
                    if page_errors:
                        raise HinaaError("RENDER_JS_ERROR", page_errors[0][:500], 422, True)
                    frame_path = frames_dir / f"frame_{idx:05d}.jpg"
                    page.screenshot(path=str(frame_path), type="jpeg", quality=92)
            finally:
                browser.close()

        qc_stats = _check_rendered_frames_qc(frames_dir, total_frames)
        storyboard_path = _save_vision_storyboard(frames_dir, total_frames)

        raw_mp4 = tmp_path / "video_only.mp4"
        final_mp4 = tmp_path / "final.mp4"
        enc_cmd = [
            ffmpeg, "-y",
            "-framerate", str(fps),
            "-i", str(frames_dir / "frame_%05d.jpg"),
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
            str(raw_mp4),
        ]
        enc_proc = subprocess.run(enc_cmd, capture_output=True, text=True, timeout=300)
        if enc_proc.returncode != 0:
            raise HinaaError("RENDER_FAILED", f"FFmpeg encode failed: {enc_proc.stderr[-400:]}", 502, True)

        audio_input: Path | None = None
        if audio_path:
            audio_input = _resolve_confined_media_path(audio_path, code="BAD_AUDIO_PATH", label="Audio")
        elif (audio_preset or "auto").strip().lower() != "none":
            synth_wav = tmp_path / "studio_pulse.wav"
            _synthesize_studio_audio_wav(synth_wav, duration_seconds, preset=audio_preset)
            audio_input = synth_wav

        if audio_input is not None:
            mix_cmd = [
                ffmpeg, "-y",
                "-i", str(raw_mp4), "-ss", str(audio_start_seconds if audio_path else 0), "-i", str(audio_input),
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
        probe["qc"] = qc_stats
        if storyboard_path:
            probe["_vision_preview_path"] = storyboard_path
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
    composition_json: dict[str, Any] | None = Field(None, description="Editable local motion composition: scenes, layered text/images/video, keyframes, camera moves and transitions. See docs/creative/LOCAL_MOTION_STUDIO.md.")
    inspect_only: bool = Field(False, description="Return measured audio accents/reference cut candidates without rendering or generating media.")
    reference_path: str | None = Field(None, max_length=500, description="Optional workspace video to analyze for candidate cuts; does not perform neural motion transfer.")
    audio_start_seconds: float = Field(0, ge=0, le=86400, description="Trim position in the supplied soundtrack; preserves pitch and speed.")
    duration_seconds: float = Field(5.0, ge=0.5, le=30.0, description="Duration in seconds (0.5..30).")
    fps: int = Field(24, ge=1, le=60, description="Frames per second (1..60).")
    width: int = Field(1080, ge=64, le=1920, description="Output width in pixels.")
    height: int = Field(1920, ge=64, le=1920, description="Output height in pixels.")
    preview: bool = Field(False, description="When true, renders fast 480p@30fps draft for rapid approval.")
    audio_path: str | None = Field(None, max_length=500, description="Optional .mp3/.wav path inside workspace/data.")
    audio_preset: str = Field("auto", max_length=40, description="Built-in beat/SFX synth when audio_path omitted: auto, kinetic_pulse, cyber_bass, minimal_clean, none.")
    normalize_audio: bool = Field(True, description="Apply EBU R128 loudness normalization (-14 LUFS) to audio.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override for html_path.")
    userId: str = Field("default_user", max_length=120)

    @model_validator(mode="before")
    @classmethod
    def _coerce_aliases_and_even_dims(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if not out.get("html_code") and isinstance(out.get("html"), str):
            out["html_code"] = out["html"]
        if not out.get("html_path"):
            p = out.get("path") or out.get("file_path")
            if isinstance(p, str):
                out["html_path"] = p
        if "duration_seconds" not in out and out.get("duration") is not None:
            out["duration_seconds"] = out["duration"]
        prompt_fb = out.get("prompt") or out.get("description") or out.get("topic")
        if not out.get("title") and isinstance(prompt_fb, str) and prompt_fb.strip():
            first = prompt_fb.strip().splitlines()[0].strip()
            out["title"] = first[:140] or "HINAA Kinetic Animation"
            if not out.get("subtitle"):
                out["subtitle"] = prompt_fb.strip()[:240]
        elif isinstance(out.get("title"), str):
            out["title"] = out["title"].strip()[:140] or "HINAA Kinetic Animation"
        if isinstance(out.get("subtitle"), str):
            out["subtitle"] = out["subtitle"].strip()[:240]
        if out.get("duration_seconds") is not None:
            try:
                out["duration_seconds"] = max(0.5, min(30.0, float(out["duration_seconds"])))
            except (TypeError, ValueError):
                pass
        if out.get("fps") is not None:
            try:
                out["fps"] = max(1, min(60, int(round(float(out["fps"])))))
            except (TypeError, ValueError):
                pass
        for dim_k in ("width", "height"):
            if out.get(dim_k) is not None:
                try:
                    val = max(64, min(1920, int(round(float(out[dim_k])))))
                    out[dim_k] = (val // 2) * 2
                except (TypeError, ValueError):
                    pass
        if isinstance(out.get("composition_json"), dict):
            from ..agent.hooks import apply_guards

            out = apply_guards("render_code_animation", out)
        return out


async def render_code_animation_handler(params: RenderCodeAnimationParams) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    width, height, fps = params.width, params.height, params.fps
    duration = params.duration_seconds
    analysis: dict[str, Any] = {}
    source_project: dict[str, str] | None = None
    motion_spec = None
    if params.composition_json is not None or params.inspect_only or params.reference_path:
        from ..agent.hooks import apply_guards
        from ..motion_studio import MotionComposition
        from ..motion_studio.analysis import analyze_audio, analyze_reference
        from ..motion_studio.compiler import confined_path
        from .workspace_coding_tools import _resolve_workspace_root

        ws_root = _resolve_workspace_root(params.workspace_root)
        if params.composition_json is not None:
            if params.timeline_json or params.html_code or params.html_path:
                raise HinaaError("AMBIGUOUS_MOTION_SOURCE", "Use one of composition_json, timeline_json or HTML", 422, False)
            guarded = apply_guards("render_code_animation", {"composition_json": dict(params.composition_json)})
            motion_spec = MotionComposition.model_validate(guarded["composition_json"])
            duration = motion_spec.duration
        if params.audio_path:
            audio_file = confined_path(params.audio_path, ws_root)
            analysis["audio"] = await asyncio.to_thread(analyze_audio, audio_file, params.audio_start_seconds, duration)
            if motion_spec is not None and not params.inspect_only and analysis["audio"]["duration_seconds"] < duration - 0.05:
                raise HinaaError("AUDIO_TOO_SHORT", "The selected soundtrack trim is shorter than the composition", 422, False)
        if params.reference_path:
            reference_file = confined_path(params.reference_path, ws_root)
            analysis["reference"] = await asyncio.to_thread(analyze_reference, reference_file, duration)
        if params.inspect_only:
            return {"status": "success", "stage": "media_analysis", "analysis": analysis,
                    "composition_schema": MotionComposition.model_json_schema(),
                    "rendered": False, "external_video_api_calls": 0}
        if motion_spec is not None and not motion_spec.accents and "audio" in analysis:
            motion_spec.accents = [t for t in analysis["audio"]["accents"] if t < duration]
    if params.preview:
        scale = min(480.0 / max(1, min(width, height)), 1.0)
        width = max(64, int(round((width * scale) / 2.0) * 2))
        height = max(64, int(round((height * scale) / 2.0) * 2))
        fps = min(fps, 30)

    if motion_spec is not None:
        from ..motion_studio import compile_composition

        html_doc = compile_composition(motion_spec, ws_root, params.width, params.height)
        project_dir = (ws_root / "motion-projects" / uuid.uuid4().hex[:12]).resolve()
        if ws_root.resolve() not in project_dir.parents:
            raise HinaaError("WORKSPACE_ESCAPE", "Motion project path escapes workspace", 403, False)
        project_dir.mkdir(parents=True)
        (project_dir / "composition.json").write_text(motion_spec.model_dump_json(indent=2), encoding="utf-8")
        (project_dir / "preview.html").write_text(html_doc, encoding="utf-8")
        (project_dir / "analysis.json").write_text(json.dumps(analysis, indent=2), encoding="utf-8")
        source_project = {"composition": str((project_dir / "composition.json").relative_to(ws_root)),
                          "html": str((project_dir / "preview.html").relative_to(ws_root)),
                          "analysis": str((project_dir / "analysis.json").relative_to(ws_root))}
        mp4_bytes, probe = await asyncio.to_thread(
            _render_html_sync, html_code=html_doc, width=width, height=height, fps=fps,
            duration_seconds=duration, audio_path=str(audio_file) if params.audio_path else None,
            normalize_audio=params.normalize_audio, audio_preset=params.audio_preset,
            audio_start_seconds=params.audio_start_seconds,
        )
        renderer = "hina_motion_studio_local"
    elif params.timeline_json:
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
            audio_preset=params.audio_preset,
            audio_start_seconds=params.audio_start_seconds,
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
        duration_seconds=float(probe.get("duration_sec") or duration),
        fps=float(probe.get("fps") or fps),
    )
    completed_at = datetime.now(timezone.utc).isoformat()
    download_url = f"/v1/creative/assets/{meta.asset_id}/download"
    res_payload: dict[str, Any] = {
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
            "loudness_lufs": -14.0 if (probe.get("audio_channels", 0) and params.normalize_audio) else None,
            "qc": probe.get("qc"),
            "checksum_sha256": meta.sha256_hash,
        },
        "started_at": started_at,
        "completed_at": completed_at,
    }
    if probe.get("_vision_preview_path"):
        res_payload["_vision_preview_path"] = probe["_vision_preview_path"]
    if source_project is not None:
        res_payload["source_project"] = source_project
        res_payload["analysis"] = analysis
        res_payload["external_video_api_calls"] = 0
        res_payload["limitations"] = "Local composition of supplied assets. Does not synthesize character acting or clone proprietary Katana models."
    return res_payload


render_code_animation_def = ToolDefinition(
    name="render_code_animation",
    display_name="Studio: Render Code Animation (Playwright + FFmpeg)",
    description=(
        "Render custom HTML/CSS/SVG/Canvas animations (using window.setAnimationTime(t) or CSS keyframes) "
        "or CodeVideoTimeline JSON directly to a ffprobe-verified H.264 MP4 asset with optional -14 LUFS audio mixing. "
        "Runs network-isolated locally with zero paid video API credits."
        " For cinematic typography use composition_json (editable scenes/layers/keyframes, ten text motions, six transitions, camera moves, images and video);"
        " inspect_only measures supplied audio accents/reference cuts first. Pass the actual audio_path; never synthesize replacement music for a supplied song."
    ),
    parameters={
        "title": {"type": "string", "description": "Title for the rendered video."},
        "subtitle": {"type": "string", "description": "Subtitle used when auto-building kinetic HTML."},
        "html_code": {"type": "string", "description": "Optional self-contained HTML animation document."},
        "html_path": {"type": "string", "description": "Optional relative path to a workspace HTML file to render."},
        "timeline_json": {"type": "object", "description": "Optional CodeVideoTimeline JSON scene specification."},
        "composition_json": {"type": "object", "description": "MotionComposition v1: {scenes:[{duration,background,accent,camera,transition,layers:[{kind,text,path,start,end,x,y,size,height,max_width,align,color,motion,unit_times,keyframes}]}],accents:[seconds]}. Get the complete schema with inspect_only=true. Source JSON and offline preview HTML are saved."},
        "inspect_only": {"type": "boolean", "description": "Analyze audio/reference and return composition schema; do not render."},
        "reference_path": {"type": "string", "description": "Workspace reference video for approximate cut timing analysis (not neural motion transfer)."},
        "audio_start_seconds": {"type": "number", "description": "Trim offset into the supplied audio file in seconds."},
        "duration_seconds": {"type": "number", "description": "Video length in seconds (0.5..30)."},
        "fps": {"type": "integer", "description": "Frames per second (1..60)."},
        "width": {"type": "integer", "description": "Pixel width."},
        "height": {"type": "integer", "description": "Pixel height."},
        "preview": {"type": "boolean", "description": "Fast 480p preview render before final export."},
        "audio_path": {"type": "string", "description": "Optional workspace/data .mp3/.wav audio file."},
        "audio_preset": {"type": "string", "description": "Built-in beat/SFX audio synth when audio_path omitted: auto, kinetic_pulse, cyber_bass, minimal_clean, none."},
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


class WorkspaceVerifyHtmlParams(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=500, description="Relative path to the HTML file inside workspace root.")
    wait_ms: int = Field(700, ge=100, le=5000, description="Milliseconds to let scripts run before inspecting DOM & visual pixels.")
    width: int = Field(1280, ge=320, le=1920, description="Browser viewport width.")
    height: int = Field(800, ge=240, le=1200, description="Browser viewport height.")
    mobile: bool = Field(False, description="When true, inspect in a mobile viewport (390x844, is_mobile=True) and report horizontal overflow.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


def _inspect_page_sync(
    target_uri: str,
    *,
    allow_loopback: bool,
    wait_ms: int,
    width: int,
    height: int,
    mobile: bool = False,
) -> dict[str, Any]:
    from PIL import Image, ImageStat
    from playwright.sync_api import sync_playwright

    from ..runtime_paths import project_root

    eff_width = 390 if mobile else width
    eff_height = 844 if mobile else height
    page_errors: list[str] = []
    console_errors: list[str] = []
    previews_dir = project_root() / ".hina" / "previews"
    previews_dir.mkdir(parents=True, exist_ok=True)
    preview_path = previews_dir / f"page_{uuid.uuid4().hex[:10]}.jpg"

    with sync_playwright() as pw:
        browser = _launch_studio_browser(pw)
        try:
            context = browser.new_context(
                viewport={"width": eff_width, "height": eff_height},
                is_mobile=bool(mobile),
                device_scale_factor=2 if mobile else 1,
            )
            page = context.new_page()
            page.on("pageerror", lambda err: page_errors.append(str(err)[:300]))
            page.on(
                "console",
                lambda msg: console_errors.append(str(msg.text)[:300]) if msg.type == "error" else None,
            )

            def _route_guard(route: Any) -> None:
                url = str(route.request.url or "").lower()
                if url.startswith("file://") or url.startswith("data:") or url.startswith("blob:") or url.startswith("about:"):
                    route.continue_()
                elif allow_loopback and (
                    url.startswith("http://127.0.0.1")
                    or url.startswith("http://localhost")
                    or url.startswith("http://[::1]")
                ):
                    route.continue_()
                else:
                    route.abort()

            page.route("**/*", _route_guard)
            resp = page.goto(target_uri, wait_until="load", timeout=15_000)
            http_status = resp.status if resp is not None else None
            page.wait_for_timeout(wait_ms)
            dom_info = page.evaluate(
                """() => ({
                    title: document.title || "",
                    domElements: document.querySelectorAll("*").length,
                    canvasCount: document.querySelectorAll("canvas").length,
                    svgCount: document.querySelectorAll("svg").length,
                    textLength: (document.body?.innerText || "").trim().length,
                    scrollWidth: document.documentElement?.scrollWidth || 0,
                    scrollHeight: document.documentElement?.scrollHeight || 0,
                    innerWidth: window.innerWidth || 0,
                    horizontalOverflow: (document.documentElement?.scrollWidth || 0) > ((window.innerWidth || 0) + 2),
                    interactiveCount: document.querySelectorAll('a,button,input,select,textarea,[role="button"]').length,
                    headingCount: document.querySelectorAll('h1,h2,h3').length,
                    brokenImageCount: Array.from(document.querySelectorAll('img')).filter(img => !img.complete || img.naturalWidth === 0).length,
                })"""
            )
            page.screenshot(path=str(preview_path), type="jpeg", quality=82)
        finally:
            browser.close()

    with Image.open(preview_path) as im:
        rgb = im.convert("RGB")
        luma_stddev = round(max(ImageStat.Stat(rgb).stddev), 2)

    has_visual = luma_stddev >= 2.0
    ok = (not page_errors) and has_visual and dom_info.get("domElements", 0) > 2
    if http_status is not None and http_status >= 400:
        ok = False
    return {
        "status": "success" if ok else "error",
        "code": None if ok else "HTML_VERIFY_FAILED",
        "httpStatus": http_status,
        "title": dom_info.get("title", ""),
        "domElements": dom_info.get("domElements", 0),
        "canvasCount": dom_info.get("canvasCount", 0),
        "svgCount": dom_info.get("svgCount", 0),
        "textLength": dom_info.get("textLength", 0),
        "viewport": f"{390 if mobile else width}x{844 if mobile else height}",
        "mobile": bool(mobile),
        "innerWidth": dom_info.get("innerWidth", 390 if mobile else width),
        "scrollWidth": dom_info.get("scrollWidth", 0),
        "scrollHeight": dom_info.get("scrollHeight", 0),
        "horizontalOverflow": bool(dom_info.get("horizontalOverflow", False)),
        "interactiveCount": dom_info.get("interactiveCount", 0),
        "headingCount": dom_info.get("headingCount", 0),
        "brokenImageCount": dom_info.get("brokenImageCount", 0),
        "lumaStddev": luma_stddev,
        "hasVisualRender": has_visual,
        "pageErrors": page_errors[:10],
        "consoleErrors": console_errors[:10],
        "_vision_preview_path": str(preview_path),
        "error": (
            f"Page verification failed: httpStatus={http_status}, pageErrors={page_errors[:2]}, hasVisualRender={has_visual}"
            if not ok
            else None
        ),
    }


def _verify_html_sync(html_file: Path, *, wait_ms: int, width: int, height: int, mobile: bool = False) -> dict[str, Any]:
    return _inspect_page_sync(html_file.as_uri(), allow_loopback=False, wait_ms=wait_ms, width=width, height=height, mobile=mobile)


class WorkspaceVerifyUrlParams(BaseModel):
    url: str = Field(..., min_length=10, max_length=500, description="Local loopback URL (http://127.0.0.1:... or http://localhost:...).")
    wait_ms: int = Field(800, ge=100, le=5000, description="Wait ms before inspecting DOM & visual pixels.")
    width: int = Field(1280, ge=320, le=1920, description="Desktop viewport width.")
    height: int = Field(800, ge=240, le=1200, description="Desktop viewport height.")
    mobile: bool = Field(False, description="When true, inspect in a mobile viewport (390x844, is_mobile=True) and report horizontal overflow.")


async def workspace_verify_url_handler(params: WorkspaceVerifyUrlParams) -> dict[str, Any]:
    from urllib.parse import urlparse

    parsed = urlparse(params.url.strip())
    if parsed.scheme != "http" or (parsed.hostname or "").lower() not in {"127.0.0.1", "localhost", "::1"}:
        return {
            "status": "error",
            "code": "LOOPBACK_ONLY_BLOCKED",
            "error": "workspace_verify_url only accepts http://127.0.0.1 or http://localhost URLs.",
        }
    res = await asyncio.to_thread(
        _inspect_page_sync,
        params.url.strip(),
        allow_loopback=True,
        wait_ms=params.wait_ms,
        width=params.width,
        height=params.height,
        mobile=params.mobile,
    )
    res["url"] = params.url.strip()
    return res


async def workspace_verify_html_handler(params: WorkspaceVerifyHtmlParams) -> dict[str, Any]:
    from .workspace_coding_tools import (
        _relative_posix,
        _resolve_inside_workspace,
        _resolve_workspace_root,
    )

    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}
    if not target.exists() or not target.is_file():
        return {"status": "error", "code": "FILE_NOT_FOUND", "error": f"HTML file not found: {params.file_path}"}

    res = await asyncio.to_thread(
        _verify_html_sync,
        target,
        wait_ms=params.wait_ms,
        width=params.width,
        height=params.height,
        mobile=params.mobile,
    )
    res["filePath"] = _relative_posix(root, target)
    return res


registry.register(
    ToolDefinition(
        name="workspace_verify_html",
        display_name="Workspace: Verify HTML Render in Chromium",
        description="Load a workspace HTML page in network-isolated headless Chromium and verify DOM elements, zero JS page/console errors, mobile responsiveness, and non-blank pixel rendering.",
        parameters={
            "file_path": {"type": "string", "description": "Relative HTML file path inside workspace."},
            "wait_ms": {"type": "integer", "description": "Wait duration in ms before DOM/pixel inspection (default 700)."},
            "width": {"type": "integer", "description": "Viewport width (default 1280)."},
            "height": {"type": "integer", "description": "Viewport height (default 800)."},
            "mobile": {"type": "boolean", "description": "Inspect mobile viewport (390x844) and check horizontal overflow."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["file_path"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        tool_effect=ToolEffect.READ,
        timeout_seconds=60,
    ),
    workspace_verify_html_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_verify_url",
        display_name="Workspace: Verify Loopback URL in Chromium",
        description="Load a running http://127.0.0.1 or http://localhost dev-server URL in Playwright and capture HTTP status, desktop/mobile layout metrics, JS errors, and screenshot preview.",
        parameters={
            "url": {"type": "string", "description": "Loopback URL such as http://127.0.0.1:8123/"},
            "wait_ms": {"type": "integer", "description": "Wait ms before inspecting DOM/pixels (default 800)."},
            "width": {"type": "integer", "description": "Viewport width (default 1280)."},
            "height": {"type": "integer", "description": "Viewport height (default 800)."},
            "mobile": {"type": "boolean", "description": "Inspect mobile viewport (390x844) and check horizontal overflow."},
        },
        required_parameters=["url"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        tool_effect=ToolEffect.READ,
        timeout_seconds=60,
    ),
    workspace_verify_url_handler,
)
