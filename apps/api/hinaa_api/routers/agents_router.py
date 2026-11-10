"""
Router for Phase 11 Multi-Agent Swarms & Autonomous Tooling Endpoints.
Extracted from main.py to maintain modular enterprise architecture.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from ..agents import ExecutionMode, agent_service

router = APIRouter(tags=["agents"])


@router.post("/api/agents/tasks")
async def create_agent_task(request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    goal = body.get("goal")
    if not goal:
        return JSONResponse({"error": "Field 'goal' is required"}, status_code=400)

    tenant_id = body.get("tenant_id", "default")
    user_id = body.get("user_id", "user-default")
    language = body.get("language", "en")
    mode_str = body.get("execution_mode")
    exec_mode = None
    if mode_str:
        try:
            exec_mode = ExecutionMode(mode_str)
        except Exception:
            pass

    try:
        task = agent_service.create_task(
            goal=goal,
            tenant_id=tenant_id,
            user_id=user_id,
            language=language,
            execution_mode=exec_mode,
        )
        routing_mode, rationale = agent_service.dispatcher.evaluate_routing_gate(goal)
        return JSONResponse({
            "task": task.model_dump(),
            "routing_mode": routing_mode,
            "routing_rationale": rationale,
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


@router.get("/api/agents/teams")
async def list_agent_teams() -> JSONResponse:
    teams = agent_service.list_teams()
    return JSONResponse({"teams": [t.model_dump() for t in teams]})


@router.get("/api/agents/tasks/{task_id}/teams")
async def get_agent_task_teams(task_id: str) -> JSONResponse:
    teams_data = agent_service.get_task_teams(task_id)
    return JSONResponse(teams_data)


@router.get("/api/agents/tasks/{task_id}")
async def get_agent_task(task_id: str) -> JSONResponse:
    task = agent_service.get_task(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse({"task": task.model_dump()})


@router.post("/api/agents/tasks/{task_id}/run")
async def run_agent_task(task_id: str) -> JSONResponse:
    res = agent_service.run_task(task_id)
    if not res:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse({"result": res.model_dump()})


@router.get("/api/agents/tasks/{task_id}/events", response_model=None)
async def stream_agent_task_events(task_id: str, since_sequence: int = 0) -> StreamingResponse | JSONResponse:
    task = agent_service.get_task(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)

    async def event_generator():
        events = agent_service.get_task_events(task_id, since_sequence=since_sequence)
        for evt in events:
            evt_dict = evt.model_dump()
            data = json.dumps(evt_dict, ensure_ascii=False)
            yield f"id: {evt.sequence}\nevent: {evt.event_type}\ndata: {data}\n\n"
        yield "event: end\ndata: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/api/agents/tasks/{task_id}/approve")
async def approve_agent_task_action(task_id: str, request: Request) -> JSONResponse:
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)

    approval_id = body.get("approval_id")
    signature = body.get("signature", "")
    if not approval_id:
        return JSONResponse({"error": "approval_id is required"}, status_code=400)

    success, msg = agent_service.approve_action(task_id=task_id, approval_id=approval_id, signature=signature)
    if not success:
        return JSONResponse({"error": msg}, status_code=400)
    return JSONResponse({"success": True, "message": msg})


@router.post("/api/agents/tasks/{task_id}/cancel")
async def cancel_agent_task(task_id: str, request: Request) -> JSONResponse:
    reason = "User requested cancellation"
    try:
        body = await request.json()
        reason = body.get("reason", reason)
    except Exception:
        pass
    success = agent_service.cancel_task(task_id, reason=reason)
    if not success:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    return JSONResponse({"success": True, "message": f"Task {task_id} cancelled"})


@router.post("/api/agents/tasks/{task_id}/resume")
async def resume_agent_task(task_id: str) -> JSONResponse:
    task = agent_service.get_task(task_id)
    if not task:
        return JSONResponse({"error": "Task not found"}, status_code=404)
    res = agent_service.run_task(task_id)
    return JSONResponse({"success": True, "result": res.model_dump() if res else None})


@router.get("/api/agents/tasks/{task_id}/artifacts")
async def get_agent_task_artifacts(task_id: str) -> JSONResponse:
    artifacts = agent_service.get_artifacts(task_id)
    return JSONResponse({"task_id": task_id, "artifacts": artifacts})


@router.get("/api/agents/registry")
async def get_specialist_registry() -> JSONResponse:
    specialists = agent_service.list_specialists()
    return JSONResponse({"specialists": [s.model_dump() for s in specialists]})


@router.get("/api/agents/health")
async def get_agent_orchestration_health() -> JSONResponse:
    health = agent_service.get_health()
    return JSONResponse(health)
