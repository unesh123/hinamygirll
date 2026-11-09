"""
HINAA OS — Independent Agency Engine Router.
Autonomous decision cycles, reflections, and administrative pause/resume switches.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter

router = APIRouter(tags=["Independent Agency"])


@router.get("/api/agency/status")
@router.get("/v1/agency/status")
async def get_agency_status() -> Dict[str, Any]:
    """Current operational status, goals, and reflections of the Independent Agency Engine."""
    from ..agency import get_agency_runtime
    return get_agency_runtime().get_status()


@router.post("/api/agency/trigger")
@router.post("/v1/agency/trigger")
async def trigger_agency_cycle() -> Dict[str, Any]:
    """Trigger an immediate autonomous decision cycle on demand."""
    from ..agency import get_agency_runtime
    goal = await get_agency_runtime().trigger_cycle()
    return {"triggered": True, "goal": goal.model_dump() if goal else None}


@router.post("/api/agency/pause")
@router.post("/v1/agency/pause")
async def pause_agency() -> Dict[str, bool]:
    """Administrative pause switch for all autonomous background activity."""
    from ..agency import get_agency_runtime
    get_agency_runtime().pause()
    return {"paused": True}


@router.post("/api/agency/resume")
@router.post("/v1/agency/resume")
async def resume_agency() -> Dict[str, bool]:
    """Administrative resume switch for autonomous background activity."""
    from ..agency import get_agency_runtime
    get_agency_runtime().resume()
    return {"paused": False}
