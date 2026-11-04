"""Runtime discovery and isolation capability detection.

Inspects host capabilities (Docker daemon, WSL2, Windows Job Objects) and
reports true security profiles without false claims of container isolation.
"""

from __future__ import annotations

import asyncio
import ctypes
import logging
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.sandbox.isolation_base import (
    IsolationBackendType,
    SandboxAdapter,
    SecurityLevel,
)

logger = logging.getLogger("hinaa.sandbox.discovery")


class IsolationHealthReport(BaseModel):
    """Detailed health and capabilities report of host sandbox isolation."""

    primary_backend: IsolationBackendType
    available_backends: List[IsolationBackendType]
    security_level: SecurityLevel
    can_execute_untrusted_code: bool
    details: Dict[str, Any] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)


class RuntimeDiscovery:
    """Discovers host isolation capabilities and selects appropriate sandbox adapters."""

    @classmethod
    def probe_docker(cls) -> bool:
        """Checks if Docker CLI exists AND Docker daemon is actively responding."""
        if not shutil.which("docker"):
            return False
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def probe_wsl2(cls) -> bool:
        """Checks if WSL2 is installed and responsive on Windows."""
        if platform.system().lower() != "windows":
            return False
        if not shutil.which("wsl"):
            return False
        try:
            res = subprocess.run(
                ["wsl", "-l", "-v"],
                capture_output=True,
                timeout=3,
                check=False,
            )
            return res.returncode == 0
        except Exception:
            return False

    @classmethod
    def probe_windows_job_object(cls) -> bool:
        """Checks if Windows Job Object kernel API is available for process tree limits."""
        if platform.system().lower() != "windows":
            return False
        try:
            return hasattr(ctypes.windll.kernel32, "CreateJobObjectW")
        except Exception:
            return False

    @classmethod
    def get_health_report(cls) -> IsolationHealthReport:
        """Generates comprehensive isolation capability report."""
        docker_live = cls.probe_docker()
        wsl_live = cls.probe_wsl2()
        job_object_live = cls.probe_windows_job_object()

        available: List[IsolationBackendType] = []
        if docker_live:
            available.append(IsolationBackendType.DOCKER_CONTAINER)
        if wsl_live:
            available.append(IsolationBackendType.WSL2_MICROVM)
        if job_object_live or platform.system().lower() in {"linux", "darwin"}:
            available.append(IsolationBackendType.RESTRICTED_HOST_PROCESS)

        if not available:
            return IsolationHealthReport(
                primary_backend=IsolationBackendType.UNAVAILABLE,
                available_backends=[],
                security_level=SecurityLevel.NONE,
                can_execute_untrusted_code=False,
                details={"error": "No isolation backend available."},
                recommendations=["Install Docker or enable WSL2 to permit code execution."],
            )

        # Primary backend prioritization
        if IsolationBackendType.DOCKER_CONTAINER in available:
            primary = IsolationBackendType.DOCKER_CONTAINER
            sec_level = SecurityLevel.HIGH
            can_untrusted = True
        elif IsolationBackendType.WSL2_MICROVM in available:
            primary = IsolationBackendType.WSL2_MICROVM
            sec_level = SecurityLevel.MEDIUM
            can_untrusted = True
        else:
            primary = IsolationBackendType.RESTRICTED_HOST_PROCESS
            sec_level = SecurityLevel.RESTRICTED
            can_untrusted = False  # Only permitted for trusted user project execution

        details = {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "processor_count": os.cpu_count(),
            "docker_daemon_active": docker_live,
            "wsl2_active": wsl_live,
            "windows_job_object_active": job_object_live,
        }

        recommendations = []
        if not docker_live:
            recommendations.append(
                "Start Docker Desktop to enable hardware container isolation (SecurityLevel.HIGH)."
            )

        return IsolationHealthReport(
            primary_backend=primary,
            available_backends=available,
            security_level=sec_level,
            can_execute_untrusted_code=can_untrusted,
            details=details,
            recommendations=recommendations,
        )
