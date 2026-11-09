"""
HINAA OS — Telemetry & Observability Router.
Metrics percentiles (P50/P90/P95/P99) and OpenTelemetry trace waterfalls.
"""

from __future__ import annotations

from typing import Any, List, Dict
from fastapi import APIRouter
from ..errors import HinaaError

router = APIRouter(tags=["Telemetry & Observability"])


@router.get("/api/telemetry/metrics")
@router.get("/v1/telemetry/metrics")
async def get_telemetry_metrics() -> Dict[str, Any]:
    """Live P50, P90, P95, and P99 latency percentiles and system resource metrics."""
    from ..telemetry import get_metrics_registry
    return get_metrics_registry().get_metrics_report()


@router.get("/api/telemetry/traces")
@router.get("/v1/telemetry/traces")
async def get_recent_traces(limit: int = 50) -> List[Dict[str, Any]]:
    """Recent OpenTelemetry trace waterfalls and span trees."""
    from ..telemetry import get_tracer
    return get_tracer().get_recent_traces(limit=min(limit, 200))


@router.get("/api/telemetry/traces/{trace_id}")
@router.get("/v1/telemetry/traces/{trace_id}")
async def get_trace_detail(trace_id: str) -> Dict[str, Any]:
    """Detailed OpenTelemetry trace waterfall for a specific trace ID."""
    from ..telemetry import get_tracer
    trace = get_tracer().get_trace(trace_id)
    if not trace:
        raise HinaaError("TRACE_NOT_FOUND", f"Trace {trace_id} was not found or expired.", 404)
    return trace
