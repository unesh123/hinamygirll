"""Diff Engine: Structured file patches, collision detection, and unified diffs."""

from __future__ import annotations

import difflib
import hashlib
import logging
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel

logger = logging.getLogger("hinaa.workspaces.diff")


class PatchResult(BaseModel):
    """Result of applying a structured patch to a file."""

    success: bool
    relative_path: str
    diff: str
    sha256_before: Optional[str] = None
    sha256_after: Optional[str] = None
    error: Optional[str] = None


class DiffEngine:
    """Manages file modification, diff calculation, and patch collision detection."""

    @staticmethod
    def compute_sha256(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_unified_diff(
        old_content: str,
        new_content: str,
        filename: str = "file",
    ) -> str:
        """Produces a human-readable unified diff."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        diff = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
        )
        return "".join(diff)

    @classmethod
    def apply_patch(
        cls,
        workspace_root: Path,
        relative_path: str,
        target_content: str,
        replacement_content: str,
        expected_base_sha256: Optional[str] = None,
    ) -> PatchResult:
        """Applies a replacement patch to a file inside the workspace root."""
        root = workspace_root.resolve()
        target_file = (root / relative_path).resolve()

        # Prevent directory traversal
        if not (target_file == root or str(target_file).startswith(str(root) + os.sep)):
            return PatchResult(
                success=False,
                relative_path=relative_path,
                diff="",
                error="PATH_TRAVERSAL_ESCAPE: Target file escapes workspace root.",
            )

        # Check existing file
        if not target_file.exists():
            # If target_content is empty, this is a new file creation
            if not target_content:
                target_file.parent.mkdir(parents=True, exist_ok=True)
                with open(target_file, "w", encoding="utf-8", newline="") as f:
                    f.write(replacement_content)
                new_sha = cls.compute_sha256(replacement_content)
                diff = cls.generate_unified_diff("", replacement_content, relative_path)
                return PatchResult(
                    success=True,
                    relative_path=relative_path,
                    diff=diff,
                    sha256_before=None,
                    sha256_after=new_sha,
                )
            return PatchResult(
                success=False,
                relative_path=relative_path,
                diff="",
                error="FILE_NOT_FOUND: Target file does not exist on disk.",
            )

        # Read existing file
        try:
            with open(target_file, "r", encoding="utf-8", newline="") as f:
                current_text = f.read()
        except Exception as e:
            return PatchResult(
                success=False,
                relative_path=relative_path,
                diff="",
                error=f"READ_ERROR: {e}",
            )

        current_sha = cls.compute_sha256(current_text)

        # Base hash verification to prevent race conditions and concurrent overwrite
        if expected_base_sha256 and current_sha != expected_base_sha256:
            return PatchResult(
                success=False,
                relative_path=relative_path,
                diff="",
                sha256_before=current_sha,
                error="CONCURRENT_MODIFICATION: Base hash mismatch. File was modified by another task or user.",
            )

        # Normalize newlines for matching if exact string not found directly
        if target_content not in current_text:
            curr_norm = current_text.replace("\r\n", "\n")
            target_norm = target_content.replace("\r\n", "\n")
            rep_norm = replacement_content.replace("\r\n", "\n")
            if target_norm in curr_norm:
                is_crlf = "\r\n" in current_text
                new_text_norm = curr_norm.replace(target_norm, rep_norm, 1)
                new_text = new_text_norm.replace("\n", "\r\n") if is_crlf else new_text_norm
            else:
                return PatchResult(
                    success=False,
                    relative_path=relative_path,
                    diff="",
                    sha256_before=current_sha,
                    error="TARGET_STRING_NOT_FOUND: The exact target string to replace was not found in the file.",
                )
        else:
            new_text = current_text.replace(target_content, replacement_content, 1)

        # Write updated text atomically
        temp_file = target_file.with_suffix(f"{target_file.suffix}.tmp")
        try:
            with open(temp_file, "w", encoding="utf-8", newline="") as f:
                f.write(new_text)
            os.replace(temp_file, target_file)
        except Exception as e:
            if temp_file.exists():
                temp_file.unlink()
            return PatchResult(
                success=False,
                relative_path=relative_path,
                diff="",
                sha256_before=current_sha,
                error=f"WRITE_ERROR: {e}",
            )

        new_sha = cls.compute_sha256(new_text)
        diff = cls.generate_unified_diff(current_text, new_text, relative_path)

        return PatchResult(
            success=True,
            relative_path=relative_path,
            diff=diff,
            sha256_before=current_sha,
            sha256_after=new_sha,
        )
