"""B3 Git Workspace & Dirty Worktree Safety Inspector (Directives §6–§9).

Implements:
1. Git worktree status inspection (branch, head commit, dirty files).
2. Unrelated dirty files isolation (prevents clobbering uncommitted user changes).
3. GitHub permission enforcement and action gating.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from .models import (
    DirtyFile,
    GitHubPermission,
    GitWorkspace,
    check_github_permission,
)

_ACTION_PERMISSION_MAP: dict[str, GitHubPermission] = {
    "read": GitHubPermission.READ_ONLY,
    "inspect": GitHubPermission.READ_ONLY,
    "search": GitHubPermission.READ_ONLY,
    "edit": GitHubPermission.WORKSPACE_WRITE,
    "write": GitHubPermission.WORKSPACE_WRITE,
    "create_file": GitHubPermission.WORKSPACE_WRITE,
    "delete_file": GitHubPermission.WORKSPACE_WRITE,
    "commit": GitHubPermission.COMMIT,
    "push": GitHubPermission.PUSH_BRANCH,
    "push_branch": GitHubPermission.PUSH_BRANCH,
    "create_pr": GitHubPermission.CREATE_PR,
    "merge_pr": GitHubPermission.MERGE_PR,
}


class GitWorkspaceService:
    def __init__(self, root_path: str, permission: GitHubPermission = GitHubPermission.WORKSPACE_WRITE) -> None:
        self.root_path = os.path.abspath(root_path)
        self.permission = permission

    def inspect_workspace(self) -> GitWorkspace:
        """Inspect current git repository branch, head commit, and dirty files."""
        branch = self._run_git(["branch", "--show-current"]) or "main"
        head_commit = self._run_git(["rev-parse", "HEAD"]) or "unknown"
        dirty_files = self._get_dirty_files()

        return GitWorkspace(
            root_path=self.root_path,
            branch=branch.strip(),
            head_commit=head_commit.strip(),
            dirty_files=dirty_files,
            permission=self.permission,
        )

    def verify_action_allowed(self, action: str) -> None:
        """Enforces that the requested action is permitted by the granted GitHubPermission."""
        required = _ACTION_PERMISSION_MAP.get(action.lower())
        if not required:
            raise ValueError(f"Unknown repository action: {action!r}")

        if not check_github_permission(self.permission, required):
            raise PermissionError(
                f"Action {action!r} requires {required.value} permission, but current workspace is granted {self.permission.value}."
            )

    def filter_task_changes(
        self,
        task_allowed_files: set[str],
        dirty_files: list[DirtyFile],
    ) -> tuple[list[DirtyFile], list[DirtyFile]]:
        """Separates task-related changes from unrelated pre-existing dirty files.

        Returns (task_dirty, unrelated_dirty). Unrelated dirty files must NEVER be discarded or clobbered.
        """
        task_dirty: list[DirtyFile] = []
        unrelated_dirty: list[DirtyFile] = []

        for df in dirty_files:
            norm_path = df.path.replace("\\", "/")
            if any(norm_path == allowed or norm_path.startswith(allowed.rstrip("/") + "/") for allowed in task_allowed_files):
                task_dirty.append(df)
            else:
                unrelated_dirty.append(df)

        return task_dirty, unrelated_dirty

    def _get_dirty_files(self) -> list[DirtyFile]:
        status_output = self._run_git(["status", "--porcelain"])
        if not status_output:
            return []

        results: list[DirtyFile] = []
        for line in status_output.splitlines():
            line = line.rstrip()
            if len(line) < 4:
                continue
            index_status = line[0]
            worktree_status = line[1]
            path = line[3:].strip()
            # Handle quoted paths with spaces
            if path.startswith('"') and path.endswith('"'):
                path = path[1:-1]

            is_staged = index_status not in (" ", "?")
            status_code = (index_status + worktree_status).strip()

            results.append(
                DirtyFile(
                    path=path,
                    status=status_code,
                    is_staged=is_staged,
                )
            )
        return results

    def _run_git(self, args: list[str]) -> str:
        try:
            res = subprocess.run(
                ["git", *args],
                cwd=self.root_path,
                capture_output=True,
                text=True,
                check=False,
            )
            return res.stdout if res.returncode == 0 else ""
        except Exception:
            return ""
