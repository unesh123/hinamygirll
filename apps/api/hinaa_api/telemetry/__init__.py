"""HINAA OpenTelemetry-Compatible Tracing & Performance Metrics Engine."""

from .tracer import (
    Tracer,
    Span,
    get_tracer,
    generate_trace_id,
    generate_span_id,
    parse_traceparent,
    format_traceparent,
)
from .metrics import (
    TelemetryMetricsRegistry,
    get_metrics_registry,
    record_turn_metrics,
)

__all__ = [
    "Tracer",
    "Span",
    "get_tracer",
    "generate_trace_id",
    "generate_span_id",
    "parse_traceparent",
    "format_traceparent",
    "TelemetryMetricsRegistry",
    "get_metrics_registry",
    "record_turn_metrics",
]
