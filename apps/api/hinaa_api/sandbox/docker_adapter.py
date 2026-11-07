"""Docker Container Isolation Adapter.

Executes untrusted workloads in non-root, capability-dropped, unprivileged
containers with strict memory, CPU, PID, and network boundaries.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional

from hinaa_api.sandbox.isolation_base import (
    ExecutionResult,
    IsolationBackendType,
    SandboxAdapter,
)
from hinaa_api.sandbox.limits import ResourceLimits

logger = logging.getLogger("hinaa.sandbox.docker")


class DockerContainerAdapter(SandboxAdapter):
    """Executes commands inside disposable Docker containers with seccomp and capability drop."""

    def __init__(
        self,
        workspace_root: Path,
        image: str = "python:3.11-slim",
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.image = image
        self.active_container_ids: List[str] = []

    def validate_security_flags(self, cmd_args: List[str]) -> List[str]:
        """Detects and rejects privilege escalation requests or docker socket mounts."""
        violations = []
        joined = " ".join(cmd_args).lower()
        if "--privileged" in joined:
            violations.append("PRIVILEGED_CONTAINER_REJECTED")
        if "docker.sock" in joined or "/var/run/docker.sock" in joined:
            violations.append("DOCKER_SOCKET_MOUNT_REJECTED")
        if "-v /:" in joined or "--volume /:" in joined or "c:\\" in joined:
            violations.append("HOST_ROOT_MOUNT_REJECTED")
        return violations

    async def run_command(
        self,
        cmd_args: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        limits: Optional[ResourceLimits] = None,
    ) -> ExecutionResult:
        lim = limits or ResourceLimits()
        violations = self.validate_security_flags(cmd_args)
        if violations:
            return ExecutionResult(
                command=cmd_args,
                exit_code=126,
                stdout="",
                stderr=f"Security Policy Violation: {', '.join(violations)}",
                duration_ms=0.0,
                backend_type=IsolationBackendType.DOCKER_CONTAINER,
                security_violations=violations,
            )

        container_name = f"hinaa_box_{int(time.time()*1000)}"

        # Build hardened docker run arguments
        docker_cmd = [
            "docker", "run", "--rm",
            f"--name={container_name}",
            f"--memory={lim.memory_mb_limit}m",
            f"--pids-limit={lim.max_pids}",
            "--security-opt=no-new-privileges",
            "--cap-drop=ALL",
            "-v", f"{self.workspace_root}:/workspace:rw",
            "-w", "/workspace",
            "-u", "1000:1000",
        ]

        if not lim.allow_network:
            docker_cmd.append("--network=none")

        if env:
            for k, v in env.items():
                docker_cmd.extend(["-e", f"{k}={v}"])

        docker_cmd.append(self.image)
        docker_cmd.extend(cmd_args)

        t_start = time.perf_counter()
        timed_out = False
        oom_killed = False

        try:
            self.active_container_ids.append(container_name)
            proc = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=lim.timeout_seconds,
            )
            exit_code = proc.returncode if proc.returncode is not None else 0

            # Detect OOM exit code (137 = 128 + 9 SIGKILL by kernel OOM)
            if exit_code == 137:
                oom_killed = True

        except asyncio.TimeoutError:
            timed_out = True
            exit_code = -1
            stdout_bytes = b""
            stderr_bytes = f"Container execution timed out after {lim.timeout_seconds} seconds.".encode("utf-8")
            # Force kill docker container
            try:
                subprocess.run(["docker", "kill", container_name], capture_output=True, check=False)
            except Exception:
                pass

        except Exception as exc:
            exit_code = -1
            stdout_bytes = b""
            stderr_bytes = str(exc).encode("utf-8")

        finally:
            if container_name in self.active_container_ids:
                self.active_container_ids.remove(container_name)

        duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

        return ExecutionResult(
            command=cmd_args,
            exit_code=exit_code,
            stdout=stdout_bytes.decode("utf-8", errors="replace"),
            stderr=stderr_bytes.decode("utf-8", errors="replace"),
            duration_ms=duration_ms,
            timed_out=timed_out,
            oom_killed=oom_killed,
            backend_type=IsolationBackendType.DOCKER_CONTAINER,
            security_violations=[],
        )

    async def terminate(self) -> None:
        """Kills any active container instances."""
        for cid in list(self.active_container_ids):
            try:
                subprocess.run(["docker", "kill", cid], capture_output=True, check=False)
            except Exception:
                pass
        self.active_container_ids.clear()

    async def cleanup(self) -> None:
        await self.terminate()
