"""
Persistent Bidirectional Streaming PTY / Terminal Session Manager for HINAA.

Enables HINAA to manage stateful interactive terminal sessions across multiple turns:
- Persistent shell sessions (PowerShell / CMD on Windows, Bash / Sh on Unix).
- Thread-safe background stdout/stderr streaming into ring buffers.
- Interactive input injection (REPLs, confirmation prompts, stdin streaming).
- Graceful signals (Ctrl+C, break, kill).
- ANSI terminal escape sequence parsing and stripping.
- Windows SelectorEventLoop resilient: Uses dedicated background I/O threads to prevent
  asyncio NotImplementedError on Windows Uvicorn.
"""

from __future__ import annotations

import asyncio
import collections
import concurrent.futures
import logging
import os
import queue
import re
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..runtime_paths import project_root
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.pty_session")

# ANSI color and escape code regex
ANSI_ESCAPE_RE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from terminal output."""
    return ANSI_ESCAPE_RE.sub("", text)


def _default_shell() -> list[str]:
    """Resolve standard interactive shell executable."""
    if os.name == "nt":
        ps = shutil.which("powershell.exe")
        if not ps:
            system_root = os.environ.get("SystemRoot", r"C:\Windows")
            candidate = Path(system_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
            ps = str(candidate) if candidate.exists() else "powershell.exe"
        return [ps, "-NoLogo", "-NoExit", "-Command", "-"]
    bash = shutil.which("bash") or shutil.which("sh") or "/bin/sh"
    return [bash, "-i"]


class PTYSession:
    """Manages an active persistent terminal subprocess with streaming I/O."""

    def __init__(
        self,
        session_id: str,
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        max_buffer_lines: int = 2000,
    ) -> None:
        self.session_id = session_id
        self.cwd = cwd
        self.max_buffer_lines = max_buffer_lines
        self.created_at = time.time()
        self.last_activity = self.created_at

        # Ring buffer of (timestamp, stream_name, line)
        self.buffer: collections.deque = collections.deque(maxlen=max_buffer_lines)
        self.lock = threading.Lock()
        self.is_alive = True

        # Process creation with pipes
        custom_env = os.environ.copy()
        custom_env["TERM"] = "xterm-256color"
        custom_env["PYTHONUNBUFFERED"] = "1"
        if env:
            custom_env.update(env)

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        cmd = _default_shell()

        try:
            self.proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(self.cwd),
                env=custom_env,
                creationflags=creationflags,
                bufsize=0,
            )
        except Exception as exc:
            logger.exception("Failed to spawn PTY shell process: %s", exc)
            self.is_alive = False
            raise

        # Spawn background reader threads for stdout and stderr
        self.stdout_thread = threading.Thread(
            target=self._read_stream,
            args=(self.proc.stdout, "stdout"),
            daemon=True,
            name=f"pty-stdout-{session_id}",
        )
        self.stderr_thread = threading.Thread(
            target=self._read_stream,
            args=(self.proc.stderr, "stderr"),
            daemon=True,
            name=f"pty-stderr-{session_id}",
        )
        self.stdout_thread.start()
        self.stderr_thread.start()

    def _read_stream(self, stream: Any, stream_name: str) -> None:
        """Continuously read lines from process stream into thread-safe buffer."""
        try:
            while self.is_alive and stream:
                line_bytes = stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="replace")
                with self.lock:
                    self.buffer.append((time.time(), stream_name, line))
                    self.last_activity = time.time()
        except Exception as exc:
            logger.debug("PTY stream %s reader stopped: %s", stream_name, exc)
        finally:
            with self.lock:
                if self.proc.poll() is not None:
                    self.is_alive = False

    def write(self, data: str) -> bool:
        """Write text / command to subprocess stdin."""
        if not self.is_alive or not self.proc.stdin:
            return False
        try:
            if not data.endswith("\n"):
                data += "\n"
            self.proc.stdin.write(data.encode("utf-8"))
            self.proc.stdin.flush()
            with self.lock:
                self.last_activity = time.time()
            return True
        except Exception as exc:
            logger.warning("Failed writing to PTY session %s: %s", self.session_id, exc)
            self.is_alive = False
            return False

    def send_interrupt(self) -> bool:
        """Send Ctrl+C interrupt signal."""
        if not self.is_alive:
            return False
        try:
            if os.name == "nt":
                # Write ASCII ETX (Ctrl+C) to stdin
                return self.write("\x03")
            else:
                import signal
                os.kill(self.proc.pid, signal.SIGINT)
                return True
        except Exception as exc:
            logger.warning("Failed sending interrupt to PTY %s: %s", self.session_id, exc)
            return False

    def read_delta(self, since_timestamp: float = 0.0, clean_ansi: bool = True) -> str:
        """Read all lines added since timestamp."""
        with self.lock:
            lines = [
                line
                for ts, _, line in self.buffer
                if ts >= since_timestamp
            ]
        text = "".join(lines)
        return strip_ansi(text) if clean_ansi else text

    def terminate(self) -> None:
        """Terminate the running PTY process cleanly."""
        self.is_alive = False
        try:
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
        except Exception as exc:
            logger.debug("PTY termination cleanup exception: %s", exc)


class PTYSessionManager:
    """Singleton registry and orchestrator for active PTY sessions."""

    def __init__(self) -> None:
        self.sessions: Dict[str, PTYSession] = {}
        self.lock = threading.Lock()

    def get_or_create(
        self,
        session_id: str = "default",
        cwd: Optional[Path] = None,
        env: Optional[Dict[str, str]] = None,
    ) -> PTYSession:
        with self.lock:
            existing = self.sessions.get(session_id)
            if existing and existing.is_alive:
                return existing

            target_cwd = cwd or project_root()
            session = PTYSession(session_id=session_id, cwd=target_cwd, env=env)
            self.sessions[session_id] = session
            return session

    def close(self, session_id: str) -> bool:
        with self.lock:
            session = self.sessions.pop(session_id, None)
            if session:
                session.terminate()
                return True
            return False

    def close_all(self) -> None:
        with self.lock:
            for s in list(self.sessions.values()):
                s.terminate()
            self.sessions.clear()

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self.lock:
            now = time.time()
            return [
                {
                    "session_id": sid,
                    "is_alive": s.is_alive,
                    "cwd": str(s.cwd),
                    "created_at": s.created_at,
                    "idle_seconds": round(now - s.last_activity, 2),
                    "buffered_lines": len(s.buffer),
                }
                for sid, s in self.sessions.items()
            ]


# Singleton instance
_pty_manager = PTYSessionManager()


def get_pty_manager() -> PTYSessionManager:
    return _pty_manager


# ============================================================================
# Registered Agent Tools
# ============================================================================

async def pty_session_run_handler(
    command: str,
    session_id: str = "default",
    wait_seconds: float = 2.0,
    cwd: Optional[str] = None,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute command in a persistent PTY session and stream output delta."""
    mgr = get_pty_manager()
    target_cwd = Path(cwd).resolve() if cwd else project_root()
    session = mgr.get_or_create(session_id=session_id, cwd=target_cwd)

    start_ts = time.time()
    ok = session.write(command)
    if not ok:
        return {
            "success": False,
            "session_id": session_id,
            "error": "Failed to write command to PTY session stdin",
            "output": "",
        }

    # Polling wait for output delta
    elapsed = 0.0
    poll_step = 0.1
    last_text = ""
    while elapsed < wait_seconds:
        await asyncio.sleep(poll_step)
        elapsed += poll_step
        curr_text = session.read_delta(since_timestamp=start_ts)
        # If output appeared and has settled for at least 0.3s
        if curr_text and curr_text == last_text and elapsed >= 0.5:
            break
        last_text = curr_text

    output = session.read_delta(since_timestamp=start_ts)
    return {
        "success": True,
        "session_id": session_id,
        "is_alive": session.is_alive,
        "command": command,
        "output": output,
        "duration_seconds": round(elapsed, 2),
    }


async def pty_session_interact_handler(
    session_id: str,
    input_text: str,
    send_interrupt: bool = False,
    wait_seconds: float = 1.0,
    **kwargs: Any,
) -> Dict[str, Any]:
    """Send interactive input or Ctrl+C signal to a running PTY session."""
    mgr = get_pty_manager()
    session = mgr.sessions.get(session_id)
    if not session or not session.is_alive:
        return {
            "success": False,
            "session_id": session_id,
            "error": f"PTY session '{session_id}' not found or inactive.",
            "output": "",
        }

    start_ts = time.time()
    if send_interrupt:
        session.send_interrupt()
    elif input_text:
        session.write(input_text)

    await asyncio.sleep(wait_seconds)
    output = session.read_delta(since_timestamp=start_ts)

    return {
        "success": True,
        "session_id": session_id,
        "is_alive": session.is_alive,
        "output": output,
    }


pty_run_def = ToolDefinition(
    name="pty_session_run",
    display_name="Persistent PTY Run",
    description=(
        "Executes a command inside a persistent stateful interactive PTY terminal session. "
        "Allows running long-lived background jobs, REPLs, and live dev servers with continuous output streaming."
    ),
    parameters={
        "command": {"type": "string", "description": "Shell command to execute in PTY session"},
        "session_id": {"type": "string", "description": "Persistent session identifier (default: 'default')"},
        "wait_seconds": {"type": "number", "description": "Initial seconds to wait and gather output buffer (default: 2.0)"},
        "cwd": {"type": "string", "description": "Working directory override for the session"},
    },
    required_parameters=["command"],
    permission_level="elevated",
    requires_confirmation=False,
    risk_level="high",
    cancellable=True,
    voice_aliases=["run in pty", "interactive terminal", "pty command"],
)

pty_interact_def = ToolDefinition(
    name="pty_session_interact",
    display_name="Persistent PTY Interact",
    description=(
        "Sends interactive stdin input, answers confirmation prompts, or sends Ctrl+C interrupt signals "
        "to an active persistent PTY session."
    ),
    parameters={
        "session_id": {"type": "string", "description": "Active session identifier"},
        "input_text": {"type": "string", "description": "Input text or keystrokes to write to stdin"},
        "send_interrupt": {"type": "boolean", "description": "If true, send Ctrl+C break signal to interrupt execution"},
        "wait_seconds": {"type": "number", "description": "Seconds to wait for response output (default: 1.0)"},
    },
    required_parameters=["session_id"],
    permission_level="elevated",
    requires_confirmation=False,
    risk_level="medium",
    cancellable=True,
    voice_aliases=["interact pty", "send input to terminal", "interrupt pty"],
)

registry.register(pty_run_def, pty_session_run_handler)
registry.register(pty_interact_def, pty_session_interact_handler)
