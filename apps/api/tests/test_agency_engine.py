"""Comprehensive test suite for MODULE 01 - HINAA Independent Agency Engine."""

import pytest
import time
from hinaa_api.agency.models import (
    GoalCategory,
    GoalStatus,
    PermissionTier,
    Priority,
    ProposedGoal,
    TaskPlan,
    TaskStep,
)
from hinaa_api.agency.decision_cycle import DecisionCycle
from hinaa_api.agency.runtime import AgencyRuntime


def test_proposed_goal_utility_scoring():
    goal = ProposedGoal(
        title="Automated Test",
        description="Verify scoring",
        category=GoalCategory.MAINTENANCE,
        expected_impact=0.9,
        confidence=0.8,
        resource_cost=0.1,
    )
    score = goal.calculate_score()
    # (0.9 * 0.8) / (0.1 + 0.1) = 0.72 / 0.2 = 3.6
    assert score == 3.6
    assert goal.score == 3.6


@pytest.mark.asyncio
async def test_decision_cycle_steps():
    cycle = DecisionCycle()

    # 1. Observe
    obs = await cycle.observe()
    assert "timestamp" in obs
    assert "system" in obs

    # 2. Understand
    ctx = await cycle.understand(obs)
    assert "situational_summary" in ctx
    assert "resource_budget_available" in ctx

    # 3. Retrieve Memory
    mems = await cycle.retrieve_memory(ctx)
    assert len(mems) > 0

    # 4. Generate Goals
    candidates = await cycle.generate_goals(ctx, mems)
    assert len(candidates) >= 3
    for c in candidates:
        assert c.score > 0.0

    # 5. Evaluate Priorities
    ranked = await cycle.evaluate_priorities(candidates)
    assert len(ranked) >= 3
    assert ranked[0].score >= ranked[1].score >= ranked[2].score

    # 6. Check Permissions
    top_goal = ranked[0]
    permitted = await cycle.check_permissions(top_goal)
    assert permitted is True
    assert top_goal.status == GoalStatus.APPROVED

    # 7. Plan
    plan = await cycle.plan(top_goal)
    assert len(plan.steps) >= 2
    assert top_goal.status == GoalStatus.PLANNING

    # 8. Execute
    exec_ok = await cycle.execute(top_goal)
    assert exec_ok is True
    for s in plan.steps:
        assert s.status == "completed"

    # 9. Verify
    verified = await cycle.verify(top_goal, exec_ok)
    assert verified is True
    assert top_goal.status == GoalStatus.COMPLETED

    # 10. Reflect
    ref = await cycle.reflect(top_goal, verified)
    assert ref.success is True
    assert len(ref.key_learnings) > 0

    # 11. Update Memory
    await cycle.update_memory(top_goal, ref)
    assert len(cycle._recent_goal_hashes) == 1


@pytest.mark.asyncio
async def test_permission_tier_enforcement():
    cycle = DecisionCycle()

    # Level A: Auto approved
    goal_a = ProposedGoal(
        title="Safe Read-only Telemetry",
        description="Inspect metrics",
        category=GoalCategory.MAINTENANCE,
        permission_tier=PermissionTier.LEVEL_A_INDEPENDENT,
    )
    assert await cycle.check_permissions(goal_a) is True
    assert goal_a.status == GoalStatus.APPROVED

    # Level B: Controlled
    goal_b = ProposedGoal(
        title="Local Sandbox Run",
        description="Run test script",
        category=GoalCategory.PROJECT,
        permission_tier=PermissionTier.LEVEL_B_CONTROLLED,
    )
    assert await cycle.check_permissions(goal_b) is True
    assert goal_b.status == GoalStatus.APPROVED

    # Level C: Requires Human Approval
    goal_c = ProposedGoal(
        title="Public Post Action",
        description="Broadcast announcement",
        category=GoalCategory.CREATIVE,
        permission_tier=PermissionTier.LEVEL_C_APPROVAL_REQUIRED,
    )
    assert await cycle.check_permissions(goal_c) is False
    assert goal_c.status == GoalStatus.EVALUATED


@pytest.mark.asyncio
async def test_duplicate_goal_prevention():
    cycle = DecisionCycle()
    goal = ProposedGoal(
        title="Unique Autonomous Task",
        description="Run once only",
        category=GoalCategory.RESEARCH,
    )

    candidates = [goal]
    eval1 = await cycle.evaluate_priorities(candidates)
    assert len(eval1) == 1

    # Simulate completion
    ref = await cycle.reflect(goal, True)
    await cycle.update_memory(goal, ref)

    # Next cycle with same goal should be filtered out
    eval2 = await cycle.evaluate_priorities([goal])
    assert len(eval2) == 0


@pytest.mark.asyncio
async def test_agency_runtime_budget_and_pause():
    runtime = AgencyRuntime(cycle_interval_seconds=60, max_goals_per_hour=2)

    assert runtime.is_paused is False
    runtime.pause()
    assert runtime.is_paused is True

    # When paused, trigger_cycle returns None
    res = await runtime.trigger_cycle()
    assert res is None

    runtime.resume()
    assert runtime.is_paused is False

    # Run up to max budget (2)
    g1 = await runtime.trigger_cycle()
    assert g1 is not None
    assert g1.status == GoalStatus.COMPLETED

    g2 = await runtime.trigger_cycle()
    assert g2 is not None

    # Budget reached: _can_execute_this_hour should now be False
    assert runtime._can_execute_this_hour() is False

    status = runtime.get_status()
    assert status["goals_run_last_hour"] == 2
    assert status["budget_remaining"] == 0
    assert status["paused"] is False
    assert len(status["recent_goals"]) == 2
    assert len(status["recent_reflections"]) == 2
