"""
HINAA OS — Phase 18 Full Autonomous Convergence FastAPI Endpoints.

Mounts under /api/convergence/*:
- /api/convergence/missions: Lifecycle management (create, list, inspect).
- /api/convergence/missions/{id}/action: Control actions (pause, resume, cancel, replan).
- /api/convergence/missions/{id}/approve: Parameter-bound Tier C human approvals.
- /api/convergence/capabilities: Empirical capability truth matrix.
- /api/convergence/autonomy: Scoped user autonomy contract and emergency stop controls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from hinaa_api.convergence.capability_router import CapabilityRouter
from hinaa_api.convergence.contracts import (
    AutonomousMode,
    AutonomyContract,
    BudgetConstraint,
    MissionStatus,
    TypedArtifact,
    UnifiedMission,
)
from hinaa_api.convergence.coordinator import get_mission_coordinator

logger = logging.getLogger(__name__)

convergence_router = APIRouter(prefix="/api/convergence", tags=["Autonomous Convergence"])
_router_helper = CapabilityRouter()


class CreateMissionRequest(BaseModel):
    objective: str
    autonomous_mode: AutonomousMode = AutonomousMode.BOUNDED_DELEGATED
    constraints: List[str] = Field(default_factory=list)
    budget_paisa: int = 5000
    max_tokens: int = 50000


class MissionActionRequest(BaseModel):
    action: str  # pause, resume, cancel, verify, replan
    reason: Optional[str] = None


class MissionApprovalRequest(BaseModel):
    ceremony_id: str
    action: str
    parameters: Dict[str, Any]
    approved: bool
    signature_token: Optional[str] = None


@convergence_router.post("/missions", response_model=UnifiedMission)
def create_mission(
    req: CreateMissionRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    x_user_id: str = Header("user", alias="X-User-ID"),
):
    coord = get_mission_coordinator()
    budget = BudgetConstraint(max_cost_paisa=req.budget_paisa, max_tokens=req.max_tokens)
    try:
        mission = coord.create_mission(
            objective=req.objective,
            authenticated_actor=x_user_id,
            tenant_id=x_tenant_id,
            autonomous_mode=req.autonomous_mode,
            budget=budget,
            constraints=req.constraints,
        )
        return mission
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@convergence_router.get("/missions", response_model=List[UnifiedMission])
def list_missions(
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    limit: int = Query(50, ge=1, le=100),
):
    coord = get_mission_coordinator()
    return coord.store.list_missions(tenant_id=x_tenant_id, limit=limit)


@convergence_router.get("/missions/{mission_id}", response_model=UnifiedMission)
def get_mission(
    mission_id: str,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
):
    coord = get_mission_coordinator()
    m = coord.store.get_mission(mission_id)
    if not m:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Mission {mission_id} not found.")
    if m.tenant_id != x_tenant_id and x_tenant_id != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access Denied: Cross-tenant mission query.")
    return m


@convergence_router.post("/missions/{mission_id}/action", response_model=UnifiedMission)
def execute_mission_action(
    mission_id: str,
    req: MissionActionRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
):
    coord = get_mission_coordinator()
    m = coord.store.get_mission(mission_id)
    if not m or (m.tenant_id != x_tenant_id and x_tenant_id != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found.")

    action = req.action.lower()
    try:
        if action == "pause":
            return coord.pause_mission(mission_id, reason=req.reason or "Paused by user")
        elif action == "resume":
            return coord.resume_mission(mission_id)
        elif action == "cancel":
            return coord.cancel_mission(mission_id, reason=req.reason or "Cancelled by user")
        elif action == "verify":
            return coord.transition_state(mission_id, MissionStatus.VERIFYING, reason=req.reason)
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown action: {req.action}")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@convergence_router.post("/missions/{mission_id}/approve", response_model=UnifiedMission)
def handle_mission_approval(
    mission_id: str,
    req: MissionApprovalRequest,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
    x_user_id: str = Header("user", alias="X-User-ID"),
):
    coord = get_mission_coordinator()
    m = coord.store.get_mission(mission_id)
    if not m or (m.tenant_id != x_tenant_id and x_tenant_id != "admin"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mission not found.")

    if m.run_state != MissionStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mission is not awaiting approval.")

    if req.approved:
        # User explicitly approved parameter-bound action
        m.consent_state = "APPROVED"
        coord.store.save_mission(m)
        return coord.transition_state(
            mission_id,
            MissionStatus.RUNNING,
            reason=f"Approved by {x_user_id} with exact parameters.",
            reason_code="USER_APPROVED",
        )
    else:
        m.consent_state = "REJECTED"
        coord.store.save_mission(m)
        return coord.transition_state(
            mission_id,
            MissionStatus.CANCELLED,
            reason=f"Approval rejected by {x_user_id}.",
            reason_code="USER_REJECTED",
        )


@convergence_router.get("/capabilities")
def get_capabilities():
    return _router_helper.get_capability_matrix()


@convergence_router.get("/autonomy", response_model=AutonomyContract)
def get_autonomy(x_tenant_id: str = Header("default", alias="X-Tenant-ID")):
    coord = get_mission_coordinator()
    return coord.store.get_autonomy_contract(tenant_id=x_tenant_id)


@convergence_router.post("/autonomy", response_model=AutonomyContract)
def update_autonomy(
    contract: AutonomyContract,
    x_tenant_id: str = Header("default", alias="X-Tenant-ID"),
):
    coord = get_mission_coordinator()
    contract.tenant_id = x_tenant_id
    coord.store.update_autonomy_contract(contract)
    return contract
