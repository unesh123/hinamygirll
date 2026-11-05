"""
HINAA OS — Phase 14: Hierarchical Goal Planner & Dependency Engine (Module B)
Decomposes goals into verifiable milestone DAGs, checks cycle safety, allocates verification reserves,
detects missing external dependencies upfront (e.g. unavailable video weights), and manages versioned plans.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    CostCategory,
    GoalSpec,
    GoalStatus,
    Milestone,
    MilestoneStatus,
    PlanVersion,
)
from .self_model import ObservedSelfModel
from .store import GoalStore

logger = logging.getLogger(__name__)


class DAGCycleError(Exception):
    """Raised when milestone dependencies contain a circular dependency."""
    pass


class InfeasibleDependencyError(Exception):
    """Raised when a milestone requires an unavailable or unverified capability."""
    pass


class HierarchicalGoalPlanner:
    """Constructs, validates, and versions milestone DAGs for accepted goals."""

    def __init__(self, store: GoalStore, self_model: Optional[ObservedSelfModel] = None):
        self.store = store
        self.self_model = self_model or ObservedSelfModel(store)

    def plan_goal(
        self,
        goal: GoalSpec,
        template_name: Optional[str] = None,
        custom_milestones: Optional[List[Milestone]] = None,
    ) -> PlanVersion:
        """
        Generates a version 1 plan for an accepted goal.
        Allocates verification reserve and checks dependency feasibility.
        """
        # Determine milestones
        milestones = custom_milestones or self._decompose_goal(goal, template_name)

        # Allocate verification reserve (10% of budget)
        qa_reserve_paisa = int(goal.budget_paisa * 0.10)
        qa_reserve_tokens = int(goal.budget_tokens * 0.10)
        allocatable_paisa = max(0, goal.budget_paisa - qa_reserve_paisa)
        allocatable_tokens = max(0, goal.budget_tokens - qa_reserve_tokens)

        # Distribute remaining budget across milestones
        count = max(1, len(milestones))
        paisa_per_ms = allocatable_paisa // count
        tokens_per_ms = allocatable_tokens // count

        edges: List[List[str]] = []
        for ms in milestones:
            ms.goal_id = goal.goal_id
            if ms.estimated_paisa == 0:
                ms.estimated_paisa = paisa_per_ms
            if ms.estimated_tokens == 0:
                ms.estimated_tokens = tokens_per_ms
            for prereq in ms.prerequisites:
                edges.append([prereq, ms.milestone_id])

        # Validate DAG acyclicity
        self._validate_acyclic(milestones, edges)

        # Check capability feasibility (e.g., generative video blocked if unavailable)
        self._check_capability_feasibility(milestones)

        plan = PlanVersion(
            goal_id=goal.goal_id,
            version_number=1,
            parent_version_id=None,
            milestones=milestones,
            edges=edges,
            reason_for_change="Initial plan formulation",
            verification_reserve_paisa=qa_reserve_paisa,
            verification_reserve_tokens=qa_reserve_tokens,
            created_at_utc=time.time(),
        )

        self.store.save_plan_version(plan)
        goal.status = GoalStatus.RUNNING
        goal.active_plan_version = 1
        self.store.save_goal(goal)
        return plan

    def _decompose_goal(self, goal: GoalSpec, template: Optional[str] = None) -> List[Milestone]:
        """Creates standard milestone sequences based on goal scope and title."""
        title_l = goal.title.lower()

        # 1. Coding / Software Project DAG
        if "website" in title_l or "app" in title_l or "code" in title_l or "software" in title_l:
            m1 = Milestone(
                goal_id=goal.goal_id,
                title="1. Environment & Architecture Spec",
                description="Inspect workspace, configure package dependencies, write architectural scaffold",
                inputs={"project_id": goal.project_id},
                exit_criteria=["Workspace directory exists", "Spec approved"],
                evidence_requirements=["file_manifest", "schema_hash"],
                assigned_role="engineer",
                execution_mode="single_agent",
            )
            m2 = Milestone(
                goal_id=goal.goal_id,
                title="2. Implement Application Code",
                description="Write production application source and components",
                inputs={"spec_milestone": m1.milestone_id},
                prerequisites=[m1.milestone_id],
                exit_criteria=["Source files written cleanly"],
                evidence_requirements=["source_diff", "ast_check"],
                assigned_role="engineer",
                execution_mode="flat_swarm",
            )
            m3 = Milestone(
                goal_id=goal.goal_id,
                title="3. Automated Testing & Verification",
                description="Run pytest / vitest test suites, verify browser layout and exit codes",
                inputs={"impl_milestone": m2.milestone_id},
                prerequisites=[m2.milestone_id],
                exit_criteria=["Exit code 0", "All tests passing"],
                evidence_requirements=["test_receipt", "browser_snapshot"],
                assigned_role="qa",
                execution_mode="hierarchical",
            )
            return [m1, m2, m3]

        # 2. Research & CRAG Investigation DAG
        if "research" in title_l or "investigate" in title_l or "study" in title_l:
            m1 = Milestone(
                goal_id=goal.goal_id,
                title="1. Multi-Source Evidence Retrieval",
                description="Search authoritative sources, query academic and documentation APIs",
                exit_criteria=["At least 2 authoritative sources retrieved"],
                evidence_requirements=["url_provenance", "source_hash"],
                assigned_role="researcher",
                execution_mode="single_agent",
            )
            m2 = Milestone(
                goal_id=goal.goal_id,
                title="2. Contradiction & Claim Analysis",
                description="Cross-examine citations, identify discrepancies and compute confidence scores",
                prerequisites=[m1.milestone_id],
                exit_criteria=["Claim table verified"],
                evidence_requirements=["claim_provenance", "contradiction_report"],
                assigned_role="supervisor",
                execution_mode="hierarchical",
            )
            m3 = Milestone(
                goal_id=goal.goal_id,
                title="3. Synthesis & Memory Staging",
                description="Stage validated takeaways into quarantined knowledge memory",
                prerequisites=[m2.milestone_id],
                exit_criteria=["Quarantine staging complete"],
                evidence_requirements=["quarantine_receipt"],
                assigned_role="knowledge_curator",
                execution_mode="single_agent",
            )
            return [m1, m2, m3]

        # Default 2-Milestone DAG
        m1 = Milestone(
            goal_id=goal.goal_id,
            title="1. Investigation & Execution",
            description=f"Initial discovery and execution phase for {goal.title}",
            exit_criteria=["Step execution complete"],
            evidence_requirements=["execution_log"],
        )
        m2 = Milestone(
            goal_id=goal.goal_id,
            title="2. Independent Verification & Sign-off",
            description="Verify outcomes against success criteria",
            prerequisites=[m1.milestone_id],
            exit_criteria=["Postcondition verified"],
            evidence_requirements=["qa_signoff"],
        )
        return [m1, m2]

    def _validate_acyclic(self, milestones: List[Milestone], edges: List[List[str]]) -> None:
        """Kahn's algorithm to ensure topological sort is acyclic."""
        in_degree: Dict[str, int] = {ms.milestone_id: 0 for ms in milestones}
        adj: Dict[str, List[str]] = {ms.milestone_id: [] for ms in milestones}

        for u, v in edges:
            if u in adj and v in in_degree:
                adj[u].append(v)
                in_degree[v] += 1

        queue = [node for node, deg in in_degree.items() if deg == 0]
        visited_count = 0

        while queue:
            curr = queue.pop(0)
            visited_count += 1
            for neighbor in adj.get(curr, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited_count < len(milestones):
            raise DAGCycleError(f"Circular dependency detected in plan graph ({visited_count}/{len(milestones)} visited)")

    def _check_capability_feasibility(self, milestones: List[Milestone]) -> None:
        """Inspects milestones for dependencies on unavailable capabilities."""
        for ms in milestones:
            text = (ms.title + " " + ms.description).lower()
            if "video generation" in text or "image-to-video" in text or "text-to-video" in text:
                cap = self.self_model.probe_capability("video_generation")
                if not cap.is_available:
                    ms.status = MilestoneStatus.BLOCKED
                    ms.failure_reason = "BLOCKED_UNAVAILABLE: Video generation models/weights are unverified or absent."
                    raise InfeasibleDependencyError(
                        "Milestone requires unavailable capability: video_generation (weights missing)"
                    )
