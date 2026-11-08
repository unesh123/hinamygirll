"""Request context, metrics, rate limiting, body limit and CORS policy."""
from __future__ import annotations

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.ops.context import JsonFormatter, request_id_var
from hinaa_api.ops.ratelimit import TokenBucketLimiter

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
TRACEPARENT = f"00-{TRACE_ID}-00f067aa0ba902b7-01"


def make_settings(settings: Settings, **overrides: object) -> Settings:
    return settings.model_copy(update=overrides)


def client_for(settings: Settings, **overrides: object) -> TestClient:
    return TestClient(create_app(make_settings(settings, **overrides)))


# --- request context -------------------------------------------------------


def test_request_id_generated_and_echoed(settings: Settings) -> None:
    response = client_for(settings).get("/health/live")
    assert len(response.headers["X-Request-Id"]) == 32
    assert len(response.headers["X-Trace-Id"]) == 32


def test_incoming_request_id_and_traceparent_honored(settings: Settings) -> None:
    response = client_for(settings).get(
        "/health/live", headers={"X-Request-Id": "req-abc_123", "traceparent": TRACEPARENT}
    )
    assert response.headers["X-Request-Id"] == "req-abc_123"
    assert response.headers["X-Trace-Id"] == TRACE_ID


def test_invalid_request_id_replaced(settings: Settings) -> None:
    response = client_for(settings).get("/health/live", headers={"X-Request-Id": "bad id\twith spaces"})
    assert response.headers["X-Request-Id"] != "bad id\twith spaces"
    assert len(response.headers["X-Request-Id"]) == 32


def test_json_log_formatter_fields() -> None:
    token = request_id_var.set("rid-1")
    try:
        record = logging.LogRecord("hinaa.access", logging.INFO, __file__, 1, "GET %s", ("/x",), None)
        record.status = 200
        record.duration_ms = 1.5
        payload = json.loads(JsonFormatter().format(record))
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "rid-1"
    assert payload["level"] == "INFO"
    assert payload["message"] == "GET /x"
    assert payload["status"] == 200
    assert payload["duration_ms"] == 1.5


def test_access_log_has_route_status_duration(settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    client = client_for(settings)
    with caplog.at_level(logging.INFO, logger="hinaa.access"):
        client.get("/v1/ledger/turns", headers={"X-Request-Id": "log-test-1"})
    records = [r for r in caplog.records if r.name == "hinaa.access"]
    assert records, "access log line expected"
    record = records[-1]
    assert record.method == "GET"
    assert record.path == "/v1/ledger/turns"
    assert isinstance(record.status, int)
    assert record.duration_ms >= 0
    assert "authorization" not in json.dumps(record.__dict__, default=str).lower()


# --- metrics ---------------------------------------------------------------


def test_metrics_hidden_from_public(settings: Settings) -> None:
    assert client_for(settings).get("/metrics").status_code == 404


def test_metrics_from_loopback(settings: Settings) -> None:
    app = create_app(make_settings(settings))
    client = TestClient(app, client=("127.0.0.1", 50000))
    client.get("/health/live")
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    body = response.text
    assert "hinaa_http_requests_total" in body
    assert 'route="/health/live"' in body
    assert "hinaa_http_request_duration_seconds_bucket" in body
    assert "hinaa_http_requests_in_flight" in body


def test_metrics_loopback_with_forwarded_header_denied(settings: Settings) -> None:
    client = TestClient(create_app(make_settings(settings)), client=("127.0.0.1", 1))
    assert client.get("/metrics", headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 404


def test_metrics_token_required_when_configured(settings: Settings) -> None:
    app = create_app(make_settings(settings, metrics_token=SecretStr("s3cret-token")))
    client = TestClient(app)
    assert client.get("/metrics").status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/metrics", headers={"Authorization": "Bearer s3cret-token"}).status_code == 200


def test_metrics_bypasses_clerk_but_still_enforced(settings: Settings) -> None:
    client = client_for(settings, auth_mode="clerk")
    assert client.get("/metrics").status_code == 404  # reaches handler, not 401 from Clerk


# --- rate limiting ---------------------------------------------------------


def test_token_bucket_refills() -> None:
    now = [0.0]
    limiter = TokenBucketLimiter(clock=lambda: now[0])
    assert limiter.check("k", 2).allowed
    assert limiter.check("k", 2).allowed
    denied = limiter.check("k", 2)
    assert not denied.allowed and denied.retry_after >= 1
    now[0] += 30.0
    assert limiter.check("k", 2).allowed


def test_rate_limit_429_with_retry_after_and_exemptions(settings: Settings) -> None:
    client = client_for(
        settings, rate_limit_enabled=True, rate_limit_per_minute=3, rate_limit_expensive_per_minute=1
    )
    codes = [client.get("/v1/ledger/turns").status_code for _ in range(5)]
    assert codes[:3] != [429, 429, 429] and codes[-1] == 429
    limited = client.get("/v1/ledger/turns")
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1
    assert limited.json()["error"]["code"] == "RATE_LIMITED"
    assert "X-Request-Id" in limited.headers
    for path in ("/health/live", "/healthz", "/readyz"):
        for _ in range(6):
            assert client.get(path).status_code != 429


def test_rate_limit_expensive_bucket_is_stricter(settings: Settings) -> None:
    client = client_for(
        settings, rate_limit_enabled=True, rate_limit_per_minute=100, rate_limit_expensive_per_minute=1
    )
    first = client.post("/v1/vision/react", json={})
    second = client.post("/v1/vision/react", json={})
    assert first.status_code != 429
    assert second.status_code == 429
    assert client.get("/v1/ledger/turns").status_code != 429


def test_rate_limit_exempts_telephony_webhooks(settings: Settings) -> None:
    from hinaa_api.telephony import calls

    client = client_for(settings, rate_limit_enabled=True, rate_limit_per_minute=1)
    for _ in range(4):
        assert client.post(calls.VOICE_PATH).status_code != 429


def test_rate_limit_keyed_by_forwarded_ip_only_when_trusted(settings: Settings) -> None:
    untrusted = client_for(settings, rate_limit_enabled=True, rate_limit_per_minute=1)
    untrusted.get("/v1/ledger/turns", headers={"X-Forwarded-For": "1.1.1.1"})
    assert untrusted.get("/v1/ledger/turns", headers={"X-Forwarded-For": "2.2.2.2"}).status_code == 429

    trusted = client_for(settings, rate_limit_enabled=True, rate_limit_per_minute=1, trust_proxy=True)
    trusted.get("/v1/ledger/turns", headers={"X-Forwarded-For": "1.1.1.1"})
    assert trusted.get("/v1/ledger/turns", headers={"X-Forwarded-For": "2.2.2.2"}).status_code != 429
    assert trusted.get("/v1/ledger/turns", headers={"X-Forwarded-For": "1.1.1.1"}).status_code == 429


def test_rate_limit_off_by_default_outside_production(settings: Settings) -> None:
    client = client_for(settings, rate_limit_per_minute=1)
    assert all(client.get("/v1/ledger/turns").status_code != 429 for _ in range(5))
    assert make_settings(settings, environment="production").rate_limit_active is True


# --- body limit ------------------------------------------------------------


def test_body_over_limit_rejected_413(settings: Settings) -> None:
    client = client_for(settings, max_body_bytes=1024)
    response = client.post("/v1/vision/react", content=b"x" * 2048)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "PAYLOAD_TOO_LARGE"
    assert "X-Request-Id" in response.headers


def test_chunked_body_over_limit_rejected_413(settings: Settings) -> None:
    client = client_for(settings, max_body_bytes=1024)

    def chunks():  # type: ignore[no-untyped-def]
        for _ in range(8):
            yield b"x" * 512

    response = client.post("/v1/vision/react", content=chunks(), headers={"Content-Type": "application/json"})
    assert response.status_code == 413


def test_small_body_and_upload_route_allowance(settings: Settings) -> None:
    client = client_for(settings, max_body_bytes=1024, max_upload_bytes=1024 * 1024)
    assert client.post("/v1/vision/react", content=b"{}").status_code != 413
    upload = client.post(
        "/v1/avatar-assets/import",
        files={"file": ("a.vrm", io.BytesIO(b"x" * 4096), "application/octet-stream")},
    )
    assert upload.status_code != 413


# --- CORS ------------------------------------------------------------------


def preflight(client: TestClient, origin: str, headers: str = "authorization,content-type") -> dict[str, str]:
    response = client.options(
        "/v1/ledger/turns",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": headers,
        },
    )
    return {"status": str(response.status_code), **response.headers}


def test_cors_allows_production_and_localhost(settings: Settings) -> None:
    client = client_for(settings)
    for origin in ("https://hinaa-workspace.vercel.app", "http://localhost:5173"):
        assert preflight(client, origin).get("access-control-allow-origin") == origin


def test_cors_allows_project_preview_not_other_vercel_apps(settings: Settings) -> None:
    client = client_for(settings)
    preview = "https://hinaa-workspace-git-feat-team.vercel.app"
    assert preflight(client, preview).get("access-control-allow-origin") == preview
    for evil in (
        "https://evil.vercel.app",
        "https://hinaa-workspace.vercel.app.evil.com",
        "https://other-hinaa-workspace.vercel.app",
    ):
        assert "access-control-allow-origin" not in preflight(client, evil)


def test_cors_extra_origin_setting_and_regex_override(settings: Settings) -> None:
    client = client_for(
        settings,
        cors_origins=["https://app.example.com"],
        cors_origin_regex=r"^https://staging-[a-z]+\.example\.com$",
    )
    assert preflight(client, "https://app.example.com")["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" in preflight(client, "https://staging-x.example.com")
    assert "access-control-allow-origin" not in preflight(client, "https://hinaa-workspace-abc.vercel.app")


def test_cors_empty_regex_disables_previews(settings: Settings) -> None:
    client = client_for(settings, cors_origin_regex="")
    assert "access-control-allow-origin" not in preflight(client, "https://hinaa-workspace-abc.vercel.app")


def test_cors_headers_are_explicit(settings: Settings) -> None:
    client = client_for(settings)
    ok = preflight(client, "https://hinaa-workspace.vercel.app", "authorization,traceparent,x-hinaa-dev-user")
    assert ok["status"] == "200"
    bad = preflight(client, "https://hinaa-workspace.vercel.app", "x-evil-header")
    assert bad["status"] == "400"
    assert ok["access-control-allow-headers"] != "*"
