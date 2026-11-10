"""
HINAA OS — Agent Evaluations & Reasoning Benchmark Router.
Endpoints for inspecting benchmark scorecards and triggering eval runs on demand.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from fastapi import APIRouter, HTTPException

from ..evaluation.agent_eval_runner import AgentEvalRunner
from ..runtime_paths import project_root

router = APIRouter(prefix="/api/evals", tags=["Agent Evaluations & Benchmarks"])


@router.get("/latest")
async def get_latest_eval_scorecard() -> Dict[str, Any]:
    """Retrieves the most recent agent eval benchmark scorecard from disk."""
    scorecard_path = project_root() / ".runtime" / "evals" / "latest_scorecard.json"
    if not scorecard_path.exists():
        # If no scorecard yet, run the suite to produce the baseline
        runner = AgentEvalRunner()
        card = await runner.run_full_suite()
        from dataclasses import asdict
        return asdict(card)

    try:
        data = json.loads(scorecard_path.read_text(encoding="utf-8"))
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read eval scorecard: {e}")


@router.post("/run")
async def trigger_eval_run() -> Dict[str, Any]:
    """Runs the full agent eval benchmark battery and writes a new scorecard."""
    runner = AgentEvalRunner()
    card = await runner.run_full_suite()
    from dataclasses import asdict
    return asdict(card)
