"""
HINAA OS — Phase 14: Goal Intake, Ownership & Prioritization Engine (Module A)
Derives candidate goals from explicit user requests, unfinished work, and schedules.
Enforces multi-tenant isolation, semantic deduplication within tenants, permission scoping,
rate limiting, intent revision supersession, and deadline expiration.
"""

from __future__ import annotations

import hashlib
import re
import time
from typing import Any, Dict, List, Optional, Tuple

from .contracts import GoalSpec, GoalStatus, RiskTier
from .store import GoalStore


class GoalIntakeEngine:
    """Manages the lifecycle of goal proposals, deduplication, acceptance, and supersession."""

    def __init__(self, store: GoalStore):
        self.store = store
        self._rate_limits: Dict[str, List[float]] = {}  # tenant_id -> list of submission timestamps

    def propose_goal(
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
        success_criteria: Optional[List[str]] = None,
        stop_conditions: Optional[List[str]] = None,
        budget_paisa: int = 5000,
        budget_tokens: int = 50000,
        source_refs: Optional[List[str]] = None,
        max_rate_per_minute: int = 30,
    ) -> Tuple[GoalSpec, bool, str]:
        """
        Proposes a candidate goal.
        Returns (goal, is_new, reason). If near-duplicate exists in tenant, returns existing goal.
        """
        now = time.time()

        # 1. Rate Limiting per tenant
        timestamps = self._rate_limits.setdefault(tenant_id, [])
        # Evict timestamps older than 60s
        self._rate_limits[tenant_id] = [t for t in timestamps if now - t < 60.0]
        if len(self._rate_limits[tenant_id]) >= max_rate_per_minute:
            # Decline due to rate limit
            declined = GoalSpec(
                tenant_id=tenant_id,
                user_id=user_id,
                project_id=project_id,
                title=title,
                description=description,
                origin=origin,
                status=GoalStatus.BLOCKED,
                termination_reason="Rate limit exceeded for tenant",
            )
            return declined, False, "Tenant submission rate limit exceeded"

        self._rate_limits[tenant_id].append(now)

        # 2. Semantic Deduplication within Tenant
        existing_goals = self.store.list_goals(tenant_id=tenant_id, limit=100)
        for eg in existing_goals:
            if eg.status in (GoalStatus.PROPOSED, GoalStatus.ACCEPTED, GoalStatus.RUNNING, GoalStatus.PAUSED):
                if self._are_goals_near_duplicates(title, description, eg.title, eg.description):
                    return eg, False, f"Near-duplicate of existing active goal {eg.goal_id}"

        # 3. Create New Goal Proposal
        scope = authorized_scope or ["read", "sandbox_exec"]
        goal = GoalSpec(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            title=title,
            description=description,
            origin=origin,
            authorized_scope=scope,
            priority=priority,
            risk_tier=risk_tier,
            time_horizon_seconds=time_horizon_seconds,
            deadline_utc=deadline_utc,
            success_criteria=success_criteria or [f"Verify outcome of {title}"],
            stop_conditions=stop_conditions or ["Stop on unrecoverable test failure", "Stop on budget exhaustion"],
            budget_paisa=budget_paisa,
            budget_tokens=budget_tokens,
            source_refs=source_refs or [],
            status=GoalStatus.PROPOSED,
            created_at_utc=now,
            last_reviewed_at_utc=now,
        )

        self.store.save_goal(goal)
        return goal, True, "Goal proposal registered"

    def accept_goal(self, goal_id: str, operator_user_id: str) -> Optional[GoalSpec]:
        """User or authorized operator explicitly accepts a proposed goal."""
        goal = self.store.get_goal(goal_id)
        if not goal:
            return None
        if goal.status != GoalStatus.PROPOSED:
            return goal

        goal.status = GoalStatus.ACCEPTED
        goal.last_reviewed_at_utc = time.time()
        goal.metadata["accepted_by"] = operator_user_id
        self.store.save_goal(goal)
        return goal

    def revise_goal_intent(
        self,
        old_goal_id: str,
        new_title: str,
        new_description: str,
        operator_user_id: str,
    ) -> Optional[GoalSpec]:
        """
        User revises intent mid-stream.
        Supersedes the old goal and creates a new accepted goal referencing prior compatible work.
        """
        old_goal = self.store.get_goal(old_goal_id)
        if not old_goal:
            return None

        # Supersede old goal
        old_goal.status = GoalStatus.CANCELLED
        old_goal.termination_reason = f"Superseded by user revised intent: {new_title}"
        old_goal.completed_at_utc = time.time()
        self.store.save_goal(old_goal)

        # Create new goal with incremented version in metadata
        new_goal = GoalSpec(
            tenant_id=old_goal.tenant_id,
            user_id=operator_user_id,
            project_id=old_goal.project_id,
            title=new_title,
            description=new_description,
            origin="USER_REVISION",
            authorized_scope=list(old_goal.authorized_scope),
            priority=old_goal.priority,
            risk_tier=old_goal.risk_tier,
            budget_paisa=max(0, old_goal.budget_paisa - old_goal.consumed_paisa),
            budget_tokens=max(0, old_goal.budget_tokens - old_goal.consumed_tokens),
            source_refs=old_goal.source_refs + [f"superseded_goal:{old_goal.goal_id}"],
            status=GoalStatus.ACCEPTED,
            created_at_utc=time.time(),
            last_reviewed_at_utc=time.time(),
            metadata={"superseded_goal_id": old_goal.goal_id},
        )
        self.store.save_goal(new_goal)
        return new_goal

    def check_and_expire_deadlines(self, tenant_id: str) -> List[str]:
        """Scans active goals for passed deadlines and transitions them to EXPIRED."""
        now = time.time()
        expired_ids: List[str] = []
        active_goals = self.store.list_goals(tenant_id=tenant_id, limit=200)

        for g in active_goals:
            if g.status in (GoalStatus.PROPOSED, GoalStatus.ACCEPTED, GoalStatus.RUNNING):
                if g.deadline_utc and g.deadline_utc < now:
                    g.status = GoalStatus.EXPIRED
                    g.termination_reason = f"Deadline {g.deadline_utc} elapsed before completion"
                    g.completed_at_utc = now
                    self.store.save_goal(g)
                    expired_ids.append(g.goal_id)

        return expired_ids

    def prioritize_queue(self, tenant_id: str) -> List[GoalSpec]:
        """
        Orders authorized active goals by priority, remaining budget, and deadline proximity.
        """
        goals = self.store.list_goals(tenant_id=tenant_id, limit=100)
        accepted = [g for g in goals if g.status in (GoalStatus.ACCEPTED, GoalStatus.RUNNING)]

        now = time.time()

        def _sort_key(g: GoalSpec) -> Tuple[int, float, int]:
            # 1. Overdue/Urgent deadline gets highest tier
            is_urgent = 1 if (g.deadline_utc and (g.deadline_utc - now) < 1800) else 0
            # 2. Priority value (higher first)
            # 3. Consumed paisa within budget
            under_budget = 1 if g.consumed_paisa < g.budget_paisa else 0
            return (is_urgent, g.priority, under_budget)

        return sorted(accepted, key=_sort_key, reverse=True)

    # ── Helpers ──

    def _are_goals_near_duplicates(self, t1: str, d1: str, t2: str, d2: str) -> bool:
        text1 = (t1 + " " + d1).lower().strip()
        text2 = (t2 + " " + d2).lower().strip()
        if text1 == text2:
            return True
        # Distinguish if different numeric or alphanumeric suffixes
        digits1 = re.findall(r"\b\d+\b", text1)
        digits2 = re.findall(r"\b\d+\b", text2)
        if digits1 != digits2:
            return False
        chars1 = re.findall(r"\b[a-zA-Z]\b", text1)
        chars2 = re.findall(r"\b[a-zA-Z]\b", text2)
        if chars1 != chars2:
            return False
        tokens1 = set(re.findall(r"\b\w{3,}\b", text1))
        tokens2 = set(re.findall(r"\b\w{3,}\b", text2))
        if not tokens1 or not tokens2:
            return False
        jaccard = len(tokens1 & tokens2) / len(tokens1 | tokens2)
        return jaccard >= 0.85
