"""Request-scoped context and structured (JSON) logging."""
from __future__ import annotations

import contextvars
import json
import logging
import re
import uuid
from datetime import UTC, datetime

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("hinaa_request_id", default="-")
trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("hinaa_trace_id", default="-")
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar("hinaa_user_id", default="-")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_TRACEPARENT_RE = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-([0-9a-f]{16})-[0-9a-f]{2}$")

# Standard LogRecord attributes; anything else was passed via `extra=`.
_RESERVED = frozenset(logging.LogRecord("", 0, "", 0, "", None, None).__dict__) | {
    "message",
    "asctime",
    "taskName",
}


def sanitize_request_id(value: str | None) -> str | None:
    if value and _REQUEST_ID_RE.match(value.strip()):
        return value.strip()
    return None


def new_request_id() -> str:
    return uuid.uuid4().hex


def trace_id_from_traceparent(value: str | None) -> str | None:
    if not value:
        return None
    match = _TRACEPARENT_RE.match(value.strip().lower())
    if not match or match.group(1) == "0" * 32 or match.group(2) == "0" * 16:
        return None
    return match.group(1)


class RequestContextFilter(logging.Filter):
    """Stamps request/trace/user ids from contextvars onto every record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        record.trace_id = trace_id_var.get()
        record.user_id = user_id_var.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", request_id_var.get()),
            "trace_id": getattr(record, "trace_id", trace_id_var.get()),
        }
        user = getattr(record, "user_id", user_id_var.get())
        if user != "-":
            payload["user_id"] = user
        for key, value in record.__dict__.items():
            if key not in _RESERVED and key not in payload and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


_HUMAN_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(fmt: str = "text", level: int = logging.INFO) -> None:
    """Idempotent root-logger setup; `json` swaps in the structured formatter."""
    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(level=level, format=_HUMAN_FORMAT)
    for handler in root.handlers:
        if not any(isinstance(f, RequestContextFilter) for f in handler.filters):
            handler.addFilter(RequestContextFilter())
        if fmt == "json":
            handler.setFormatter(JsonFormatter())
