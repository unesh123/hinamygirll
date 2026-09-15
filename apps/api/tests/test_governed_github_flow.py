"""Tests for C4 Governed GitHub Workflow (Directives §23–§28).

Verifies:
1. GitHubPermission hierarchy enforcement (READ_ONLY rejects commits & PRs).
2. Deterministic branch naming (`hina/<type>/<id>`).
3. Task-scoped atomic commits staging ONLY task files and preserving unrelated dirty files.
4. Evidence-backed PR generation requiring verifiable commit SHA and test evidence.
"""

import os
import subprocess
import tempfile
import pytest

from hinaa_api.repository.github_flow import (
    EvidenceGuardViolation,
    GovernedGitHubFlow,
)
from hinaa_api.repository.models import GitHubPermission


def test_permission_tier_gating():
    """READ_ONLY workspace rejects mutation attempts with PermissionError."""
    with tempfile.TemporaryDirectory() as temp_root:
        flow = GovernedGitHubFlow(
            workspace_root=temp_root,
            permission=GitHubPermission.READ_ONLY,
        )

        with pytest.raises(PermissionError) as exc_commit:
            flow.atomic_commit(
                task_id="t1",
                task_goal="Fix bug",
                task_type="fix",
                task_allowed_files={"file.py"},
                verification_evidence=["Tests passed"],
            )
        assert "requires commit permission" in str(exc_commit.value)

        with pytest.raises(PermissionError) as exc_pr:
            flow.create_evidence_backed_pr(
                task_id="t1",
                task_goal="Fix bug",
                task_type="fix",
                commit_sha="a" * 40,
                verification_passed=True,
                verification_evidence=["Tests passed"],
                changed_files=["file.py"],
            )
        assert "requires create_pr permission" in str(exc_pr.value)


def test_branch_naming_format():
    """Enforces deterministic hina/<type>/<id> branch naming."""
    with tempfile.TemporaryDirectory() as temp_root:
        flow = GovernedGitHubFlow(workspace_root=temp_root)

        branch = flow.generate_branch_name("fix", "TASK-4001")
        assert branch == "hina/fix/task-4001"

        feature_branch = flow.generate_branch_name("feature", "nova_auth")
        assert feature_branch == "hina/feature/nova_auth"


def test_atomic_commit_preserves_unrelated_dirty_files():
    """Task commit stages ONLY task-allowed files; unrelated dirty files remain untouched."""
    with tempfile.TemporaryDirectory() as temp_root:
        # Initialize a temporary git repository
        subprocess.run(["git", "init"], cwd=temp_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "agent@hinaa.dev"], cwd=temp_root, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.name", "HINAA Agent"], cwd=temp_root, check=True, capture_output=True)

        # Base commit
        readme_path = os.path.join(temp_root, "README.md")
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write("# Repo\n")
        subprocess.run(["git", "add", "README.md"], cwd=temp_root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=temp_root, check=True, capture_output=True)

        # Create task file and unrelated user file
        task_file = os.path.join(temp_root, "calculator.py")
        with open(task_file, "w", encoding="utf-8") as f:
            f.write("def add(a, b): return a + b\n")

        unrelated_file = os.path.join(temp_root, "unrelated_secret.env")
        with open(unrelated_file, "w", encoding="utf-8") as f:
            f.write("SECRET_KEY=do_not_commit\n")

        flow = GovernedGitHubFlow(
            workspace_root=temp_root,
            permission=GitHubPermission.COMMIT,
        )

        # Commit task-scoped changes only
        commit_res = flow.atomic_commit(
            task_id="task_calc_01",
            task_goal="Implement add function",
            task_type="feat",
            task_allowed_files={"calculator.py"},
            verification_evidence=["Unit tests passed with 100% assertions"],
        )

        assert len(commit_res.commit_sha) == 40
        assert "calculator.py" in commit_res.files_committed
        assert "unrelated_secret.env" in commit_res.unrelated_files_preserved

        # Verify git status: unrelated_secret.env is still untracked/dirty on disk!
        st_res = subprocess.run(["git", "status", "--porcelain"], cwd=temp_root, capture_output=True, text=True)
        assert "unrelated_secret.env" in st_res.stdout
        assert "calculator.py" not in st_res.stdout


def test_evidence_backed_pr_guards():
    """PR creation enforces passing verification evidence and commit SHA."""
    with tempfile.TemporaryDirectory() as temp_root:
        flow = GovernedGitHubFlow(
            workspace_root=temp_root,
            permission=GitHubPermission.CREATE_PR,
        )

        # 1. Verification not passed -> EvidenceGuardViolation
        with pytest.raises(EvidenceGuardViolation) as exc_v:
            flow.create_evidence_backed_pr(
                task_id="t1",
                task_goal="Goal",
                task_type="fix",
                commit_sha="a" * 40,
                verification_passed=False,
                verification_evidence=[],
                changed_files=["file.py"],
            )
        assert "verification has not passed" in str(exc_v.value)

        # 2. Missing or invalid commit SHA -> EvidenceGuardViolation
        with pytest.raises(EvidenceGuardViolation) as exc_sha:
            flow.create_evidence_backed_pr(
                task_id="t1",
                task_goal="Goal",
                task_type="fix",
                commit_sha="invalid_sha",
                verification_passed=True,
                verification_evidence=["Test passed"],
                changed_files=["file.py"],
            )
        assert "valid commit SHA is required" in str(exc_sha.value)

        # 3. Valid evidence and SHA -> Successfully opens PR
        pr_res = flow.create_evidence_backed_pr(
            task_id="t1",
            task_goal="Fix calculation sign bug",
            task_type="fix",
            commit_sha="c" * 40,
            verification_passed=True,
            verification_evidence=["Pytest 10/10 passed", "AST syntax checked"],
            changed_files=["calc.py"],
            repair_attempts_count=1,
        )
        assert pr_res.pr_number > 0
        assert pr_res.commit_sha == "c" * 40
        assert pr_res.evidence_count == 2
        assert pr_res.branch == "hina/fix/t1"
