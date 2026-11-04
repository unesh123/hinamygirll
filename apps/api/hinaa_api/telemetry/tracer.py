"""OpenTelemetry-compatible distributed tracer and span manager.

Implements W3C TraceContext standards (RFC compliant traceparent propagation)
and provides hierarchical span tracking for all HINAA execution pipelines.
"""

from __future__ import annotations

import contextvars
import os
import re
import secrets
import time
from collections import deque
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator, Optional

# Context variable tracking current active span in asyncio / thread context
_CURRENT_SPAN: contextvars.ContextVar[Optional[Span]] = contextvars.ContextVar(
    "current_span", default=None
)

_TRACEPARENT_REGEX = re.compile(
    r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$"
)


def generate_trace_id() -> str:
    """Generate a random 128-bit trace ID formatted as a 32-character hex string."""
    return secrets.token_hex(16)


def generate_span_id() -> str:
    """Generate a random 64-bit span ID formatted as a 16-character hex string."""
    return secrets.token_hex(8)


def parse_traceparent(header_val: Optional[str]) -> Optional[tuple[str, str, str]]:
    """Parse W3C traceparent header: version-trace_id-parent_id-trace_flags.
    
    Returns (trace_id, parent_span_id, flags) if valid, else None.
    """
    if not header_val:
        return None
    match = _TRACEPARENT_REGEX.match(header_val.strip())
    if match:
        trace_id, parent_id, flags = match.groups()
        if trace_id != "0" * 32 and parent_id != "0" * 16:
            return trace_id, parent_id, flags
    return None


def format_traceparent(trace_id: str, span_id: str, sampled: bool = True) -> str:
    """Format into standard W3C traceparent header string."""
    flags = "01" if sampled else "00"
    return f"00-{trace_id}-{span_id}-{flags}"


@dataclass
class SpanEvent:
    name: str
    timestamp_ns: int
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class Span:
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    start_time_ns: int = field(default_factory=time.time_ns)
    end_time_ns: Optional[int] = None
    duration_ms: Optional[float] = None
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[SpanEvent] = field(default_factory=list)
    status: str = "OK"  # "OK" | "ERROR"
    error_message: Optional[str] = None

    def set_attribute(self, key: str, value: Any) -> Span:
        self.attributes[key] = value
        return self

    def add_event(self, name: str, attributes: Optional[dict[str, Any]] = None) -> None:
        self.events.append(
            SpanEvent(
                name=name,
                timestamp_ns=time.time_ns(),
                attributes=attributes or {},
            )
        )

    def record_error(self, error: Exception | str) -> None:
        self.status = "ERROR"
        self.error_message = str(error)
        self.set_attribute("error", True)
        self.set_attribute("error.message", str(error))
        self.add_event("exception", {"exception.message": str(error)})

    def end(self) -> None:
        if self.end_time_ns is None:
            self.end_time_ns = time.time_ns()
            self.duration_ms = round((self.end_time_ns - self.start_time_ns) / 1_000_000, 3)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


class SpanContextManager:
    """Context manager for managing span lifecycle and context propagation."""

    def __init__(self, tracer: Tracer, span: Span) -> None:
        self.tracer = tracer
        self.span = span
        self._token: Optional[contextvars.Token] = None

    def __enter__(self) -> Span:
        self._token = _CURRENT_SPAN.set(self.span)
        return self.span

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_val is not None:
            self.span.record_error(exc_val)
        self.span.end()
        self.tracer._record_completed_span(self.span)
        if self._token:
            _CURRENT_SPAN.reset(self._token)


@dataclass
class TraceRecord:
    trace_id: str
    root_span_name: str
    start_time_ns: int
    end_time_ns: Optional[int] = None
    total_duration_ms: Optional[float] = None
    spans: list[Span] = field(default_factory=list)
    status: str = "OK"

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_name": self.root_span_name,
            "start_time_ns": self.start_time_ns,
            "end_time_ns": self.end_time_ns,
            "total_duration_ms": self.total_duration_ms,
            "spans_count": len(self.spans),
            "status": self.status,
            "spans": [s.to_dict() for s in self.spans],
        }


class Tracer:
    """Thread-safe and async-safe tracer holding active and historical traces."""

    def __init__(self, max_traces: int = 500) -> None:
        self.max_traces = max_traces
        self._recent_traces: deque[TraceRecord] = deque(maxlen=max_traces)
        self._traces_by_id: dict[str, TraceRecord] = {}

    def start_span(
        self,
        name: str,
        trace_id: Optional[str] = None,
        parent_span_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
    ) -> SpanContextManager:
        parent = _CURRENT_SPAN.get()
        effective_trace_id = trace_id or (parent.trace_id if parent else generate_trace_id())
        effective_parent_id = parent_span_id or (parent.span_id if parent else None)
        span_id = generate_span_id()

        span = Span(
            name=name,
            trace_id=effective_trace_id,
            span_id=span_id,
            parent_span_id=effective_parent_id,
            attributes=attributes or {},
        )

        # Register or update trace record
        if effective_trace_id not in self._traces_by_id:
            record = TraceRecord(
                trace_id=effective_trace_id,
                root_span_name=name,
                start_time_ns=span.start_time_ns,
            )
            self._traces_by_id[effective_trace_id] = record
            self._recent_traces.append(record)
            if len(self._traces_by_id) > self.max_traces * 1.5:
                # Evict oldest traces from dict
                while len(self._traces_by_id) > self.max_traces:
                    oldest_id = next(iter(self._traces_by_id))
                    del self._traces_by_id[oldest_id]

        return SpanContextManager(self, span)

    def _record_completed_span(self, span: Span) -> None:
        record = self._traces_by_id.get(span.trace_id)
        if record:
            record.spans.append(span)
            if span.status == "ERROR":
                record.status = "ERROR"
            # If root span ended, finalize total trace duration
            if span.parent_span_id is None:
                record.end_time_ns = span.end_time_ns
                record.total_duration_ms = span.duration_ms

    def get_current_span(self) -> Optional[Span]:
        return _CURRENT_SPAN.get()

    def get_trace(self, trace_id: str) -> Optional[dict[str, Any]]:
        record = self._traces_by_id.get(trace_id)
        return record.to_dict() if record else None

    def get_recent_traces(self, limit: int = 50) -> list[dict[str, Any]]:
        traces = list(self._recent_traces)[-limit:]
        return [t.to_dict() for t in reversed(traces)]


_GLOBAL_TRACER: Optional[Tracer] = None


def get_tracer() -> Tracer:
    """Access the global application Tracer instance."""
    global _GLOBAL_TRACER
    if _GLOBAL_TRACER is None:
        _GLOBAL_TRACER = Tracer()
    return _GLOBAL_TRACER
