"""Autonomous OS Terminal & Kali Linux Security Workbench Execution Tool for HINAA.

Enables HINAA to execute shell commands, run Python/Node scripts, control Kali Linux WSL,
manage project worktrees, perform ethical red-team security audits, and execute test suites
with execution timeouts, guardrails, and structured telemetry.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import socket
import ssl
import subprocess
import sys
from typing import Literal
from pathlib import Path
from typing import Any
from pydantic import BaseModel, Field

from hinaa_api.runtime_paths import project_root
from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.terminal_hands")

# Root directory whitelist boundary
PROJECT_ROOT = project_root()

# Command blocklist to prevent destructive accidental OS wipes
DISALLOWED_COMMANDS = [
    "format",
    "rmdir /s /q c:",
    "del /f /s /q c:",
    ":(){ :|:& };:",
    "shutdown",
    "drop database",
]

def _wsl_distributions() -> list[str]:
    if os.name != "nt":
        return []
    try:
        result = subprocess.run(["wsl.exe", "--list", "--quiet"], capture_output=True, timeout=5,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        return [line.strip() for line in result.stdout.decode("utf-16-le", errors="replace").replace("\x00", "").splitlines() if line.strip()] if result.returncode == 0 else []
    except (OSError, subprocess.TimeoutExpired):
        return []


def _powershell_exe() -> str:
    """Locate powershell.exe even when WindowsPowerShell is missing from PATH.

    The backend inherits a minimal PATH from its launcher, and on machines
    where that PATH lacks the WindowsPowerShell directory the bare name fails
    with WinError 2 — every terminal command then reported "failed" even
    though PowerShell is installed at its well-known System32 location.
    """
    import shutil

    found = shutil.which("powershell.exe")
    if found:
        return found
    candidate = (
        Path(os.environ.get("SystemRoot", r"C:\Windows"))
        / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    )
    return str(candidate) if candidate.exists() else "powershell.exe"


def _run_command(command: list[str], cwd: Path, env: dict[str, str], timeout: int) -> tuple[int, bytes, bytes]:
    # Windows Uvicorn uses a Selector event loop, which cannot create asyncio
    # subprocess transports. Run process I/O in a worker thread instead.
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            cwd=str(cwd), env=env, creationflags=flags,
                            start_new_session=os.name != "nt")
    try:
        out, err = proc.communicate(timeout=timeout)
        return proc.returncode, out, err
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            subprocess.run(["taskkill.exe", "/PID", str(proc.pid), "/T", "/F"],
                           capture_output=True, timeout=10, creationflags=flags)
        else:
            import signal
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise


class TerminalExecuteParams(BaseModel):
    command: str = Field(..., description="The shell command or script to execute (e.g. 'git status', 'uname -a', 'python -m pytest')")
    cwd: str | None = Field(default=None, description="Working directory relative to project root")
    timeout_seconds: int = Field(default=30, ge=1, le=120, description="Max execution timeout in seconds")
    runtime: Literal["auto", "linux", "kali", "powershell", "cmd"] = Field(default="auto", description="Execution runtime: 'auto', 'linux', 'kali', 'powershell', 'cmd'")
    env: dict[str, str] | None = Field(default=None, description="Optional extra environment variables")


def _to_wsl_path(path: Path) -> str:
    """Convert Windows path to WSL /mnt/... path."""
    drive = path.drive.rstrip(":").lower()
    rest = path.as_posix()[len(path.drive):].lstrip("/")
    return f"/mnt/{drive}/{rest}"


async def _run_security_audit_action(action: str, target: str) -> dict[str, Any] | None:
    """Built-in ethical security inspection primitives."""
    action = action.lower()
    target = target.strip()

    if action == "sec:headers":
        url = target if target.startswith("http") else f"https://{target}"
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                resp = await client.get(url)
                headers = dict(resp.headers)
                
                required_sec_headers = {
                    "strict-transport-security": "Protects against SSL stripping (HSTS)",
                    "content-security-policy": "Prevents XSS and malicious script injection",
                    "x-content-type-options": "Prevents MIME sniffing attacks",
                    "x-frame-options": "Defends against clickjacking",
                    "referrer-policy": "Controls referrer information leakage",
                    "permissions-policy": "Restricts browser feature access",
                }
                
                present = {h: headers.get(h) for h in required_sec_headers if h in headers}
                missing = [h for h in required_sec_headers if h not in headers]
                score = round((len(present) / len(required_sec_headers)) * 100)
                grade = "A" if score >= 85 else ("B" if score >= 65 else ("C" if score >= 40 else "F"))
                
                return {
                    "auditType": "HTTP Security Headers",
                    "target": url,
                    "statusCode": resp.status_code,
                    "score": f"{score}/100",
                    "grade": grade,
                    "presentHeaders": present,
                    "missingHeaders": missing,
                    "recommendation": (
                        "All essential headers present." if not missing
                        else f"Add missing security headers: {', '.join(missing[:3])} to protect against web vulnerabilities."
                    ),
                }
        except Exception as exc:
            return {"auditType": "HTTP Security Headers", "target": url, "error": str(exc)}

    elif action == "sec:ssl":
        host = target.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        try:
            ctx = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=6) as sock:
                with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                    cert = ssock.getpeercert()
                    cipher = ssock.cipher()
                    version = ssock.version()
                    return {
                        "auditType": "TLS/SSL Certificate Audit",
                        "host": host,
                        "tlsVersion": version,
                        "cipherSuite": cipher,
                        "issuer": dict(x[0] for x in cert.get("issuer", ())),
                        "subject": dict(x[0] for x in cert.get("subject", ())),
                        "notBefore": cert.get("notBefore"),
                        "notAfter": cert.get("notAfter"),
                        "san": [x[1] for x in cert.get("subjectAltName", ()) if x[0] == "DNS"],
                        "status": "VALID",
                    }
        except Exception as exc:
            return {"auditType": "TLS/SSL Certificate Audit", "host": host, "status": "ERROR", "error": str(exc)}

    elif action == "sec:ports":
        host = target.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0]
        common_ports = [21, 22, 25, 53, 80, 110, 143, 443, 3000, 3306, 5432, 6379, 8000, 8080, 8443]
        open_ports = []
        for port in common_ports:
            try:
                _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=0.8)
                open_ports.append(port)
                writer.close()
                await writer.wait_closed()
            except Exception:
                pass
        return {
            "auditType": "Port Enumeration",
            "host": host,
            "probedPortsCount": len(common_ports),
            "openPorts": open_ports,
            "summary": f"Found {len(open_ports)} open port(s): {', '.join(map(str, open_ports))}" if open_ports else "No common ports open.",
        }

    elif action == "sec:gitleaks":
        try:
            # Check recent git diff for secret tokens
            code, stdout, stderr = await asyncio.to_thread(
                _run_command, ["git", "diff", "HEAD~1"], PROJECT_ROOT, dict(os.environ), 15,
            )
            if code != 0:
                return {"auditType": "Git Secret Exposure Scan", "error": "Git diff could not be read; ensure this workspace has a previous commit."}
            diff_text = stdout.decode("utf-8", errors="replace")
            
            patterns = [
                (r"(?i)api[_-]?key\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "API Key assignment"),
                (r"(?i)sk-[A-Za-z0-9]{24,}", "OpenAI API Key format"),
                (r"(?i)ghp_[A-Za-z0-9]{36}", "GitHub Personal Access Token"),
                (r"-----BEGIN (?:RSA )?PRIVATE KEY-----", "Private RSA Key"),
            ]
            leaks = []
            for pat, desc in patterns:
                matches = re.findall(pat, diff_text)
                if matches:
                    leaks.append(f"{desc} ({len(matches)} match(es))")
            return {
                "auditType": "Git Secret Exposure Scan",
                "scannedDiffLines": len(diff_text.splitlines()),
                "findingsCount": len(leaks),
                "leaksDetected": leaks,
                "status": "CLEAN" if not leaks else "WARNING_SECRETS_FOUND",
            }
        except Exception as exc:
            return {"auditType": "Git Secret Exposure Scan", "error": str(exc)}

    return None


async def execute_terminal_hands(params: TerminalExecuteParams | dict[str, Any]) -> dict[str, Any]:
    """Execute terminal command, Kali Linux WSL session, or security inspection."""
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

    # 2. Check for built-in security inspection prefix
    parts = cmd.split(maxsplit=1)
    if len(parts) >= 1 and parts[0].startswith("sec:"):
        action = parts[0]
        target = parts[1] if len(parts) > 1 else ""
        audit_result = await _run_security_audit_action(action, target)
        if audit_result is not None:
            import json
            pretty = json.dumps(audit_result, indent=2)
            return {
                "status": "success",
                "runtime": "security-workbench",
                "exitCode": 0,
                "command": cmd,
                "cwd": str(PROJECT_ROOT),
                "stdout": pretty,
                "stderr": "",
                "summary": f"Security audit '{action}' completed.",
                "securityAudit": audit_result,
            }

    # Reject invalid paths rather than silently running in another directory.
    resolved_cwd = (PROJECT_ROOT / (params.cwd or ".")).resolve()
    if not resolved_cwd.is_relative_to(PROJECT_ROOT) or not resolved_cwd.is_dir():
        return {"status":"rejected", "command":cmd, "error":"Working directory must be an existing folder inside the Hina workspace."}

    active_runtime = "powershell" if os.name == "nt" else "linux-bash"
    sub_cmd = [_powershell_exe(), "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", cmd] if os.name == "nt" else ["/bin/bash", "-c", cmd]
    if params.runtime in ("linux", "kali") and os.name == "nt":
        distributions = await asyncio.to_thread(_wsl_distributions)
        chosen = next((name for name in distributions if "kali" in name.lower()), None) if params.runtime == "kali" else next(iter(distributions), None)
        if not chosen:
            return {"status":"unavailable", "command":cmd, "runtime":params.runtime,
                    "error":"Kali Linux WSL is not installed or running. Use PowerShell, or install your chosen WSL distribution before selecting this runtime."}
        active_runtime = f"wsl:{chosen}"
        sub_cmd = ["wsl.exe", "-d", chosen, "--cd", _to_wsl_path(resolved_cwd), "--", "bash", "-c", cmd]
    elif params.runtime == "cmd" and os.name == "nt":
        active_runtime, sub_cmd = "cmd", ["cmd.exe", "/d", "/c", cmd]
    elif params.runtime in ("powershell", "cmd") and os.name != "nt":
        return {"status":"unavailable", "command":cmd, "runtime":params.runtime, "error":"This runtime requires a Windows host."}

    proc_env = os.environ.copy()
    python_bin = PROJECT_ROOT / "apps/api/.venv" / ("Scripts" if os.name == "nt" else "bin")
    proc_env["PATH"] = str(python_bin) + os.pathsep + proc_env.get("PATH", "")
    if params.env:
        proc_env.update(params.env)
    try:
        exit_code, stdout_bytes, stderr_bytes = await asyncio.to_thread(
            _run_command, sub_cmd, resolved_cwd, proc_env, params.timeout_seconds)
        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()

        # Truncate giant outputs if needed
        max_output_len = 10000
        truncated_stdout = stdout_text[:max_output_len] + ("\n... [truncated]" if len(stdout_text) > max_output_len else "")
        truncated_stderr = stderr_text[:max_output_len] + ("\n... [truncated]" if len(stderr_text) > max_output_len else "")

        return {
            "status": "success" if exit_code == 0 else "error",
            "runtime": active_runtime,
            "exitCode": exit_code,
            "command": cmd,
            "cwd": str(resolved_cwd),
            "stdout": truncated_stdout,
            "stderr": truncated_stderr,
            "summary": (
                f"Command completed successfully on {active_runtime} (exit {exit_code})."
                if exit_code == 0
                else f"Command failed with exit code {exit_code} on {active_runtime}."
            ),
        }
    except subprocess.TimeoutExpired:
        return {"status":"timeout", "runtime":active_runtime, "command":cmd,
                "timeoutSeconds":params.timeout_seconds, "error":f"Command timed out after {params.timeout_seconds} seconds; its process tree was stopped."}
    except Exception as exc:
        logger.error("Terminal execution failed: %s", exc)
        return {
            "status": "failed",
            "runtime": active_runtime,
            "command": cmd,
            "error": str(exc),
        }


terminal_hands_def = ToolDefinition(
    name="terminal_hands",
    display_name="Terminal / Kali Linux & Security Hands",
    description="Executes shell commands in native OS or Kali Linux WSL, runs test suites, performs ethical security audits (sec:headers, sec:ssl, sec:ports, sec:gitleaks), and manages code worktrees.",
    parameters={
        "command": {"type": "string", "description": "The exact command to run (e.g. 'git status', 'uname -a', 'python -m pytest', 'sec:headers google.com')"},
        "cwd": {"type": "string", "description": "Relative working directory from project root"},
        "timeout_seconds": {"type": "integer", "description": "Max timeout in seconds (default 30, max 120)"},
        "runtime": {"type": "string", "description": "Target runtime: 'auto', 'linux', 'kali', 'powershell', 'cmd'"},
    },
    required_parameters=["command"],
    voice_aliases=["run command", "terminal hands", "execute command", "run test", "git status", "run linux command", "security audit"],
    requires_confirmation=True,
)

registry.register(terminal_hands_def, execute_terminal_hands)
