from __future__ import annotations

from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app

BASE = {
    "HINAA_PROVIDER_MODE": "mock",
    "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
    "HINAA_AUTH_MODE": "dev",
    "HINAA_PERSISTENCE_ENABLED": False,
    "HINAA_AGENT_RUNTIME_ENABLED": False,
    "HINAA_VMC_PORT": 0,
}


def app_with(**overrides: object) -> TestClient:
    return TestClient(create_app(Settings(**{**BASE, **overrides}, _env_file=None)))


def test_realtime_url_is_served_under_both_route_prefixes() -> None:
    """The deployed frontend reaches the API only through /api/* rewrites, so the
    alias the generic block creates is not optional."""
    with app_with() as client:
        assert client.get("/v1/realtime/url").status_code == 200
        assert client.get("/api/v1/realtime/url").status_code == 200


def test_realtime_url_advertises_the_websocket_path_not_the_http_alias() -> None:
    # /api/v1/realtime is an HTTP-only alias; the upgrade route is /v1/realtime.
    with app_with() as client:
        payload = client.get(
            "/api/v1/realtime/url", headers={"host": "hinaa.example"}
        ).json()
    assert payload["url"] == "wss://hinaa.example/v1/realtime"
    assert payload["source"] == "host"


def test_realtime_url_prefers_the_configured_public_origin() -> None:
    with app_with(HINAA_REALTIME_PUBLIC_ORIGIN="https://pinned.example.com/") as client:
        payload = client.get("/api/v1/realtime/url").json()
    assert payload["url"] == "wss://pinned.example.com/v1/realtime"
    assert payload["source"] == "configured"


def test_realtime_url_reports_plain_ws_for_loopback_origins() -> None:
    with app_with() as client:
        payload = client.get(
            "/v1/realtime/url", headers={"host": "localhost:8000"}
        ).json()
    assert payload["url"] == "ws://localhost:8000/v1/realtime"
