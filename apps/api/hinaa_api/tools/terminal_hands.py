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

# Check if WSL is available on Windows
WSL_AVAILABLE = False
if os.name == "nt":
    try:
        r = subprocess.run(["wsl", "--status"], capture_output=True, timeout=3)
        WSL_AVAILABLE = (r.returncode == 0)
    except Exception:
        WSL_AVAILABLE = False


class TerminalExecuteParams(BaseModel):
    command: str = Field(..., description="The shell command or script to execute (e.g. 'git status', 'uname -a', 'python -m pytest')")
    cwd: str | None = Field(default=None, description="Working directory relative to project root")
    timeout_seconds: int = Field(default=30, le=120, description="Max execution timeout in seconds")
    runtime: str = Field(default="auto", description="Execution runtime: 'auto', 'linux', 'kali', 'powershell', 'cmd'")
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
            proc = await asyncio.create_subprocess_exec(
                "git", "diff", "HEAD~1",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(PROJECT_ROOT),
            )
            stdout, _ = await proc.communicate()
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

    # 3. Resolve working directory
    resolved_cwd = PROJECT_ROOT
    if params.cwd:
        candidate = (PROJECT_ROOT / params.cwd).resolve()
        if candidate.is_relative_to(PROJECT_ROOT) and candidate.exists():
            resolved_cwd = candidate

    # 4. Resolve Runtime: Kali Linux (WSL), PowerShell, or Native Shell
    active_runtime = "native"
    sub_cmd: list[str] | str = cmd

    want_linux = params.runtime in ("linux", "kali") or (
        params.runtime == "auto"
        and os.name == "nt"
        and WSL_AVAILABLE
        and any(
            cmd_lower.startswith(x)
            for x in (
                "uname", "apt", "cat /etc", "grep ", "ps aux", "df -h",
                "free -m", "which ", "whoami", "ip a", "netstat", "nmap",
                "curl -", "sed ", "awk ", "ls -l", "top -b"
            )
        )
    )

    if want_linux:
        if os.name == "nt" and WSL_AVAILABLE:
            active_runtime = "kali-linux-wsl"
            wsl_cwd = _to_wsl_path(resolved_cwd)
            # Run inside Kali Linux with working directory set
            wrapped = f"cd {shlex.quote(wsl_cwd)} && {cmd}"
            sub_cmd = ["wsl", "-d", "kali-linux", "--", "bash", "-c", wrapped]
        else:
            active_runtime = "linux-bash"
            sub_cmd = ["/bin/bash", "-c", cmd]
    elif params.runtime == "powershell" and os.name == "nt":
        active_runtime = "powershell"
        sub_cmd = ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd]
    elif params.runtime == "cmd" and os.name == "nt":
        active_runtime = "cmd"
        sub_cmd = ["cmd.exe", "/c", cmd]

    logger.info("Executing terminal command: %s (runtime=%s, cwd=%s)", cmd, active_runtime, resolved_cwd)

    # 5. Build environment
    proc_env = os.environ.copy()
    if params.env:
        proc_env.update(params.env)

    # 6. Execute subprocess
    try:
        if isinstance(sub_cmd, list):
            proc = await asyncio.create_subprocess_exec(
                *sub_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved_cwd) if active_runtime != "kali-linux-wsl" else None,
                env=proc_env,
            )
        else:
            proc = await asyncio.create_subprocess_shell(
                sub_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(resolved_cwd),
                env=proc_env,
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
                "runtime": active_runtime,
                "command": cmd,
                "timeoutSeconds": params.timeout_seconds,
                "error": f"Command timed out after {params.timeout_seconds} seconds.",
            }

        stdout_text = stdout_bytes.decode("utf-8", errors="replace").strip()
        stderr_text = stderr_bytes.decode("utf-8", errors="replace").strip()
        exit_code = proc.returncode

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
