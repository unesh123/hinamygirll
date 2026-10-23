"""
Tests for HINAA Git Worktree & Isolated Subagent Workspace Subsystem.
Verifies isolated worktree provisioning, execution, diffing, committing,
and cleanup without clobbering primary working tree state.
"""

import os
import subprocess
import pytest
from pathlib import Path

from hinaa_api.harness.git_worktrees import (
    GitWorktreeManager,
    WorktreeStatus,
    get_worktree_manager,
)
from hinaa_api.tools.subagent_fork import execute_subagent_fork


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Provisions a clean, isolated Git repository with an initial commit."""
    cwd = str(tmp_path)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    # git init
    subprocess.run(["git", "init", "-b", "main"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "config", "user.name", "HinaTest"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "config", "user.email", "hina@test.local"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)

    # Initial commit
    init_file = tmp_path / "README.md"
    init_file.write_text("# Main Workspace\nOriginal content.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)

    return tmp_path


def test_git_worktree_detection(temp_git_repo: Path):
    """Verifies that GitWorktreeManager detects Git repositories correctly."""
    mgr = GitWorktreeManager(workspace_root=str(temp_git_repo))
    assert mgr.is_git_repository() is True


def test_git_worktree_full_lifecycle(temp_git_repo: Path):
    """
    Tests complete lifecycle: create -> isolate -> mutate -> commit -> diff -> cleanup.
    Ensures the main workspace is never polluted.
    """
    mgr = GitWorktreeManager(workspace_root=str(temp_git_repo))
    subagent_id = "agent_coder_alpha"

    # 1. Create isolated worktree
    ctx = mgr.create_worktree(subagent_id=subagent_id, base_ref="HEAD")
    assert ctx.subagent_id == subagent_id
    assert ctx.status == WorktreeStatus.ACTIVE
    assert ctx.is_git_worktree is True
    assert os.path.isdir(ctx.worktree_path)

    # 2. Mutate file inside worktree ONLY
    wt_readme = Path(ctx.worktree_path) / "README.md"
    wt_readme.write_text("# Subagent Patch\nIsolated changes applied.\n", encoding="utf-8")
    new_subagent_file = Path(ctx.worktree_path) / "subagent_module.py"
    new_subagent_file.write_text("print('hello from isolated worktree')\n", encoding="utf-8")

    # Verify main repo is NOT contaminated
    main_readme = temp_git_repo / "README.md"
    assert "Original content." in main_readme.read_text(encoding="utf-8")
    assert not (temp_git_repo / "subagent_module.py").exists()

    # 3. Diff verification
    diff_output = mgr.diff_worktree(subagent_id)
    assert "Isolated changes applied" in diff_output or "Original content" in diff_output

    # 4. Commit inside worktree
    commit_res = mgr.commit_worktree(subagent_id, "feat: isolated subagent patch")
    assert commit_res["success"] is True

    # 5. Clean removal
    removed = mgr.remove_worktree(subagent_id, force=True, delete_branch=True)
    assert removed is True
    assert not os.path.exists(ctx.worktree_path)
    assert mgr.get_worktree(subagent_id) is None


def test_shadow_worktree_fallback_when_non_git(tmp_path: Path):
    """Verifies graceful fallback to shadow directory if no Git repository is present."""
    non_git_dir = tmp_path / "non_git_workspace"
    non_git_dir.mkdir()

    mgr = GitWorktreeManager(workspace_root=str(non_git_dir))
    assert mgr.is_git_repository() is False

    ctx = mgr.create_worktree("shadow_agent")
    assert ctx.is_git_worktree is False
    assert os.path.isdir(ctx.worktree_path)
    assert ctx.status == WorktreeStatus.ACTIVE

    # Commit non-git
    c_res = mgr.commit_worktree("shadow_agent", "dummy message")
    assert c_res["success"] is True

    # Cleanup
    cleaned = mgr.remove_worktree("shadow_agent")
    assert cleaned is True
    assert not os.path.exists(ctx.worktree_path)


@pytest.mark.asyncio
async def test_subagent_fork_with_isolated_worktree():
    """Verifies that subagent_fork provisions an isolated worktree when isolate_worktree=True."""
    subagent_id_prefix = "subagent_coder"
    res = await execute_subagent_fork({
        "role": "coder",
        "objective": "Author isolated micro-module",
        "isolate_worktree": True,
        "timeout_seconds": 15.0,
    })

    assert res["success"] is True
    assert "worktree" in res
    wt = res["worktree"]
    assert "worktree_path" in wt
    assert os.path.isdir(wt["worktree_path"])
    assert wt["status"] == "active"

    # Clean up worktree after test
    subagent_id = res["subagent_id"]
    mgr = get_worktree_manager()
    mgr.remove_worktree(subagent_id, force=True, delete_branch=True)
    assert not os.path.exists(wt["worktree_path"])
