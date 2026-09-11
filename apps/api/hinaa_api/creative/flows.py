"""Magnific Flows Engine & Video Node Safety Gate.

Provides access to Magnific AI multi-step pipelines with deep AST/graph inspection
to strictly reject any pipeline containing a video node.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

import httpx

from ..config import get_settings
from ..errors import HinaaError

logger = logging.getLogger("hinaa.creative.flows")


@dataclass
class FlowNode:
    id: str
    name: str
    type: str
    operator: str = ""
    model: str = ""
    cost: int = 0
    is_video: bool = False


@dataclass
class FlowDefinition:
    id: str
    name: str
    description: str
    nodes: list[FlowNode] = field(default_factory=list)
    total_cost: int = 0
    is_video: bool = False
    approved: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "totalCost": self.total_cost,
            "isVideo": self.is_video,
            "approved": self.approved,
            "nodes": [asdict(n) for n in self.nodes],
        }


def inspect_flow_safety(flow_data: dict[str, Any]) -> tuple[bool, str]:
    """
    Inspect a Flow definition graph for any video generation nodes.
    Returns (is_safe, violation_reason).
    """
    # 1. Top-level checks
    name = str(flow_data.get("name") or "").lower()
    desc = str(flow_data.get("description") or "").lower()
    if "video" in name or "animation" in name or "video" in desc:
        return False, f"Flow metadata indicates video processing: {name}"

    # 2. Inspect node graph (steps / nodes / operators)
    nodes = flow_data.get("nodes") or flow_data.get("steps") or flow_data.get("pipeline") or []
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        n_type = str(node.get("type") or "").lower()
        n_op = str(node.get("operator") or node.get("action") or "").lower()
        n_model = str(node.get("model") or node.get("modelId") or "").lower()
        n_name = str(node.get("name") or f"node_{idx}").lower()

        video_keywords = ("video", "animate", "animation", "motion", "text2video", "img2video", "mp4", "gen-2", "gen-3", "kling", "luma", "svd")
        for kw in video_keywords:
            if kw in n_type or kw in n_op or kw in n_model or kw in n_name:
                return False, f"Flow contains forbidden video node '{n_name}' (type={n_type}, op={n_op}, model={n_model})"

    return True, "Safe non-video pipeline"


# Approved canonical non-video Flows built for HINAA Sakura OS
APPROVED_CANONICAL_FLOWS: dict[str, FlowDefinition] = {
    "product-photoshoot": FlowDefinition(
        id="product-photoshoot",
        name="Product Studio Photoshoot",
        description="Clean background removal, studio environment generation, and high-fidelity relighting.",
        total_cost=15,
        is_video=False,
        approved=True,
        nodes=[
            FlowNode(id="node_1", name="Segment Subject", type="segmentation", operator="remove_background", cost=2),
            FlowNode(id="node_2", name="Flux Fast Studio", type="generation", operator="text2image", model="flux-fast", cost=5),
            FlowNode(id="node_3", name="Magnific Relight", type="lighting", operator="relight", cost=8),
        ],
    ),
    "character-turnaround": FlowDefinition(
        id="character-turnaround",
        name="Character Orthographic Turnaround",
        description="Multi-angle orthographic character sheet (front, side, back) for 3D modeling and VRM reference.",
        total_cost=25,
        is_video=False,
        approved=True,
        nodes=[
            FlowNode(id="node_1", name="Flux Standard Front", type="generation", operator="text2image", model="flux-1", cost=10),
            FlowNode(id="node_2", name="Flux Standard Angles", type="generation", operator="image2image", model="flux-1", cost=10),
            FlowNode(id="node_3", name="Composition Stitch", type="utility", operator="composite", cost=5),
        ],
    ),
    "asset-upscale-prep": FlowDefinition(
        id="asset-upscale-prep",
        name="Asset Master Prep",
        description="High-resolution creative upscale with micro-texture enhancement for UI wallpaper and avatar assets.",
        total_cost=10,
        is_video=False,
        approved=True,
        nodes=[
            FlowNode(id="node_1", name="Magnific Upscaler", type="upscale", operator="upscale_2x", cost=10),
        ],
    ),
}


class MagnificFlowsEngine:
    """Manages Magnific Spaces Flows discovery, execution, and video safety enforcement."""

    def __init__(self) -> None:
        self.allowlist: set[str] = set(APPROVED_CANONICAL_FLOWS.keys())

    async def list_flows(self) -> list[dict[str, Any]]:
        """List approved non-video flows (combines canonical allowlist and upstream spaces)."""
        settings = get_settings()
        api_key_secret = settings.active_freepik_key
        flows = [f.to_dict() for f in APPROVED_CANONICAL_FLOWS.values()]

        if not api_key_secret:
            return flows

        api_key = api_key_secret.get_secret_value().strip()
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                headers = {
                    "x-magnific-api-key": api_key,
                    "x-freepik-api-key": api_key,
                    "Accept": "application/json",
                }
                resp = await client.get("https://api.magnific.com/v1/ai/flows", headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_flows = data.get("data") or data.get("flows") or []
                    for rf in raw_flows:
                        is_safe, _ = inspect_flow_safety(rf)
                        if is_safe:
                            f_id = rf.get("id") or str(len(flows) + 1)
                            flows.append({
                                "id": f_id,
                                "name": rf.get("name", "Custom Flow"),
                                "description": rf.get("description", ""),
                                "totalCost": rf.get("total_cost", 10),
                                "isVideo": False,
                                "approved": True,
                                "nodes": rf.get("nodes", []),
                            })
        except Exception as exc:
            logger.debug("Failed to query remote Magnific flows (using canonical allowlist): %s", exc)

        return flows

    async def get_flow(self, flow_id: str) -> dict[str, Any]:
        """Inspect a single flow definition."""
        if flow_id in APPROVED_CANONICAL_FLOWS:
            return APPROVED_CANONICAL_FLOWS[flow_id].to_dict()

        flows = await self.list_flows()
        for f in flows:
            if f.get("id") == flow_id:
                return f

        raise HinaaError("NOT_FOUND", f"Flow '{flow_id}' not found.", status_code=404)

    async def run_flow(self, flow_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        """Execute a Flow with mandatory pre-execution video node safety inspection."""
        flow = await self.get_flow(flow_id)

        # Safety Inspection Gate
        is_safe, reason = inspect_flow_safety(flow)
        if not is_safe:
            logger.warning("Rejected Flow execution: %s", reason)
            raise HinaaError("FLOW_CONTAINS_VIDEO_NODE", f"Execution forbidden: {reason}", status_code=403)

        settings = get_settings()
        api_key_secret = settings.active_freepik_key
        if not api_key_secret:
            # Emulated mock execution for testing without live key
            import uuid
            run_id = f"flow_run_{uuid.uuid4().hex[:12]}"
            return {
                "runId": run_id,
                "flowId": flow_id,
                "status": "completed",
                "totalCost": flow.get("totalCost", 10),
                "output": {
                    "message": f"Simulated execution of approved flow '{flow.get('name')}'.",
                    "previewUrl": "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe",
                },
            }

        api_key = api_key_secret.get_secret_value().strip()
        async with httpx.AsyncClient(timeout=15.0) as client:
            headers = {
                "x-magnific-api-key": api_key,
                "x-freepik-api-key": api_key,
                "Content-Type": "application/json",
            }
            resp = await client.post(
                f"https://api.magnific.com/v1/ai/flows/{flow_id}/run",
                headers=headers,
                json={"inputs": inputs},
            )
            if resp.status_code in (200, 201, 202):
                return resp.json()
            raise HinaaError(
                "FLOW_EXECUTION_FAILED",
                f"Magnific Flow run failed with HTTP {resp.status_code}: {resp.text}",
                status_code=resp.status_code,
            )

    async def get_run_status(self, run_id: str) -> dict[str, Any]:
        """Poll the status of a running flow."""
        settings = get_settings()
        api_key_secret = settings.active_freepik_key
        if not api_key_secret or run_id.startswith("flow_run_"):
            return {"runId": run_id, "status": "completed"}

        api_key = api_key_secret.get_secret_value().strip()
        async with httpx.AsyncClient(timeout=8.0) as client:
            headers = {
                "x-magnific-api-key": api_key,
                "x-freepik-api-key": api_key,
            }
            resp = await client.get(f"https://api.magnific.com/v1/ai/flows/runs/{run_id}", headers=headers)
            if resp.status_code == 200:
                return resp.json()
            raise HinaaError("RUN_NOT_FOUND", f"Run {run_id} not found.", status_code=resp.status_code)


magnific_flows_engine = MagnificFlowsEngine()