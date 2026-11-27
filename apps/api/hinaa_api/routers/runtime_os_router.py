"""Runtime OS Contract endpoints (tool manifest, 12-state connector health, preview tracking, ToolResultEnvelope runner)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..runtime.os_contract import (
    ALLOWED_CAPABILITY_STATES,
    PREVIEW_STAGES,
    CapabilityState,
    _ConnectorNameParam,
    connector_healthcheck_handler,
    connector_status_handler,
    connector_test_handler,
    list_previews_snapshot,
    make_tool_envelope,
    register_runtime_os_tools,
)
from ..tools.registry import RiskTier, registry

router = APIRouter()
register_runtime_os_tools()


class ToolEnvelopeInvokeBody(BaseModel):
    parameters: dict[str, Any] = Field(default_factory=dict)


@router.get("/v1/runtime/tools-manifest")
@router.get("/api/v1/runtime/tools-manifest")
async def runtime_tools_manifest() -> dict[str, Any]:
    register_runtime_os_tools()
    tools = registry.get_all_tools()
    audit = registry.audit_registry()
    return {
        "status": "success",
        "capabilityStates": list(ALLOWED_CAPABILITY_STATES),
        "previewStages": list(PREVIEW_STAGES),
        "totalTools": len(tools),
        "audit": audit,
        "tools": [
            {
                "name": t.name,
                "displayName": t.display_name,
                "description": t.description,
                "riskTier": int(t.risk_tier),
                "effect": str(t.tool_effect.value),
                "readOnly": t.is_read_only,
                "requiresConfirmation": t.requires_confirmation,
                "parameters": t.parameters,
                "requiredParameters": t.required_parameters,
            }
            for t in tools
        ],
    }


@router.get("/v1/connectors/health")
@router.get("/api/v1/connectors/health")
async def connectors_health(live: bool = False) -> dict[str, Any]:
    return await connector_healthcheck_handler(_ConnectorNameParam(live_probe=live))


@router.get("/v1/connectors/{connector_id}")
@router.get("/api/v1/connectors/{connector_id}")
async def connector_single_status(connector_id: str) -> dict[str, Any]:
    res = await connector_status_handler(_ConnectorNameParam(name=connector_id))
    if res.get("status") != "success":
        raise HTTPException(status_code=404, detail=res.get("error", "Connector not found"))
    return res


@router.post("/v1/connectors/{connector_id}/test")
@router.post("/api/v1/connectors/{connector_id}/test")
async def connector_single_test(connector_id: str) -> dict[str, Any]:
    res = await connector_test_handler(_ConnectorNameParam(name=connector_id))
    return make_tool_envelope(
        f"connector_test:{connector_id}",
        res,
        reversible=True,
        verification_state=res.get("state", CapabilityState.NOT_VERIFIED.value),
    ).model_dump()


@router.get("/v1/runtime/previews")
@router.get("/api/v1/runtime/previews")
async def runtime_previews() -> dict[str, Any]:
    return {
        "status": "success",
        "stages": list(PREVIEW_STAGES),
        "previews": list_previews_snapshot(),
    }


@router.post("/v1/runtime/tools/{tool_name}/envelope")
@router.post("/api/v1/runtime/tools/{tool_name}/envelope")
async def invoke_readonly_tool_envelope(tool_name: str, body: ToolEnvelopeInvokeBody) -> dict[str, Any]:
    register_runtime_os_tools()
    tdef = registry.get(tool_name)
    handler = registry.get_handler(tool_name) if hasattr(registry, "get_handler") else None
    if tdef is None:
        raise HTTPException(status_code=404, detail=f"Unknown tool '{tool_name}'")
    if not tdef.is_read_only or tdef.risk_tier >= RiskTier.TIER_2_WORKSPACE_WRITE:
        raise HTTPException(status_code=403, detail=f"Tool '{tool_name}' requires approved execution pipeline")
    if handler is None:
        raise HTTPException(status_code=500, detail=f"Handler missing for '{tool_name}'")
    raw = await handler(body.parameters)
    return make_tool_envelope(tool_name, raw, reversible=True, verification_state=CapabilityState.TESTED).model_dump()
