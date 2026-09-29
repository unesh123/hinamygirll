"""Computer Hands & OS Terminal Execution Tool for HINAA.

Enables HINAA to execute shell commands, run Python scripts, manage project worktrees,
execute test suites, and perform local file operations with execution timeouts,
security guardrails, and structured output reporting.
"""
from __future__ import annotations

import asyncio
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.terminal_hands")

# Root directory whitelist boundary
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Command blocklist to prevent destructive accidental OS wipes
DISALLOWED_COMMANDS = [
    "format",
    "rmdir /s /q c:",
    "del /f /s /q c:",
    ":(){ :|:& };:",
    "shutdown",
    "drop database",
]


class TerminalExecuteParams(BaseModel):
    command: str = Field(..., description="The shell command or script to execute (e.g. 'git status', 'python -m pytest')")
    cwd: str | None = Field(default=None, description="Working directory relative to project root")
    timeout_seconds: int = Field(default=30, le=120, description="Max execution timeout in seconds")


async def execute_terminal_hands(params: TerminalExecuteParams | dict[str, Any]) -> dict[str, Any]:
    """Execute a terminal command with security guardrails and return captured stdout/stderr."""
    if isinstance(params, dict):
        params = TerminalExecuteParams(**params)

    cmd = params.command.strip()
    cmd_lower = cmd.lower()

    # 1. Guardrail check
    for disallowed in DISALLOWED_COMMANDS:
        if disallowed in cmd_lower:
            return {
                "status": "rejected",
                "command": cmd,
                "error": f"Security Guardrail: Execution of '{disallowed}' is prohibited by system safety policy.",
            }

    # 2. Resolve working directory
    resolved_cwd = PROJECT_ROOT
    if params.cwd:
        candidate = (PROJECT_ROOT / params.cwd).resolve()
        if candidate.is_relative_to(PROJECT_ROOT) and candidate.exists():
            resolved_cwd = candidate

    logger.info("Executing terminal command: %s (cwd=%s)", cmd, resolved_cwd)

    # 3. Asynchronously run command in subprocess
    try:
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(resolved_cwd),
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=params.timeout_seconds,
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            return {
                "status": "timeout",
                "command": cmd,
                "timeoutSeconds": params.timeout_seconds,
                "error": f"Command timed out after {params.timeout_seconds} seconds.",
            }

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        exit_code = proc.returncode

        # Truncate giant outputs if needed
        max_output_len = 8000
        truncated_stdout = stdout_text[:max_output_len] + ("\n... [truncated]" if len(stdout_text) > max_output_len else "")
        truncated_stderr = stderr_text[:max_output_len] + ("\n... [truncated]" if len(stderr_text) > max_output_len else "")

        return {
            "status": "success" if exit_code == 0 else "error",
            "exitCode": exit_code,
            "command": cmd,
            "cwd": str(resolved_cwd),
            "stdout": truncated_stdout,
            "stderr": truncated_stderr,
            "summary": (
                f"Command completed successfully (exit {exit_code})."
                if exit_code == 0
                else f"Command failed with exit code {exit_code}."
            ),
        }
    except Exception as exc:
        logger.error("Terminal execution failed: %s", exc)
        return {
            "status": "failed",
            "command": cmd,
            "error": str(exc),
        }


terminal_hands_def = ToolDefinition(
    name="terminal_hands",
    display_name="Terminal / Computer Hands",
    description="Executes shell commands, runs test suites, manages git, and executes Python scripts in the local environment.",
    parameters={
        "command": {"type": "string", "description": "The exact command to run (e.g. 'git log -n 5', 'npm test')"},
        "cwd": {"type": "string", "description": "Relative working directory from project root"},
        "timeout_seconds": {"type": "integer", "description": "Max timeout in seconds (default 30, max 120)"},
    },
    required_parameters=["command"],
    voice_aliases=["run command", "terminal hands", "execute command", "run test", "git status"],
    requires_confirmation=True,
)

registry.register(terminal_hands_def, execute_terminal_hands)
