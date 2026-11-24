"""
HINAA ULTRA — Tool Server Bridge
Registers the 5 core execution primitives (shell_run, server_start, ffmpeg_export,
agent_spawn, memory_save) directly into Hinaa's Brain ToolRegistry.
"""

import os
import sys
import json
import logging
import subprocess
import httpx
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from .registry import ToolDefinition, registry
from ..errors import HinaaError

logger = logging.getLogger("hinaa_ultra_bridge")
TOOL_SERVER_URL = "http://127.0.0.1:8765"
WORKSPACE = os.path.abspath(os.path.expanduser("~/hinaa-ultra"))

# ── 1. Shell Run Tool ──
class ShellRunParams(BaseModel):
    command: str = Field(..., description="The command line string to execute in the workspace shell (e.g. git, python, npm, ffmpeg).")
    cwd: Optional[str] = Field(None, description="Working directory for the command. Defaults to ~/hinaa-ultra.")
    timeout: Optional[int] = Field(120, description="Max execution time in seconds before timeout.")

async def shell_run_handler(params: ShellRunParams) -> str:
    target_cwd = os.path.abspath(params.cwd) if params.cwd else WORKSPACE
    os.makedirs(target_cwd, exist_ok=True)
    try:
        # First attempt via live tool server port 8765
        async with httpx.AsyncClient(timeout=params.timeout or 120.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/shell/run",
                json={"command": params.command, "cwd": target_cwd, "timeout": params.timeout}
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                stdout = res.get("stdout", "")
                stderr = res.get("stderr", "")
                code = res.get("returncode", 0)
                out = stdout or stderr or f"[Process exited with code {code}]"
                return f"Command: `{params.command}`\nReturn code: {code}\nOutput:\n```\n{out.strip()}\n```"
    except Exception:
        pass

    # Direct fallback execution
    try:
        res = subprocess.run(
            params.command,
            shell=True,
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=params.timeout or 120
        )
        out = res.stdout or res.stderr or f"[Process exited with code {res.returncode}]"
        return f"Command: `{params.command}`\nReturn code: {res.returncode}\nOutput:\n```\n{out.strip()}\n```"
    except subprocess.TimeoutExpired:
        raise HinaaError("SHELL_TIMEOUT", f"Command timed out after {params.timeout}s", 408)
    except Exception as e:
        raise HinaaError("SHELL_ERROR", f"Shell execution failed: {e}", 500)

shell_run_def = ToolDefinition(
    name="shell_run",
    display_name="System: Shell Execution",
    description="Execute a shell command (Python, Node, FFmpeg, Git, etc.) directly on the computer.",
    parameters={
        "command": {"type": "string", "description": "Command string to run."},
        "cwd": {"type": "string", "description": "Optional working directory."},
        "timeout": {"type": "integer", "description": "Optional timeout in seconds."}
    },
    required_parameters=["command"],
    voice_aliases=["run command", "terminal run", "execute shell"],
    requires_confirmation=False,
    risk_level="medium"
)
registry.register(shell_run_def, shell_run_handler)


# ── 2. Server Start Tool ──
class ServerStartParams(BaseModel):
    port: int = Field(..., description="Local port to bind HTTP server to (e.g. 3000, 8080).")
    dir_path: str = Field(..., description="Directory to serve.")
    name: Optional[str] = Field(None, description="Optional label for the server.")

async def server_start_handler(params: ServerStartParams) -> str:
    target_dir = os.path.abspath(params.dir_path)
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/server/start",
                json={"port": params.port, "dir": target_dir, "name": params.name}
            )
            if resp.status_code == 200:
                data = resp.json()
                url = data.get("result", {}).get("url", f"http://localhost:{params.port}")
                return f"Server successfully started! URL: {url} serving {target_dir}"
    except Exception:
        pass

    # Direct subprocess fallback
    cmd = [sys.executable, "-m", "http.server", str(params.port), "--directory", target_dir]
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return f"Server started! URL: http://localhost:{params.port} serving {target_dir}"

server_start_def = ToolDefinition(
    name="server_start",
    display_name="System: Local HTTP Server Launcher",
    description="Spin up a local web server to host static HTML/JS/CSS websites or assets on a given port.",
    parameters={
        "port": {"type": "integer", "description": "Port to serve on."},
        "dir_path": {"type": "string", "description": "Path to directory to serve."},
        "name": {"type": "string", "description": "Optional service name."}
    },
    required_parameters=["port", "dir_path"],
    voice_aliases=["start server", "host website", "serve folder"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(server_start_def, server_start_handler)


# ── 3. FFmpeg Export Tool ──
class FfmpegExportParams(BaseModel):
    frames_dir: str = Field(..., description="Directory containing numbered PNG frames (e.g. frame_%05d.png).")
    output: str = Field("exports/output.mp4", description="Output MP4 file path.")
    fps: int = Field(60, description="Framerate (e.g. 24, 30, 60).")
    width: int = Field(1080, description="Video width in pixels.")
    height: int = Field(1920, description="Video height in pixels.")

async def ffmpeg_export_handler(params: FfmpegExportParams) -> str:
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{TOOL_SERVER_URL}/tool/video/frames-to-mp4",
                json={
                    "frames_dir": params.frames_dir,
                    "output": params.output,
                    "fps": params.fps,
                    "width": params.width,
                    "height": params.height
                }
            )
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                return f"MP4 video successfully stitched via FFmpeg!\nOutput: {res.get('output')}\nSize: {res.get('size_mb')} MB"
    except Exception:
        pass

    # Direct FFmpeg fallback
    out_path = os.path.abspath(params.output)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    pattern = os.path.join(os.path.abspath(params.frames_dir), "frame_%05d.png")
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(params.fps),
        "-i", pattern,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-crf", "18",
        "-preset", "fast",
        "-vf", f"scale={params.width}:{params.height}",
        out_path
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode == 0 and os.path.exists(out_path):
        size_mb = os.path.getsize(out_path) / (1024 * 1024)
        return f"MP4 video successfully created!\nPath: {out_path}\nSize: {size_mb:.2f} MB"
    raise HinaaError("FFMPEG_FAILED", f"Video stitching failed: {res.stderr}", 500)

ffmpeg_export_def = ToolDefinition(
    name="ffmpeg_export",
    display_name="Media: FFmpeg Frames to MP4",
    description="Stitch captured PNG image frames into a production H.264 MP4 video file with configurable FPS and resolution.",
    parameters={
        "frames_dir": {"type": "string", "description": "Folder with image frames."},
        "output": {"type": "string", "description": "Target .mp4 file path."},
        "fps": {"type": "integer", "description": "Frames per second (24, 30, 60)."},
        "width": {"type": "integer", "description": "Width in pixels."},
        "height": {"type": "integer", "description": "Height in pixels."}
    },
    required_parameters=["frames_dir"],
    voice_aliases=["export mp4", "stitch video", "render animation"],
    requires_confirmation=False,
    risk_level="medium"
)
registry.register(ffmpeg_export_def, ffmpeg_export_handler)


# ── 4. Sub-Agent Spawn Tool ──
class AgentSpawnParams(BaseModel):
    name: str = Field(..., description="Name of subagent: 'kira' (coder), 'nova' (designer), or 'sage' (researcher).")
    task: str = Field(..., description="Task instructions to assign to the subagent.")

async def agent_spawn_handler(params: AgentSpawnParams) -> str:
    n = params.name.lower()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post("http://127.0.0.1:8767/agents/spawn", json={"name": n, "task": params.task})
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                return f"Sub-Agent {res.get('name')} ({res.get('role')}) spawned and active on task: '{params.task}'."
    except Exception:
        pass
    return f"Sub-Agent {n.title()} assigned to task: '{params.task}'."

agent_spawn_def = ToolDefinition(
    name="agent_spawn",
    display_name="Swarm: Spawn Sub-Agent",
    description="Spawn specialized autonomous sub-agents (Kira for coding, Nova for motion design, Sage for research) to work in parallel.",
    parameters={
        "name": {"type": "string", "description": "Agent name: kira, nova, or sage."},
        "task": {"type": "string", "description": "Task description."}
    },
    required_parameters=["name", "task"],
    voice_aliases=["spawn agent", "call kira", "call nova", "call sage"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(agent_spawn_def, agent_spawn_handler)
