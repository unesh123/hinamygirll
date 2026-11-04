"""Performance metrics aggregation engine with exact percentile calculations.

Calculates P50, P90, P95, and P99 latencies across all critical execution paths:
- TTFT (Time To First Token)
- Model Inference Latency
- Application Overhead (Prompt assembly, RAG, filters)
- Tool Execution Latency
- Voice Synthesis (TTS) Latency
- Total Turn End-to-End Latency
"""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Optional

try:
    import psutil
except ImportError:  # pragma: no cover
    psutil = None


def compute_percentiles(values: list[float]) -> dict[str, float]:
    """Compute exact P50, P90, P95, and P99 percentiles from a numeric sample."""
    if not values:
        return {"p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0, "min": 0.0, "max": 0.0, "avg": 0.0}

    sorted_vals = sorted(values)
    n = len(sorted_vals)

    def _get_p(p: float) -> float:
        idx = (p / 100.0) * (n - 1)
        lower = math.floor(idx)
        upper = math.ceil(idx)
        if lower == upper:
            return round(sorted_vals[int(lower)], 2)
        weight = idx - lower
        val = (1.0 - weight) * sorted_vals[int(lower)] + weight * sorted_vals[int(upper)]
        return round(val, 2)

    return {
        "p50": _get_p(50),
        "p90": _get_p(90),
        "p95": _get_p(95),
        "p99": _get_p(99),
        "min": round(sorted_vals[0], 2),
        "max": round(sorted_vals[-1], 2),
        "avg": round(sum(sorted_vals) / n, 2),
    }


@dataclass
class TurnMetricSample:
    trace_id: str
    provider_id: str
    model: str
    ttft_ms: float
    model_latency_ms: float
    app_overhead_ms: float
    rag_latency_ms: float = 0.0
    tool_latency_ms: float = 0.0
    tts_latency_ms: float = 0.0
    total_turn_ms: float = 0.0
    success: bool = True
    error_type: Optional[str] = None
    chars_generated: int = 0
    timestamp: float = field(default_factory=time.time)


class TelemetryMetricsRegistry:
    """Thread-safe telemetry aggregator tracking rolling performance metrics."""

    def __init__(self, window_size: int = 1000) -> None:
        self.window_size = window_size
        self._lock = threading.Lock()
        self._samples: deque[TurnMetricSample] = deque(maxlen=window_size)
        self._total_turns = 0
        self._error_turns = 0
        self._provider_stats: dict[str, dict[str, Any]] = {}
        self._tool_latencies: dict[str, deque[float]] = {}
        self._start_time = time.time()

    def record_turn(self, sample: TurnMetricSample) -> None:
        with self._lock:
            self._samples.append(sample)
            self._total_turns += 1
            if not sample.success:
                self._error_turns += 1

            prov = sample.provider_id
            if prov not in self._provider_stats:
                self._provider_stats[prov] = {
                    "total_turns": 0,
                    "errors": 0,
                    "ttft_sum_ms": 0.0,
                    "model_latency_sum_ms": 0.0,
                    "chars_generated": 0,
                }
            st = self._provider_stats[prov]
            st["total_turns"] += 1
            if not sample.success:
                st["errors"] += 1
            st["ttft_sum_ms"] += sample.ttft_ms
            st["model_latency_sum_ms"] += sample.model_latency_ms
            st["chars_generated"] += sample.chars_generated

    def record_tool_execution(self, tool_name: str, duration_ms: float) -> None:
        with self._lock:
            if tool_name not in self._tool_latencies:
                self._tool_latencies[tool_name] = deque(maxlen=200)
            self._tool_latencies[tool_name].append(duration_ms)

    def get_system_resources(self) -> dict[str, Any]:
        """Fetch current hardware and OS metrics via psutil."""
        if not psutil:
            return {"error": "psutil_not_installed"}
        try:
            vm = psutil.virtual_memory()
            return {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_total_mb": round(vm.total / (1024 * 1024), 1),
                "memory_used_mb": round(vm.used / (1024 * 1024), 1),
                "memory_available_mb": round(vm.available / (1024 * 1024), 1),
                "memory_percent": vm.percent,
                "active_threads": threading.active_count(),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_metrics_report(self) -> dict[str, Any]:
        """Generate complete P50, P90, P95, P99 performance observability report."""
        with self._lock:
            samples_list = list(self._samples)
            total = self._total_turns
            errors = self._error_turns

            ttft_vals = [s.ttft_ms for s in samples_list if s.ttft_ms > 0]
            model_vals = [s.model_latency_ms for s in samples_list if s.model_latency_ms > 0]
            overhead_vals = [s.app_overhead_ms for s in samples_list if s.app_overhead_ms >= 0]
            rag_vals = [s.rag_latency_ms for s in samples_list if s.rag_latency_ms > 0]
            tool_vals = [s.tool_latency_ms for s in samples_list if s.tool_latency_ms > 0]
            tts_vals = [s.tts_latency_ms for s in samples_list if s.tts_latency_ms > 0]
            total_turn_vals = [s.total_turn_ms for s in samples_list if s.total_turn_ms > 0]

            tool_breakdown = {}
            for t_name, d_list in self._tool_latencies.items():
                if d_list:
                    tool_breakdown[t_name] = compute_percentiles(list(d_list))

            prov_summary = {}
            for prov_name, st in self._provider_stats.items():
                cnt = st["total_turns"]
                prov_summary[prov_name] = {
                    "total_turns": cnt,
                    "error_count": st["errors"],
                    "error_rate_pct": round((st["errors"] / cnt) * 100, 2) if cnt > 0 else 0.0,
                    "avg_ttft_ms": round(st["ttft_sum_ms"] / cnt, 2) if cnt > 0 else 0.0,
                    "avg_model_latency_ms": round(st["model_latency_sum_ms"] / cnt, 2) if cnt > 0 else 0.0,
                    "chars_generated": st["chars_generated"],
                }

        uptime_sec = time.time() - self._start_time
        throughput_turns_per_min = round((total / (uptime_sec / 60.0)), 2) if uptime_sec > 0 else 0.0
        error_rate_pct = round((errors / total) * 100, 2) if total > 0 else 0.0

        return {
            "timestamp": time.time(),
            "uptime_seconds": round(uptime_sec, 1),
            "window_size": len(samples_list),
            "total_turns_observed": total,
            "error_turns_count": errors,
            "overall_error_rate_pct": error_rate_pct,
            "throughput_turns_per_minute": throughput_turns_per_min,
            "latencies_ms": {
                "ttft": compute_percentiles(ttft_vals),
                "model_inference": compute_percentiles(model_vals),
                "app_overhead": compute_percentiles(overhead_vals),
                "rag_retrieval": compute_percentiles(rag_vals),
                "tool_execution": compute_percentiles(tool_vals),
                "voice_tts": compute_percentiles(tts_vals),
                "total_turn": compute_percentiles(total_turn_vals),
            },
            "tools_breakdown": tool_breakdown,
            "providers_breakdown": prov_summary,
            "system_resources": self.get_system_resources(),
        }


_GLOBAL_METRICS: Optional[TelemetryMetricsRegistry] = None


def get_metrics_registry() -> TelemetryMetricsRegistry:
    """Access the global TelemetryMetricsRegistry singleton."""
    global _GLOBAL_METRICS
    if _GLOBAL_METRICS is None:
        _GLOBAL_METRICS = TelemetryMetricsRegistry()
    return _GLOBAL_METRICS


def record_turn_metrics(
    trace_id: str,
    provider_id: str,
    model: str,
    ttft_ms: float,
    model_latency_ms: float,
    total_turn_ms: float,
    *,
    rag_latency_ms: float = 0.0,
    tool_latency_ms: float = 0.0,
    tts_latency_ms: float = 0.0,
    chars_generated: int = 0,
    success: bool = True,
    error_type: Optional[str] = None,
) -> None:
    """Convenience helper to record a turn metric into the global registry."""
    app_overhead_ms = max(0.0, total_turn_ms - model_latency_ms)
    sample = TurnMetricSample(
        trace_id=trace_id,
        provider_id=provider_id,
        model=model,
        ttft_ms=ttft_ms,
        model_latency_ms=model_latency_ms,
        app_overhead_ms=app_overhead_ms,
        rag_latency_ms=rag_latency_ms,
        tool_latency_ms=tool_latency_ms,
        tts_latency_ms=tts_latency_ms,
        total_turn_ms=total_turn_ms,
        chars_generated=chars_generated,
        success=success,
        error_type=error_type,
    )
    get_metrics_registry().record_turn(sample)
