import importlib.util
from pathlib import Path
from unittest.mock import Mock
import pytest

spec = importlib.util.spec_from_file_location("live_runner", Path(__file__).resolve().parents[3] / "scripts/live_runner.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def test_public_profile_fails_closed_without_verified_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    with pytest.raises(RuntimeError, match="verified owner"):
        runner.public_environment()


def test_public_profile_overrides_insecure_local_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "RUNTIME", tmp_path)
    (tmp_path / "owner-id.txt").write_text("user_verifiedowner")
    monkeypatch.setenv("CLERK_SECRET_KEY", "sk_test_fixture")
    monkeypatch.setenv("VITE_CLERK_PUBLISHABLE_KEY", "pk_test_fixture")
    monkeypatch.setenv("HINAA_AUTH_MODE", "dev")
    monkeypatch.setenv("HINAA_ALLOW_REMOTE_LOCAL_TOOLS", "true")
    profile = runner.public_environment()
    assert profile["HINAA_AUTH_MODE"] == "clerk"
    assert profile["HINAA_ALLOWED_USER_IDS"] == "user_verifiedowner"
    assert profile["HINAA_ALLOW_TUNNEL_DEV_AUTH"] == "false"
    assert profile["HINAA_ALLOW_REMOTE_LOCAL_TOOLS"] == "false"
    assert "CLERK_SECRET_KEY" not in profile


def test_ensure_does_not_kill_or_replace_an_unowned_service(monkeypatch):
    live = object.__new__(runner.Runner)
    live.children, live.failures, live.retry_at = {}, {}, {}
    live.start, live.stop = Mock(), Mock()
    monkeypatch.setattr(runner, "port_open", lambda _: True)
    for _ in range(4):
        live.ensure("api", 8000, False, [], Path.cwd())
    live.stop.assert_not_called()
    live.start.assert_not_called()


def test_tunnel_discovery_uses_latest_address(tmp_path):
    log = tmp_path / "tunnel.log"
    log.write_text("https://old-name.trycloudflare.com\nhttps://new-name.trycloudflare.com")
    assert runner.tunnel_origin(log) == "https://new-name.trycloudflare.com"
