"""ML AI Code (https://code.ml.ai) cloud coding automations connector.

Docs: https://code.ml.ai/docs/reference/api
Endpoints supported by the official API:
- GET /api/routines
- POST /api/routines/{id}/run (with optional Idempotency-Key & JSON input)
"""

from __future__ import annotations

import re
import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field

from ..config import Settings
from ..errors import safe_error_text
from .registry import RiskTier, ToolDefinition, ToolEffect, registry

_ROUTINE_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_IDEMPOTENCY_RE = re.compile(r"^[A-Za-z0-9.:_-]{1,100}$")
_MAX_INPUT_BYTES = 256 * 1024


class MlaiListRoutinesParams(BaseModel):
    pass


class MlaiRunRoutineParams(BaseModel):
    routine_id: str = Field(..., min_length=1, max_length=128, description="ID of an API-triggered ML AI Code routine.")
    input_text: str = Field("", max_length=256_000, description="Optional text/JSON payload passed to the routine.")
    idempotency_key: str = Field("", max_length=100, description="Optional Idempotency-Key (letters, numbers, . : _ -).")


async def mlai_list_routines_handler(_params: MlaiListRoutinesParams) -> dict[str, Any]:
    settings = Settings()
    key = settings.active_mlai_code_key
    base_url = settings.active_mlai_code_base_url
    if key is None or not base_url:
        return {
            "status": "error",
            "code": "MLAI_NOT_CONFIGURED",
            "error": "ML AI Code is not configured. Set MLAI_CODE_API_KEY in apps/api/.env.local.",
        }
    secret = key.get_secret_value()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{base_url}/api/routines",
                headers={"Authorization": f"Bearer {secret}", "Accept": "application/json"},
            )
    except Exception as exc:
        return {
            "status": "error",
            "code": "MLAI_UNREACHABLE",
            "error": f"Failed to reach ML AI Code API: {safe_error_text(exc, [secret])}",
        }

    if resp.status_code == 401:
        return {
            "status": "error",
            "code": "MLAI_UNAUTHORIZED",
            "error": "ML AI Code rejected the API key (HTTP 401).",
        }
    if resp.status_code >= 400:
        return {
            "status": "error",
            "code": "MLAI_API_ERROR",
            "httpStatus": resp.status_code,
            "error": safe_error_text(resp.text, [secret])[:300],
        }
    data = resp.json()
    routines = data.get("routines") or []
    return {
        "status": "success",
        "configured": bool(data.get("configured", True)),
        "count": len(routines),
        "routines": routines,
    }


async def mlai_run_routine_handler(params: MlaiRunRoutineParams) -> dict[str, Any]:
    settings = Settings()
    key = settings.active_mlai_code_key
    base_url = settings.active_mlai_code_base_url
    if key is None or not base_url:
        return {
            "status": "error",
            "code": "MLAI_NOT_CONFIGURED",
            "error": "ML AI Code is not configured. Set MLAI_CODE_API_KEY in apps/api/.env.local.",
        }

    rid = params.routine_id.strip()
    if not _ROUTINE_ID_RE.match(rid):
        return {"status": "error", "code": "INVALID_ROUTINE_ID", "error": "Invalid ML AI Code routine_id format."}

    idem = (params.idempotency_key or "").strip() or f"hinaa-{uuid.uuid4().hex[:16]}"
    if not _IDEMPOTENCY_RE.match(idem):
        return {
            "status": "error",
            "code": "INVALID_IDEMPOTENCY_KEY",
            "error": "Idempotency-Key must match ^[A-Za-z0-9.:_-]{1,100}$.",
        }

    if len(params.input_text.encode("utf-8")) > _MAX_INPUT_BYTES:
        return {"status": "error", "code": "INPUT_TOO_LARGE", "error": "Input payload exceeds 256 KB limit."}

    secret = key.get_secret_value()
    body = {"input": params.input_text} if params.input_text else {}
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base_url}/api/routines/{rid}/run",
                headers={
                    "Authorization": f"Bearer {secret}",
                    "Idempotency-Key": idem,
                    "Content-Type": "application/json",
                },
                json=body,
            )
    except Exception as exc:
        return {
            "status": "error",
            "code": "MLAI_UNREACHABLE",
            "error": f"Failed to reach ML AI Code API: {safe_error_text(exc, [secret])}",
        }

    raw_text = safe_error_text(resp.text, [secret])[:300]
    try:
        payload = resp.json() if resp.content else {}
    except Exception:
        payload = {}

    if resp.status_code in (200, 202):
        return {
            "status": "success",
            "httpStatus": resp.status_code,
            "runStatus": payload.get("status", "started" if resp.status_code == 202 else "duplicate"),
            "idempotencyKey": idem,
            "result": payload,
        }

    code_map = {
        401: "MLAI_UNAUTHORIZED",
        402: "MLAI_BLOCKED",
        404: "MLAI_ROUTINE_NOT_FOUND",
        409: "MLAI_ROUTINE_DISABLED",
        429: "MLAI_RATE_LIMITED",
    }
    return {
        "status": "error",
        "code": code_map.get(resp.status_code, "MLAI_API_ERROR"),
        "httpStatus": resp.status_code,
        "error": payload.get("reason") or payload.get("error") or raw_text or f"HTTP {resp.status_code}",
    }


registry.register(
    ToolDefinition(
        name="mlai_list_routines",
        display_name="ML AI Code: List Routines",
        description="List API-triggered cloud coding routines configured in ML AI Code (https://code.ml.ai).",
        parameters={},
        required_parameters=[],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    mlai_list_routines_handler,
)

registry.register(
    ToolDefinition(
        name="mlai_run_routine",
        display_name="ML AI Code: Run Routine",
        description="Trigger an ML AI Code API routine by ID with optional input and Idempotency-Key. Requires confirmation.",
        parameters={
            "routine_id": {"type": "string", "description": "Routine ID from mlai_list_routines."},
            "input_text": {"type": "string", "description": "Optional prompt/event string (up to 256 KB)."},
            "idempotency_key": {"type": "string", "description": "Optional dedupe key matching ^[A-Za-z0-9.:_-]{1,100}$."},
        },
        required_parameters=["routine_id"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=True,
        risk_tier=RiskTier.TIER_4_DESTRUCTIVE,
        risk_level="high",
        effect=ToolEffect.EXTERNAL_NETWORK,
    ),
    mlai_run_routine_handler,
)
