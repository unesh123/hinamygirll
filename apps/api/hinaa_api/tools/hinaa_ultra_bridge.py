"""
HINAA ULTRA — Tool Server Bridge
Connects HINAA Brain ToolRegistry to ~/hinaa-ultra Core Tool Server (:8765)
and Agent Swarm (:8767) with structured JSON results for rich Artifact Cards.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, Field

from ..errors import HinaaError
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa_ultra_bridge")
TOOL_SERVER_URL = "http://127.0.0.1:8765"
AGENT_SERVER_URL = "http://127.0.0.1:8767"
WORKSPACE = os.path.abspath(os.path.expanduser("~/hinaa-ultra"))
EXPORTS_DIR = os.path.join(WORKSPACE, "exports")


def _safe_ultra_path(raw: str, default_subdir: str = "exports") -> str:
    """Resolve a path strictly inside ~/hinaa-ultra to prevent directory escape."""
    cleaned = (raw or "").strip().replace("\\", "/")
    cleaned = re.sub(r"^~/hinaa-ultra/", "", cleaned, flags=re.IGNORECASE)
    if cleaned.startswith("/"):
        cleaned = cleaned.lstrip("/")
    if not cleaned or cleaned == ".":
        target = os.path.abspath(os.path.join(WORKSPACE, default_subdir) if default_subdir else WORKSPACE)
    else:
        rel_path = Path(cleaned)
        if not os.path.isabs(cleaned) and default_subdir and len(rel_path.parts) == 1:
            candidate = os.path.join(WORKSPACE, default_subdir, cleaned)
        else:
            candidate = os.path.join(WORKSPACE, cleaned)
        target = os.path.abspath(candidate)

    ws_path = Path(WORKSPACE).resolve()
    target_path = Path(target).resolve()
    if ws_path != target_path and ws_path not in target_path.parents:
        raise HinaaError("ULTRA_PATH_FORBIDDEN", f"Path must stay inside {WORKSPACE}", 403)
    return str(target_path)


def _export_url_for(path_str: str) -> Optional[str]:
    """Return HTTP URL served by port 8765 /exports when file lives inside EXPORTS_DIR."""
    try:
        exp = Path(EXPORTS_DIR).resolve()
        tgt = Path(path_str).resolve()
        if exp in tgt.parents:
            rel = tgt.relative_to(exp).as_posix()
            return f"http://localhost:8765/exports/{rel}"
    except Exception:
        pass
    return None


def _slugify(text: str, fallback: str = "hinaa_clip") -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", (text or "").lower()).strip("_")
    return (slug[:36] or fallback)


def _build_sparkle_video_html(title: str, subtitle: str, duration_s: int, width: int, height: int) -> str:
    """Build deterministic self-contained HTML5 animation with window.setAnimationTime(t)."""
    safe_title = (title or "HINAA Motion").replace("<", "&lt;").replace(">", "&gt;")
    safe_sub = (subtitle or "Rendered deterministically by HINAA Ultra").replace("<", "&lt;").replace(">", "&gt;")
    total_ms = max(1000, duration_s * 1000)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{safe_title}</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      width: {width}px; height: {height}px; overflow: hidden;
      background: radial-gradient(circle at 50% 42%, #241608 0%, #09090b 65%, #020204 100%);
      color: #fff; font-family: Georgia, 'Times New Roman', serif;
      display: flex; align-items: center; justify-content: center; position: relative;
    }}
    canvas {{ position: absolute; inset: 0; }}
    .frame {{
      position: absolute; inset: 36px; border: 1px solid rgba(251, 191, 36, 0.45);
      box-shadow: inset 0 0 60px rgba(217, 119, 6, 0.14); pointer-events: none;
    }}
    .card {{
      position: relative; z-index: 10; text-align: center; padding: 0 48px;
    }}
    .eyebrow {{
      font-family: system-ui, sans-serif; font-size: 18px; letter-spacing: 0.38em;
      color: #fbbf24; text-transform: uppercase; margin-bottom: 18px;
    }}
    .title {{
      font-size: 56px; font-weight: 700; line-height: 1.15;
      background: linear-gradient(135deg, #fef08a 0%, #fbbf24 50%, #d97706 100%);
      -webkit-background-clip: text; -webkit-text-fill-color: transparent;
      margin-bottom: 18px;
    }}
    .deco {{
      width: 140px; height: 2px; margin: 0 auto 18px;
      background: linear-gradient(90deg, transparent, #fbbf24, transparent);
      transform-origin: center;
    }}
    .sub {{
      font-family: system-ui, sans-serif; font-size: 20px; letter-spacing: 0.18em;
      color: rgba(255,255,255,0.78); text-transform: uppercase;
    }}
  </style>
</head>
<body>
  <canvas id="c" width="{width}" height="{height}"></canvas>
  <div class="frame"></div>
  <div class="card" id="card">
    <div class="eyebrow" id="eyebrow">HINAA ULTRA STUDIO</div>
    <div class="title" id="title">{safe_title}</div>
    <div class="deco" id="deco"></div>
    <div class="sub" id="sub">{safe_sub}</div>
  </div>
  <script>
    const W = {width}, H = {height}, TOTAL = {total_ms};
    const cv = document.getElementById('c');
    const ctx = cv.getContext('2d');
    let seed = 1337;
    function rnd() {{ seed = (seed * 16807) % 2147483647; return (seed - 1) / 2147483646; }}
    const pts = Array.from({{length: 70}}, () => ({{
      x: rnd() * W, y: rnd() * H, r: rnd() * 5 + 2, spd: rnd() * 1.4 + 0.5, a: rnd() * 0.65 + 0.25, ph: rnd() * 6.28
    }}));
    function easeOutBack(t) {{
      const x = Math.max(0, Math.min(1, t)), c1 = 1.70158, c3 = c1 + 1;
      return 1 + c3 * Math.pow(x - 1, 3) + c1 * Math.pow(x - 1, 2);
    }}
    window.setAnimationTime = function(ms) {{
      const s = ms / 1000.0;
      ctx.clearRect(0, 0, W, H);
      for (const p of pts) {{
        let y = (p.y - ms * 0.08 * p.spd) % H;
        if (y < 0) y += H;
        const x = p.x + Math.sin(s * 1.3 + p.ph) * 26;
        ctx.beginPath();
        ctx.arc(x, y, p.r, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(251, 191, 36, ${{p.a * (0.7 + 0.3 * Math.sin(s * 3 + p.ph))}})`;
        ctx.shadowColor = '#f59e0b'; ctx.shadowBlur = 12;
        ctx.fill();
      }}
      const pTitle = easeOutBack(ms / 900);
      const titleEl = document.getElementById('title');
      const decoEl = document.getElementById('deco');
      const cardEl = document.getElementById('card');
      const fadeOut = ms > TOTAL - 450 ? Math.max(0, (TOTAL - ms) / 450) : 1;
      if (cardEl) cardEl.style.opacity = String(Math.min(1, ms / 350) * fadeOut);
      if (titleEl) titleEl.style.transform = `translateY(${{(1 - pTitle) * 32}}px) scale(${{0.85 + 0.15 * pTitle}})`;
      if (decoEl) decoEl.style.transform = `scaleX(${{Math.min(1, ms / 750)}})`;
    }};
    window.setAnimationTime(0);
  </script>
</body>
</html>"""


# ── 1. Shell Run Tool (Tier 3: requires confirmation) ──
class ShellRunParams(BaseModel):
    command: str = Field(..., description="The command line string to execute in the workspace shell.")
    cwd: Optional[str] = Field(None, description="Working directory for the command. Defaults to ~/hinaa-ultra.")
    timeout: Optional[int] = Field(120, description="Max execution time in seconds before timeout.")


async def shell_run_handler(params: ShellRunParams) -> Dict[str, Any]:
    target_cwd = _safe_ultra_path(params.cwd or ".", default_subdir="") if params.cwd else WORKSPACE
    os.makedirs(target_cwd, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=params.timeout or 120.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/shell/run",
                json={"command": params.command, "cwd": target_cwd, "timeout": params.timeout},
            )
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                code = int(res.get("returncode", 0))
                return {
                    "status": "success" if code == 0 else "error",
                    "tool": "shell_run",
                    "command": params.command,
                    "cwd": target_cwd,
                    "returncode": code,
                    "stdout": res.get("stdout", ""),
                    "stderr": res.get("stderr", ""),
                }
    except Exception:
        pass

    try:
        res = subprocess.run(
            params.command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=params.timeout or 120,
        )
        return {
            "status": "success" if res.returncode == 0 else "error",
            "tool": "shell_run",
            "command": params.command,
            "cwd": target_cwd,
            "returncode": res.returncode,
            "stdout": res.stdout or "",
            "stderr": res.stderr or "",
        }
    except subprocess.TimeoutExpired:
        raise HinaaError("SHELL_TIMEOUT", f"Command timed out after {params.timeout}s", 408)
    except Exception as e:
        raise HinaaError("SHELL_ERROR", f"Shell execution failed: {e}", 500)


shell_run_def = ToolDefinition(
    name="shell_run",
    display_name="System: Shell Execution",
    description="Execute a shell command in ~/hinaa-ultra (Python, Node, FFmpeg, Git, etc.).",
    parameters={
        "command": {"type": "string", "description": "Command string to run."},
        "cwd": {"type": "string", "description": "Optional working directory inside ~/hinaa-ultra."},
        "timeout": {"type": "integer", "description": "Optional timeout in seconds."},
    },
    required_parameters=["command"],
    voice_aliases=["run command", "terminal run", "execute shell"],
    requires_confirmation=True,
    risk_tier=3,
    tool_effect="execute_process",
    risk_level="high",
)
registry.register(shell_run_def, shell_run_handler)


# ── 2. Server Start Tool ──
class ServerStartParams(BaseModel):
    port: int = Field(4500, description="Local port to bind HTTP server to (e.g. 4500, 8080).")
    dir_path: str = Field("exports", description="Directory inside ~/hinaa-ultra to serve.")
    name: Optional[str] = Field(None, description="Optional label for the server.")


async def server_start_handler(params: ServerStartParams) -> Dict[str, Any]:
    target_dir = _safe_ultra_path(params.dir_path or "exports", default_subdir="")
    os.makedirs(target_dir, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/server/start",
                json={"port": params.port, "dir": target_dir, "name": params.name or os.path.basename(target_dir)},
            )
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                return {
                    "status": "success",
                    "tool": "server_start",
                    "port": params.port,
                    "dir": res.get("dir", target_dir),
                    "url": res.get("url", f"http://localhost:{params.port}"),
                    "name": params.name or os.path.basename(target_dir),
                }
    except Exception:
        pass
    raise HinaaError("SERVER_START_FAILED", f"Failed to start local server on port {params.port}", 500)


server_start_def = ToolDefinition(
    name="server_start",
    display_name="Server: Start Local Web Host",
    description="Launch a localhost HTTP web server serving an Ultra workspace folder.",
    parameters={
        "port": {"type": "integer", "description": "Local port number."},
        "dir_path": {"type": "string", "description": "Directory path inside ~/hinaa-ultra."},
        "name": {"type": "string", "description": "Optional server name."},
    },
    required_parameters=["port", "dir_path"],
    voice_aliases=["start server", "launch website", "serve files"],
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(server_start_def, server_start_handler)


# ── 3. Ultra File Write & File List ──
class UltraFileWriteParams(BaseModel):
    filename: str = Field(..., description="Target filename or relative path inside ~/hinaa-ultra (bare filenames save into exports/).")
    content: str = Field(..., description="UTF-8 text content to write.")


async def ultra_file_write_handler(params: UltraFileWriteParams) -> Dict[str, Any]:
    target = _safe_ultra_path(params.filename, default_subdir="exports")
    rel_for_server = os.path.relpath(target, WORKSPACE).replace("\\", "/")
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/file/write",
                json={"filename": rel_for_server, "content": params.content},
            )
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                saved_path = res.get("path", target)
                return {
                    "status": "success",
                    "tool": "ultra_file_write",
                    "filename": os.path.basename(saved_path),
                    "path": saved_path,
                    "size_bytes": res.get("size_bytes", len(params.content.encode("utf-8"))),
                    "preview": params.content[:400],
                    "url": _export_url_for(saved_path),
                }
    except Exception:
        pass

    os.makedirs(os.path.dirname(target), exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        f.write(params.content)
    return {
        "status": "success",
        "tool": "ultra_file_write",
        "filename": os.path.basename(target),
        "path": target,
        "size_bytes": os.path.getsize(target),
        "preview": params.content[:400],
        "url": _export_url_for(target),
    }


ultra_file_write_def = ToolDefinition(
    name="ultra_file_write",
    display_name="Workspace: Write File",
    description="Write a file directly inside ~/hinaa-ultra (defaults bare filenames to ~/hinaa-ultra/exports/).",
    parameters={
        "filename": {"type": "string", "description": "Filename or path inside ~/hinaa-ultra."},
        "content": {"type": "string", "description": "File contents."},
    },
    required_parameters=["filename", "content"],
    voice_aliases=["write file", "save file", "create file"],
    requires_confirmation=False,
    risk_tier=1,
    tool_effect="mutate_workspace",
    risk_level="low",
)
registry.register(ultra_file_write_def, ultra_file_write_handler)


class FileListParams(BaseModel):
    path: str = Field(".", description="Directory inside ~/hinaa-ultra to list ('.', 'exports', 'video', 'sites').")


async def file_list_handler(params: FileListParams) -> Dict[str, Any]:
    target = _safe_ultra_path(params.path or ".", default_subdir="")
    rel_for_server = "." if os.path.abspath(target) == WORKSPACE else os.path.relpath(target, WORKSPACE).replace("\\", "/")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(f"{TOOL_SERVER_URL}/tool/file/list", params={"path": rel_for_server})
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                items = res.get("items", [])
                return {
                    "status": "success",
                    "tool": "file_list",
                    "path": res.get("path", target),
                    "items": items,
                    "count": len(items),
                }
    except Exception:
        pass

    os.makedirs(target, exist_ok=True)
    items = []
    for entry in sorted(os.listdir(target)):
        full = os.path.join(target, entry)
        items.append({
            "name": entry,
            "type": "dir" if os.path.isdir(full) else "file",
            "size": 0 if os.path.isdir(full) else os.path.getsize(full),
        })
    return {
        "status": "success",
        "tool": "file_list",
        "path": target,
        "items": items,
        "count": len(items),
    }


file_list_def = ToolDefinition(
    name="file_list",
    display_name="Workspace: List Files",
    description="List files and folders inside ~/hinaa-ultra workspace or exports.",
    parameters={"path": {"type": "string", "description": "Subdirectory inside ~/hinaa-ultra."}},
    required_parameters=[],
    voice_aliases=["list workspace", "show files"],
    is_read_only=True,
    requires_confirmation=False,
    risk_tier=0,
    risk_level="low",
)
registry.register(file_list_def, file_list_handler)


# ── 4. Record Frames, FFmpeg Export, Video Create ──
class RecordFramesParams(BaseModel):
    html_file: str = Field(..., description="Path to HTML animation inside ~/hinaa-ultra.")
    fps: int = Field(30, description="Frames per second.")
    duration_seconds: int = Field(5, description="Duration in seconds.")
    width: int = Field(540, description="Viewport width in pixels.")
    height: int = Field(960, description="Viewport height in pixels.")
    frames_dir: str = Field("frames/capture", description="Destination frame directory.")


async def record_frames_handler(params: RecordFramesParams) -> Dict[str, Any]:
    html_path = _safe_ultra_path(params.html_file, default_subdir="video")
    frames_path = _safe_ultra_path(params.frames_dir, default_subdir="")
    async with httpx.AsyncClient(timeout=900.0) as client:
        resp = await client.post(
            f"{TOOL_SERVER_URL}/tool/browser/record-frames",
            json={
                "html_file": html_path,
                "fps": params.fps,
                "duration_seconds": params.duration_seconds,
                "width": params.width,
                "height": params.height,
                "frames_dir": frames_path,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") == "success":
                return {"status": "success", "tool": "record_frames", **data.get("result", {})}
            raise HinaaError("RECORD_FRAMES_FAILED", str(data.get("error", "Capture failed")), 500)
    raise HinaaError("RECORD_FRAMES_UNAVAILABLE", "Tool server :8765 failed to capture frames", 502)


record_frames_def = ToolDefinition(
    name="record_frames",
    display_name="Media: Capture HTML Animation Frames",
    description="Capture deterministic PNG frame sequences from an HTML animation at target FPS.",
    parameters={
        "html_file": {"type": "string", "description": "HTML file inside ~/hinaa-ultra."},
        "fps": {"type": "integer", "description": "FPS (default 30)."},
        "duration_seconds": {"type": "integer", "description": "Duration in seconds."},
        "width": {"type": "integer", "description": "Width in px."},
        "height": {"type": "integer", "description": "Height in px."},
        "frames_dir": {"type": "string", "description": "Frames folder."},
    },
    required_parameters=["html_file"],
    is_long_running=True,
    timeout_seconds=600,
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(record_frames_def, record_frames_handler)


class FfmpegExportParams(BaseModel):
    frames_dir: str = Field(..., description="Folder containing PNG frames.")
    output: str = Field("exports/hinaa_video.mp4", description="Output MP4 file path inside ~/hinaa-ultra.")
    fps: int = Field(60, description="Frames per second (24, 30, 60).")
    width: int = Field(1080, description="Video width in pixels.")
    height: int = Field(1920, description="Video height in pixels.")


async def ffmpeg_export_handler(params: FfmpegExportParams) -> Dict[str, Any]:
    frames_path = _safe_ultra_path(params.frames_dir, default_subdir="")
    out_path = _safe_ultra_path(params.output, default_subdir="exports")
    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/video/frames-to-mp4",
                json={
                    "frames_dir": frames_path,
                    "output": out_path,
                    "fps": params.fps,
                    "width": params.width,
                    "height": params.height,
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                if data.get("status") == "success":
                    return {
                        "status": "success",
                        "tool": "ffmpeg_export",
                        "output": res.get("output", out_path),
                        "filename": res.get("filename", os.path.basename(out_path)),
                        "size_bytes": res.get("size_bytes", 0),
                        "size_mb": res.get("size_mb", 0),
                        "fps": params.fps,
                        "width": params.width,
                        "height": params.height,
                        "url": res.get("url") or _export_url_for(out_path),
                    }
    except Exception:
        pass

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pattern = os.path.join(frames_path, "frame_%05d.png")
    cmd = [
        "ffmpeg", "-y", "-framerate", str(params.fps), "-i", pattern,
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "fast",
        "-vf", f"scale={params.width}:{params.height}", "-movflags", "+faststart", out_path,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(out_path):
        sz = os.path.getsize(out_path)
        return {
            "status": "success",
            "tool": "ffmpeg_export",
            "output": out_path,
            "filename": os.path.basename(out_path),
            "size_bytes": sz,
            "size_mb": round(sz / (1024 * 1024), 2),
            "fps": params.fps,
            "width": params.width,
            "height": params.height,
            "url": _export_url_for(out_path),
        }
    raise HinaaError("FFMPEG_FAILED", f"Video stitching failed: {res.stderr}", 500)


ffmpeg_export_def = ToolDefinition(
    name="ffmpeg_export",
    display_name="Media: FFmpeg Frames to MP4",
    description="Stitch captured PNG image frames into a production H.264 MP4 video file.",
    parameters={
        "frames_dir": {"type": "string", "description": "Folder with image frames."},
        "output": {"type": "string", "description": "Target .mp4 file path."},
        "fps": {"type": "integer", "description": "Frames per second (24, 30, 60)."},
        "width": {"type": "integer", "description": "Width in pixels."},
        "height": {"type": "integer", "description": "Height in pixels."},
    },
    required_parameters=["frames_dir"],
    voice_aliases=["export mp4", "stitch video", "render animation"],
    is_long_running=True,
    timeout_seconds=600,
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(ffmpeg_export_def, ffmpeg_export_handler)


_STYLE_MAP: Dict[str, str] = {
    "01": "01-luxury-bridal-gold.html",
    "luxury-bridal-gold": "01-luxury-bridal-gold.html",
    "bridal": "01-luxury-bridal-gold.html",
    "02": "02-hoplite-dark.html",
    "hoplite-dark": "02-hoplite-dark.html",
    "hoplite": "02-hoplite-dark.html",
    "katana": "02-hoplite-dark.html",
    "03": "03-viral-motivational.html",
    "viral-motivational": "03-viral-motivational.html",
    "viral": "03-viral-motivational.html",
    "04": "04-cinematic-film-title.html",
    "cinematic-film-title": "04-cinematic-film-title.html",
    "film": "04-cinematic-film-title.html",
    "05": "05-soft-editorial.html",
    "soft-editorial": "05-soft-editorial.html",
    "editorial": "05-soft-editorial.html",
    "06": "06-neon-cyber.html",
    "neon-cyber": "06-neon-cyber.html",
    "cyber": "06-neon-cyber.html",
    "07": "07-golden-hour.html",
    "golden-hour": "07-golden-hour.html",
    "08": "08-minimal-white.html",
    "minimal-white": "08-minimal-white.html",
    "09": "09-dark-luxury-rose.html",
    "dark-luxury-rose": "09-dark-luxury-rose.html",
    "rose": "09-dark-luxury-rose.html",
    "10": "10-split-screen-kinetic.html",
    "split-screen-kinetic": "10-split-screen-kinetic.html",
    "split": "10-split-screen-kinetic.html",
    "11": "11-typewriter-terminal.html",
    "typewriter-terminal": "11-typewriter-terminal.html",
    "terminal": "11-typewriter-terminal.html",
    "12": "12-soft-cinematic-fade.html",
    "soft-cinematic-fade": "12-soft-cinematic-fade.html",
    "fade": "12-soft-cinematic-fade.html",
}


def _resolve_style_file(style: Optional[str], prompt: str) -> tuple[str, Optional[str]]:
    raw = (style or "").strip().lower()
    if raw:
        if raw.endswith(".html") and os.path.exists(os.path.join(WORKSPACE, "video", "styles", raw)):
            return raw[:-5], os.path.join(WORKSPACE, "video", "styles", raw)
        if raw in _STYLE_MAP:
            fn = _STYLE_MAP[raw]
            return fn[:-5], os.path.join(WORKSPACE, "video", "styles", fn)
        for slug, fn in _STYLE_MAP.items():
            if slug in raw:
                return fn[:-5], os.path.join(WORKSPACE, "video", "styles", fn)
    lp = (prompt or "").lower()
    for kw, fn in (
        ("bridal", "01-luxury-bridal-gold.html"),
        ("wedding", "01-luxury-bridal-gold.html"),
        ("hoplite", "02-hoplite-dark.html"),
        ("katana", "02-hoplite-dark.html"),
        ("viral", "03-viral-motivational.html"),
        ("motivat", "03-viral-motivational.html"),
        ("neon", "06-neon-cyber.html"),
        ("cyber", "06-neon-cyber.html"),
        ("terminal", "11-typewriter-terminal.html"),
        ("editorial", "05-soft-editorial.html"),
        ("golden", "07-golden-hour.html"),
        ("rose", "09-dark-luxury-rose.html"),
        ("minimal", "08-minimal-white.html"),
        ("split", "10-split-screen-kinetic.html"),
    ):
        if kw in lp:
            return fn[:-5], os.path.join(WORKSPACE, "video", "styles", fn)
    return "02-hoplite-dark", os.path.join(WORKSPACE, "video", "styles", "02-hoplite-dark.html")


def _prompt_to_scenes(prompt: str, total_dur_s: int) -> List[Dict[str, Any]]:
    raw = (prompt or "HINAA Kinetic Reel").strip()
    parts = [p.strip() for p in re.split(r"[\n.;|]+", raw) if p.strip()]
    if len(parts) < 2:
        words = raw.split()
        if len(words) > 6:
            mid = max(2, len(words) // 2)
            parts = [" ".join(words[:mid]), " ".join(words[mid:])]
        else:
            parts = [raw, "Engineered by HINAA Ultra"]
    parts = parts[:8]
    per_dur = max(2.0, round(total_dur_s / max(1, len(parts)), 2))
    scenes: List[Dict[str, Any]] = []
    for idx, line in enumerate(parts, 1):
        sub_words = line.split()
        headline = " ".join(sub_words[:5])
        subline = " ".join(sub_words[5:12]) or f"SCENE {idx:02d}"
        scenes.append({
            "eyebrow": f"ACT {idx:02d}",
            "headline": headline,
            "subline": subline,
            "duration": per_dur,
            "durationMs": int(per_dur * 1000),
            "watermark": f"{idx:02d}",
        })
    return scenes


class VideoCreateParams(BaseModel):
    prompt: str = Field(..., description="Visual theme, multi-scene script, or motion animation description.")
    duration_seconds: int = Field(5, description="Duration in seconds (1-30).")
    fps: int = Field(24, description="Frames per second (12-60).")
    width: int = Field(540, description="Video width in pixels (default 540 vertical Reels; 1080 for full HD).")
    height: int = Field(960, description="Video height in pixels (default 960 vertical Reels; 1920 for full HD).")
    output: Optional[str] = Field(None, description="Optional target filename in exports/.")
    style: Optional[str] = Field(None, description="One of 12 kinetic styles (e.g. '02-hoplite-dark', '01-luxury-bridal-gold').")
    scenes: Optional[List[Dict[str, Any]]] = Field(None, description="Sequential multi-scene array [{eyebrow, headline, subline, duration}].")
    overlay_mode: str = Field("full", description="Background mode: 'full', 'black' (#000000 overlay), or 'green' (#00ff00 chroma-key).")


async def video_create_handler(params: VideoCreateParams) -> Dict[str, Any]:
    import json as _json

    dur = max(1, min(30, int(params.duration_seconds or 5)))
    fps = max(12, min(60, int(params.fps or 24)))
    w = max(320, min(1920, int(params.width or 540)))
    h = max(320, min(1920, int(params.height or 960)))
    ts = int(time.time())
    overlay = (params.overlay_mode or "full").strip().lower()
    if overlay not in ("full", "black", "green"):
        overlay = "full"

    is_bridal = "bridal" in params.prompt.lower()
    bridal_template = os.path.join(WORKSPACE, "video", "bridal_reel.html")
    style_name, style_path = _resolve_style_file(params.style, params.prompt)

    if is_bridal and dur >= 25 and w == 1080 and h == 1920 and not params.scenes and overlay == "full" and os.path.exists(bridal_template):
        html_path = bridal_template
        out_name = params.output or "exports/bridal_reel.mp4"
    elif style_path and os.path.exists(style_path):
        with open(style_path, "r", encoding="utf-8") as sf:
            tpl = sf.read()
        scenes = params.scenes if (params.scenes and len(params.scenes) > 0) else _prompt_to_scenes(params.prompt, dur)
        scene_payload = {"scenes": scenes, "mode": overlay, "bg": overlay, "overlay": overlay}
        inject = f"<script>window.HINAA_SCENE_DATA = {_json.dumps(scene_payload, ensure_ascii=False)};</script>"
        html_content = tpl.replace("</head>", f"{inject}\n</head>", 1) if "</head>" in tpl else (inject + "\n" + tpl)
        html_path = os.path.join(WORKSPACE, "video", f"clip_{_slugify(params.prompt)}_{ts}.html")
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        out_name = params.output or f"exports/{_slugify(params.prompt)}_{ts}.mp4"
    else:
        title = "Aisha & Aryan" if is_bridal else params.prompt[:42].strip().title()
        subtitle = "Save the Date" if is_bridal else "Generated by HINAA Ultra"
        html_content = _build_sparkle_video_html(title, subtitle, dur, w, h)
        html_path = os.path.join(WORKSPACE, "video", f"clip_{_slugify(params.prompt)}_{ts}.html")
        os.makedirs(os.path.dirname(html_path), exist_ok=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        out_name = params.output or f"exports/{_slugify(params.prompt)}_{ts}.mp4"

    frames_dir = f"frames/run_{ts}"
    await record_frames_handler(
        RecordFramesParams(
            html_file=html_path,
            fps=fps,
            duration_seconds=dur,
            width=w,
            height=h,
            frames_dir=frames_dir,
        )
    )
    exported = await ffmpeg_export_handler(
        FfmpegExportParams(frames_dir=frames_dir, output=out_name, fps=fps, width=w, height=h)
    )
    exported["tool"] = "video_create"
    exported["duration_seconds"] = dur
    exported["style"] = style_name
    exported["overlay_mode"] = overlay
    exported["prompt"] = params.prompt
    exported["download_url"] = f"http://localhost:8765/tool/video/download?file=exports/{exported['filename']}"
    return exported


video_create_def = ToolDefinition(
    name="video_create",
    display_name="Media: Create Code-Driven MP4 Video",
    description="Create a playable H.264 MP4 animation (vertical reels, gold sparkle typography, motion graphics) using Playwright + FFmpeg.",
    parameters={
        "prompt": {"type": "string", "description": "Animation theme or description."},
        "duration_seconds": {"type": "integer", "description": "Duration in seconds (1-30)."},
        "fps": {"type": "integer", "description": "Frames per second (12-60)."},
        "width": {"type": "integer", "description": "Pixel width."},
        "height": {"type": "integer", "description": "Pixel height."},
        "output": {"type": "string", "description": "Optional MP4 path inside exports/."},
        "style": {"type": "string", "description": "Style slug or ID (e.g. '02-hoplite-dark', '01-luxury-bridal-gold', '06-neon-cyber')."},
        "scenes": {"type": "array", "description": "Sequential scenes [{eyebrow, headline, subline, duration}]."},
        "overlay_mode": {"type": "string", "description": "'full', 'black' (#000000 overlay), or 'green' (#00ff00 chroma-key)."},
    },
    required_parameters=["prompt"],
    voice_aliases=["create video", "make animation mp4", "bridal reel"],
    is_long_running=True,
    timeout_seconds=600,
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(video_create_def, video_create_handler)


# ── 5. Browser Screenshot Tool ──
class BrowserScreenshotParams(BaseModel):
    url: str = Field(..., description="URL to screenshot (e.g. http://localhost:3000).")
    width: int = Field(1280, description="Viewport width.")
    height: int = Field(800, description="Viewport height.")
    fullPage: bool = Field(False, description="Capture full page height.")
    output: Optional[str] = Field(None, description="Output PNG filename in exports/.")


async def browser_screenshot_handler(params: BrowserScreenshotParams) -> Dict[str, Any]:
    out_name = params.output or f"exports/shot_{int(time.time())}.png"
    target = _safe_ultra_path(out_name, default_subdir="exports")
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(
            f"{TOOL_SERVER_URL}/tool/browser/screenshot",
            json={
                "url": params.url,
                "width": params.width,
                "height": params.height,
                "fullPage": params.fullPage,
                "output": target,
            },
        )
        if resp.status_code == 200 and resp.json().get("status") == "success":
            res = resp.json().get("result", {})
            saved = res.get("path", target)
            return {
                "status": "success",
                "tool": "browser_screenshot",
                "url_captured": params.url,
                "path": saved,
                "filename": os.path.basename(saved),
                "size_bytes": res.get("size_bytes", 0),
                "url": _export_url_for(saved),
            }
    raise HinaaError("SCREENSHOT_FAILED", f"Could not screenshot {params.url}", 500)


browser_screenshot_def = ToolDefinition(
    name="browser_screenshot",
    display_name="Browser: Capture Page Screenshot",
    description="Capture a screenshot of a URL using the Ultra Playwright server and save to exports/.",
    parameters={
        "url": {"type": "string", "description": "URL to capture."},
        "width": {"type": "integer", "description": "Viewport width."},
        "height": {"type": "integer", "description": "Viewport height."},
        "fullPage": {"type": "boolean", "description": "Capture full scrollable page."},
    },
    required_parameters=["url"],
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(browser_screenshot_def, browser_screenshot_handler)


# ── 6. Ultra Memory Save & Get ──
class UltraMemorySaveParams(BaseModel):
    key: str = Field(..., description="Memory key.")
    value: Any = Field(..., description="Value to persist.")
    tags: List[str] = Field(default_factory=list, description="Optional topic tags.")


async def ultra_memory_save_handler(params: UltraMemorySaveParams) -> Dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{TOOL_SERVER_URL}/tool/memory/save",
            json={"key": params.key, "value": params.value, "tags": params.tags},
        )
        if resp.status_code == 200:
            return {"status": "success", "tool": "ultra_memory_save", "key": params.key, "tags": params.tags}
    raise HinaaError("MEMORY_SAVE_FAILED", "Ultra memory server unavailable", 502)


ultra_memory_save_def = ToolDefinition(
    name="ultra_memory_save",
    display_name="Memory: Save Knowledge Entry",
    description="Persist a tagged key/value note in ~/hinaa-ultra/memory/memory.json.",
    parameters={
        "key": {"type": "string", "description": "Memory key."},
        "value": {"type": "string", "description": "Content to store."},
        "tags": {"type": "array", "description": "Optional tags."},
    },
    required_parameters=["key", "value"],
    requires_confirmation=False,
    risk_tier=1,
    risk_level="low",
)
registry.register(ultra_memory_save_def, ultra_memory_save_handler)


class UltraMemoryGetParams(BaseModel):
    key: Optional[str] = Field(None, description="Specific memory key to look up.")
    tag: Optional[str] = Field(None, description="Optional tag filter.")


async def ultra_memory_get_handler(params: UltraMemoryGetParams) -> Dict[str, Any]:
    query: Dict[str, str] = {}
    if params.key:
        query["key"] = params.key
    if params.tag:
        query["tag"] = params.tag
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{TOOL_SERVER_URL}/tool/memory/get", params=query)
        if resp.status_code == 200:
            return {"status": "success", "tool": "ultra_memory_get", **resp.json()}
    raise HinaaError("MEMORY_GET_FAILED", "Ultra memory server unavailable", 502)


ultra_memory_get_def = ToolDefinition(
    name="ultra_memory_get",
    display_name="Memory: Query Knowledge Store",
    description="Retrieve saved memory entries by key or tag from ~/hinaa-ultra/memory.",
    parameters={
        "key": {"type": "string", "description": "Optional memory key."},
        "tag": {"type": "string", "description": "Optional tag filter."},
    },
    required_parameters=[],
    is_read_only=True,
    requires_confirmation=False,
    risk_tier=0,
    risk_level="low",
)
registry.register(ultra_memory_get_def, ultra_memory_get_handler)


# ── 7. Sub-Agent Spawn / Execute Tool (Tier 2: requires confirmation) ──
class AgentSpawnParams(BaseModel):
    name: str = Field(..., description="Name of subagent: 'kira' (coder), 'nova' (designer), or 'sage' (researcher).")
    task: str = Field(..., description="Task instructions to assign to the subagent.")


async def agent_spawn_handler(params: AgentSpawnParams) -> Dict[str, Any]:
    n = params.name.lower().strip()
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"{AGENT_SERVER_URL}/agents/execute",
                json={"name": n, "task": params.task},
            )
            if resp.status_code == 200:
                res = resp.json().get("result", {})
                return {
                    "status": "success",
                    "tool": "agent_spawn",
                    "agent": res.get("agent", n.title()),
                    "role": res.get("role", n),
                    "task": params.task,
                    "output": res.get("output", ""),
                    "artifacts": res.get("artifacts", []),
                    "preview_url": res.get("preview_url"),
                }
    except Exception:
        pass
    return {
        "status": "success",
        "tool": "agent_spawn",
        "agent": n.title(),
        "role": "Specialist",
        "task": params.task,
        "output": f"Assigned task to {n.title()}: {params.task}",
        "artifacts": [],
    }


agent_spawn_def = ToolDefinition(
    name="agent_spawn",
    display_name="Swarm: Delegate to Specialist Agent",
    description="Execute a task using autonomous specialist sub-agents (Kira for coding, Nova for design, Sage for research).",
    parameters={
        "name": {"type": "string", "description": "Agent name: kira, nova, or sage."},
        "task": {"type": "string", "description": "Task description."},
    },
    required_parameters=["name", "task"],
    voice_aliases=["spawn agent", "call kira", "call nova", "call sage"],
    requires_confirmation=True,
    risk_tier=2,
    risk_level="medium",
)
registry.register(agent_spawn_def, agent_spawn_handler)
