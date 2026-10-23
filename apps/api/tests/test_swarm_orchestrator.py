"""
Tests for HINAA Autonomous Multi-Agent Tree and Consciousness Swarm Orchestrator.
Verifies multi-role consensus gates, worktree isolation, adversarial criticism,
syntax test verification, and DevSecOps secret leak gating.
"""

import os
import subprocess
import pytest
from pathlib import Path

from hinaa_api.harness.swarm_orchestrator import (
    ConsensusVerdict,
    SwarmGoal,
    SwarmOrchestrator,
)


@pytest.fixture
def temp_git_repo(tmp_path: Path):
    """Provisions a clean, isolated Git repository with an initial commit."""
    cwd = str(tmp_path)
    creationflags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    subprocess.run(["git", "init", "-b", "main"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "config", "user.name", "HinaSwarmTest"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "config", "user.email", "swarm@hina.local"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)

    init_file = tmp_path / "README.md"
    init_file.write_text("# Production Core\nClean state.\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=cwd, check=True, capture_output=True, creationflags=creationflags)

    return tmp_path


@pytest.mark.asyncio
async def test_swarm_unanimous_pass_lifecycle(temp_git_repo: Path):
    """Verifies that a valid task produces unanimous consensus across all 5 roles."""
    orchestrator = SwarmOrchestrator(workspace_root=str(temp_git_repo))
    goal = SwarmGoal(
        title="Scaffold Data Pipeline",
        description="Creates clean-room data processing manifest and module.",
        acceptance_criteria=["Clean Python syntax", "Zero secret leakage"],
        auto_merge=False,
    )

    def synthesizer(wt_path: str):
        mod_file = Path(wt_path) / "pipeline.py"
        mod_file.write_text("def process_telemetry(data: list) -> int:\n    return len(data)\n", encoding="utf-8")

    result = await orchestrator.execute_swarm(goal, code_synthesizer=synthesizer)

    assert result.verdict == ConsensusVerdict.UNANIMOUS_PASS
    assert result.consensus_score >= 0.90
    assert len(result.votes) == 5
    roles = {v.role for v in result.votes}
    assert roles == {"architect", "coder", "tester", "devsecops", "critic"}
    assert all(v.verdict == "pass" for v in result.votes)
    # Worktree should be cleanly pruned
    assert not os.path.exists(result.worktree_path)


@pytest.mark.asyncio
async def test_swarm_tester_rejection_on_syntax_error(temp_git_repo: Path):
    """Verifies that syntax errors trigger tester failure and consensus rejection."""
    orchestrator = SwarmOrchestrator(workspace_root=str(temp_git_repo))
    goal = SwarmGoal(
        title="Flawed Module Synthesis",
        description="Attempts to inject invalid syntax.",
    )

    def broken_synthesizer(wt_path: str):
        mod_file = Path(wt_path) / "broken.py"
        mod_file.write_text("def invalid_syntax(:\n", encoding="utf-8")

    result = await orchestrator.execute_swarm(goal, code_synthesizer=broken_synthesizer)

    assert result.verdict == ConsensusVerdict.REJECTED
    tester_vote = next(v for v in result.votes if v.role == "tester")
    assert tester_vote.verdict == "fail"
    assert "SyntaxError" in str(tester_vote.findings)
    assert not os.path.exists(result.worktree_path)


@pytest.mark.asyncio
async def test_swarm_devsecops_rejection_on_secret_leak(temp_git_repo: Path):
    """Verifies that embedded secrets trigger DevSecOps veto and consensus rejection."""
    orchestrator = SwarmOrchestrator(workspace_root=str(temp_git_repo))
    goal = SwarmGoal(
        title="Insecure Token Injection",
        description="Attempts to commit exposed API token.",
    )

    def leaking_synthesizer(wt_path: str):
        mod_file = Path(wt_path) / "config.py"
        mod_file.write_text("API_KEY = 'sk-1234567890abcdef1234567890abcdef'\n", encoding="utf-8")

    result = await orchestrator.execute_swarm(goal, code_synthesizer=leaking_synthesizer)

    assert result.verdict == ConsensusVerdict.REJECTED
    devsecops_vote = next(v for v in result.votes if v.role == "devsecops")
    assert devsecops_vote.verdict == "fail"
    assert any("raw credentials" in f.lower() for f in devsecops_vote.findings)
    assert not os.path.exists(result.worktree_path)


@pytest.mark.asyncio
async def test_swarm_auto_merge_promotion(temp_git_repo: Path):
    """Verifies that an approved task commits worktree branch when auto_merge=True."""
    orchestrator = SwarmOrchestrator(workspace_root=str(temp_git_repo))
    goal = SwarmGoal(
        title="Promote Verified Analytics",
        description="Adds analytics utility module.",
        auto_merge=True,
    )

    def safe_synthesizer(wt_path: str):
        mod_file = Path(wt_path) / "analytics.py"
        mod_file.write_text("def get_metric(): return 42\n", encoding="utf-8")

    result = await orchestrator.execute_swarm(goal, code_synthesizer=safe_synthesizer)

    assert result.verdict == ConsensusVerdict.UNANIMOUS_PASS
    assert result.promoted_to_main is True
