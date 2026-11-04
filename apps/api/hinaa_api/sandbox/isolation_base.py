"""Abstract base contract for sandbox isolation backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.sandbox.limits import ResourceLimits


class IsolationBackendType(str, Enum):
    DOCKER_CONTAINER = "DOCKER_CONTAINER"
    WSL2_MICROVM = "WSL2_MICROVM"
    RESTRICTED_HOST_PROCESS = "RESTRICTED_HOST_PROCESS"
    UNAVAILABLE = "UNAVAILABLE"


class SecurityLevel(str, Enum):
    HIGH = "HIGH"          # Kernel container with user namespaces & seccomp
    MEDIUM = "MEDIUM"      # VM / MicroVM isolation
    RESTRICTED = "RESTRICTED" # OS Job Object + scrubbed env + workspace boundary
    NONE = "NONE"


class ExecutionResult(BaseModel):
    """Normalized result of executing a command inside a sandbox."""

    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float
    timed_out: bool = False
    oom_killed: bool = False
    memory_peak_mb: Optional[float] = None
    truncated: bool = False
    backend_type: IsolationBackendType = IsolationBackendType.RESTRICTED_HOST_PROCESS
    security_violations: List[str] = Field(default_factory=list)


class SandboxAdapter(ABC):
    """Base interface for sandbox isolation adapters."""

    @abstractmethod
    async def run_command(
        self,
        cmd_args: List[str],
        cwd: Path,
        env: Optional[Dict[str, str]] = None,
        limits: Optional[ResourceLimits] = None,
    ) -> ExecutionResult:
        """Executes a command under isolation constraints."""
        pass

    @abstractmethod
    async def terminate(self) -> None:
        """Kills any active process tree and cleans up sandbox resources."""
        pass

    @abstractmethod
    async def cleanup(self) -> None:
        """Cleans up ephemeral files and resets adapter state."""
        pass
