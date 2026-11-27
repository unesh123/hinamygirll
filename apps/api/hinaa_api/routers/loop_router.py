"""
HINAA OS — Loop Engineering API Router (sorrycc 2026 Autonomous Paradigm).

Endpoints for starting, inspecting, and governing autonomous unattended goal/issue loops.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..harness.agent_step import build_llm_agent_step, list_pending_approvals, resolve_approval
from ..harness.loop_engine import EvidenceReceipt, LoopEngine, LoopExecutionReport, LoopTaskSpec
from ..harness.loop_events import EVENT_BUS, sse_stream
from ..harness.media_ingest import ingest_streamed_attachment, load_media_insights
from ..runtime_paths import project_root

logger = logging.getLogger("hinaa.routers.loop")

router = APIRouter(prefix="/api/loop", tags=["Loop Engineering Harness"])
_loop_engine: Optional[LoopEngine] = None
_running_tasks: Dict[str, asyncio.Task] = {}
_task_reports: Dict[str, LoopExecutionReport] = {}
_cancel_reasons: Dict[str, str] = {}
_TASK_ID_RE = re.compile(r"^[A-Za-z0-9_-]{3,64}$")


def get_loop_engine() -> LoopEngine:
    global _loop_engine
    if _loop_engine is None:
        _loop_engine = LoopEngine()
    return _loop_engine


class StartLoopPayload(BaseModel):
    goal_title: str
    description: str = ""
    verification_command: List[str]
    target_files: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    max_turns: int = Field(default=10, ge=1, le=50)
    consecutive_failure_limit: int = Field(default=2, ge=1, le=10)
    timeout_per_turn_seconds: float = Field(default=60.0, ge=5.0, le=300.0)
    pre_script: Optional[List[str]] = None
    post_script: Optional[List[str]] = None
    workspace_dir: Optional[str] = None
    require_human_approval: bool = False
    review_diff: bool = False


class ApproveActionPayload(BaseModel):
    approval_id: str = Field(min_length=4, max_length=64)
    approved: bool = True


class ResumeLoopPayload(BaseModel):
    max_turns: Optional[int] = Field(default=None, ge=1, le=50)
    require_human_approval: Optional[bool] = None
    review_diff: Optional[bool] = None


def _spec_file(engine: LoopEngine, task_id: str) -> Path:
    return engine.base_dir / f"{task_id}_spec.json"


def _persist_spec(engine: LoopEngine, spec: LoopTaskSpec, *, require_human_approval: bool, review_diff: bool) -> None:
    payload = spec.model_dump()
    payload["require_human_approval"] = require_human_approval
    payload["review_diff"] = review_diff
    _spec_file(engine, spec.task_id).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _launch_loop_task(
    engine: LoopEngine,
    spec: LoopTaskSpec,
    *,
    require_human_approval: bool = False,
    review_diff: bool = False,
) -> Dict[str, Any]:
    task_id = spec.task_id
    llm_step = build_llm_agent_step(
        spec,
        state_dir=engine.base_dir,
        require_human_approval=require_human_approval,
    )
    if llm_step is not None:
        agent_step = llm_step.as_engine_step(spec)
        agent_mode = f"llm:{llm_step.provider.name}/{llm_step.provider.model}"
    else:

        async def agent_step(turn: int, last_receipt: Optional[EvidenceReceipt]) -> str:
            logger.warning(
                "Loop task %s turn %d: no LLM provider configured; set "
                "AGENT_ROUTER_API_KEY, ANTHROPIC_API_KEY or OPENAI_API_KEY to enable "
                "real model-driven repair.",
                task_id,
                turn,
            )
            return (
                "NO_LLM_CONFIGURED: no provider key found in settings "
                "(AGENT_ROUTER_API_KEY / ANTHROPIC_API_KEY / OPENAI_API_KEY). "
                "No repair actions were taken this turn."
            )

        agent_mode = "no_llm"

    async def _run_in_background():
        try:
            await EVENT_BUS.publish(task_id, "loop_started", {"goal_title": spec.goal_title, "agent_mode": agent_mode})
            report = await engine.run_loop(spec, agent_step)
            if report.status == "COMPLETED" and review_diff and llm_step is not None:
                verdict = await llm_step.run_diff_review(spec)
                if not verdict.get("approved") and verdict.get("severity") == "critical":
                    findings_txt = "; ".join(str(x) for x in (verdict.get("findings") or [])[:3])
                    spec.constraints.append(f"Reviewer critical finding: {findings_txt}")
                    last_rcpt = report.receipts[-1] if report.receipts else None
                    await agent_step(report.total_turns + 1, last_rcpt)
                    cwd = Path(spec.workspace_dir) if spec.workspace_dir else project_root()
                    recheck = await asyncio.to_thread(
                        engine.execute_hard_gate,
                        spec.verification_command,
                        cwd,
                        report.total_turns + 1,
                        spec.timeout_per_turn_seconds,
                    )
                    report.receipts.append(recheck)
                    report.total_turns += 1
                    report.status = "COMPLETED" if recheck.passed else "FAILED"
                    engine._write_ledger_disk(spec, report.receipts, report.status)
            _task_reports[task_id] = report
            await EVENT_BUS.publish(
                task_id,
                "loop_finished" if report.status == "COMPLETED" else "loop_failed",
                {"status": report.status, "summary": report.summary, "total_turns": report.total_turns},
            )
        except asyncio.CancelledError:
            reason = _cancel_reasons.pop(task_id, "CANCELLED")
            engine._write_ledger_disk(spec, [], reason)
            # Scheduled (not awaited): the current task is being cancelled, so
            # awaiting here would immediately re-raise CancelledError.
            EVENT_BUS.publish_sync(
                task_id,
                "loop_paused" if reason == "PAUSED" else "loop_cancelled",
                {
                    "status": reason,
                    "summary": "Loop paused by user." if reason == "PAUSED" else "Loop cancelled by user.",
                },
            )
            raise
        except Exception as e:
            logger.error("Error in background loop task %s: %s", task_id, e)
            await EVENT_BUS.publish(task_id, "loop_failed", {"status": "ERROR", "error": str(e)[:500]})
        finally:
            _running_tasks.pop(task_id, None)
            if llm_step is not None:
                await llm_step.aclose()

    _persist_spec(engine, spec, require_human_approval=require_human_approval, review_diff=review_diff)
    engine._write_ledger_disk(spec, [], "RUNNING")

    bg_task = asyncio.create_task(_run_in_background())
    _running_tasks[task_id] = bg_task

    return {
        "ok": True,
        "task_id": task_id,
        "goal_title": spec.goal_title,
        "status": "RUNNING",
        "agent_mode": agent_mode,
        "require_human_approval": require_human_approval,
        "state_file": str(engine.base_dir / f"{task_id}_state.json"),
    }


@router.post("/start")
async def start_loop(payload: StartLoopPayload, background_tasks: BackgroundTasks, request: Request) -> Dict[str, Any]:
    """Start an autonomous unattended loop for a goal/issue."""
    engine = get_loop_engine()
    task_id = f"loop_{uuid.uuid4().hex[:8]}"

    spec = LoopTaskSpec(
        task_id=task_id,
        goal_title=payload.goal_title,
        description=payload.description,
        verification_command=payload.verification_command,
        target_files=payload.target_files,
        constraints=payload.constraints,
        max_turns=payload.max_turns,
        consecutive_failure_limit=payload.consecutive_failure_limit,
        timeout_per_turn_seconds=payload.timeout_per_turn_seconds,
        pre_script=payload.pre_script,
        post_script=payload.post_script,
        workspace_dir=payload.workspace_dir,
    )
    return _launch_loop_task(
        engine,
        spec,
        require_human_approval=payload.require_human_approval,
        review_diff=payload.review_diff,
    )


@router.get("/status/{task_id}")
async def get_loop_status(task_id: str) -> Dict[str, Any]:
    """Query current status and receipts of a loop task."""
    engine = get_loop_engine()
    pending = list_pending_approvals(task_id)

    # Check in-memory report first
    if task_id in _task_reports:
        out = _task_reports[task_id].model_dump()
        out["pending_approvals"] = pending
        return out

    # Check disk ledger
    state_file = engine.base_dir / f"{task_id}_state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            data["pending_approvals"] = pending
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read loop state: {e}")

    # Check if currently running
    if task_id in _running_tasks:
        return {
            "task_id": task_id,
            "status": "RUNNING",
            "message": "Loop is currently executing in background",
            "pending_approvals": pending,
        }

    raise HTTPException(status_code=404, detail=f"Loop task '{task_id}' not found")


@router.get("/events/{task_id}")
async def stream_loop_events(task_id: str, since_sequence: int = 0) -> StreamingResponse:
    """Stream live loop events (turn thoughts, actions, receipts) as SSE."""
    return StreamingResponse(
        sse_stream(task_id, since_sequence=since_sequence),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/tasks")
async def list_loop_tasks() -> Dict[str, Any]:
    """List recent loop tasks persisted to disk."""
    engine = get_loop_engine()
    tasks: List[Dict[str, Any]] = []

    seen_ids = set()
    for task_id in list(_running_tasks.keys()):
        seen_ids.add(task_id)

    for f in engine.base_dir.glob("*_state.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            tid = d.get("task_id", f.stem.replace("_state", ""))
            seen_ids.add(tid)
            tasks.append({
                "task_id": tid,
                "goal_title": d.get("goal_title", ""),
                "status": d.get("status", "UNKNOWN"),
                "updated_at": d.get("updated_at", ""),
                "total_receipts": len(d.get("receipts", [])),
            })
        except Exception:
            continue

    return {"tasks": sorted(tasks, key=lambda x: x.get("updated_at", ""), reverse=True)}


@router.post("/stop/{task_id}")
async def stop_loop(task_id: str) -> Dict[str, Any]:
    """Cancel a running loop task."""
    task = _running_tasks.get(task_id)
    if not task:
        return {"ok": False, "message": f"Task '{task_id}' is not actively running"}

    task.cancel()
    _running_tasks.pop(task_id, None)
    return {"ok": True, "task_id": task_id, "status": "CANCELLED"}


@router.post("/pause/{task_id}")
async def pause_loop(task_id: str) -> Dict[str, Any]:
    """Pause a running loop task: stop executing further turns and persist a
    PAUSED ledger entry. Resuming means starting a new loop with the same goal."""
    task = _running_tasks.get(task_id)
    if not task:
        return {"ok": False, "message": f"Task '{task_id}' is not actively running"}

    _cancel_reasons[task_id] = "PAUSED"
    task.cancel()
    _running_tasks.pop(task_id, None)
    return {"ok": True, "task_id": task_id, "status": "PAUSED"}


def _validate_task_id(task_id: str) -> None:
    if not _TASK_ID_RE.fullmatch(task_id or ""):
        raise HTTPException(status_code=400, detail="Invalid task_id format")


@router.post("/resume/{task_id}")
async def resume_loop(task_id: str, payload: Optional[ResumeLoopPayload] = None) -> Dict[str, Any]:
    """Resume a paused or stopped loop task from its persisted spec ledger."""
    _validate_task_id(task_id)
    if task_id in _running_tasks:
        raise HTTPException(status_code=409, detail=f"Loop task '{task_id}' is already running")

    engine = get_loop_engine()
    spec_path = _spec_file(engine, task_id)
    state_path = engine.base_dir / f"{task_id}_state.json"

    req_human = False
    rev_diff = False
    if spec_path.is_file():
        raw_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        req_human = bool(raw_spec.pop("require_human_approval", False))
        rev_diff = bool(raw_spec.pop("review_diff", False))
        spec = LoopTaskSpec.model_validate(raw_spec)
    elif state_path.is_file():
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
        cmd = raw_state.get("verification_command") or []
        if not cmd:
            raise HTTPException(status_code=400, detail="Saved loop state missing verification_command; cannot resume")
        spec = LoopTaskSpec(
            task_id=task_id,
            goal_title=str(raw_state.get("goal_title") or "Resumed Task"),
            verification_command=list(cmd),
            workspace_dir=raw_state.get("workspace_dir"),
        )
    else:
        raise HTTPException(status_code=404, detail=f"Loop task '{task_id}' not found")

    if payload is not None:
        if payload.max_turns is not None:
            spec.max_turns = payload.max_turns
        if payload.require_human_approval is not None:
            req_human = payload.require_human_approval
        if payload.review_diff is not None:
            rev_diff = payload.review_diff

    return _launch_loop_task(
        engine,
        spec,
        require_human_approval=req_human,
        review_diff=rev_diff,
    )


@router.post("/{task_id}/approve")
async def approve_loop_action(task_id: str, payload: ApproveActionPayload) -> Dict[str, Any]:
    """Resolve a pending server-bound side-effect approval for a running loop task."""
    _validate_task_id(task_id)
    if not resolve_approval(task_id, payload.approval_id, payload.approved):
        raise HTTPException(
            status_code=409,
            detail=f"Run has no pending approval matching '{payload.approval_id}'",
        )
    await EVENT_BUS.publish(
        task_id,
        "approval_resolved",
        {"approval_id": payload.approval_id, "approved": payload.approved},
    )
    return {
        "ok": True,
        "task_id": task_id,
        "approval_id": payload.approval_id,
        "approved": payload.approved,
    }


@router.post("/{task_id}/attachments")
async def upload_loop_attachment(task_id: str, file: UploadFile = File(...)) -> Dict[str, Any]:
    """Stream an image, video, audio, or document attachment and extract derived MediaInsight."""
    _validate_task_id(task_id)
    engine = get_loop_engine()
    try:
        insight = await ingest_streamed_attachment(
            state_dir=engine.base_dir,
            task_id=task_id,
            upload_file=file,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    meta = insight.model_dump(exclude={"stored_path"})
    await EVENT_BUS.publish(task_id, "media_attached", meta)
    return {"ok": True, "task_id": task_id, "media": meta}


@router.get("/{task_id}/attachments")
async def list_loop_attachments(task_id: str) -> Dict[str, Any]:
    """List derived metadata for attachments registered on a loop task (never raw bytes)."""
    _validate_task_id(task_id)
    engine = get_loop_engine()
    items = load_media_insights(engine.base_dir, task_id)
    return {
        "task_id": task_id,
        "attachments": [m.model_dump(exclude={"stored_path"}) for m in items],
    }
