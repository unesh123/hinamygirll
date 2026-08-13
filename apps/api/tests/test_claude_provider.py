from fastapi.testclient import TestClient
import pytest

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.services import ProviderRouter


def _settings(**overrides: object) -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_CLAUDE_API_KEY="test-claude-key",
        HINAA_CLAUDE_MODEL="claude-sonnet-4-20250514",
        HINAA_CLAUDE_ALLOWED_MODELS="claude-sonnet-4-20250514,claude-opus-4-20250514",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
        **overrides,
    )


def test_claude_settings_are_configured_without_exposing_secret() -> None:
    settings = _settings()

    assert settings.claude_configured is True
    assert settings.active_claude_key is not None
    assert settings.active_claude_key.get_secret_value() == "test-claude-key"
    assert settings.resolve_claude_model() == "claude-sonnet-4-20250514"
    with pytest.raises(ValueError, match="HINAA_CLAUDE_ALLOWED_MODELS"):
        settings.resolve_claude_model("not-allowed")


def test_provider_router_selects_claude_adapter_without_live_call() -> None:
    provider = ProviderRouter(_settings()).llm("claude")

    assert provider.id == "claude"


def test_provider_status_reports_claude_readiness_without_key_material() -> None:
    with TestClient(create_app(_settings())) as client:
        response = client.get("/v1/providers")

    assert response.status_code == 200
    claude = next(item for item in response.json() if item["id"] == "claude")
    assert claude["state"] == "healthy"
    assert "model:claude-sonnet-4-20250514" in claude["capabilities"]
    assert "test-claude-key" not in str(claude)


def test_standard_anthropic_environment_alias_is_accepted() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        ANTHROPIC_API_KEY="standard-test-key",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
    )

    assert settings.claude_configured is True
    assert settings.active_claude_key is not None
    assert settings.active_claude_key.get_secret_value() == "standard-test-key"
