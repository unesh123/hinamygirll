"""
HINAA OS — Reflective Voice & Metacognitive Explanation Endpoints
Exposes REST APIs for delivery mode routing, artifact understanding,
explanation planning, script composition, verification, speech turn coordination,
and topic ledger management.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .contracts import (
    ArtifactUnderstanding,
    DeliveryMode,
    ExplanationPlan,
    KeyClaim,
    SpokenSegment,
)
from .service import ExplanationService

logger = logging.getLogger("hinaa.explanation.endpoints")

router = APIRouter(prefix="/api/v1/explanation", tags=["explanation"])
_service = ExplanationService()


def get_explanation_service() -> ExplanationService:
    return _service


# ── Request / Response Schemas ──

class RouteRequest(BaseModel):
    user_text: str
    artifact_present: bool = False
    default_mode: str = "EXPLAIN_BRIEFLY"


class UnderstandRequest(BaseModel):
    artifact_id: str
    content: str
    content_type: str = "research_report"
    title: str = ""
    tenant_id: str = "default"
    access_scope: str = "tenant"
    version: int = 1
    code_receipts: Optional[Dict[str, Any]] = None
    media_receipts: Optional[Dict[str, Any]] = None


class PlanRequest(BaseModel):
    artifact_id: str
    conversation_id: str
    delivery_mode: str = "EXPLAIN_BRIEFLY"
    user_goal: str = ""
    audience_level: str = "general"
    language: str = "en"
    time_budget_seconds: float = 30.0
    target_section: Optional[str] = None
    tenant_id: str = "default"


class ComposeAndVerifyRequest(BaseModel):
    plan: Dict[str, Any]
    understanding: Dict[str, Any]


class SpeakRequest(BaseModel):
    conversation_id: str
    response_id: str
    script: str
    delivery_mode: str = "EXPLAIN_BRIEFLY"


class BargeInRequest(BaseModel):
    conversation_id: str
    reason: str = "user_speech_detected"


# ── API Routes ──

@router.post("/route")
async def route_intent(req: RouteRequest) -> JSONResponse:
    try:
        def_mode = DeliveryMode(req.default_mode)
    except ValueError:
        def_mode = DeliveryMode.EXPLAIN_BRIEFLY
    res = _service.route_request(req.user_text, artifact_present=req.artifact_present, default_mode=def_mode)
    return JSONResponse({
        "delivery_mode": res.delivery_mode.value,
        "language": res.language,
        "audience_level": res.audience_level,
        "confidence": res.confidence,
        "reason": res.reason,
        "target_section": res.target_section,
        "time_budget_seconds": res.time_budget_seconds,
    })


@router.post("/understand")
async def understand_artifact(req: UnderstandRequest) -> JSONResponse:
    understanding = _service.understand_artifact(
        artifact_id=req.artifact_id,
        content=req.content,
        content_type=req.content_type,
        title=req.title,
        tenant_id=req.tenant_id,
        access_scope=req.access_scope,
        version=req.version,
        code_receipts=req.code_receipts,
        media_receipts=req.media_receipts,
    )
    return JSONResponse(understanding.to_dict())


@router.post("/plan")
async def plan_explanation(req: PlanRequest) -> JSONResponse:
    cached = _service.analyzer.get_cached(req.artifact_id, tenant_id=req.tenant_id)
    if not cached:
        raise HTTPException(status_code=404, detail=f"Artifact {req.artifact_id} not found in understanding cache")

    try:
        mode = DeliveryMode(req.delivery_mode)
    except ValueError:
        mode = DeliveryMode.EXPLAIN_BRIEFLY

    plan = _service.plan_explanation(
        understanding=cached,
        delivery_mode=mode,
        conversation_id=req.conversation_id,
        user_goal=req.user_goal,
        audience_level=req.audience_level,
        language=req.language,
        time_budget_seconds=req.time_budget_seconds,
        target_section=req.target_section,
    )
    return JSONResponse(plan.to_dict())


@router.post("/compose")
async def compose_and_verify(req: ComposeAndVerifyRequest) -> JSONResponse:
    plan = ExplanationPlan.from_dict(req.plan)
    understanding = ArtifactUnderstanding.from_dict(req.understanding)

    script, verif = _service.compose_and_verify(plan, understanding)

    return JSONResponse({
        "script": script,
        "verification": {
            "passed": verif.passed,
            "grounded_score": verif.grounded_score,
            "novelty_score": verif.novelty_score,
            "three_gram_jaccard": verif.three_gram_jaccard,
            "covered_claim_ids": verif.covered_claim_ids,
            "missing_claim_ids": verif.missing_claim_ids,
            "injection_detected": verif.injection_detected,
            "invalidation_reason": verif.invalidation_reason,
            "perspectives": [{"sentence": s, "perspective": p.value} for s, p in verif.sentence_perspectives],
        }
    })


@router.post("/speak")
async def coordinate_speech(req: SpeakRequest) -> JSONResponse:
    try:
        mode = DeliveryMode(req.delivery_mode)
    except ValueError:
        mode = DeliveryMode.EXPLAIN_BRIEFLY

    segments = _service.coordinate_speech(
        conversation_id=req.conversation_id,
        response_id=req.response_id,
        script=req.script,
        delivery_mode=mode,
    )
    return JSONResponse({
        "conversation_id": req.conversation_id,
        "response_id": req.response_id,
        "segments": [s.to_dict() for s in segments],
        "total_segments": len(segments),
    })


@router.post("/barge-in")
async def handle_barge_in(req: BargeInRequest) -> JSONResponse:
    new_gen = _service.handle_barge_in(req.conversation_id, reason=req.reason)
    return JSONResponse({
        "conversation_id": req.conversation_id,
        "barge_in_executed": True,
        "new_generation_id": new_gen,
        "reason": req.reason,
    })


@router.get("/ledger/{conversation_id}")
async def get_ledger(conversation_id: str, artifact_id: str, tenant_id: str = "default") -> JSONResponse:
    claims = _service.ledger.get_explained_claim_ids(conversation_id, artifact_id, tenant_id=tenant_id)
    angles = _service.ledger.get_prior_angles(conversation_id, artifact_id, tenant_id=tenant_id)
    return JSONResponse({
        "conversation_id": conversation_id,
        "artifact_id": artifact_id,
        "tenant_id": tenant_id,
        "explained_claim_ids": claims,
        "prior_angles": angles,
    })


@router.delete("/artifacts/{artifact_id}")
async def delete_artifact(artifact_id: str, tenant_id: str = "default") -> JSONResponse:
    _service.invalidate_artifact(artifact_id, tenant_id=tenant_id)
    return JSONResponse({
        "artifact_id": artifact_id,
        "tenant_id": tenant_id,
        "invalidated": True,
    })


@router.get("/self-model")
async def get_self_model() -> JSONResponse:
    return JSONResponse(_service.get_self_model())


@router.get("/health")
async def get_health() -> JSONResponse:
    return JSONResponse({
        "status": "healthy",
        "subsystem": "reflective_voice_and_metacognitive_explanation",
        "version": "1.0.0",
    })
