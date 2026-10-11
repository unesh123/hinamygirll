from __future__ import annotations

import pytest
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


def test_realtime_url_advertises_the_websocket_path_not_the_http_alias(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # /api/v1/realtime is an HTTP-only alias; the upgrade route is /v1/realtime.
    with app_with() as client:
        # The endpoint falls back to .runtime/live/runner-state.json (a cwd-relative
        # runtime file) so a live local Hina can point her preview at the public
        # socket. Isolated to a tmp cwd, the test must never see that file.
        monkeypatch.chdir(tmp_path)
        # A direct request on this machine advertises its own host. A non-local
        # hostname is treated as the public edge, and an unconfigured edge request
        # must advertise nothing (see test_edge_request_without_origin_advertises_nothing).
        payload = client.get(
            "/api/v1/realtime/url", headers={"host": "127.0.0.1:8000"}
        ).json()
    assert payload["url"] == "ws://127.0.0.1:8000/v1/realtime"
    assert payload["source"] == "host"


def test_edge_request_without_origin_advertises_nothing(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Regression: an edge request advertised wss://<its own host>/v1/realtime, which
    # the Vercel rewrite cannot upgrade. Nothing is advertised instead.
    with app_with() as client:
        monkeypatch.chdir(tmp_path)
        payload = client.get(
            "/api/v1/realtime/url",
            headers={"host": "hinaa-workspace.vercel.app", "cf-connecting-ip": "203.0.113.9"},
        ).json()
    assert payload["url"] is None
    assert payload["source"] == "unavailable-edge"


def test_realtime_url_prefers_the_configured_public_origin() -> None:
    with app_with(HINAA_REALTIME_PUBLIC_ORIGIN="https://pinned.example.com/") as client:
        payload = client.get("/api/v1/realtime/url").json()
    assert payload["url"] == "wss://pinned.example.com/v1/realtime"
    assert payload["source"] == "configured"


def test_realtime_url_reports_plain_ws_for_loopback_origins(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    with app_with() as client:
        monkeypatch.chdir(tmp_path)  # never see the live runner's state file
        payload = client.get(
            "/v1/realtime/url", headers={"host": "localhost:8000"}
        ).json()
    assert payload["url"] == "ws://localhost:8000/v1/realtime"
