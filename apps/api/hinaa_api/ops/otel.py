"""OpenTelemetry tracing: provider/exporter/instrumentors behind one switch.

Everything is a no-op until ``setup_tracing`` succeeds; call sites guard on
``tracing_enabled()`` so the disabled path costs one attribute read.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fastapi import FastAPI

    from ..config import Settings

logger = logging.getLogger(__name__)

INSTRUMENTATION_NAME = "hinaa_api"


@dataclass
class _State:
    enabled: bool = False
    capture_content: bool = False
    tracer: Any = None
    provider: Any = None
    undo: list[Any] = field(default_factory=list)


_state = _State()


def tracing_enabled() -> bool:
    return _state.enabled


def capture_content_enabled() -> bool:
    return _state.enabled and _state.capture_content


def get_tracer() -> Any:
    return _state.tracer


def current_ids() -> tuple[str, str] | None:
    """(trace_id, span_id) hex of the active valid span, else None."""
    if not _state.enabled:
        return None
    from opentelemetry import trace

    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


def _resource(settings: Settings) -> Any:
    from opentelemetry.sdk.resources import Resource

    from .. import __version__

    return Resource.create(
        {
            "service.name": os.environ.get("OTEL_SERVICE_NAME", "hinaa-api"),
            "service.version": __version__,
            "deployment.environment.name": settings.environment,
        }
    )


def setup_tracing(
    app: FastAPI,
    settings: Settings,
    *,
    session_factory: Any = None,
    span_exporter: Any = None,
) -> bool:
    """Enable tracing. ``span_exporter`` (tests) replaces the OTLP exporter."""
    if not settings.otel_enabled:
        return False
    if span_exporter is None and not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logger.warning("HINAA_OTEL_ENABLED is true but OTEL_EXPORTER_OTLP_ENDPOINT is unset; skipping")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning("OpenTelemetry packages are not installed; skipping (see docs/observability.md)")
        return False

    shutdown_tracing()
    provider = TracerProvider(
        resource=_resource(settings),
        sampler=ParentBased(TraceIdRatioBased(settings.otel_sampler_ratio)),
    )
    if span_exporter is not None:
        provider.add_span_processor(SimpleSpanProcessor(span_exporter))
    else:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
        trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/metrics,/health.*,/healthz,/readyz,/api/health",
    )
    httpx_instr = HTTPXClientInstrumentor()
    httpx_instr.instrument(tracer_provider=provider)
    _state.undo = [lambda: FastAPIInstrumentor.uninstrument_app(app), httpx_instr.uninstrument]

    engine = getattr(session_factory, "kw", {}).get("bind") if session_factory is not None else None
    if engine is not None:
        sa_instr = SQLAlchemyInstrumentor()
        sa_instr.instrument(engine=engine, tracer_provider=provider)
        _state.undo.append(sa_instr.uninstrument)

    _state.provider = provider
    _state.tracer = provider.get_tracer(INSTRUMENTATION_NAME)
    _state.capture_content = settings.otel_capture_content
    _state.enabled = True
    return True


def shutdown_tracing() -> None:
    """Undo instrumentation and flush; idempotent (also used between tests)."""
    undo, provider = _state.undo, _state.provider
    _state.enabled = False
    _state.capture_content = False
    _state.tracer = None
    _state.provider = None
    _state.undo = []
    for fn in undo:
        try:
            fn()
        except Exception:  # pragma: no cover - best-effort teardown
            logger.debug("otel uninstrument failed", exc_info=True)
    if provider is not None:
        try:
            provider.shutdown()
        except Exception:  # pragma: no cover
            logger.debug("otel provider shutdown failed", exc_info=True)
