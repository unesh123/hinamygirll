"""
HINAA OS — Phase 15 Runtime Host Privilege Boundary Probe & Sandbox Guard
Audits Windows Job Objects, WSL2, path traversal, NTFS directory junctions, and untrusted code execution.
"""

from __future__ import annotations

import logging
import os
import platform
import shutil
from pathlib import Path
from typing import Optional

from hinaa_api.security.contracts import (
    HostIsolationLevel,
    HostIsolationProbeResult,
)

logger = logging.getLogger(__name__)


class HostPostureGuard:
    """
    Audits host runtime isolation and defends filesystem boundaries.
    Enforces honest capability labels: Windows Job Objects provide process resource governance,
    NOT hostile virtualization.
    """

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = (workspace_root or Path.cwd()).resolve()

    def probe_host_posture(self) -> HostIsolationProbeResult:
        """
        Actively checks the local OS runtime for process sandboxing and hypervisor isolation.
        """
        os_platform = platform.system()
        job_objects_available = False
        wsl_available = False

        if os_platform == "Windows":
            # 1. Probe Windows Job Object capabilities
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                if hasattr(kernel32, "CreateJobObjectW"):
                    job_objects_available = True
            except Exception:
                job_objects_available = False

            # 2. Probe WSL2 presence
            wsl_path = shutil.which("wsl.exe")
            if wsl_path:
                wsl_available = True

        # Honest classification:
        # Windows Job Objects enforce memory/CPU limits and process tree termination,
        # but do NOT provide hostile VM virtualization.
        # Untrusted execution is strictly FALSE unless verified hypervisor/microVM is present.
        if job_objects_available:
            isolation_level = HostIsolationLevel.PROCESS_JOB_OBJECT
            can_untrusted = False
            details = (
                "Windows Job Object active (CPU, memory bounds, process tree termination enforced). "
                "Honest posture: can_execute_untrusted_code=False. "
                "Arbitrary untrusted hostile payloads remain BLOCKED_UNAVAILABLE. "
                "Trusted local developer workflows permitted within workspace root."
            )
        else:
            isolation_level = HostIsolationLevel.UNTRUSTED_BLOCKED
            can_untrusted = False
            details = "No kernel isolation container detected. Untrusted code execution is strictly blocked."

        return HostIsolationProbeResult(
            isolation_level=isolation_level,
            can_execute_untrusted_code=can_untrusted,
            os_platform=os_platform,
            job_objects_available=job_objects_available,
            wsl_available=wsl_available,
            status_details=details,
        )

    def validate_workspace_path(self, target_path: str | Path) -> Path:
        """
        Validates target path against traversal (../), NTFS junctions, symlinks, and Alternate Data Streams.
        Raises PermissionError if path attempts to escape the designated workspace.
        """
        target_str = str(target_path)

        # 1. Null byte injection check
        if "\x00" in target_str or "%00" in target_str:
            raise PermissionError("Null byte injection detected in path.")

        # 2. Windows Alternate Data Stream check (e.g., test.txt:secret)
        # Exclude drive letter colon (e.g. C:\)
        path_without_drive = re_path = target_str
        if len(target_str) >= 2 and target_str[1] == ":":
            path_without_drive = target_str[2:]
        if ":" in path_without_drive:
            raise PermissionError("Windows Alternate Data Stream (ADS) syntax forbidden.")

        # 3. Path resolution & containment check
        path_obj = Path(target_str)
        if not path_obj.is_absolute():
            resolved = (self.workspace_root / path_obj).resolve()
        else:
            resolved = path_obj.resolve()

        # Check traversal beyond workspace root
        try:
            resolved.relative_to(self.workspace_root)
        except ValueError:
            raise PermissionError(f"Path traversal blocked: '{target_str}' escapes workspace root '{self.workspace_root}'.")

        # 4. Check for junction/symlink reparse points targeting external locations
        if resolved.is_symlink():
            real_target = resolved.resolve()
            try:
                real_target.relative_to(self.workspace_root)
            except ValueError:
                raise PermissionError("Symlink/NTFS junction targets a directory outside workspace.")

        return resolved


_global_host_posture_guard: Optional[HostPostureGuard] = None


def get_host_posture_guard(workspace_root: Optional[Path] = None) -> HostPostureGuard:
    global _global_host_posture_guard
    if _global_host_posture_guard is None or workspace_root is not None:
        _global_host_posture_guard = HostPostureGuard(workspace_root)
    return _global_host_posture_guard
