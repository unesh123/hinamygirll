"""Workspace Manager: Snapshots, task-scoped rollback, and change isolation."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.workspaces.manager")

_SNAPSHOTS_ROOT = Path("apps/data/workspaces/snapshots")


class FileBackup(BaseModel):
    relative_path: str
    original_content: Optional[str] = None  # None if file was newly created
    original_sha256: Optional[str] = None


class WorkspaceManager:
    """Manages workspace snapshots and non-destructive atomic rollbacks."""

    def __init__(self, workspace_root: Path, snapshots_dir: Optional[Path] = None) -> None:
        self.workspace_root = workspace_root.resolve()
        self.snapshots_dir = snapshots_dir or _SNAPSHOTS_ROOT
        self.snapshots_dir.mkdir(parents=True, exist_ok=True)
        # In-memory registry of backups per task: task_id -> { relative_path -> FileBackup }
        self._backups: Dict[str, Dict[str, FileBackup]] = {}

    def backup_file_before_mutation(self, task_id: str, relative_path: str) -> None:
        """Stores original file state prior to applying an edit."""
        if task_id not in self._backups:
            self._backups[task_id] = {}

        if relative_path in self._backups[task_id]:
            return  # Already backed up original pre-task version

        file_path = self.workspace_root / relative_path
        if file_path.exists():
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read()
                self._backups[task_id][relative_path] = FileBackup(
                    relative_path=relative_path,
                    original_content=content,
                )
            except Exception as e:
                logger.warning("Failed backing up %s: %s", relative_path, e)
        else:
            # File did not exist (will be a newly created file)
            self._backups[task_id][relative_path] = FileBackup(
                relative_path=relative_path,
                original_content=None,
            )

    def rollback(self, task_id: str) -> List[str]:
        """Reverts all files modified or created by task_id back to their pre-task state."""
        reverted: List[str] = []
        task_backups = self._backups.get(task_id, {})

        for rel_path, backup in task_backups.items():
            file_path = self.workspace_root / rel_path
            try:
                if backup.original_content is None:
                    # File was newly created by task: delete it
                    if file_path.exists():
                        file_path.unlink()
                        reverted.append(f"Deleted new file: {rel_path}")
                else:
                    # File existed: restore original content
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, "w", encoding="utf-8", newline="") as f:
                        f.write(backup.original_content)
                    reverted.append(f"Restored: {rel_path}")
            except Exception as e:
                logger.error("Failed rollback for %s: %s", rel_path, e)

        # Clear backups for task
        self._backups.pop(task_id, None)
        return reverted
