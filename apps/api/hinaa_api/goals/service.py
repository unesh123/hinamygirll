"""
HINAA OS — Phase 14: Unified Goal & Self-Correction Service (Module H)
Coordinates goal intake, hierarchical milestone planning, independent evidence evaluation,
continuous monitoring, bounded replanning, observed self-model checks, and Tier C approvals.
Integrates directly with Phase 13 Autopilot storage and Phase 12 Hierarchical Dispatch.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from .contracts import (
    CostCategory,
    EvidenceReceipt,
    GoalApprovalRequest,
    GoalSpec,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanVersion,
    QuarantinedReflection,
    ReplanDecision,
    RiskTier,
    RootCauseType,
    SelfModelCapability,
)
from .critic import MilestoneCritic
from .intake import GoalIntakeEngine
from .monitor import GoalMonitor
from .planner import HierarchicalGoalPlanner
from .reflections import ReflectionManager
from .replan import BoundedReplanner
from .self_model import ObservedSelfModel
from .store import GoalStore

logger = logging.getLogger(__name__)


class GoalService:
    """Master service governing autonomous goal pursuit, continuous self-correction, and safety."""

    def __init__(self, db_path: str = "hinaa_autopilot.db", approval_secret: str = "hinaa-tier-c-approval-secret-v1"):
        self.store = GoalStore(db_path=db_path)
        self.approval_secret = approval_secret

        self.self_model = ObservedSelfModel(store=self.store)
        self.intake = GoalIntakeEngine(store=self.store)
        self.planner = HierarchicalGoalPlanner(store=self.store, self_model=self.self_model)
        self.critic = MilestoneCritic()
        self.monitor = GoalMonitor(store=self.store, critic=self.critic)
        self.replanner = BoundedReplanner(store=self.store)
        self.reflections = ReflectionManager(store=self.store)

    # ── Goal Lifecycle ──

    def submit_goal(
        self,
        title: str,
        description: str = "",
        tenant_id: str = "default_tenant",
        user_id: str = "default_user",
        project_id: str = "default_project",
        origin: str = "USER_PROMPT",
        authorized_scope: Optional[List[str]] = None,
        priority: int = 50,
        risk_tier: RiskTier = RiskTier.TIER_B_INTERNAL_DEV,
        time_horizon_seconds: float = 3600.0,
        deadline_utc: Optional[float] = None,
        budget_paisa: int = 5000,
        budget_tokens: int = 50000,
        auto_accept: bool = False,
    ) -> Tuple[GoalSpec, bool, str]:
        """Submits a candidate goal. If auto_accept is True and user authorized, plans immediately."""
        goal, is_new, reason = self.intake.propose_goal(
            title=title,
            description=description,
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            origin=origin,
            authorized_scope=authorized_scope,
            priority=priority,
            risk_tier=risk_tier,
            time_horizon_seconds=time_horizon_seconds,
            deadline_utc=deadline_utc,
            budget_paisa=budget_paisa,
            budget_tokens=budget_tokens,
        )

        if auto_accept and is_new and goal.status == GoalStatus.PROPOSED:
            self.intake.accept_goal(goal.goal_id, operator_user_id=user_id)
            self.planner.plan_goal(goal)

        return goal, is_new, reason

    def start_goal(self, goal_id: str, operator_user_id: str = "default_user") -> PlanVersion:
        """Explicitly accepts a proposed goal and generates its active PlanVersion."""
        goal = self.intake.accept_goal(goal_id, operator_user_id=operator_user_id)
        if not goal:
            raise ValueError(f"Goal {goal_id} not found")
        return self.planner.plan_goal(goal)

    def pause_goal(self, goal_id: str) -> Optional[GoalSpec]:
        goal = self.store.get_goal(goal_id)
        if not goal:
            return None
        goal.status = GoalStatus.PAUSED
        self.store.save_goal(goal)
        return goal

    def resume_goal(self, goal_id: str) -> Optional[GoalSpec]:
        goal = self.store.get_goal(goal_id)
        if not goal:
            return None
        goal.status = GoalStatus.RUNNING
        self.store.save_goal(goal)
        return goal

    def cancel_goal(self, goal_id: str, reason: str = "User cancelled") -> Optional[GoalSpec]:
        goal = self.store.get_goal(goal_id)
        if not goal:
            return None
        goal.status = GoalStatus.CANCELLED
        goal.termination_reason = reason
        goal.completed_at_utc = time.time()
        self.store.save_goal(goal)
        return goal

    def emergency_stop(self, tenant_id: str, reason: str = "Emergency stop invoked") -> int:
        """Immediately stops all running and accepted goals within a tenant."""
        goals = self.store.list_goals(tenant_id=tenant_id, limit=500)
        stopped_count = 0
        now = time.time()
        for g in goals:
            if g.status in (GoalStatus.RUNNING, GoalStatus.ACCEPTED, GoalStatus.PAUSED, GoalStatus.WAITING_APPROVAL):
                g.status = GoalStatus.CANCELLED
                g.termination_reason = f"EMERGENCY_STOP: {reason}"
                g.completed_at_utc = now
                self.store.save_goal(g)
                stopped_count += 1
        return stopped_count

    # ── Milestone Execution & Evidence Recording ──

    def record_milestone_receipt(
        self,
        milestone_id: str,
        tool_name: str,
        exit_code: int = 0,
        output_hash: str = "",
        source_provenance: Optional[Dict[str, Any]] = None,
        verified_by_qa: bool = False,
        raw_snippet: Optional[str] = None,
        signature: Optional[str] = None,
    ) -> EvidenceReceipt:
        """Records a verifiable evidence receipt for a milestone."""
        # Find milestone to retrieve goal_id
        conn = self.store._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT goal_id FROM goal_milestones WHERE milestone_id = ?", (milestone_id,))
            row = cur.fetchone()
            goal_id = row["goal_id"] if row else "unknown_goal"
        finally:
            if self.store._mem_conn is None:
                conn.close()

        receipt = EvidenceReceipt(
            milestone_id=milestone_id,
            goal_id=goal_id,
            tool_name=tool_name,
            exit_code=exit_code,
            output_hash=output_hash or hashlib.sha256((raw_snippet or "").encode("utf-8")).hexdigest(),
            source_provenance=source_provenance or {},
            verified_by_qa=verified_by_qa,
            timestamp_utc=time.time(),
            is_valid=True,
            raw_snippet=raw_snippet,
            signature=signature,
        )
        self.store.save_evidence_receipt(receipt)
        return receipt

    def complete_milestone(
        self,
        milestone_id: str,
        actual_paisa: int = 0,
        actual_tokens: int = 0,
    ) -> Tuple[MilestoneStatus, str]:
        """
        Evaluates milestone receipts using the independent critic.
        If valid, marks VERIFIED. If failing, triggers bounded self-correction.
        """
        # Find milestone
        conn = self.store._get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT * FROM goal_milestones WHERE milestone_id = ?", (milestone_id,))
            row = cur.fetchone()
            if not row:
                return MilestoneStatus.FAILED, "Milestone not found"
            ms = self.store._row_to_milestone(conn, row)
        finally:
            if self.store._mem_conn is None:
                conn.close()

        goal = self.store.get_goal(ms.goal_id)
        if not goal:
            return MilestoneStatus.FAILED, "Goal not found"

        # Update consumed budget
        goal.consumed_paisa += actual_paisa
        goal.consumed_tokens += actual_tokens
        self.store.save_goal(goal)

        # Retrieve all receipts
        receipts = self.store.list_evidence_receipts(ms.goal_id, ms.milestone_id)

        # Independent Critic Evaluation
        status, justification = self.critic.evaluate_milestone(ms, receipts)
        self.store.update_milestone_status(
            milestone_id=ms.milestone_id,
            status=status,
            failure_reason=justification if status != MilestoneStatus.VERIFIED else None,
            actual_paisa=actual_paisa,
            actual_tokens=actual_tokens,
        )

        # If failed or partial contradiction, trigger bounded replan
        if status in (MilestoneStatus.FAILED, MilestoneStatus.PARTIAL):
            root_cause = RootCauseType.CONTRADICTION if status == MilestoneStatus.PARTIAL else RootCauseType.TEST_FAILURE
            trigger_receipt = receipts[0].receipt_id if receipts else None
            try:
                new_plan = self.replanner.replan_goal(
                    goal=goal,
                    root_cause=root_cause,
                    failed_milestone_id=ms.milestone_id,
                    trigger_evidence_id=trigger_receipt,
                    context_notes=justification,
                )
                # Stage reflection for self-correction lesson
                self.reflections.stage_reflection(
                    goal_id=goal.goal_id,
                    tenant_id=goal.tenant_id,
                    lesson=f"Resolved failure in {goal.title} ('{ms.title}'): {justification}",
                    trigger_failure=justification,
                    corrective_action=f"Replaced with adapted milestone in Plan Version {new_plan.version_number}",
                    source_receipts=[r.receipt_id for r in receipts],
                )
            except Exception as e:
                logger.error(f"Replan attempt halted: {e}")

        # Check overall goal completion
        self.monitor.inspect_goal_progress(goal.goal_id)
        return status, justification

    # ── Tier C Parameter-Bound Approvals ──

    def request_tier_c_approval(
        self,
        goal_id: str,
        action_type: str,
        resource: str,
        amount_paisa: int = 0,
        recipient: Optional[str] = None,
        duration_seconds: float = 300.0,
    ) -> GoalApprovalRequest:
        """Generates a cryptographic parameter-bound approval request requiring operator sign-off."""
        goal = self.store.get_goal(goal_id)
        tenant_id = goal.tenant_id if goal else "default_tenant"

        approval = GoalApprovalRequest(
            goal_id=goal_id,
            tenant_id=tenant_id,
            action_type=action_type,
            resource=resource,
            amount_paisa=amount_paisa,
            recipient=recipient,
            nonce=uuid.uuid4().hex,
            expires_at_utc=time.time() + duration_seconds,
            is_consumed=False,
        )
        approval.hmac_signature = approval.compute_signature(self.approval_secret)
        self.store.save_approval(approval)

        # Mark goal as WAITING_APPROVAL
        if goal:
            goal.status = GoalStatus.WAITING_APPROVAL
            self.store.save_goal(goal)

        return approval

    def execute_tier_c_action(
        self,
        approval_id: str,
        action_type: str,
        resource: str,
        amount_paisa: int,
        recipient: Optional[str] = None,
    ) -> Tuple[bool, str]:
        """
        Executes a Tier C action only if the approval matches exact bound parameters,
        has not expired, has not been consumed, and has a valid HMAC signature.
        """
        approval = self.store.get_approval(approval_id)
        if not approval:
            return False, "Approval request not found."

        if approval.is_consumed:
            return False, "Replay attack detected: Approval token already consumed."

        if time.time() > approval.expires_at_utc:
            return False, "Approval token has expired."

        # Verify HMAC
        if not approval.verify_signature(self.approval_secret):
            return False, "Cryptographic HMAC verification failed. Signature mismatch."

        # Verify exact parameters
        if (
            approval.action_type != action_type
            or approval.resource != resource
            or approval.amount_paisa != amount_paisa
            or approval.recipient != recipient
        ):
            return False, "Parameter mismatch: Action parameters do not match approved scope."

        # Atomically consume approval
        success = self.store.consume_approval(approval_id)
        if not success:
            return False, "Failed to atomically consume approval token."

        return True, f"Tier C action '{action_type}' authorized and executed successfully."
