"""Unit tests for HINAA OpenTelemetry tracer and performance metrics engine."""

import pytest
import time
from hinaa_api.telemetry.tracer import (
    Tracer,
    generate_trace_id,
    generate_span_id,
    parse_traceparent,
    format_traceparent,
    get_tracer,
)
from hinaa_api.telemetry.metrics import (
    compute_percentiles,
    TelemetryMetricsRegistry,
    TurnMetricSample,
    record_turn_metrics,
    get_metrics_registry,
)


def test_w3c_traceparent_parsing_and_formatting():
    trace_id = generate_trace_id()
    span_id = generate_span_id()
    assert len(trace_id) == 32
    assert len(span_id) == 16

    header = format_traceparent(trace_id, span_id, sampled=True)
    assert header.startswith("00-")
    assert header.endswith("-01")

    parsed = parse_traceparent(header)
    assert parsed is not None
    p_trace, p_span, p_flags = parsed
    assert p_trace == trace_id
    assert p_span == span_id
    assert p_flags == "01"

    # Invalid header handling
    assert parse_traceparent("invalid-header") is None
    assert parse_traceparent("") is None
    assert parse_traceparent("00-00000000000000000000000000000000-0000000000000000-01") is None


def test_tracer_spans_lifecycle():
    tracer = Tracer(max_traces=50)
    trace_id = generate_trace_id()

    with tracer.start_span("root.operation", trace_id=trace_id) as root:
        root.set_attribute("user.id", "test-user")
        assert tracer.get_current_span() is root

        with tracer.start_span("child.inference") as child:
            child.set_attribute("model", "qwen3.8-max")
            child.add_event("token_stream_started")
            assert child.parent_span_id == root.span_id
            time.sleep(0.01)

    trace = tracer.get_trace(trace_id)
    assert trace is not None
    assert trace["trace_id"] == trace_id
    assert trace["root_span_name"] == "root.operation"
    assert trace["status"] == "OK"
    assert trace["total_duration_ms"] is not None
    assert trace["total_duration_ms"] > 0
    assert len(trace["spans"]) == 2


def test_tracer_error_capture():
    tracer = Tracer()
    trace_id = generate_trace_id()

    try:
        with tracer.start_span("failing.operation", trace_id=trace_id) as span:
            span.set_attribute("provider", "mock")
            raise ValueError("Upstream gateway error")
    except ValueError:
        pass

    trace = tracer.get_trace(trace_id)
    assert trace is not None
    assert trace["status"] == "ERROR"
    assert len(trace["spans"]) == 1
    span_data = trace["spans"][0]
    assert span_data["status"] == "ERROR"
    assert "Upstream gateway error" in span_data["error_message"]


def test_percentile_calculations():
    # Empty set
    p_empty = compute_percentiles([])
    assert p_empty["p50"] == 0.0

    # Single value
    p_single = compute_percentiles([100.0])
    assert p_single["p50"] == 100.0
    assert p_single["p99"] == 100.0

    # 1 to 100 range
    data = list(range(1, 101))
    p = compute_percentiles(data)
    assert 50.0 <= p["p50"] <= 51.0
    assert 90.0 <= p["p90"] <= 91.0
    assert 95.0 <= p["p95"] <= 96.0
    assert 99.0 <= p["p99"] <= 100.0
    assert p["min"] == 1.0
    assert p["max"] == 100.0


def test_metrics_registry():
    registry = TelemetryMetricsRegistry(window_size=50)

    # Record 10 turns
    for i in range(10):
        registry.record_turn(
            TurnMetricSample(
                trace_id=f"trace-{i}",
                provider_id="xkiro",
                model="qwen3.8-max",
                ttft_ms=100.0 + i * 10,
                model_latency_ms=500.0 + i * 20,
                app_overhead_ms=50.0,
                total_turn_ms=550.0 + i * 20,
                success=True if i != 9 else False,
            )
        )

    registry.record_tool_execution("adb_shell", 120.0)
    registry.record_tool_execution("adb_shell", 140.0)

    report = registry.get_metrics_report()
    assert report["total_turns_observed"] == 10
    assert report["error_turns_count"] == 1
    assert report["overall_error_rate_pct"] == 10.0
    assert "ttft" in report["latencies_ms"]
    assert report["latencies_ms"]["ttft"]["p50"] > 0
    assert "xkiro" in report["providers_breakdown"]
    assert report["providers_breakdown"]["xkiro"]["total_turns"] == 10
    assert "adb_shell" in report["tools_breakdown"]
    assert "system_resources" in report
