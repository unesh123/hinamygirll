"""
HINAA OS — Loop Engineering API Router (sorrycc 2026 Autonomous Paradigm).

Endpoints for starting, inspecting, and governing autonomous unattended goal/issue loops.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..harness.agent_step import build_llm_agent_step
from ..harness.loop_engine import LoopEngine, LoopTaskSpec, LoopExecutionReport, EvidenceReceipt
from ..harness.loop_events import EVENT_BUS, sse_stream
from ..runtime_paths import project_root

logger = logging.getLogger("hinaa.routers.loop")

router = APIRouter(prefix="/api/loop", tags=["Loop Engineering Harness"])
_loop_engine: Optional[LoopEngine] = None
_running_tasks: Dict[str, asyncio.Task] = {}
_task_reports: Dict[str, LoopExecutionReport] = {}
_cancel_reasons: Dict[str, str] = {}


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
    )

    # Real LLM-backed agent step when a provider is configured; otherwise an
    # honest no-op that reports the missing configuration instead of faking work.
    llm_step = build_llm_agent_step(spec)
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

    # Immediately seed state on disk so state exists synchronously
    engine._write_ledger_disk(spec, [], "RUNNING")

    bg_task = asyncio.create_task(_run_in_background())
    _running_tasks[task_id] = bg_task

    return {
        "ok": True,
        "task_id": task_id,
        "goal_title": spec.goal_title,
        "status": "RUNNING",
        "agent_mode": agent_mode,
        "state_file": str(engine.base_dir / f"{task_id}_state.json"),
    }


@router.get("/status/{task_id}")
async def get_loop_status(task_id: str) -> Dict[str, Any]:
    """Query current status and receipts of a loop task."""
    engine = get_loop_engine()

    # Check in-memory report first
    if task_id in _task_reports:
        return _task_reports[task_id].model_dump()

    # Check disk ledger
    state_file = engine.base_dir / f"{task_id}_state.json"
    if state_file.exists():
        try:
            data = json.loads(state_file.read_text(encoding="utf-8"))
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read loop state: {e}")

    # Check if currently running
    if task_id in _running_tasks:
        return {
            "task_id": task_id,
            "status": "RUNNING",
            "message": "Loop is currently executing in background",
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
