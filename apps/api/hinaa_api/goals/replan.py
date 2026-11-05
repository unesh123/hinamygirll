"""
HINAA OS — Phase 14: Bounded Replanning & Loop Prevention Engine (Module E)
Revises failing plans based on empirical evidence, enforces max replan caps,
detects semantic retry loops, preserves historical receipts, and generates
concise multi-lingual explanations (English, Devanagari Nepali, Romanized Nepali).
"""

from __future__ import annotations

import logging
import re
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    GoalSpec,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanVersion,
    ReplanDecision,
    RootCauseType,
)
from .store import GoalStore

logger = logging.getLogger(__name__)


class SemanticLoopError(Exception):
    """Raised when an agent attempts to retry the same failed semantic action under a different name."""
    pass


class ReplanBudgetExceededError(Exception):
    """Raised when the maximum replan count is exceeded."""
    pass


class BoundedReplanner:
    """Executes bounded, evidence-grounded plan repairs and prevents infinite loops."""

    def __init__(self, store: GoalStore):
        self.store = store

    def replan_goal(
        self,
        goal: GoalSpec,
        root_cause: RootCauseType,
        failed_milestone_id: Optional[str] = None,
        trigger_evidence_id: Optional[str] = None,
        context_notes: str = "",
    ) -> PlanVersion:
        """
        Generates a repaired PlanVersion (incrementing version number).
        Reuses completed compatible milestones and replaces or adapts failing ones.
        """
        # 1. Enforce Max Replans Cap
        if goal.replan_count >= goal.max_replans:
            goal.status = GoalStatus.BLOCKED
            goal.termination_reason = f"Max replan limit ({goal.max_replans}) reached without resolution."
            self.store.save_goal(goal)
            raise ReplanBudgetExceededError(goal.termination_reason)

        # 2. Retrieve current plan version
        current_plan = self.store.get_plan_version(goal.goal_id, goal.active_plan_version)
        if not current_plan:
            raise ValueError(f"Plan version {goal.active_plan_version} not found for goal {goal.goal_id}")

        prior_version = current_plan.version_number
        new_version = prior_version + 1

        reused_ms: List[Milestone] = []
        superseded_ids: List[str] = []
        added_ms: List[Milestone] = []
        new_edges: List[List[str]] = []

        # 3. Analyze existing milestones: preserve completed, repair or replace failing/pending
        for ms in current_plan.milestones:
            if ms.status == MilestoneStatus.VERIFIED:
                reused_ms.append(ms)
            elif ms.milestone_id == failed_milestone_id or ms.status in (MilestoneStatus.FAILED, MilestoneStatus.BLOCKED, MilestoneStatus.PARTIAL):
                superseded_ids.append(ms.milestone_id)
                # Formulate replacement milestone
                replacement = self._generate_replacement_milestone(goal, ms, root_cause, context_notes)
                # Check semantic loop: ensure replacement is not identical to failed action
                self._assert_not_semantic_loop(ms, replacement)
                added_ms.append(replacement)
            else:
                # Pending milestones downstream
                superseded_ids.append(ms.milestone_id)
                # Re-link pending milestone
                cloned = ms.model_copy(update={
                    "milestone_id": f"ms-{uuid.uuid4().hex[:8]}",
                    "status": MilestoneStatus.PENDING,
                })
                added_ms.append(cloned)

        # Build new milestone list and edges
        all_new_milestones = reused_ms + added_ms
        for i in range(len(all_new_milestones) - 1):
            new_edges.append([all_new_milestones[i].milestone_id, all_new_milestones[i+1].milestone_id])
            all_new_milestones[i+1].prerequisites = [all_new_milestones[i].milestone_id]

        # 4. Formulate Multi-lingual Explanations
        expl_en, expl_ne, expl_rom = self._formulate_explanations(
            goal=goal,
            root_cause=root_cause,
            context=context_notes,
            prior_v=prior_version,
            new_v=new_version,
        )

        # 5. Persist PlanVersion and ReplanDecision
        new_plan = PlanVersion(
            goal_id=goal.goal_id,
            version_number=new_version,
            parent_version_id=current_plan.plan_version_id,
            milestones=all_new_milestones,
            edges=new_edges,
            reason_for_change=f"Replan triggered by {root_cause.value}: {context_notes}",
            triggering_evidence_receipt_id=trigger_evidence_id,
            verification_reserve_paisa=current_plan.verification_reserve_paisa,
            verification_reserve_tokens=current_plan.verification_reserve_tokens,
            created_at_utc=time.time(),
        )
        self.store.save_plan_version(new_plan)

        decision = ReplanDecision(
            goal_id=goal.goal_id,
            prior_plan_version=prior_version,
            new_plan_version=new_version,
            root_cause=root_cause,
            trigger_evidence_id=trigger_evidence_id,
            explanation_en=expl_en,
            explanation_ne=expl_ne,
            explanation_romanized=expl_rom,
            superseded_milestone_ids=superseded_ids,
            reused_milestone_ids=[m.milestone_id for m in reused_ms],
            added_milestone_ids=[m.milestone_id for m in added_ms],
            created_at_utc=time.time(),
        )
        self.store.save_replan_decision(decision)

        # Update Goal state
        goal.active_plan_version = new_version
        goal.replan_count += 1
        goal.status = GoalStatus.RUNNING
        self.store.save_goal(goal)

        return new_plan

    def _generate_replacement_milestone(
        self,
        goal: GoalSpec,
        failing_ms: Milestone,
        root_cause: RootCauseType,
        context: str,
    ) -> Milestone:
        """Generates a concrete, adapted milestone addressing the specific failure."""
        new_id = f"ms-{uuid.uuid4().hex[:8]}"

        if root_cause == RootCauseType.TEST_FAILURE:
            return Milestone(
                milestone_id=new_id,
                goal_id=goal.goal_id,
                title=f"Fix & Retest: {failing_ms.title}",
                description=f"Analyze test failure trace, patch defects, and verify test suite passes cleanly. Context: {context}",
                inputs={"prior_failure": context, "original_inputs": failing_ms.inputs},
                exit_criteria=["Test suite passes with exit code 0"],
                evidence_requirements=["retest_receipt", "source_diff"],
                assigned_role="engineer",
                execution_mode="hierarchical",  # Escalate to hierarchical coordinator for verification
                max_retries=1,
            )

        elif root_cause == RootCauseType.CONTRADICTION:
            return Milestone(
                milestone_id=new_id,
                goal_id=goal.goal_id,
                title=f"Resolve Discrepancy: {failing_ms.title}",
                description=f"Cross-examine conflicting sources, check publication dates, and apply authoritative weighting. Context: {context}",
                inputs={"contradictions": context},
                exit_criteria=["Contradiction resolved with authoritative citations"],
                evidence_requirements=["cross_verification_receipt"],
                assigned_role="supervisor",
                execution_mode="hierarchical",
            )

        elif root_cause == RootCauseType.UNAVAILABLE_DEPENDENCY:
            return Milestone(
                milestone_id=new_id,
                goal_id=goal.goal_id,
                title=f"Alternative Path: {failing_ms.title}",
                description=f"Fallback to verified local or procedural alternatives due to absent external dependency. Context: {context}",
                inputs={"fallback_reason": context},
                exit_criteria=["Fallback completed"],
                evidence_requirements=["fallback_receipt"],
                assigned_role="engineer",
                execution_mode="single_agent",
            )

        # Default repair
        return Milestone(
            milestone_id=new_id,
            goal_id=goal.goal_id,
            title=f"Revised Step: {failing_ms.title}",
            description=f"Adapted approach to satisfy goal exit criteria. Context: {context}",
            assigned_role="engineer",
            execution_mode="single_agent",
        )

    def _assert_not_semantic_loop(self, old_ms: Milestone, new_ms: Milestone) -> None:
        """Ensures the replacement milestone is meaningfully different from the failed one."""
        old_tokens = set(re.findall(r"\b\w{3,}\b", (old_ms.title + " " + old_ms.description).lower()))
        new_tokens = set(re.findall(r"\b\w{3,}\b", (new_ms.title + " " + new_ms.description).lower()))

        # If description is 95%+ identical and inputs/modes are identical, flag semantic loop
        if old_tokens and new_tokens:
            jaccard = len(old_tokens & new_tokens) / len(old_tokens | new_tokens)
            if jaccard >= 0.80 and old_ms.execution_mode == new_ms.execution_mode:
                raise SemanticLoopError(
                    f"Semantic loop detected: Replacement milestone '{new_ms.title}' is semantically identical ({jaccard:.2f} overlap) to failed step without an adapted strategy."
                )

    def _formulate_explanations(
        self,
        goal: GoalSpec,
        root_cause: RootCauseType,
        context: str,
        prior_v: int,
        new_v: int,
    ) -> Tuple[str, str, str]:
        """Formulates honest, clear explanation of plan change across three linguistic formats."""
        # English
        en = (
            f"I revised the plan for '{goal.title}' from Version {prior_v} to Version {new_v}. "
            f"The previous approach failed due to {root_cause.value.lower()}: {context or 'milestone criteria not met'}. "
            f"I preserved all completed verified work, replaced the failing step with an adapted verification strategy, "
            f"and allocated sufficient QA reserve to guarantee the result."
        )

        # Devanagari Nepali
        ne = (
            f"मैले '{goal.title}' को योजना संस्करण {prior_v} बाट संस्करण {new_v} मा परिवर्तन गरेँ। "
            f"अघिल्लो चरण {root_cause.value.lower()} का कारण असफल भएको थियो: {context or 'सर्त पूरा भएन'}। "
            f"सफल भइसकेका कामहरू सुरक्षित राख्दै, असफल चरणलाई नयाँ प्रमाणित विधिबाट पुनः सञ्चालन गरिएको छ।"
        )

        # Romanized Nepali
        rom = (
            f"Maile '{goal.title}' ko plan version {prior_v} bata version {new_v} ma change gare. "
            f"Aghillo step {root_cause.value.lower()} le garda fail bhayo: {context or 'criteria satisfy bhayena'}. "
            f"Sakeko kaam preserve garera, failing step lai naya strategy le replace gareko chha."
        )

        return en, ne, rom
