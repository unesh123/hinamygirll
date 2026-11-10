"""
HINAA OS — Autonomous Browser Operations Router.
Phase 07: Isolated browser tasks, CDP event streaming, approvals, and artifacts.
"""

from __future__ import annotations

from typing import Any, Dict
from uuid import uuid4
from fastapi import APIRouter, Body, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Browser Automation"])


@router.post("/api/browser/tasks")
@router.post("/v1/browser/tasks")
async def create_browser_task(request: Request, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Creates a new isolated browser automation task."""
    from ..browser import BrowserAutomationService, BrowserTaskSpec, BrowserActionRequest
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if service is None:
        service = BrowserAutomationService()
        request.app.state.browser_service = service

    task_id = body.get("taskId") or f"task-brw-{uuid4().hex[:8]}"
    spec = BrowserTaskSpec(
        task_id=task_id,
        objective=body.get("objective", "Web browsing task"),
        user_id=body.get("userId", "default_user"),
        tenant_id=body.get("tenantId", "default_tenant"),
        start_url=body.get("startUrl"),
        max_steps=int(body.get("maxSteps", 15)),
    )
    session = await service.create_task(spec)

    initial_results = []
    if spec.start_url:
        plan = service.planner.create_navigation_plan(spec, spec.start_url)
        initial_results = await service.run_task_plan(task_id, plan)

    return {
        "taskId": task_id,
        "state": session.state.value,
        "objective": spec.objective,
        "startUrl": spec.start_url,
        "initialResults": [r.model_dump() for r in initial_results],
    }


@router.get("/api/browser/tasks/{task_id}")
@router.get("/v1/browser/tasks/{task_id}")
async def get_browser_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Retrieves status, active tabs, and pending approvals for a browser task."""
    from ..browser import BrowserAutomationService
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Browser service not initialized")
    session = service.get_task(task_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Browser task '{task_id}' not found")

    tabs = await session.list_tabs()
    return {
        "taskId": session.task_id,
        "state": session.state.value,
        "objective": session.spec.objective,
        "currentUrl": session.current_page.url if session.pages else None,
        "tabs": [t.model_dump() for t in tabs],
        "pendingApproval": session.pending_approval.model_dump() if session.pending_approval else None,
    }


@router.get("/api/browser/tasks/{task_id}/events")
@router.get("/v1/browser/tasks/{task_id}/events")
async def stream_browser_task_events(request: Request, task_id: str) -> StreamingResponse:
    """Streams real-time action events and state transitions via SSE."""
    from ..browser import BrowserAutomationService, BrowserTaskEvent
    from ..browser.action_schema import BrowserTaskState
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Browser service not initialized")
    session = service.get_task(task_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Browser task '{task_id}' not found")

    q = session.subscribe_events()

    async def sse_generator():
        try:
            while True:
                evt: BrowserTaskEvent = await q.get()
                yield f"data: {evt.model_dump_json()}\n\n"
                if evt.state in {BrowserTaskState.COMPLETED, BrowserTaskState.FAILED, BrowserTaskState.CANCELLED}:
                    break
        finally:
            session.unsubscribe_events(q)

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@router.post("/api/browser/tasks/{task_id}/cancel")
@router.post("/v1/browser/tasks/{task_id}/cancel")
async def cancel_browser_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Cancels an active browser task and aborts in-flight actions."""
    from ..browser import BrowserAutomationService
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Browser service not initialized")
    cancelled = await service.cancel_task(task_id)
    return {"taskId": task_id, "cancelled": cancelled}


@router.post("/api/browser/tasks/{task_id}/approve")
@router.post("/v1/browser/tasks/{task_id}/approve")
async def approve_browser_task_action(request: Request, task_id: str, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Submits human approval for a paused Tier C action."""
    from ..browser import BrowserAutomationService, BrowserActionRequest
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Browser service not initialized")
    approval_id = str(body.get("approvalId", ""))
    token = str(body.get("token", ""))
    action_data = body.get("actionRequest", {})
    action_req = BrowserActionRequest.model_validate(action_data)

    result = await service.approve_and_resume(task_id, approval_id, token, action_req)
    return {"taskId": task_id, "result": result.model_dump()}


@router.get("/api/browser/tasks/{task_id}/artifacts")
@router.get("/v1/browser/tasks/{task_id}/artifacts")
async def get_browser_task_artifacts(request: Request, task_id: str) -> Dict[str, Any]:
    """Returns collected artifacts (screenshots, downloads) for a browser task."""
    from ..browser import BrowserAutomationService
    service: BrowserAutomationService = getattr(request.app.state, "browser_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Browser service not initialized")
    artifacts = service.get_task_artifacts(task_id)
    return {"taskId": task_id, "artifacts": artifacts}
