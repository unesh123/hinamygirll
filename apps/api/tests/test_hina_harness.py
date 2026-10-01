"""
Comprehensive Test Suite for HINAA Codex-grade Agent Harness.
"""

import os
import tempfile
import pytest

from hinaa_api.harness import (
    AgentRole,
    AgentScheduler,
    CapabilityPermissions,
    CompactionWorker,
    EnvironmentState,
    HinaThreadManager,
    LocalAgentMessageBoard,
    ReasoningEffort,
    RepositoryMemoryManager,
    SandboxPolicyEngine,
    SandboxSecurityViolation,
    TurnItemType,
    VerifierBrain,
)


def test_thread_creation_and_forking():
    """Verify thread creation and non-destructive forking preserving ancestry."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tm = HinaThreadManager(workspace_root=tmpdir)
        thread = tm.create_thread(title="Master Engineering Thread")
        assert thread.thread_id.startswith("thr_")
        assert thread.active_session is not None
        assert thread.active_session.environment.cwd == os.path.realpath(tmpdir)

        # Append turn items
        tm.append_turn_item(thread.thread_id, TurnItemType.USER_MESSAGE, {"text": "Build feature X"})
        tm.append_turn_item(thread.thread_id, TurnItemType.AGENT_MESSAGE, {"displayText": "Planning feature X"})

        # Fork thread
        forked = tm.fork_thread(thread.thread_id, title="Alternative Architecture B")
        assert forked.thread_id != thread.thread_id
        assert forked.parent_thread_id == thread.thread_id
        assert forked.active_session.fork_info is not None
        assert forked.active_session.fork_info.forked_from_thread_id == thread.thread_id
        assert len(forked.turns) == len(thread.turns)


def test_sandbox_policy_ghsa_w5fx_fh39_j5rw_mitigation():
    """Verify path containment blocks directory traversal and path escapes."""
    with tempfile.TemporaryDirectory() as allowed_root:
        canonical_root = os.path.realpath(allowed_root)
        inside_path = os.path.join(canonical_root, "subdir", "file.py")

        # 1. Valid path inside workspace root passes
        validated = SandboxPolicyEngine.validate_path_containment(inside_path, [canonical_root])
        assert validated == os.path.realpath(inside_path)

        # 2. Path traversal escaping root is blocked
        outside_path = os.path.join(canonical_root, "..", "escaped.txt")
        with pytest.raises(SandboxSecurityViolation):
            SandboxPolicyEngine.validate_path_containment(outside_path, [canonical_root])


def test_multi_agent_scheduler_depth_and_concurrency():
    """Verify agent graph enforces recursion depth limits and messaging."""
    scheduler = AgentScheduler(max_concurrency=4, max_depth=3)
    root = scheduler.register_root("sess_1", AgentRole.ROOT)

    # Spawn depth 1
    child1 = scheduler.spawn_subagent(root.node_id, "sess_1", AgentRole.RESEARCHER, "Research codebase")
    assert child1.depth == 1
    assert child1.parent_id == root.node_id

    # Spawn depth 2
    child2 = scheduler.spawn_subagent(child1.node_id, "sess_1", AgentRole.CODER, "Write tests")
    assert child2.depth == 2

    # Spawn depth 3
    child3 = scheduler.spawn_subagent(child2.node_id, "sess_1", AgentRole.VERIFIER, "Verify syntax")
    assert child3.depth == 3

    # Depth 4 should be rejected (max_depth=3)
    with pytest.raises(RuntimeError, match="Maximum agent recursion depth"):
        scheduler.spawn_subagent(child3.node_id, "sess_1", AgentRole.CRITIC, "Excessive child")

    # Message board delivery
    inbox = scheduler.message_board.fetch_inbox(child1.node_id)
    assert len(inbox) == 1
    assert inbox[0].message_type == "task_assignment"
    assert inbox[0].payload["objective"] == "Research codebase"


def test_repository_memory_scaffolding():
    """Verify .hina/ repository memory scaffolding and prompt compilation."""
    with tempfile.TemporaryDirectory() as tmpdir:
        rm = RepositoryMemoryManager(workspace_root=tmpdir)
        created = rm.scaffold_if_missing()
        assert len(created) > 0
        assert os.path.exists(os.path.join(tmpdir, ".hina", "architecture.md"))
        assert os.path.exists(os.path.join(tmpdir, ".hina", "security.md"))

        prompt_block = rm.compile_prompt_block()
        assert "<repository_memory>" in prompt_block
        assert "<security>" in prompt_block


def test_verifier_brain_speech_and_code():
    """Verify verifier catches thinking token leakage, syntax errors, and hardcoded secrets."""
    verifier = VerifierBrain()

    # 1. Clean response passes
    clean = verifier.verify_candidate_output("Hello, I am ready to assist with your codebase.")
    assert clean.valid is True
    assert clean.score >= 0.9

    # 2. Thinking token leakage is caught and penalized
    leaked = verifier.verify_candidate_output("<think>Analyzing user question</think> I will now proceed to help.")
    assert leaked.valid is False
    assert any("thinking tag" in i.lower() for i in leaked.issues)

    # 3. Python syntax error is caught
    bad_code = verifier.verify_candidate_output("def broken_syntax(:", file_path="script.py")
    assert bad_code.valid is False
    assert any("syntaxerror" in i.lower() for i in bad_code.issues)
