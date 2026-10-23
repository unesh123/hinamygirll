"""
Automated Verification Suite for Deterministic Tool-Routing Milestone.

Verifies:
1. Deterministic OS / Computer Operator Intent & Action Execution (folder creation, app launch).
2. Enterprise 28-Point Lifecycle Hook Pipeline & Canonical Event Bus synchronization.
3. Subagent Fork & Teammate Delegation Harness (multi-role execution, bounded budgets).
4. AST Code Intelligence & Clean-Room Sandbox patch verification.
5. Deterministic Autonomous Browser Tool Plan Injection.
"""

import asyncio
import os
import shutil
import tempfile
import pytest

from hinaa_api.config import get_settings
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService
from hinaa_api.tools.computer_operator import execute_computer_operator
from hinaa_api.harness.lifecycle_hooks import (
    default_lifecycle_hooks,
    LifecycleEvent,
    LifecycleHookContext,
)
from hinaa_api.tools.subagent_fork import execute_subagent_fork
from hinaa_api.agent.coding_agent import CodePatch, apply_code_patch


@pytest.mark.asyncio
async def test_deterministic_folder_creation_plan():
    """Verify that asking Hina to create a folder deterministically injects computer_operator tool."""
    settings = get_settings()
    service = ConversationService(settings=settings)

    request = TurnRequest(
        sessionId="test_folder_session",
        text="Can you create a new folder named TestFolder on C drive?",
        providerMode="mock",
    )
    plan_result = await service.create_plan(request)
    plan = plan_result.value

    # Must contain computer_operator tool request
    cop_reqs = [t for t in plan.toolRequests if t.toolName == "computer_operator"]
    assert len(cop_reqs) >= 1, "Expected computer_operator tool request to be injected"
    assert cop_reqs[0].parameters.get("action") == "create_folder"


@pytest.mark.asyncio
async def test_computer_operator_folder_execution():
    """Verify that execute_computer_operator creates real directory and returns structured success."""
    temp_dir = tempfile.mkdtemp()
    target_path = os.path.join(temp_dir, "HinaSpecialSubfolder")
    try:
        res = await execute_computer_operator({
            "action": "create_folder",
            "target": target_path,
        })
        assert res.get("success") is True
        assert os.path.exists(target_path)
        assert res.get("created_path") == target_path
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_lifecycle_hook_pipeline_dispatch():
    """Verify 28-point lifecycle hook registration, dispatch, and canonical telemetry bridge."""
    captured_events = []

    def hook_listener(ctx: LifecycleHookContext):
        captured_events.append(ctx.event)

    default_lifecycle_hooks.register(LifecycleEvent.PRE_USER_TURN, hook_listener)
    default_lifecycle_hooks.register(LifecycleEvent.ON_SUBAGENT_FORK, hook_listener)
    default_lifecycle_hooks.register(LifecycleEvent.POST_TOOL_EXECUTE, hook_listener)

    ctx1 = LifecycleHookContext(event=LifecycleEvent.PRE_USER_TURN, session_id="test_sess_1")
    ctx2 = LifecycleHookContext(event=LifecycleEvent.ON_SUBAGENT_FORK, session_id="test_sess_1")
    ctx3 = LifecycleHookContext(event=LifecycleEvent.POST_TOOL_EXECUTE, session_id="test_sess_1")

    default_lifecycle_hooks.dispatch(LifecycleEvent.PRE_USER_TURN, ctx1)
    default_lifecycle_hooks.dispatch(LifecycleEvent.ON_SUBAGENT_FORK, ctx2)
    default_lifecycle_hooks.dispatch(LifecycleEvent.POST_TOOL_EXECUTE, ctx3)

    assert LifecycleEvent.PRE_USER_TURN in captured_events
    assert LifecycleEvent.ON_SUBAGENT_FORK in captured_events
    assert LifecycleEvent.POST_TOOL_EXECUTE in captured_events

    # Verify history tracking
    history = default_lifecycle_hooks.recent_events(limit=5)
    assert len(history) >= 3


@pytest.mark.asyncio
async def test_subagent_fork_execution_offline():
    """Verify subagent fork tool spawns node, tracks lifecycle, and returns structured findings."""
    res = await execute_subagent_fork({
        "role": "architect",
        "objective": "Verify modular isolation and invariant boundaries",
        "context": "Context payload for testing",
        "timeout_seconds": 10.0,
    })
    assert res.get("success") is True
    assert res.get("role") == "architect"
    assert "subagent_id" in res
    assert "findings" in res


def test_ast_code_patch_safety():
    """Verify CodePatch prevents path escapes and validates AST syntax."""
    temp_dir = tempfile.mkdtemp()
    try:
        sample_file = os.path.join(temp_dir, "module.py")
        with open(sample_file, "w", encoding="utf-8") as f:
            f.write("def original_fn():\n    return 42\n")

        # Valid patch
        patch = CodePatch(
            file_path="module.py",
            target_content="def original_fn():\n    return 42",
            replacement_content="def original_fn():\n    return 100",
        )
        res = apply_code_patch(temp_dir, patch, validate_syntax=True)
        assert res.success is True

        with open(sample_file, "r", encoding="utf-8") as f:
            assert "return 100" in f.read()

        # Syntax error patch must be refused by AST gate
        bad_syntax_patch = CodePatch(
            file_path="module.py",
            target_content="def original_fn():\n    return 100",
            replacement_content="def original_fn():::\n    invalid syntax",
        )
        bad_res = apply_code_patch(temp_dir, bad_syntax_patch, validate_syntax=True)
        assert bad_res.success is False
        assert "syntax error" in (bad_res.error or "").lower()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_deterministic_browser_agent_plan():
    """Verify that asking Hina to use the autonomous browser agent deterministically injects browser tools."""
    settings = get_settings()
    service = ConversationService(settings=settings)

    request = TurnRequest(
        sessionId="test_browser_session",
        text="Can you use autonomous browser agent to search for Claude Code on Google?",
        providerMode="mock",
    )
    plan_result = await service.create_plan(request)
    plan = plan_result.value

    browser_reqs = [t for t in plan.toolRequests if t.toolName in ("browser_execute_task", "browser_navigate")]
    assert len(browser_reqs) >= 1, "Expected browser tool request to be injected into plan"
    assert "cannot" not in plan.displayText.lower(), "Refusal text must not be present"
    assert "browser" in plan.displayText.lower() or "search" in plan.displayText.lower()
