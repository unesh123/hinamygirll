"""Prometheus metrics (dedicated registry; no default process collectors)."""
from __future__ import annotations

import hmac
import ipaddress

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest
from prometheus_client.exposition import CONTENT_TYPE_LATEST

REGISTRY = CollectorRegistry()

HTTP_REQUESTS = Counter(
    "hinaa_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=REGISTRY
)
HTTP_LATENCY = Histogram(
    "hinaa_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120),
    registry=REGISTRY,
)
HTTP_IN_FLIGHT = Gauge("hinaa_http_requests_in_flight", "In-flight HTTP requests", registry=REGISTRY)
RATE_LIMITED = Counter(
    "hinaa_rate_limited_total", "Requests rejected by the rate limiter", ["bucket"], registry=REGISTRY
)
BODY_REJECTED = Counter(
    "hinaa_body_too_large_total", "Requests rejected for exceeding the body limit", registry=REGISTRY
)
LLM_REQUESTS = Counter(
    "hinaa_llm_requests_total", "LLM requests", ["provider", "model", "outcome"], registry=REGISTRY
)
LLM_LATENCY = Histogram(
    "hinaa_llm_request_duration_seconds",
    "LLM request latency",
    ["provider", "model"],
    buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 80, 160),
    registry=REGISTRY,
)
LLM_TOKENS = Counter(
    "hinaa_llm_tokens_total", "LLM tokens", ["provider", "model", "type"], registry=REGISTRY
)
TOOL_CALLS = Counter(
    "hinaa_tool_calls_total", "Agent tool executions", ["tool", "outcome"], registry=REGISTRY
)
TOOL_LATENCY = Histogram(
    "hinaa_tool_duration_seconds",
    "Agent tool execution latency",
    ["tool"],
    buckets=(0.01, 0.05, 0.25, 1, 2.5, 5, 15, 30, 60, 120, 300),
    registry=REGISTRY,
)
PROCESS_START = Gauge(
    "hinaa_process_start_time_seconds", "Unix start time of the API process", registry=REGISTRY
)


def render() -> tuple[bytes, str]:
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def _is_loopback(host: str | None) -> bool:
    if not host:
        return False
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def metrics_access(
    *, client_host: str | None, authorization: str | None, forwarded_for: str | None, token: str | None
) -> int:
    """Return 200 if allowed, 401 if a bearer token is required, else 404."""
    if token and authorization and authorization.lower().startswith("bearer "):
        if hmac.compare_digest(authorization[7:].strip().encode(), token.encode()):
            return 200
    # Loopback behind a local reverse proxy still carries X-Forwarded-For.
    if _is_loopback(client_host) and not forwarded_for:
        return 200
    return 401 if token else 404
