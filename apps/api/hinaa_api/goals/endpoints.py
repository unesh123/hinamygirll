"""
HINAA OS — Phase 14: Goals & Continuous Self-Correction Endpoints
REST & SSE endpoints for Goal intake, Plan Versions, Milestone DAGs, Evidence Receipts,
Replanning Decisions, Parameter-Bound Approvals, Self-Model Auditing, and Quarantined Reflections.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from .contracts import (
    CostCategory,
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
from .service import GoalService

router = APIRouter(prefix="/api/goals", tags=["Goals & Continuous Self-Correction"])
_goal_service: Optional[GoalService] = None


def get_goal_service() -> GoalService:
    global _goal_service
    if _goal_service is None:
        _goal_service = GoalService()
    return _goal_service


class SubmitGoalPayload(BaseModel):
    title: str
    description: str = ""
    tenant_id: str = "default_tenant"
    user_id: str = "default_user"
    project_id: str = "default_project"
    origin: str = "USER_PROMPT"
    authorized_scope: Optional[List[str]] = None
    priority: int = 50
    risk_tier: RiskTier = RiskTier.TIER_B_INTERNAL_DEV
    time_horizon_seconds: float = 3600.0
    deadline_utc: Optional[float] = None
    budget_paisa: int = 5000
    budget_tokens: int = 50000
    auto_accept: bool = False


class ReviseGoalPayload(BaseModel):
    new_title: str
    new_description: str
    operator_user_id: str = "default_user"


class RecordReceiptPayload(BaseModel):
    tool_name: str
    exit_code: int = 0
    output_hash: str = ""
    source_provenance: Dict[str, Any] = Field(default_factory=dict)
    verified_by_qa: bool = False
    raw_snippet: Optional[str] = None
    signature: Optional[str] = None


class CompleteMilestonePayload(BaseModel):
    actual_paisa: int = 0
    actual_tokens: int = 0


class TierCApprovalRequestPayload(BaseModel):
    action_type: str
    resource: str
    amount_paisa: int = 0
    recipient: Optional[str] = None
    duration_seconds: float = 300.0


class TierCExecutePayload(BaseModel):
    approval_id: str
    action_type: str
    resource: str
    amount_paisa: int
    recipient: Optional[str] = None


class ReviewReflectionPayload(BaseModel):
    approve: bool
    reviewer_user_id: str = "default_user"


@router.post("", response_model=Dict[str, Any])
async def submit_goal(payload: SubmitGoalPayload):
    service = get_goal_service()
    goal, is_new, reason = service.submit_goal(
        title=payload.title,
        description=payload.description,
        tenant_id=payload.tenant_id,
        user_id=payload.user_id,
        project_id=payload.project_id,
        origin=payload.origin,
        authorized_scope=payload.authorized_scope,
        priority=payload.priority,
        risk_tier=payload.risk_tier,
        time_horizon_seconds=payload.time_horizon_seconds,
        deadline_utc=payload.deadline_utc,
        budget_paisa=payload.budget_paisa,
        budget_tokens=payload.budget_tokens,
        auto_accept=payload.auto_accept,
    )
    return {
        "goal": goal.model_dump(),
        "is_new": is_new,
        "reason": reason,
    }


@router.get("", response_model=List[Dict[str, Any]])
async def list_goals(
    tenant_id: str = "default_tenant",
    status: Optional[GoalStatus] = None,
    limit: int = 50,
):
    service = get_goal_service()
    goals = service.store.list_goals(tenant_id=tenant_id, status=status, limit=limit)
    return [g.model_dump() for g in goals]


@router.get("/self-model", response_model=Dict[str, Any])
async def get_self_model():
    service = get_goal_service()
    return service.self_model.get_self_model_summary()


@router.get("/reflections", response_model=List[Dict[str, Any]])
async def list_reflections(tenant_id: str = "default_tenant", status: Optional[str] = "PENDING_REVIEW"):
    service = get_goal_service()
    refls = service.reflections.list_quarantined_lessons(tenant_id=tenant_id, status=status)
    return [r.model_dump() for r in refls]


@router.post("/reflections/{reflection_id}/review", response_model=Dict[str, Any])
async def review_reflection(reflection_id: str, payload: ReviewReflectionPayload):
    service = get_goal_service()
    ok = service.reflections.review_reflection(
        reflection_id=reflection_id,
        approve=payload.approve,
        reviewer_user_id=payload.reviewer_user_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Reflection not found")
    return {"status": "success", "approved": payload.approve}


@router.post("/emergency-stop", response_model=Dict[str, Any])
async def emergency_stop(tenant_id: str = "default_tenant", reason: str = "Operator emergency stop"):
    service = get_goal_service()
    count = service.emergency_stop(tenant_id=tenant_id, reason=reason)
    return {"status": "emergency_stop_executed", "goals_stopped": count}


@router.get("/{goal_id}", response_model=Dict[str, Any])
async def get_goal(goal_id: str):
    service = get_goal_service()
    goal = service.store.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail=f"Goal {goal_id} not found")
    plan = service.store.get_plan_version(goal_id, goal.active_plan_version)
    return {
        "goal": goal.model_dump(),
        "active_plan": plan.model_dump() if plan else None,
    }


@router.post("/{goal_id}/start", response_model=Dict[str, Any])
async def start_goal(goal_id: str, operator_user_id: str = "default_user"):
    service = get_goal_service()
    try:
        plan = service.start_goal(goal_id, operator_user_id=operator_user_id)
        return {"status": "started", "active_plan": plan.model_dump()}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{goal_id}/pause", response_model=Dict[str, Any])
async def pause_goal(goal_id: str):
    service = get_goal_service()
    g = service.pause_goal(goal_id)
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "paused", "goal": g.model_dump()}


@router.post("/{goal_id}/resume", response_model=Dict[str, Any])
async def resume_goal(goal_id: str):
    service = get_goal_service()
    g = service.resume_goal(goal_id)
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "resumed", "goal": g.model_dump()}


@router.post("/{goal_id}/cancel", response_model=Dict[str, Any])
async def cancel_goal(goal_id: str, reason: str = "User cancelled"):
    service = get_goal_service()
    g = service.cancel_goal(goal_id, reason=reason)
    if not g:
        raise HTTPException(status_code=404, detail="Goal not found")
    return {"status": "cancelled", "goal": g.model_dump()}


@router.post("/{goal_id}/revise", response_model=Dict[str, Any])
async def revise_goal_intent(goal_id: str, payload: ReviseGoalPayload):
    service = get_goal_service()
    new_g = service.intake.revise_goal_intent(
        old_goal_id=goal_id,
        new_title=payload.new_title,
        new_description=payload.new_description,
        operator_user_id=payload.operator_user_id,
    )
    if not new_g:
        raise HTTPException(status_code=404, detail="Old goal not found")
    # Plan new goal
    new_plan = service.planner.plan_goal(new_g)
    return {
        "status": "revised",
        "new_goal": new_g.model_dump(),
        "active_plan": new_plan.model_dump(),
    }


@router.get("/{goal_id}/plans/{version}", response_model=Dict[str, Any])
async def get_plan_version(goal_id: str, version: int):
    service = get_goal_service()
    plan = service.store.get_plan_version(goal_id, version)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan version not found")
    return plan.model_dump()


@router.get("/{goal_id}/replans", response_model=List[Dict[str, Any]])
async def list_replans(goal_id: str):
    service = get_goal_service()
    replans = service.store.list_replans(goal_id)
    return [r.model_dump() for r in replans]


@router.post("/{goal_id}/milestones/{milestone_id}/receipt", response_model=Dict[str, Any])
async def record_receipt(goal_id: str, milestone_id: str, payload: RecordReceiptPayload):
    service = get_goal_service()
    rec = service.record_milestone_receipt(
        milestone_id=milestone_id,
        tool_name=payload.tool_name,
        exit_code=payload.exit_code,
        output_hash=payload.output_hash,
        source_provenance=payload.source_provenance,
        verified_by_qa=payload.verified_by_qa,
        raw_snippet=payload.raw_snippet,
        signature=payload.signature,
    )
    return rec.model_dump()


@router.post("/{goal_id}/milestones/{milestone_id}/complete", response_model=Dict[str, Any])
async def complete_milestone(goal_id: str, milestone_id: str, payload: CompleteMilestonePayload):
    service = get_goal_service()
    status, justification = service.complete_milestone(
        milestone_id=milestone_id,
        actual_paisa=payload.actual_paisa,
        actual_tokens=payload.actual_tokens,
    )
    return {
        "status": status.value,
        "justification": justification,
    }


@router.get("/{goal_id}/receipts", response_model=List[Dict[str, Any]])
async def list_receipts(goal_id: str, milestone_id: Optional[str] = None):
    service = get_goal_service()
    receipts = service.store.list_evidence_receipts(goal_id=goal_id, milestone_id=milestone_id)
    return [r.model_dump() for r in receipts]


@router.post("/{goal_id}/approvals/request", response_model=Dict[str, Any])
async def request_tier_c_approval(goal_id: str, payload: TierCApprovalRequestPayload):
    service = get_goal_service()
    appr = service.request_tier_c_approval(
        goal_id=goal_id,
        action_type=payload.action_type,
        resource=payload.resource,
        amount_paisa=payload.amount_paisa,
        recipient=payload.recipient,
        duration_seconds=payload.duration_seconds,
    )
    return appr.model_dump()


@router.post("/{goal_id}/approvals/execute", response_model=Dict[str, Any])
async def execute_tier_c_action(goal_id: str, payload: TierCExecutePayload):
    service = get_goal_service()
    ok, msg = service.execute_tier_c_action(
        approval_id=payload.approval_id,
        action_type=payload.action_type,
        resource=payload.resource,
        amount_paisa=payload.amount_paisa,
        recipient=payload.recipient,
    )
    if not ok:
        raise HTTPException(status_code=403, detail=msg)
    return {"status": "executed", "message": msg}
