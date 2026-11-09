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
from pydantic import BaseModel, Field

from ..harness.loop_engine import LoopEngine, LoopTaskSpec, LoopExecutionReport, EvidenceReceipt
from ..runtime_paths import project_root

logger = logging.getLogger("hinaa.routers.loop")

router = APIRouter(prefix="/api/loop", tags=["Loop Engineering Harness"])
_loop_engine: Optional[LoopEngine] = None
_running_tasks: Dict[str, asyncio.Task] = {}
_task_reports: Dict[str, LoopExecutionReport] = {}


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

    # Agent step simulator / runner using HINAA service if available
    service = getattr(request.app.state, "service", None)

    async def agent_step(turn: int, last_receipt: Optional[EvidenceReceipt]) -> str:
        prompt = f"Goal: {spec.goal_title}\nTurn: {turn}/{spec.max_turns}\n"
        if last_receipt and not last_receipt.passed:
            err = last_receipt.stderr_snippet or last_receipt.stdout_snippet or "Non-zero exit code"
            prompt += f"Verification failed with exit code {last_receipt.exit_code}:\n{err}\nPlease diagnose and repair."
        logger.info("Loop agent executing turn %d for %s", turn, task_id)
        # Give small async yield so background loop remains non-blocking
        await asyncio.sleep(0.1)
        return "Executed repair step."

    async def _run_in_background():
        try:
            report = await engine.run_loop(spec, agent_step)
            _task_reports[task_id] = report
        except Exception as e:
            logger.error("Error in background loop task %s: %s", task_id, e)
        finally:
            _running_tasks.pop(task_id, None)

    # Immediately seed state on disk so state exists synchronously
    engine._write_ledger_disk(spec, [], "RUNNING")

    bg_task = asyncio.create_task(_run_in_background())
    _running_tasks[task_id] = bg_task

    return {
        "ok": True,
        "task_id": task_id,
        "goal_title": spec.goal_title,
        "status": "RUNNING",
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
