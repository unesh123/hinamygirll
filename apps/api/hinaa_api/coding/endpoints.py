"""FastAPI REST & SSE Router for Phase 19 Live Coding Studio.

Mounts live coding tasks, SSE event streaming with Last-Event-ID reconnection,
workspace file inspection/mutation, sandboxed preview runtime, design critique,
evidence bundle retrieval, and 12 Flagship Missions.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Header, HTTPException, Query, Request, Response
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field

from hinaa_api.coding.developer_events import (
    DeveloperEvent,
    get_developer_event_store,
)
from hinaa_api.coding.flagship_catalog import (
    FLAGSHIP_MISSIONS,
    FlagshipMission,
    get_flagship_catalog,
    get_mission,
)
from hinaa_api.coding.preview_runtime import get_preview_manager
from hinaa_api.coding.project_engine import (
    AutonomousProjectEngine,
    ProjectTask,
    get_project_engine,
)
from hinaa_api.coding.design_critic import DesignAuditScorecard, DesignCritic

logger = logging.getLogger("hinaa.coding.endpoints")

coding_router = APIRouter(prefix="/api/coding", tags=["coding"])


class CreateTaskRequest(BaseModel):
    title: str
    description: str
    mission_id: Optional[str] = None


class WriteFileRequest(BaseModel):
    path: str
    content: str


# ----------------------------------------------------------------------
# 1. Missions Catalog & Execution
# ----------------------------------------------------------------------

@coding_router.get("/missions", response_model=List[FlagshipMission])
async def list_flagship_missions() -> List[FlagshipMission]:
    """Returns all 12 flagship missions available for live coding."""
    return list(get_flagship_catalog().values())


@coding_router.get("/missions/{mission_id}", response_model=FlagshipMission)
async def get_flagship_mission(mission_id: str) -> FlagshipMission:
    """Returns specification and files for a specific flagship mission."""
    mission = get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission not found: {mission_id}")
    return mission


@coding_router.post("/missions/{mission_id}/run", response_model=ProjectTask)
async def run_flagship_mission(mission_id: str) -> ProjectTask:
    """Launches end-to-end execution of a flagship mission."""
    engine = get_project_engine()
    try:
        task = await engine.run_mission(mission_id)
        return task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error running mission {mission_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ----------------------------------------------------------------------
# 2. Task Management
# ----------------------------------------------------------------------

@coding_router.get("/tasks", response_model=List[ProjectTask])
async def list_tasks() -> List[ProjectTask]:
    """Returns all coding tasks."""
    return get_project_engine().list_tasks()


@coding_router.post("/tasks", response_model=ProjectTask)
async def create_task(req: CreateTaskRequest) -> ProjectTask:
    """Creates a new autonomous coding task."""
    return get_project_engine().create_task(
        title=req.title,
        description=req.description,
        mission_id=req.mission_id,
    )


@coding_router.get("/tasks/{task_id}", response_model=ProjectTask)
async def get_task(task_id: str) -> ProjectTask:
    """Returns current status and metadata of a task."""
    task = get_project_engine().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task


# ----------------------------------------------------------------------
# 3. SSE Live Event Stream
# ----------------------------------------------------------------------

@coding_router.get("/tasks/{task_id}/events")
async def stream_task_events(
    task_id: str,
    request: Request,
    after_seq: Optional[int] = Query(None, description="Resume events after this sequence number"),
    last_event_id: Optional[str] = Header(None, alias="Last-Event-ID"),
) -> StreamingResponse:
    """Server-Sent Events stream for task progress, file diffs, previews, and tests."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Determine starting sequence from query or header
    start_seq = 0
    if after_seq is not None:
        start_seq = after_seq
    elif last_event_id and last_event_id.isdigit():
        start_seq = int(last_event_id)

    event_store = get_developer_event_store()

    async def event_generator():
        # 1. Replay historical missed events
        missed = event_store.get_events_after(task_id=task_id, after_seq=start_seq)
        current_max = start_seq
        for ev in missed:
            current_max = max(current_max, ev.seq)
            yield f"id: {ev.seq}\nevent: {ev.kind}\ndata: {ev.model_dump_json()}\n\n"

        # 2. Subscribe to live queue
        q = await event_store.subscribe(task_id)
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    ev: DeveloperEvent = await asyncio.wait_for(q.get(), timeout=15.0)
                    if ev.seq > current_max:
                        current_max = ev.seq
                        yield f"id: {ev.seq}\nevent: {ev.kind}\ndata: {ev.model_dump_json()}\n\n"
                except asyncio.TimeoutError:
                    # SSE heartbeat keepalive comment
                    yield ": keepalive\n\n"
        finally:
            await event_store.unsubscribe(task_id, q)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ----------------------------------------------------------------------
# 4. Workspace File Operations
# ----------------------------------------------------------------------

@coding_router.get("/tasks/{task_id}/tree")
@coding_router.get("/workspaces/{task_id}/tree")
async def get_workspace_tree(task_id: str) -> List[Dict[str, Any]]:
    """Returns tree structure of files in the workspace."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return engine.get_workspace_tree(task_id)


@coding_router.get("/tasks/{task_id}/file")
@coding_router.get("/workspaces/{task_id}/file")
async def get_workspace_file(
    task_id: str,
    path: str = Query(..., description="Relative file path"),
) -> Dict[str, Any]:
    """Retrieves text content of a specific file."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    try:
        content = engine.get_file(task_id, path)
        return {
            "path": path,
            "content": content,
            "size_bytes": len(content.encode("utf-8")),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"File not found: {path}")
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))


@coding_router.post("/tasks/{task_id}/file")
@coding_router.post("/workspaces/{task_id}/file")
async def write_workspace_file(task_id: str, req: WriteFileRequest) -> Dict[str, Any]:
    """Writes content to a file, records diff, emits events, and re-audits preview."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    try:
        res = await engine.write_file(task_id, req.path, req.content)
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@coding_router.get("/tasks/{task_id}/diffs")
async def get_task_diffs(task_id: str) -> List[Dict[str, Any]]:
    """Returns recorded unified diff history for this task."""
    task = get_project_engine().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task.diff_history


@coding_router.get("/tasks/{task_id}/commands")
async def get_task_commands(task_id: str) -> List[Dict[str, Any]]:
    """Returns commands executed during this task."""
    task = get_project_engine().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return task.command_history


# ----------------------------------------------------------------------
# 5. Sandboxed Preview Server & Inspection
# ----------------------------------------------------------------------

@coding_router.get("/preview/{preview_id}/{path:path}")
async def serve_preview_asset(preview_id: str, path: str) -> Response:
    """Serves isolated workspace asset with strict CSP and hot-reload bridge."""
    pm = get_preview_manager()
    asset = pm.serve_asset(preview_id, path)
    if not asset:
        raise HTTPException(status_code=404, detail=f"Preview asset not found: {path}")

    return Response(
        content=asset.content_bytes,
        media_type=asset.media_type,
        headers=asset.headers,
    )


@coding_router.post("/tasks/{task_id}/preview")
async def refresh_task_preview(task_id: str) -> Dict[str, Any]:
    """Ensures an active preview session exists for this task."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    pm = get_preview_manager()
    from pathlib import Path
    session = pm.create_session(
        task_id=task.task_id,
        workspace_id=task.workspace_id,
        workspace_path=Path(task.workspace_path),
        entry_file="index.html",
    )
    task.preview_session_id = session.preview_id
    task.preview_url = session.preview_url
    return {
        "preview_id": session.preview_id,
        "preview_url": session.preview_url,
        "status": session.status,
    }


# ----------------------------------------------------------------------
# 6. Design Critique, Evidence & ZIP Export
# ----------------------------------------------------------------------

@coding_router.post("/tasks/{task_id}/review", response_model=DesignAuditScorecard)
async def review_task_design(task_id: str) -> DesignAuditScorecard:
    """Runs automated Design Critic audit on workspace HTML/CSS/JS."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    try:
        html = engine.get_file(task_id, "index.html")
    except Exception:
        html = ""
    try:
        css = engine.get_file(task_id, "style.css")
    except Exception:
        css = ""
    try:
        js = engine.get_file(task_id, "app.js")
    except Exception:
        js = ""

    scorecard = DesignCritic.evaluate(html, css, js)
    task.scorecard = scorecard.model_dump()
    return scorecard


@coding_router.get("/tasks/{task_id}/evidence")
async def get_task_evidence(task_id: str) -> Dict[str, Any]:
    """Retrieves cryptographic verification bundle with file hashes and audit scores."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
    return engine.generate_evidence(task_id)


@coding_router.get("/tasks/{task_id}/export")
async def export_task_zip(task_id: str) -> Response:
    """Exports workspace as a downloadable ZIP archive."""
    engine = get_project_engine()
    task = engine.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    zip_bytes = engine.export_zip(task_id)
    filename = f"{task.mission_id or 'project'}-{task_id[:8]}.zip"
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(zip_bytes)),
        },
    )
