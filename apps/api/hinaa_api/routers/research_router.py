"""
HINAA OS — Grounded Research & Corrective RAG (CRAG) Router.
Phase 06: Multi-hop research coordination, claim-grounding, evaluation, and source attribution.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body, Request

router = APIRouter(tags=["Grounded Research & CRAG"])


@router.post("/api/research/query")
@router.post("/v1/research/query")
async def execute_grounded_research(request: Request, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Executes full CRAG research pipeline: multi-hop, deduplication, claim-grounding, and citations."""
    from ..research import GroundedResearchCoordinator
    query = str(body.get("query", ""))
    force = bool(body.get("forceResearch", False))
    user_id = body.get("userId")
    coordinator: GroundedResearchCoordinator = getattr(
        request.app.state, "research_coordinator", None
    )
    if coordinator is None:
        coordinator = GroundedResearchCoordinator()
    answer = await coordinator.execute_research(query, requesting_user_id=user_id, force_research=force)
    return answer.model_dump()


@router.post("/api/research/evaluate")
@router.post("/v1/research/evaluate")
async def evaluate_crag_retrieval(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Evaluates retrieval quality (CORRECT / INCORRECT / AMBIGUOUS) using the CRAG engine."""
    from ..research import CRAGEngine, Source
    query = str(body.get("query", ""))
    sources_raw = body.get("sources", [])
    sources = [Source.model_validate(s) for s in sources_raw]
    crag = CRAGEngine()
    verdict, score = crag.evaluate_retrieval(query, sources)
    return {
        "verdict": verdict.value,
        "confidenceScore": score,
        "sourcesCount": len(sources),
    }
