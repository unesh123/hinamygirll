"""
HINAA OS — Developer Coding Sandbox & Autonomous Task Execution Router.
Phase 08+: Durable sandbox isolation, bounded coding loops, rollback, approvals,
checkpoint resume, and SSE streaming.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import APIRouter, Body, HTTPException, Request
from fastapi.responses import StreamingResponse

router = APIRouter(tags=["Coding Sandbox"])


def _get_coding_service(request: Request):
    from ..coding import CodingService

    service = getattr(request.app.state, "coding_service", None)
    if service is None:
        service = CodingService()
        request.app.state.coding_service = service
    return service


@router.get("/api/coding/sandbox/status")
@router.get("/v1/coding/sandbox/status")
async def get_coding_sandbox_status(request: Request) -> Dict[str, Any]:
    """Returns host sandbox isolation capabilities and health."""
    service = _get_coding_service(request)
    return service.get_sandbox_status().model_dump()


@router.get("/api/coding/tasks")
@router.get("/v1/coding/tasks")
async def list_coding_tasks(request: Request, limit: int = 50) -> Dict[str, Any]:
    """Lists persisted and active coding tasks."""
    service = _get_coding_service(request)
    tasks = service.list_tasks(limit=max(1, min(200, limit)))
    return {"status": "ok", "count": len(tasks), "tasks": [t.model_dump(mode="json") for t in tasks]}


@router.post("/api/coding/tasks")
@router.post("/v1/coding/tasks")
async def create_coding_task(request: Request, spec_data: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Creates and initiates a durable bounded coding or studio task."""
    from ..coding import CodingTaskSpec

    service = _get_coding_service(request)
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
    elif spec_data.get("run_goal", False):
        from ..agent.agentic_runner import DEFAULT_AGENTIC_TOOLS
        from ..agent.live_agentic_service import make_provider_planner
        from ..config import get_settings
        from ..services import ProviderRouter

        settings = get_settings()
        router_inst = ProviderRouter(settings)
        planner = make_provider_planner(
            router=router_inst,
            settings=settings,
            provider_mode=str(spec_data.get("providerMode") or settings.provider_mode or "xkiro"),
            brain_model=spec_data.get("brainModel"),
            allowed_tools=set(DEFAULT_AGENTIC_TOOLS),
            max_steps=min(max(1, int(spec_data.get("max_steps") or 8)), 12),
        )
        asyncio.create_task(loop.execute_goal(
            planner=planner,
            test_command=test_cmd,
            use_worktree=bool(spec_data.get("use_worktree", False)),
            max_steps=min(max(1, int(spec_data.get("max_steps") or 8)), 12),
        ))
    return loop.status.model_dump()


@router.get("/api/coding/tasks/{task_id}")
@router.get("/v1/coding/tasks/{task_id}")
async def get_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Returns current status and step results (hydrating from durable store on restart)."""
    service = _get_coding_service(request)
    status = service.get_task(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    return status.model_dump()


@router.post("/api/coding/tasks/{task_id}/resume")
@router.post("/v1/coding/tasks/{task_id}/resume")
async def resume_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Rehydrates a durable coding task checkpoint from disk after interruption."""
    service = _get_coding_service(request)
    loop = service.resume_task(task_id)
    if not loop:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} cannot be resumed or does not exist")
    return loop.status.model_dump()


@router.get("/api/coding/tasks/{task_id}/events")
@router.get("/v1/coding/tasks/{task_id}/events")
async def stream_coding_task_events(request: Request, task_id: str):
    """Streams real-time or persisted activity events over SSE for developer workspace."""
    service = _get_coding_service(request)
    status = service.get_task(task_id)
    if not status:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    loop = service._active_loops.get(task_id)
    queue = service.subscribe_events(task_id)

    async def sse_generator():
        try:
            while True:
                if loop is None and queue.empty():
                    break
                evt = await queue.get()
                data = json.dumps(evt.model_dump())
                yield f"event: progress\ndata: {data}\n\n"
                if evt.type in {"run.completed", "run.failed"} or (loop is not None and loop.is_cancelled):
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
    """Cancels an active coding task and terminates sandbox child processes."""
    service = _get_coding_service(request)
    cancelled = service.cancel_task(task_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail=f"Coding task {task_id} not found")
    return {"taskId": task_id, "status": "CANCELLED"}


@router.post("/api/coding/tasks/{task_id}/approve")
@router.post("/v1/coding/tasks/{task_id}/approve")
async def approve_coding_action(request: Request, task_id: str, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Verifies cryptographic human approval for Tier C action."""
    from ..coding import CodingActionRequest

    service = _get_coding_service(request)
    token = str(body.get("token", ""))
    action_req = CodingActionRequest.model_validate(body.get("actionRequest", {}))
    approved = service.approve_action(task_id, action_req, token)
    return {"taskId": task_id, "approved": approved}


@router.get("/api/coding/tasks/{task_id}/artifacts")
@router.get("/v1/coding/tasks/{task_id}/artifacts")
async def get_coding_task_artifacts(request: Request, task_id: str) -> Dict[str, Any]:
    """Returns artifacts produced by the coding task."""
    service = _get_coding_service(request)
    artifacts = service.list_artifacts(task_id)
    return {"taskId": task_id, "artifacts": artifacts}


@router.post("/api/coding/tasks/{task_id}/rollback")
@router.post("/v1/coding/tasks/{task_id}/rollback")
async def rollback_coding_task(request: Request, task_id: str) -> Dict[str, Any]:
    """Rolls back all files modified by the task."""
    service = _get_coding_service(request)
    reverted = service.rollback_task(task_id)
    return {"taskId": task_id, "status": "ROLLED_BACK", "reverted": reverted}
