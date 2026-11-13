"""
HINAA OS — Developer Coding Sandbox & Autonomous Task Execution Router.
Phase 08: Sandbox isolation, bounded coding loops, rollback, approvals, and SSE streaming.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict
from fastapi import APIRouter, Body, Request, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Coding Sandbox"])


@router.get("/api/coding/sandbox/status")
@router.get("/v1/coding/sandbox/status")
async def get_coding_sandbox_status(request: Request) -> Dict[str, Any]:
    """Returns host sandbox isolation capabilities and health."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        service = CodingService()
        request.app.state.coding_service = service
    return service.get_sandbox_status().model_dump()


@router.post("/api/coding/tasks")
@router.post("/v1/coding/tasks")
async def create_coding_task(request: Request, spec_data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Creates and initiates an autonomous bounded coding task."""
    from ..coding import CodingService, CodingTaskSpec
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        service = CodingService()
        request.app.state.coding_service = service
    spec = CodingTaskSpec.model_validate(spec_data)
    loop = service.create_task(spec)
    target_file = spec_data.get("target_file", "")
    target_content = spec_data.get("target_content", "")
    replacement_content = spec_data.get("replacement_content", "")
    test_cmd = spec_data.get("test_command")
    repair_patches = spec_data.get("repair_patches")
    if target_file:
        asyncio.create_task(loop.execute_task(
            target_file,
            target_content,
            replacement_content,
            test_cmd,
            repair_patches=repair_patches,
        ))
    return loop.status.model_dump()


@router.get("/api/coding/tasks/{task_id}")
@router.get("/v1/coding/tasks/{task_id}")
async def get_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Returns current status and step results for a coding task."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    status = service.get_task(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    return status.model_dump()


@router.get("/api/coding/tasks/{task_id}/events")
@router.get("/v1/coding/tasks/{task_id}/events")
async def stream_coding_task_events(request: Request, task_id: str):
    """Streams real-time activity events over SSE for developer workspace."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    loop = service._active_loops.get(task_id)
    if not loop:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    queue = service.subscribe_events(task_id)

    async def sse_generator():
        try:
            while True:
                evt = await queue.get()
                data = json.dumps(evt.model_dump())
                yield f"event: progress\ndata: {data}\n\n"
                if evt.type in {"run.completed", "run.failed"} or loop.is_cancelled:
                    break
        finally:
            service.unsubscribe_events(task_id, queue)

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/coding/tasks/{task_id}/cancel")
@router.post("/v1/coding/tasks/{task_id}/cancel")
async def cancel_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Cancels an active coding task and terminates sandbox processes."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    cancelled = service.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    return {"taskId": task_id, "status": "CANCELLED"}


@router.post("/api/coding/tasks/{task_id}/approve")
@router.post("/v1/coding/tasks/{task_id}/approve")
async def approve_coding_action(request: Request, task_id: str, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Verifies cryptographic human approval for Tier C action."""
    from ..coding import CodingService, CodingActionRequest
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    token = str(body.get("token", ""))
    action_req = CodingActionRequest.model_validate(body.get("actionRequest", {}))
    approved = service.approve_action(task_id, action_req, token)
    return {"taskId": task_id, "approved": approved}


@router.get("/api/coding/tasks/{task_id}/artifacts")
@router.get("/v1/coding/tasks/{task_id}/artifacts")
async def get_coding_task_artifacts(request: Request, task_id: str) -> Dict[str, Any]:
    """Returns artifacts produced by the coding task."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    artifacts = service.list_artifacts(task_id)
    return {"taskId": task_id, "artifacts": artifacts}


@router.post("/api/coding/tasks/{task_id}/rollback")
@router.post("/v1/coding/tasks/{task_id}/rollback")
async def rollback_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Rolls back all files modified by the task."""
    from ..coding import CodingService
    service: CodingService = getattr(request.app.state, "coding_service", None)
    if not service:
        raise HTTPException(status_code=404, detail="Coding service not initialized")
    reverted = service.rollback_task(task_id)
    return {"taskId": task_id, "status": "ROLLED_BACK", "reverted": reverted}
