from __future__ import annotations

from pydantic import SecretStr

from hinaa_api.auth_safety import auth_safety_report
from hinaa_api.config import Settings


def _settings(**overrides) -> Settings:
    base = dict(
        _env_file=None,
        HINAA_AUTH_MODE="clerk",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_ALLOW_TUNNEL_DEV_AUTH=False,
        CLERK_SECRET_KEY="sk_test_" + "a" * 40,
        HINAA_ALLOWED_USER_IDS="user_owner_123",
    )
    base.update(overrides)
    return Settings(**base)


def test_owner_gate_is_closed_when_clerk_owner_and_no_tunnel_dev_auth() -> None:
    report = auth_safety_report(_settings())
    assert report["ownerGateClosed"] is True
    assert report["missing"] == []


def test_owner_gate_is_open_when_tunnel_dev_auth_is_on() -> None:
    report = auth_safety_report(_settings(HINAA_ALLOW_TUNNEL_DEV_AUTH=True))
    assert report["tunnelDevAuthOff"] is False
    assert report["ownerGateClosed"] is False


def test_owner_gate_is_open_without_a_clerk_verifier() -> None:
    report = auth_safety_report(_settings(CLERK_SECRET_KEY=None))
    assert report["clerkVerifierConfigured"] is False
    assert "CLERK_SECRET_KEY or CLERK_JWT_KEY" in report["missing"]
    assert report["ownerGateClosed"] is False


def test_owner_gate_is_open_without_an_owner_allowlist() -> None:
    report = auth_safety_report(_settings(HINAA_ALLOWED_USER_IDS=""))
    assert report["ownerAllowlistConfigured"] is False
    assert "HINAA_ALLOWED_USER_IDS" in report["missing"]
    assert report["ownerGateClosed"] is False


def test_report_never_contains_a_secret_value() -> None:
    secret = "sk_test_" + "b" * 40
    owner = "user_owner_secret_456"
    report = auth_safety_report(
        _settings(CLERK_SECRET_KEY=secret, HINAA_ALLOWED_USER_IDS=owner)
    )
    rendered = repr(report)
    assert secret not in rendered
    assert owner not in rendered
    assert all(isinstance(value, (bool, list)) for value in report.values())
