"""
HINAA Subagent Git Worktree & Isolated Workspace Manager.

Modeled on modern agent architectures (Claude Code teammate worktrees):
Enables subordinate specialized agents (Coder, Architect, DevSecOps, Tester)
to execute code patches, dependency experiments, and verification suites
within isolated Git worktrees (.hina/worktrees/<subagent_id>) without
clobbering or risking the primary working directory.
"""

from __future__ import annotations

import enum
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from ..runtime_paths import project_root

logger = logging.getLogger("hinaa.harness.git_worktrees")


class WorktreeStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMMITTED = "committed"
    MERGED = "merged"
    FAILED = "failed"
    REMOVED = "removed"


class WorktreeContext(BaseModel):
    subagent_id: str
    worktree_path: str
    branch_name: str
    base_ref: str
    is_git_worktree: bool = True
    status: WorktreeStatus = WorktreeStatus.ACTIVE
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _sanitize_identifier(name: str) -> str:
    """Sanitizes names for filesystem and git ref compliance."""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    return cleaned or "subagent"


class GitWorktreeManager:
    """
    Manages isolated Git worktrees and shadow workspaces for autonomous subagents.
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        self.workspace_root = str(Path(workspace_root).resolve() if workspace_root else project_root())
        self.worktrees_root = os.path.join(self.workspace_root, ".hina", "worktrees")
        self._worktrees: Dict[str, WorktreeContext] = {}

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[str] = None,
        timeout: float = 30.0,
    ) -> subprocess.CompletedProcess[str]:
        target_cwd = cwd or self.workspace_root
        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        return subprocess.run(
            ["git", *args],
            cwd=target_cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            creationflags=creationflags,
            check=False,
        )

    def is_git_repository(self) -> bool:
        """Determines if the current workspace root is the top level or worktree of an active Git repository."""
        try:
            res = self._run_git(["rev-parse", "--show-toplevel"])
            if res.returncode == 0 and res.stdout.strip():
                top = Path(res.stdout.strip()).resolve()
                ws = Path(self.workspace_root).resolve()
                return top == ws
            return False
        except Exception as exc:
            logger.debug("Git repository check failed: %s", exc)
            return False

    def create_worktree(
        self,
        subagent_id: str,
        base_ref: str = "HEAD",
        branch_name: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorktreeContext:
        """
        Creates an isolated Git worktree under .hina/worktrees/<subagent_id>.
        If Git is unavailable, falls back to an isolated shadow directory.
        """
        clean_id = _sanitize_identifier(subagent_id)
        os.makedirs(self.worktrees_root, exist_ok=True)
        worktree_path = os.path.join(self.worktrees_root, clean_id)

        target_branch = branch_name or f"hina/worktree/{clean_id}"

        # Clean existing directory if stale
        if os.path.exists(worktree_path):
            self.remove_worktree(clean_id, force=True, delete_branch=False)

        is_git = self.is_git_repository()
        if is_git:
            # 1. Attempt to create git worktree with dedicated branch
            # Check if branch exists
            chk_br = self._run_git(["rev-parse", "--verify", target_branch])
            if chk_br.returncode == 0:
                # Branch exists, append timestamp
                target_branch = f"{target_branch}-{int(time.time())}"

            cmd = ["worktree", "add", "-b", target_branch, worktree_path, base_ref]
            res = self._run_git(cmd)

            if res.returncode != 0:
                logger.warning("git worktree add -b failed (%s). Retrying in detach mode.", res.stderr.strip())
                # Fallback to detached worktree
                cmd_detach = ["worktree", "add", "--detach", worktree_path, base_ref]
                res_detach = self._run_git(cmd_detach)
                if res_detach.returncode != 0:
                    logger.warning(
                        "git worktree add --detach failed (%s). Falling back to shadow directory.",
                        res_detach.stderr.strip(),
                    )
                    is_git = False
                    os.makedirs(worktree_path, exist_ok=True)
        else:
            os.makedirs(worktree_path, exist_ok=True)

        ctx = WorktreeContext(
            subagent_id=clean_id,
            worktree_path=os.path.abspath(worktree_path),
            branch_name=target_branch,
            base_ref=base_ref,
            is_git_worktree=is_git,
            status=WorktreeStatus.ACTIVE,
            metadata=metadata or {},
        )
        self._worktrees[clean_id] = ctx
        logger.info(
            "Created %s worktree for subagent '%s' at '%s'",
            "git" if is_git else "shadow",
            clean_id,
            worktree_path,
        )
        return ctx

    def get_worktree(self, subagent_id: str) -> Optional[WorktreeContext]:
        """Retrieves active worktree context for a subagent."""
        clean_id = _sanitize_identifier(subagent_id)
        return self._worktrees.get(clean_id)

    def list_worktrees(self) -> List[WorktreeContext]:
        """Lists all registered subagent worktrees."""
        return list(self._worktrees.values())

    def execute_in_worktree(
        self,
        subagent_id: str,
        command: List[str] | str,
        timeout: float = 60.0,
    ) -> Dict[str, Any]:
        """Executes a command inside the isolated worktree directory."""
        ctx = self.get_worktree(subagent_id)
        if not ctx or not os.path.exists(ctx.worktree_path):
            raise FileNotFoundError(f"Worktree for subagent '{subagent_id}' does not exist.")

        creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        shell = isinstance(command, str)

        try:
            res = subprocess.run(
                command,
                cwd=ctx.worktree_path,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=shell,
                creationflags=creationflags,
                check=False,
            )
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "cwd": ctx.worktree_path,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "cwd": ctx.worktree_path,
            }

    def diff_worktree(self, subagent_id: str, base_ref: Optional[str] = None) -> str:
        """Computes Git diff of changes made within the isolated worktree."""
        ctx = self.get_worktree(subagent_id)
        if not ctx:
            return ""

        if ctx.is_git_worktree and os.path.exists(ctx.worktree_path):
            # Intent to add so untracked new files are included in the diff
            self._run_git(["add", "-N", "."], cwd=ctx.worktree_path)
            ref = base_ref or ctx.base_ref
            res = self._run_git(["diff", ref], cwd=ctx.worktree_path)
            if res.returncode == 0:
                return res.stdout
            # If diff against base_ref fails, try diff HEAD
            res_head = self._run_git(["diff", "HEAD"], cwd=ctx.worktree_path)
            return res_head.stdout if res_head.returncode == 0 else ""
        return ""

    def commit_worktree(
        self,
        subagent_id: str,
        commit_message: str,
    ) -> Dict[str, Any]:
        """Stages all changes and commits them within the isolated worktree."""
        ctx = self.get_worktree(subagent_id)
        if not ctx:
            return {"success": False, "error": f"Worktree '{subagent_id}' not found"}

        if not ctx.is_git_worktree:
            ctx.status = WorktreeStatus.COMMITTED
            return {"success": True, "message": "Shadow workspace committed (non-git)"}

        # Stage
        res_add = self._run_git(["add", "-A"], cwd=ctx.worktree_path)
        if res_add.returncode != 0:
            return {"success": False, "error": f"git add failed: {res_add.stderr}"}

        # Commit
        res_commit = self._run_git(
            ["commit", "-m", commit_message],
            cwd=ctx.worktree_path,
        )
        if res_commit.returncode == 0:
            ctx.status = WorktreeStatus.COMMITTED
            return {
                "success": True,
                "commit_hash": res_commit.stdout.strip(),
                "branch": ctx.branch_name,
            }
        # Nothing to commit is also handled cleanly
        if "nothing to commit" in res_commit.stdout.lower():
            return {"success": True, "message": "No changes to commit"}

        return {"success": False, "error": res_commit.stderr}

    def remove_worktree(
        self,
        subagent_id: str,
        force: bool = True,
        delete_branch: bool = True,
    ) -> bool:
        """
        Prunes and cleanly removes the isolated worktree directory and branch.
        """
        clean_id = _sanitize_identifier(subagent_id)
        ctx = self._worktrees.get(clean_id)
        worktree_path = (
            ctx.worktree_path
            if ctx
            else os.path.join(self.worktrees_root, clean_id)
        )
        branch_name = ctx.branch_name if ctx else f"hina/worktree/{clean_id}"

        # 1. Remove git worktree if registered
        if self.is_git_repository():
            args = ["worktree", "remove"]
            if force:
                args.append("--force")
            args.append(worktree_path)
            self._run_git(args)
            self._run_git(["worktree", "prune"])

            if delete_branch:
                self._run_git(["branch", "-D", branch_name])

        # 2. Filesystem cleanup fallback
        if os.path.exists(worktree_path):
            try:
                shutil.rmtree(worktree_path, ignore_errors=True)
            except Exception as exc:
                logger.warning("Failed to rmtree worktree dir %s: %s", worktree_path, exc)

        if clean_id in self._worktrees:
            self._worktrees[clean_id].status = WorktreeStatus.REMOVED
            del self._worktrees[clean_id]

        logger.info("Cleaned up worktree for '%s'", clean_id)
        return True


# Global Singleton
_global_worktree_manager: Optional[GitWorktreeManager] = None


def get_worktree_manager(workspace_root: Optional[str] = None) -> GitWorktreeManager:
    global _global_worktree_manager
    if _global_worktree_manager is None:
        _global_worktree_manager = GitWorktreeManager(workspace_root=workspace_root)
    return _global_worktree_manager
