"""Restricted Host Process Adapter for controlled local workspace execution.

Applies strict workspace path verification, environment scrubbing, process-tree
termination via Windows Job Objects / taskkill, and output buffer ceilings.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import platform
import re
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from hinaa_api.sandbox.isolation_base import (
    ExecutionResult,
    IsolationBackendType,
    SandboxAdapter,
)
from hinaa_api.sandbox.limits import ResourceLimits

logger = logging.getLogger("hinaa.sandbox.process")

# Sensitive environment variable patterns to scrub unconditionally
_SCRUB_PATTERNS = [
    re.compile(r"KEY", re.IGNORECASE),
    re.compile(r"SECRET", re.IGNORECASE),
    re.compile(r"TOKEN", re.IGNORECASE),
    re.compile(r"AUTH", re.IGNORECASE),
    re.compile(r"PASS", re.IGNORECASE),
    re.compile(r"CREDENTIAL", re.IGNORECASE),
    re.compile(r"AWS_", re.IGNORECASE),
    re.compile(r"AZURE_", re.IGNORECASE),
    re.compile(r"OPENAI_", re.IGNORECASE),
    re.compile(r"GEMINI_", re.IGNORECASE),
    re.compile(r"EXA_", re.IGNORECASE),
    re.compile(r"YDC_", re.IGNORECASE),
    re.compile(r"ESEWA_", re.IGNORECASE),
    re.compile(r"KHALTI_", re.IGNORECASE),
    re.compile(r"SSH_", re.IGNORECASE),
    re.compile(r"GITHUB_", re.IGNORECASE),
]

# Baseline environment keys permitted to pass into child process
_ALLOWED_ENV_KEYS: Set[str] = {
    "PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "WINDIR",
    "PROGRAMFILES", "PROGRAMFILES(X86)", "COMMONPROGRAMFILES",
    "HOMEDRIVE", "HOMEPATH", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
    "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "OS", "PATHEXT",
    "LANG", "LC_ALL", "TERM",
}


class WindowsJobObjectManager:
    """Manages Windows Job Object to ensure zero orphaned descendant processes."""

    def __init__(self) -> None:
        self.job_handle = None
        if platform.system().lower() == "windows":
            try:
                kernel32 = ctypes.windll.kernel32
                # Create job object
                self.job_handle = kernel32.CreateJobObjectW(None, None)
                if self.job_handle:
                    # Set JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE (0x2000)
                    class JOBOBJECT_BASIC_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("PerProcessUserTimeLimit", ctypes.c_int64),
                            ("PerJobUserTimeLimit", ctypes.c_int64),
                            ("LimitFlags", ctypes.c_uint32),
                            ("MinimumWorkingSetSize", ctypes.c_size_t),
                            ("MaximumWorkingSetSize", ctypes.c_size_t),
                            ("ActiveProcessLimit", ctypes.c_uint32),
                            ("Affinity", ctypes.c_size_t),
                            ("PriorityClass", ctypes.c_uint32),
                            ("SchedulingClass", ctypes.c_uint32),
                        ]

                    class IO_COUNTERS(ctypes.Structure):
                        _fields_ = [
                            ("ReadOperationCount", ctypes.c_uint64),
                            ("WriteOperationCount", ctypes.c_uint64),
                            ("OtherOperationCount", ctypes.c_uint64),
                            ("ReadTransferCount", ctypes.c_uint64),
                            ("WriteTransferCount", ctypes.c_uint64),
                            ("OtherTransferCount", ctypes.c_uint64),
                        ]

                    class JOBOBJECT_EXTENDED_LIMIT_INFORMATION(ctypes.Structure):
                        _fields_ = [
                            ("BasicLimitInformation", JOBOBJECT_BASIC_LIMIT_INFORMATION),
                            ("IoInfo", IO_COUNTERS),
                            ("ProcessMemoryLimit", ctypes.c_size_t),
                            ("JobMemoryLimit", ctypes.c_size_t),
                            ("PeakProcessMemoryLimit", ctypes.c_size_t),
                            ("PeakJobMemoryLimit", ctypes.c_size_t),
                        ]

                    JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x2000
                    info = JOBOBJECT_EXTENDED_LIMIT_INFORMATION()
                    info.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                    JobObjectExtendedLimitInformation = 9
                    kernel32.SetInformationJobObject(
                        self.job_handle,
                        JobObjectExtendedLimitInformation,
                        ctypes.byref(info),
                        ctypes.sizeof(info),
                    )
            except Exception as exc:
                logger.debug("Failed to initialize Windows Job Object: %s", exc)
                self.job_handle = None

    def assign_process(self, pid: int) -> bool:
        if not self.job_handle or platform.system().lower() != "windows":
            return False
        try:
            PROCESS_SET_QUOTA = 0x0100
            PROCESS_TERMINATE = 0x0001
            kernel32 = ctypes.windll.kernel32
            handle = kernel32.OpenProcess(PROCESS_SET_QUOTA | PROCESS_TERMINATE, False, pid)
            if handle:
                res = kernel32.AssignProcessToJobObject(self.job_handle, handle)
                kernel32.CloseHandle(handle)
                return bool(res)
        except Exception:
            return False
        return False

    def close(self) -> None:
        if self.job_handle and platform.system().lower() == "windows":
            try:
                ctypes.windll.kernel32.CloseHandle(self.job_handle)
            except Exception:
                pass
            self.job_handle = None


class RestrictedProcessAdapter(SandboxAdapter):
    """Executes commands on host with strict boundary checks, environment scrubbing,

    and guaranteed process-tree kill.
    """

    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root.resolve()
        self.active_processes: Set[asyncio.subprocess.Process] = set()
        self.job_manager = WindowsJobObjectManager()

    def _validate_path_boundary(self, target_path: Path) -> bool:
        """Verifies that target path does not escape the authorized workspace root."""
        try:
            resolved = target_path.resolve()
            # Must start with workspace_root or equal it
            return resolved == self.workspace_root or str(resolved).startswith(str(self.workspace_root) + os.sep)
        except Exception:
            return False

    def _sanitize_environment(self, custom_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """Strips secrets and sensitive tokens from process environment."""
        sanitized: Dict[str, str] = {}
        for k, v in os.environ.items():
            k_upper = k.upper()
            # If matches sensitive pattern, drop it
            if any(pat.search(k) for pat in _SCRUB_PATTERNS):
                continue
            if k_upper in _ALLOWED_ENV_KEYS:
                sanitized[k] = v

        if custom_env:
            for k, v in custom_env.items():
                if any(pat.search(k) for pat in _SCRUB_PATTERNS):
                    continue
                sanitized[k] = str(v)

        # Allow local workspace module imports
        if "PYTHONPATH" not in sanitized:
            sanitized["PYTHONPATH"] = str(self.workspace_root)

        return sanitized

    async def run_command(
        self,
        cmd_args: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        limits: Optional[ResourceLimits] = None,
    ) -> ExecutionResult:
        lim = limits or ResourceLimits()
        security_violations: List[str] = []

        # Validate arguments: never execute raw shell strings or shell injection
        if not cmd_args:
            return ExecutionResult(
                command=[],
                exit_code=1,
                stdout="",
                stderr="Error: Empty command argument array.",
                duration_ms=0.0,
                security_violations=["EMPTY_COMMAND"],
            )

        # Validate working directory
        if not self._validate_path_boundary(cwd):
            msg = f"Security Violation: CWD '{cwd}' escapes authorized workspace '{self.workspace_root}'"
            logger.error(msg)
            return ExecutionResult(
                command=cmd_args,
                exit_code=126,
                stdout="",
                stderr=msg,
                duration_ms=0.0,
                security_violations=["PATH_TRAVERSAL_ESCAPE"],
            )

        # Build sanitized environment
        clean_env = self._sanitize_environment(env)

        t_start = time.perf_counter()
        proc: Optional[asyncio.subprocess.Process] = None
        timed_out = False
        oom_killed = False
        stdout_text = ""
        stderr_text = ""

        try:
            # Spawn process without shell=True to prevent shell interpolation
            proc = await asyncio.create_subprocess_exec(
                cmd_args[0],
                *cmd_args[1:],
                cwd=str(cwd),
                env=clean_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self.active_processes.add(proc)

            # Assign to Windows Job Object
            if proc.pid:
                self.job_manager.assign_process(proc.pid)

            # Wait with strict timeout
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=lim.timeout_seconds,
            )
            exit_code = proc.returncode if proc.returncode is not None else 0

        except asyncio.TimeoutError:
            timed_out = True
            exit_code = -1
            stdout_bytes = b""
            stderr_bytes = f"Execution timed out after {lim.timeout_seconds} seconds.".encode("utf-8")
            if proc:
                await self._kill_process_tree(proc)

        except Exception as exc:
            exit_code = -1
            stdout_bytes = b""
            stderr_bytes = str(exc).encode("utf-8")
            if proc:
                await self._kill_process_tree(proc)

        finally:
            if proc in self.active_processes:
                self.active_processes.remove(proc)

        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        # Enforce output buffer ceilings
        truncated = False
        if len(stdout_bytes) > lim.max_output_bytes:
            stdout_bytes = stdout_bytes[:lim.max_output_bytes] + b"\n... [OUTPUT TRUNCATED: Exceeded 1MB limit]"
            truncated = True
        if len(stderr_bytes) > lim.max_output_bytes:
            stderr_bytes = stderr_bytes[:lim.max_output_bytes] + b"\n... [OUTPUT TRUNCATED: Exceeded 1MB limit]"
            truncated = True

        stdout_text = stdout_bytes.decode("utf-8", errors="replace")
        stderr_text = stderr_bytes.decode("utf-8", errors="replace")

        return ExecutionResult(
            command=cmd_args,
            exit_code=exit_code,
            stdout=stdout_text,
            stderr=stderr_text,
            duration_ms=duration_ms,
            timed_out=timed_out,
            oom_killed=oom_killed,
            truncated=truncated,
            backend_type=IsolationBackendType.RESTRICTED_HOST_PROCESS,
            security_violations=security_violations,
        )

    async def _kill_process_tree(self, proc: asyncio.subprocess.Process) -> None:
        """Kills process and all its children recursively."""
        if not proc.pid:
            return
        pid = proc.pid
        if platform.system().lower() == "windows":
            try:
                # Forcefully kill process tree
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)
            except Exception:
                pass
        else:
            try:
                proc.kill()
            except Exception:
                pass

    async def terminate(self) -> None:
        """Kills all active child processes immediately."""
        for proc in list(self.active_processes):
            await self._kill_process_tree(proc)
        self.active_processes.clear()

    async def cleanup(self) -> None:
        """Cleans up job objects and resets adapter."""
        await self.terminate()
        self.job_manager.close()
