"""Safe Sandboxed File Transfers (Downloads and Uploads).

Enforces:
1. Isolated quarantine directories per task.
2. Sanitized file names (anti-path-traversal).
3. Max file-size quotas and prohibited executable extensions (.exe, .bat, .cmd, .ps1).
4. SHA-256 checksum computation.
5. Strict upload source boundary controls (no .env, credentials, or arbitrary filesystem access).
"""

from __future__ import annotations

import hashlib
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Set, Tuple
from playwright.async_api import Download, Page

logger = logging.getLogger("hinaa.browser.files")

def _get_default_downloads_dir() -> Path:
    current = Path.cwd().resolve()
    for p in [current, current.parent, current.parent.parent]:
        candidate = p / "apps" / "data"
        if candidate.is_dir():
            return candidate / "browser_downloads"
    return current / "apps" / "data" / "browser_downloads"


_PROHIBITED_EXTENSIONS: Set[str] = {
    ".exe", ".bat", ".cmd", ".vbs", ".ps1", ".msi", ".scr", ".pif", ".com", ".sh", ".bash"
}
_MAX_DOWNLOAD_BYTES = 25 * 1024 * 1024  # 25 MB


class FileTransferManager:
    """Manages secure sandboxed downloads and strictly bounded uploads."""

    def __init__(self, downloads_dir: Optional[Path] = None) -> None:
        self.downloads_dir = downloads_dir or _get_default_downloads_dir()
        self.downloads_dir.mkdir(parents=True, exist_ok=True)

    def _sanitize_filename(self, filename: str) -> str:
        # Strip directories, null bytes, and path traversal sequences
        clean = Path(filename).name
        clean = re.sub(r'[\x00-\x1f\\/:\*\?"<>\|]', "_", clean)
        return clean or "downloaded_file"

    async def handle_download(
        self,
        download: Download,
        task_id: str,
        max_bytes: int = _MAX_DOWNLOAD_BYTES,
    ) -> Dict[str, Any]:
        """Saves download into task-sandboxed quarantine with safety checks."""
        task_dir = self.downloads_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        raw_filename = download.suggested_filename
        clean_filename = self._sanitize_filename(raw_filename)
        dest_path = task_dir / clean_filename

        # Extension safety check
        ext = dest_path.suffix.lower()
        if ext in _PROHIBITED_EXTENSIONS:
            logger.warning("Rejected dangerous file download extension: %s", ext)
            await download.cancel()
            return {
                "status": "REJECTED",
                "reason": f"DANGEROUS_EXTENSION: {ext}",
                "filename": clean_filename,
            }

        # Save to disk
        await download.save_as(str(dest_path.resolve()))

        # Size check
        size_bytes = dest_path.stat().st_size
        if size_bytes > max_bytes:
            dest_path.unlink(missing_ok=True)
            return {
                "status": "REJECTED",
                "reason": f"FILE_SIZE_EXCEEDED: {size_bytes} > {max_bytes}",
                "filename": clean_filename,
            }

        # Compute SHA-256
        sha256 = hashlib.sha256(dest_path.read_bytes()).hexdigest()

        return {
            "status": "COMPLETED",
            "filename": clean_filename,
            "filepath": str(dest_path.resolve()),
            "size_bytes": size_bytes,
            "sha256": sha256,
        }

    @staticmethod
    def validate_upload_source(source_path: str, allowed_workspace_dir: str) -> Tuple[bool, str]:
        """Validates that an upload file resides strictly within the approved workspace."""
        try:
            resolved_source = Path(source_path).resolve()
            resolved_allowed = Path(allowed_workspace_dir).resolve()

            # Disallow sensitive dotfiles and credentials
            name = resolved_source.name.lower()
            if any(k in name for k in [".env", "id_rsa", "credential", "secret", ".git"]):
                return False, "SENSITIVE_FILE_UPLOAD_BLOCKED"

            if not resolved_source.exists():
                return False, "FILE_NOT_FOUND"

            # Check directory containment
            if resolved_allowed not in resolved_source.parents and resolved_source != resolved_allowed:
                return False, "PATH_OUTSIDE_APPROVED_WORKSPACE"

            return True, "OK"
        except Exception as exc:
            return False, f"PATH_VALIDATION_ERROR: {exc}"
