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


async def test_permission_tier_gating():
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
            await flow.create_evidence_backed_pr(repo="owner/repo", base="main",
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


async def test_evidence_backed_pr_guards(monkeypatch):
    """PR creation enforces passing verification evidence and commit SHA."""
    with tempfile.TemporaryDirectory() as temp_root:
        flow = GovernedGitHubFlow(
            workspace_root=temp_root,
            permission=GitHubPermission.CREATE_PR,
        )

        # 1. Verification not passed -> EvidenceGuardViolation
        with pytest.raises(EvidenceGuardViolation) as exc_v:
            await flow.create_evidence_backed_pr(repo="owner/repo", base="main",
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
            await flow.create_evidence_backed_pr(repo="owner/repo", base="main",
                task_id="t1",
                task_goal="Goal",
                task_type="fix",
                commit_sha="invalid_sha",
                verification_passed=True,
                verification_evidence=["Test passed"],
                changed_files=["file.py"],
            )
        assert "valid commit SHA is required" in str(exc_sha.value)

        # A real-shaped HTTP double, never an actual remote mutation in this test.
        from unittest.mock import AsyncMock
        from hinaa_api.tools.github_tools import _GithubClient
        monkeypatch.setattr(_GithubClient, "__init__", lambda self: None)
        monkeypatch.setattr(_GithubClient, "get_json", AsyncMock(side_effect=[
            {"object": {"sha": "c" * 40}},
            {"html_url": "https://github.com/owner/repo/pull/7", "head": {"sha": "c" * 40, "ref": "hina/fix/t1"}, "base": {"ref": "main"}, "draft": True, "state": "open"},
        ]))
        post = AsyncMock(return_value={"number": 7})
        monkeypatch.setattr(_GithubClient, "post_json", post)
        # 3. Valid evidence and a matching remote branch -> verified draft PR
        pr_res = await flow.create_evidence_backed_pr(repo="owner/repo", base="main",
            task_id="t1",
            task_goal="Fix calculation sign bug",
            task_type="fix",
            commit_sha="c" * 40,
            verification_passed=True,
            verification_evidence=["Pytest 10/10 passed", "AST syntax checked"],
            changed_files=["calc.py"],
            repair_attempts_count=1,
        )
        assert pr_res.pr_number == 7
        assert post.call_args.args[1]["draft"] is True
        assert pr_res.commit_sha == "c" * 40
        assert pr_res.evidence_count == 2
        assert pr_res.branch == "hina/fix/t1"


@pytest.mark.parametrize("remote_sha,created,verified", [
    ("b" * 40, {"number": 7}, {}),
    ("a" * 40, {}, {}),
    ("a" * 40, {"number": 7}, {"html_url": "https://github.com/mock-repo/pull/7"}),
])
async def test_pr_never_reports_unverified_completion(monkeypatch, tmp_path, remote_sha, created, verified):
    from unittest.mock import AsyncMock
    from hinaa_api.tools.github_tools import _GithubClient
    monkeypatch.setattr(_GithubClient, "__init__", lambda self: None)
    monkeypatch.setattr(_GithubClient, "get_json", AsyncMock(side_effect=[{"object": {"sha": remote_sha}}, verified]))
    post = AsyncMock(return_value=created)
    monkeypatch.setattr(_GithubClient, "post_json", post)
    flow = GovernedGitHubFlow(str(tmp_path), GitHubPermission.CREATE_PR)
    with pytest.raises(EvidenceGuardViolation):
        await flow.create_evidence_backed_pr("t1", "Fix", "fix", "a" * 40, True, ["tests passed"], ["file.py"], repo="owner/repo", base="main")
    if remote_sha != "a" * 40:
        post.assert_not_called()


def test_task_commit_preserves_staged_and_unstaged_user_work(tmp_path):
    def git(*args):
        return subprocess.run(["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True).stdout
    git("init"); git("config", "user.email", "test@example.invalid"); git("config", "user.name", "Test")
    (tmp_path / "user.txt").write_text("base")
    git("add", "."); git("commit", "-m", "base")
    (tmp_path / "user.txt").write_text("staged user work")
    git("add", "user.txt")
    (tmp_path / "user.txt").write_text("unstaged user work")
    (tmp_path / "task [1].txt").write_text("task")
    staged_before = git("diff", "--cached")
    unstaged_before = git("diff")
    result = GovernedGitHubFlow(str(tmp_path), GitHubPermission.COMMIT).atomic_commit(
        "t1", "Fix", "fix", {"task [1].txt"}, ["passed"])
    assert git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines() == ["task [1].txt"]
    assert git("diff", "--cached") == staged_before
    assert git("diff") == unstaged_before
    assert result.files_committed == ["task [1].txt"]


def test_task_commit_supports_unicode_spaces_additions_and_deletions(tmp_path):
    def git(*args):
        return subprocess.run(
            ["git", *args],
            cwd=tmp_path,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        ).stdout

    git("init")
    git("config", "user.email", "test@example.invalid")
    git("config", "user.name", "Test")

    # Initial commit with a base file and an obsolete file
    (tmp_path / "आधार.txt").write_text("प्रारम्भिक", encoding="utf-8")
    (tmp_path / "पुरानो_फाइल.txt").write_text("मेटिने", encoding="utf-8")
    (tmp_path / "user_staged.txt").write_text("staged content", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "base")

    # User modifies user_staged.txt and stages it
    (tmp_path / "user_staged.txt").write_text("updated staged content", encoding="utf-8")
    git("add", "user_staged.txt")

    # Task adds a new unicode file with spaces, and deletes an existing file
    (tmp_path / "नयाँ सुविधा [संस्करण २].py").write_text("print('नमस्ते')", encoding="utf-8")
    (tmp_path / "पुरानो_फाइल.txt").unlink()

    staged_before = git("diff", "--cached")

    flow = GovernedGitHubFlow(str(tmp_path), GitHubPermission.COMMIT)
    result = flow.atomic_commit(
        task_id="t_unicode_01",
        task_goal="Add nepali feature and remove obsolete file",
        task_type="feat",
        task_allowed_files={"नयाँ सुविधा [संस्करण २].py", "पुरानो_फाइल.txt"},
        verification_evidence=["Evidence verified with Unicode support"],
    )

    committed_files = [p for p in git("diff-tree", "-z", "--no-commit-id", "--name-only", "-r", "HEAD").split("\0") if p]
    assert "नयाँ सुविधा [संस्करण २].py" in committed_files
    assert "पुरानो_फाइल.txt" in committed_files
    assert "user_staged.txt" not in committed_files

    # User's staged work is perfectly preserved
    assert git("diff", "--cached") == staged_before
    assert "नयाँ सुविधा [संस्करण २].py" in result.files_committed
    assert "पुरानो_फाइल.txt" in result.files_committed
    assert "user_staged.txt" in result.unrelated_files_preserved
