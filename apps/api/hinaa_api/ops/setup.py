"""Wiring helpers: CORS policy, optional OpenTelemetry and Sentry."""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

from fastapi import FastAPI

if TYPE_CHECKING:
    from ..config import Settings

logger = logging.getLogger(__name__)

# Previews of this project only (hinaa-workspace-<hash>-<team>.vercel.app).
DEFAULT_CORS_ORIGIN_REGEX = r"^https://hinaa-workspace(-[a-z0-9-]+)?\.vercel\.app$"

# Exactly the request headers the web client and trace propagation send.
CORS_ALLOW_HEADERS = [
    "Accept",
    "Authorization",
    "Content-Type",
    "X-Request-Id",
    "X-Correlation-ID",
    "X-Trace-Id",
    "traceparent",
    "tracestate",
    "X-HINAA-Dev-User",
    "X-HINAA-PC-Session",
    "X-HINAA-Alignment",
]


def cors_settings(settings: Settings) -> dict[str, object]:
    origins = list(dict.fromkeys([*settings.allowed_origins, *settings.cors_origins]))
    regex = settings.cors_origin_regex
    if regex is None:
        regex = DEFAULT_CORS_ORIGIN_REGEX
    return {
        "allow_origins": origins,
        "allow_origin_regex": regex or None,
        "allow_headers": CORS_ALLOW_HEADERS,
    }


def init_sentry(settings: Settings) -> bool:
    if settings.sentry_dsn is None:
        return False
    try:
        import sentry_sdk  # type: ignore[import-not-found]
    except ImportError:
        logger.warning("SENTRY_DSN is set but sentry-sdk is not installed; skipping Sentry")
        return False
    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        send_default_pii=False,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
    )
    return True


def init_otel(app: FastAPI, settings: Settings) -> bool:
    if not settings.otel_enabled:
        return False
    if not os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT"):
        logger.warning("HINAA_OTEL_ENABLED is true but OTEL_EXPORTER_OTLP_ENDPOINT is unset; skipping")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning("OpenTelemetry packages are not installed; skipping (see docs/operations.md)")
        return False
    provider = TracerProvider(
        resource=Resource.create({"service.name": os.environ.get("OTEL_SERVICE_NAME", "hinaa-api")})
    )
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app, excluded_urls="/metrics,/health.*,/readyz")
    HTTPXClientInstrumentor().instrument()
    return True
