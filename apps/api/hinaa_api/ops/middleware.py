"""Pure-ASGI middleware: request context/metrics/access log and body limit."""
from __future__ import annotations

import logging
import time
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import metrics
from .context import (
    new_request_id,
    request_id_var,
    sanitize_request_id,
    trace_id_from_traceparent,
    trace_id_var,
    user_id_var,
)

access_logger = logging.getLogger("hinaa.access")

_SKIP_ACCESS_LOG = frozenset({"/metrics", "/health", "/healthz", "/readyz", "/health/live", "/api/health"})

# Routes that legitimately accept large binary uploads (avatar/creative media).
UPLOAD_PATHS = frozenset(
    {
        "/v1/avatar-assets/import",
        "/api/v1/avatar-assets/import",
        "/v1/creative/assets/upload",
        "/api/creative/assets/upload",
    }
)


class ObservabilityMiddleware:
    """Assigns request/trace ids, records metrics, emits one access-log line."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        request_id = (
            sanitize_request_id(headers.get("x-request-id"))
            or sanitize_request_id(headers.get("x-correlation-id"))
            or new_request_id()
        )
        trace_id = trace_id_from_traceparent(headers.get("traceparent"))
        if trace_id is None:
            incoming = (headers.get("x-trace-id") or "").strip().lower()
            if len(incoming) == 32 and all(c in "0123456789abcdef" for c in incoming):
                trace_id = incoming
            else:
                trace_id = new_request_id()
                # Inner middleware honours X-Trace-Id, keeping one id end-to-end.
                scope["headers"] = [*scope["headers"], (b"x-trace-id", trace_id.encode())]

        rid_token = request_id_var.set(request_id)
        tid_token = trace_id_var.set(trace_id)
        uid_token = user_id_var.set("-")
        status = 500
        start = time.perf_counter()
        metrics.HTTP_IN_FLIGHT.inc()

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
                out = MutableHeaders(scope=message)
                out["X-Request-Id"] = request_id
                if "x-trace-id" not in out:
                    out["X-Trace-Id"] = trace_id
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            elapsed = time.perf_counter() - start
            metrics.HTTP_IN_FLIGHT.dec()
            method = scope["method"]
            path = scope["path"]
            route = getattr(scope.get("route"), "path", None) or "unmatched"
            metrics.HTTP_REQUESTS.labels(method, route, str(status)).inc()
            metrics.HTTP_LATENCY.labels(method, route).observe(elapsed)
            auth = scope.get("state", {}).get("hinaa_auth")
            user = getattr(auth, "user_id", None)
            if path not in _SKIP_ACCESS_LOG or status >= 500:
                fields: dict[str, Any] = {
                    "method": method,
                    "path": route if route != "unmatched" else path,
                    "status": status,
                    "duration_ms": round(elapsed * 1000, 2),
                }
                if user:
                    fields["user_id"] = user
                access_logger.info(
                    "%s %s -> %s", method, fields["path"], status, extra=fields
                )
            request_id_var.reset(rid_token)
            trace_id_var.reset(tid_token)
            user_id_var.reset(uid_token)


class BodyLimitMiddleware:
    """Rejects oversized bodies with 413 (Content-Length and chunked)."""

    def __init__(self, app: ASGIApp, *, max_bytes: int, max_upload_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes
        self.max_upload_bytes = max(max_upload_bytes, max_bytes)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        limit = self.max_upload_bytes if scope["path"] in UPLOAD_PATHS else self.max_bytes
        declared = Headers(scope=scope).get("content-length")
        if declared and declared.isdigit() and int(declared) > limit:
            await self._reject(send)
            return

        received = 0
        exceeded = False

        async def counting_receive() -> Message:
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    # Frameworks turn raised errors into 400s; a disconnect makes
                    # the app stop, and we substitute the 413 below.
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not exceeded:
                await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded:
            await self._reject(send)

    async def _reject(self, send: Send) -> None:
        metrics.BODY_REJECTED.inc()
        body = b'{"error":{"code":"PAYLOAD_TOO_LARGE","message":"Request body exceeds the allowed size."}}'
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
