from __future__ import annotations

from pathlib import Path

from hinaa_api.runtime_paths import live_runner_state_path


def test_explicit_override_wins(tmp_path: Path) -> None:
    target = tmp_path / "runner-state.json"
    assert live_runner_state_path(str(target)) == target.resolve()


def test_blank_override_falls_back_to_project_runtime() -> None:
    path = live_runner_state_path("   ")
    assert path.name == "runner-state.json"
    assert path.parent.name == "live"
    assert path.parent.parent.name == ".runtime"


def test_route_reads_the_configured_runner_state(tmp_path: Path, monkeypatch) -> None:
    import json

    from fastapi.testclient import TestClient

    from hinaa_api.config import Settings
    from hinaa_api.main import create_app

    state = tmp_path / "runner-state.json"
    state.write_text(json.dumps({"tunnelOrigin": "https://tunnel.example.com"}), encoding="utf-8")
    settings = Settings(
        _env_file=None,
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_PROVIDER_MODE="mock",
        HINAA_VMC_PORT=0,
        HINAA_LIVE_RUNNER_STATE=str(state),
    )
    monkeypatch.chdir(tmp_path / "..")
    with TestClient(create_app(settings)) as client:
        payload = client.get("/api/v1/realtime/url", headers={"host": "127.0.0.1:8000"}).json()
    assert payload["url"] == "wss://tunnel.example.com/v1/realtime"
    assert payload["source"] == "configured"
