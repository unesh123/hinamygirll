"""
HINAA OS — Phase 14: Continuous Goal Monitor & Deviation Detector (Module D)
Monitors execution DAGs, tracks resource and budget consumption, detects stalled steps,
deadlines, and tool anomalies, and dispatches deviation alerts to the replanning engine.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    EvidenceReceipt,
    GoalSpec,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanVersion,
    RootCauseType,
)
from .critic import MilestoneCritic
from .store import GoalStore

logger = logging.getLogger(__name__)


class GoalMonitor:
    """Watches goal execution, verifies completed steps, and flags deviations."""

    def __init__(self, store: GoalStore, critic: Optional[MilestoneCritic] = None):
        self.store = store
        self.critic = critic or MilestoneCritic()

    def inspect_goal_progress(
        self,
        goal_id: str,
    ) -> Tuple[GoalStatus, Optional[RootCauseType], Optional[str]]:
        """
        Inspects the active plan and milestones for a goal.
        Returns (current_status, root_cause_if_deviation, details).
        """
        goal = self.store.get_goal(goal_id)
        if not goal:
            return GoalStatus.FAILED, RootCauseType.POOR_QUALITY, "Goal not found"

        if goal.status in (GoalStatus.SUCCEEDED, GoalStatus.FAILED, GoalStatus.CANCELLED, GoalStatus.EXPIRED):
            return goal.status, None, None

        # Check deadline expiration
        now = time.time()
        if goal.deadline_utc and goal.deadline_utc < now:
            goal.status = GoalStatus.EXPIRED
            goal.termination_reason = "Deadline elapsed during execution"
            self.store.save_goal(goal)
            return GoalStatus.EXPIRED, RootCauseType.DEADLINE_MISSED, "Goal deadline elapsed"

        # Check resource ceilings
        if goal.consumed_paisa > goal.budget_paisa:
            goal.status = GoalStatus.BLOCKED
            goal.termination_reason = f"Paisa budget exhausted: {goal.consumed_paisa} > {goal.budget_paisa}"
            self.store.save_goal(goal)
            return GoalStatus.BLOCKED, RootCauseType.RESOURCE_EXCEEDED, "Budget paisa ceiling exceeded"

        # Check milestones in active plan
        plan = self.store.get_plan_version(goal_id, goal.active_plan_version)
        if not plan:
            return goal.status, None, None

        all_verified = True
        for ms in plan.milestones:
            receipts = self.store.list_evidence_receipts(goal_id, ms.milestone_id)

            if ms.status == MilestoneStatus.RUNNING:
                # Check for stalled step (running > 10 minutes without heartbeat)
                if ms.started_at_utc and (now - ms.started_at_utc > 600.0):
                    self.store.update_milestone_status(
                        ms.milestone_id,
                        MilestoneStatus.FAILED,
                        failure_reason="Stalled: Execution exceeded 600 seconds without completion",
                    )
                    return GoalStatus.RUNNING, RootCauseType.DEADLINE_MISSED, f"Milestone '{ms.title}' timed out"

            elif ms.status == MilestoneStatus.PENDING:
                all_verified = False

            elif ms.status in (MilestoneStatus.FAILED, MilestoneStatus.BLOCKED):
                all_verified = False
                # Determine root cause
                root_cause = RootCauseType.TEST_FAILURE
                if "unavailable" in (ms.failure_reason or "").lower():
                    root_cause = RootCauseType.UNAVAILABLE_DEPENDENCY
                return GoalStatus.RUNNING, root_cause, ms.failure_reason or "Milestone failed"

            elif ms.status == MilestoneStatus.PARTIAL:
                # Contradiction detected
                return GoalStatus.RUNNING, RootCauseType.CONTRADICTION, "Contradictory findings require plan adjustment"

            elif ms.status == MilestoneStatus.VERIFIED:
                continue

        if all_verified and plan.milestones:
            goal.status = GoalStatus.SUCCEEDED
            goal.completed_at_utc = now
            self.store.save_goal(goal)
            return GoalStatus.SUCCEEDED, None, "All milestones verified successfully"

        return GoalStatus.RUNNING, None, None
