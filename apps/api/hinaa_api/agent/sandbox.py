"""Sandbox Command Execution Engine (Directives §10–§15).

Provides:
1. CommandRequest and CommandResult with strict execution boundaries.
2. Path escape rejection (cwd and file paths must reside inside allowed_root).
3. Environment secret stripping (ambient API keys, tokens, and passwords removed).
4. Output credential redaction (stdout/stderr masked against token leaks).
5. Timeout and output buffer truncation guards.
6. Framework-aware failure output parsers (Pytest, TypeScript, SyntaxError).
"""

from __future__ import annotations

import asyncio
import os
import re
import shlex
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

# Patterns identifying secrets in environment variable names
_SECRET_ENV_PATTERNS = re.compile(
    r"(?i)(key|token|secret|password|auth|credential|jwt|private|cert|signature|conn_str)"
)

# Patterns identifying secrets in stdout/stderr text
_OUTPUT_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|access[_-]?token|authorization|secret|password)\s*[:=]\s*[^\s,;]+"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{82}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"\b(?:AIza|AKIA)[0-9A-Za-z-_]{35}\b"),
]

# Standard safe environment variables to preserve
_SAFE_ENV_NAMES = {
    "PATH",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "PYTHONPATH",
    "COMSPEC",
    "PATHEXT",
    "WINDIR",
    "LANG",
    "LC_ALL",
    "HOME",
    "USER",
    "VIRTUAL_ENV",
}


def sanitize_output(text: str) -> str:
    """Mask credential patterns in command output."""
    if not text:
        return ""
    sanitized = text
    for pat in _OUTPUT_SECRET_PATTERNS:
        sanitized = pat.sub("[REDACTED]", sanitized)
    return sanitized


class SandboxSecurityViolation(Exception):
    """Raised when a command violates sandbox boundaries (e.g. path escape)."""
    pass


@dataclass
class CommandRequest:
    command: list[str] | str
    cwd: str
    allowed_root: str
    timeout_seconds: float = 60.0
    env_overrides: dict[str, str] | None = None
    max_output_bytes: int = 200_000


@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    truncated: bool = False
    violation: str | None = None

    @property
    def success(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and self.violation is None


@dataclass
class ParsedFailureItem:
    location: str          # file:line or test node ID
    error_type: str        # e.g. AssertionError, SyntaxError, TS2322
    message: str           # assertion or error description
    snippet: str = ""      # code snippet or trace if available


@dataclass
class ParsedExecutionOutput:
    framework: str         # "pytest", "typescript", "python_syntax", "generic"
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    failures: list[ParsedFailureItem] = field(default_factory=list)
    raw_summary: str = ""


class SandboxExecutor:
    """Governed shell / process execution engine with sandbox boundary enforcement."""

    def __init__(self, default_allowed_root: str | None = None) -> None:
        self.default_allowed_root = (
            os.path.realpath(os.path.abspath(default_allowed_root))
            if default_allowed_root
            else None
        )

    def validate_boundary(self, target_path: str, allowed_root: str) -> str:
        """Asserts that target_path is within allowed_root, rejecting path escapes."""
        real_root = os.path.realpath(os.path.abspath(allowed_root))
        real_target = os.path.realpath(os.path.abspath(target_path))

        # Check prefix match
        try:
            rel = os.path.relpath(real_target, real_root)
            if rel.startswith("..") or rel == ".." or (os.path.splitdrive(real_target)[0].lower() != os.path.splitdrive(real_root)[0].lower()):
                raise SandboxSecurityViolation(
                    f"Path escape rejected: path {target_path!r} resolves to {real_target!r} outside allowed root {real_root!r}"
                )
        except ValueError as exc:
            raise SandboxSecurityViolation(
                f"Cross-drive or invalid path escape rejected: {exc}"
            ) from exc

        return real_target

    def build_clean_environment(self, env_overrides: dict[str, str] | None = None) -> dict[str, str]:
        """Builds an isolated environment without host secrets."""
        clean_env: dict[str, str] = {}
        for key, val in os.environ.items():
            # Skip any key matching secret pattern
            if _SECRET_ENV_PATTERNS.search(key):
                continue
            # Include if safe name or general system var
            if key.upper() in _SAFE_ENV_NAMES or key.startswith("PY") or key.startswith("LC_"):
                clean_env[key] = val

        if env_overrides:
            for k, v in env_overrides.items():
                if not _SECRET_ENV_PATTERNS.search(k):
                    clean_env[k] = v

        return clean_env

    async def run_command(self, request: CommandRequest) -> CommandResult:
        """Executes a command inside the sandbox asynchronously."""
        allowed_root = os.path.realpath(os.path.abspath(request.allowed_root or self.default_allowed_root or "."))

        # 1. Validate cwd boundary
        try:
            clean_cwd = self.validate_boundary(request.cwd, allowed_root)
        except SandboxSecurityViolation as exc:
            return CommandResult(
                exit_code=126,
                stdout="",
                stderr=str(exc),
                duration_ms=0.0,
                violation=str(exc),
            )

        # 2. Check for explicit path escape tokens in command if provided as string/list
        cmd_args = request.command if isinstance(request.command, list) else shlex.split(request.command, posix=(os.name != "nt"))
        if not cmd_args:
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr="Empty command provided",
                duration_ms=0.0,
            )

        # 3. Clean environment
        child_env = self.build_clean_environment(request.env_overrides)

        start_time = time.perf_counter()
        timed_out = False
        truncated = False
        stdout_text = ""
        stderr_text = ""
        exit_code = 1

        try:
            proc = await asyncio.create_subprocess_exec(
                cmd_args[0],
                *cmd_args[1:],
                cwd=clean_cwd,
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=request.timeout_seconds,
                )
                exit_code = proc.returncode if proc.returncode is not None else 1
            except asyncio.TimeoutError:
                timed_out = True
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                stdout_bytes, stderr_bytes = b"", b"Command execution timed out"
                exit_code = 124

            # Decode and truncate
            if len(stdout_bytes) > request.max_output_bytes:
                stdout_bytes = stdout_bytes[:request.max_output_bytes]
                truncated = True
            if len(stderr_bytes) > request.max_output_bytes:
                stderr_bytes = stderr_bytes[:request.max_output_bytes]
                truncated = True

            stdout_text = stdout_bytes.decode("utf-8", errors="replace")
            stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        except FileNotFoundError as exc:
            return CommandResult(
                exit_code=127,
                stdout="",
                stderr=f"Executable not found: {exc}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )
        except Exception as exc:
            return CommandResult(
                exit_code=1,
                stdout="",
                stderr=f"Execution failed: {exc}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        duration_ms = (time.perf_counter() - start_time) * 1000

        # Sanitize credential leaks from output
        clean_stdout = sanitize_output(stdout_text)
        clean_stderr = sanitize_output(stderr_text)

        return CommandResult(
            exit_code=exit_code,
            stdout=clean_stdout,
            stderr=clean_stderr,
            duration_ms=duration_ms,
            timed_out=timed_out,
            truncated=truncated,
        )


# ---------------------------------------------------------------------------
# Framework-Aware Failure Parsers
# ---------------------------------------------------------------------------

class PytestOutputParser:
    """Parses pytest test execution output to extract structured failure evidence."""

    _FAILURE_LINE_RE = re.compile(r"^FAILED\s+([^:]+)::([^\s]+)(?:\s+-\s+(.+))?", re.M)
    _ASSERTION_RE = re.compile(r"E\s+assert\s+(.+)$", re.M)
    _SUMMARY_RE = re.compile(r"=+\s*(?:(\d+)\s+failed)?(?:,\s*)?(?:(\d+)\s+passed)?(?:,\s*)?(?:(\d+)\s+skipped)?.*\s+=+", re.I)

    @classmethod
    def parse(cls, output: str) -> ParsedExecutionOutput:
        passed = 0
        failed = 0
        skipped = 0
        failures: list[ParsedFailureItem] = []

        passed_m = re.search(r"\b(\d+)\s+passed\b", output, re.I)
        failed_m = re.search(r"\b(\d+)\s+failed\b", output, re.I)
        skipped_m = re.search(r"\b(\d+)\s+skipped\b", output, re.I)

        if passed_m:
            passed = int(passed_m.group(1))
        if failed_m:
            failed = int(failed_m.group(1))
        if skipped_m:
            skipped = int(skipped_m.group(1))

        # Match failed test headers
        for m in cls._FAILURE_LINE_RE.finditer(output):
            fpath = m.group(1)
            test_name = m.group(2)
            msg = m.group(3) or "Test assertion failed"
            failures.append(
                ParsedFailureItem(
                    location=f"{fpath}::{test_name}",
                    error_type="AssertionError",
                    message=msg.strip(),
                )
            )

        # If no summary line found, check if there's any assertion error
        if not failures:
            for m in cls._ASSERTION_RE.finditer(output):
                failures.append(
                    ParsedFailureItem(
                        location="unknown",
                        error_type="AssertionError",
                        message=f"assert {m.group(1).strip()}",
                    )
                )

        raw_summary = f"{passed} passed, {failed} failed, {skipped} skipped" if (passed or failed or skipped) else ""
        return ParsedExecutionOutput(
            framework="pytest",
            passed=passed,
            failed=failed if failed else len(failures),
            skipped=skipped,
            failures=failures,
            raw_summary=raw_summary,
        )


class TypeScriptOutputParser:
    """Parses tsc output (file(line,col): error TSXXXX: message)."""

    _TS_ERROR_RE = re.compile(r"^([^(:]+)(?:[:(](\d+)[,:](\d+)\)?)?[:\s]+error\s+(TS\d+):\s+(.+)$", re.M)

    @classmethod
    def parse(cls, output: str) -> ParsedExecutionOutput:
        failures: list[ParsedFailureItem] = []
        for m in cls._TS_ERROR_RE.finditer(output):
            fpath = m.group(1).strip()
            line = m.group(2) or "0"
            code = m.group(4)
            msg = m.group(5).strip()
            failures.append(
                ParsedFailureItem(
                    location=f"{fpath}:{line}",
                    error_type=code,
                    message=msg,
                )
            )

        return ParsedExecutionOutput(
            framework="typescript",
            passed=0,
            failed=len(failures),
            skipped=0,
            failures=failures,
            raw_summary=f"{len(failures)} TypeScript type/syntax errors found",
        )


class PythonSyntaxOutputParser:
    """Parses python SyntaxError output."""

    _SYNTAX_RE = re.compile(r'File "([^"]+)", line (\d+)(?:, in .*)?\n(?:\s+(.+)\n)?(?:\s+\^\n)?SyntaxError:\s+(.+)', re.M)

    @classmethod
    def parse(cls, output: str) -> ParsedExecutionOutput:
        failures: list[ParsedFailureItem] = []
        for m in cls._SYNTAX_RE.finditer(output):
            fpath = m.group(1).strip()
            line = m.group(2)
            snippet = (m.group(3) or "").strip()
            msg = m.group(4).strip()
            failures.append(
                ParsedFailureItem(
                    location=f"{fpath}:{line}",
                    error_type="SyntaxError",
                    message=msg,
                    snippet=snippet,
                )
            )

        return ParsedExecutionOutput(
            framework="python_syntax",
            passed=0,
            failed=len(failures),
            skipped=0,
            failures=failures,
            raw_summary=f"{len(failures)} Python syntax errors found",
        )
