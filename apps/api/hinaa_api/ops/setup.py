"""Wiring helpers: CORS policy, optional OpenTelemetry and Sentry."""
from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING, Any

from fastapi import FastAPI

from .context import request_id_var, trace_id_var
from .otel import current_ids, setup_tracing

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
    from .. import __version__

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.environment,
        release=f"hinaa-api@{__version__}",
        send_default_pii=False,
        include_local_variables=False,
        max_request_body_size="never",
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0")),
        before_send=scrub_sentry_event,
        before_send_transaction=scrub_sentry_event,
        before_breadcrumb=scrub_breadcrumb,
    )
    return True


_SENSITIVE_KEY = re.compile(
    r"authorization|cookie|api[-_]?key|x-api-key|token|secret|password|passwd|credential|session|dsn|signature",
    re.IGNORECASE,
)
_SENSITIVE_VALUE = re.compile(
    r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}|\b(sk|pk|rk|gsk|xai)-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}"
)
FILTERED = "[Filtered]"


def _scrub(value: Any, depth: int = 0) -> Any:
    if depth > 12:
        return FILTERED
    if isinstance(value, dict):
        return {
            k: FILTERED if isinstance(k, str) and _SENSITIVE_KEY.search(k) else _scrub(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_scrub(v, depth + 1) for v in value]
    if isinstance(value, str):
        return _SENSITIVE_VALUE.sub(FILTERED, value)
    return value


def scrub_sentry_event(event: dict[str, Any], hint: Any = None) -> dict[str, Any]:
    """Drop credentials/PII from a Sentry event and tie it to the active trace."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("cookies", None)
        request.pop("data", None)
        request.pop("env", None)
    user = event.get("user")
    if isinstance(user, dict):
        event["user"] = {"id": user["id"]} if user.get("id") else {}
    event = _scrub(event)
    tags = event.setdefault("tags", {})
    ids = current_ids()
    trace_id = ids[0] if ids else trace_id_var.get()
    if trace_id and trace_id != "-":
        tags.setdefault("trace_id", trace_id)
    if ids:
        tags.setdefault("span_id", ids[1])
    request_id = request_id_var.get()
    if request_id != "-":
        tags.setdefault("request_id", request_id)
    return event


def scrub_breadcrumb(crumb: dict[str, Any], hint: Any = None) -> dict[str, Any]:
    return _scrub(crumb)


def init_otel(
    app: FastAPI,
    settings: Settings,
    *,
    session_factory: Any = None,
    span_exporter: Any = None,
) -> bool:
    return setup_tracing(app, settings, session_factory=session_factory, span_exporter=span_exporter)
