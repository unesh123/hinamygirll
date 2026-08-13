from fastapi.testclient import TestClient
import pytest

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.services import ProviderRouter


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "HINAA_PROVIDER_MODE": "mock",
        "HINAA_CLAUDE_API_KEY": "test-claude-key",
        "HINAA_CLAUDE_MODEL": "claude-sonnet-4-20250514",
        "HINAA_CLAUDE_ALLOWED_MODELS": "claude-sonnet-4-20250514,claude-opus-4-20250514",
        "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "HINAA_AUTH_MODE": "dev",
        "HINAA_PERSISTENCE_ENABLED": True,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


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


def test_mwapi_gateway_uses_anthropic_bearer_transport_without_live_call() -> None:
    settings = _settings(
        HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1",
        HINAA_CLAUDE_MODEL="claude-sonnet-4-6",
        HINAA_CLAUDE_ALLOWED_MODELS="claude-sonnet-4-6,claude-opus-4-6",
    )

    provider = ProviderRouter(settings).llm("claude")

    assert settings.active_claude_protocol == "anthropic"
    assert provider.id == "claude"
    assert provider.uses_bearer_auth is True  # type: ignore[attr-defined]
    assert provider.gateway_auth_headers == {"Authorization": "Bearer test-claude-key"}  # type: ignore[attr-defined]
    assert provider._model == "claude-sonnet-4-6"  # type: ignore[attr-defined]


def test_claude_status_discloses_mwapi_bearer_protocol_without_secret() -> None:
    settings = _settings(
        HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1",
        HINAA_CLAUDE_MODEL="claude-sonnet-4-6",
        HINAA_CLAUDE_ALLOWED_MODELS="claude-sonnet-4-6",
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/providers")

    claude = next(item for item in response.json() if item["id"] == "claude")
    assert "anthropic-messages" in claude["capabilities"]
    assert "bearer-auth" in claude["capabilities"]
    assert "protocol:anthropic" in claude["capabilities"]
    assert "test-claude-key" not in str(claude)


def test_claude_code_auth_token_alone_does_not_configure_hinaa() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        ANTHROPIC_AUTH_TOKEN="separate-claude-code-token",
        HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
    )

    assert settings.claude_configured is False


def test_gateway_normalizes_stale_official_model_preference() -> None:
    settings = _settings(HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1")

    assert settings.active_claude_protocol == "anthropic"
    assert settings.active_claude_model == "claude-sonnet-4-6"
    assert settings.resolve_claude_model("claude-sonnet-4-20250514") == "claude-sonnet-4-6"
    assert settings.claude_allowed_models == [
        "claude-sonnet-4-6",
        "claude-opus-4-6",
        "claude-haiku-4-5-20251001",
    ]


def test_gateway_status_reports_normalized_model_catalog() -> None:
    settings = _settings(HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1")
    with TestClient(create_app(settings)) as client:
        response = client.get("/v1/providers")

    claude = next(item for item in response.json() if item["id"] == "claude")
    assert "default-model:claude-sonnet-4-6" in claude["capabilities"]
    assert "model:claude-sonnet-4-20250514" not in claude["capabilities"]


def test_gateway_no_available_accounts_is_classified_as_upstream_capacity() -> None:
    import httpx
    from hinaa_api.errors import HinaaError
    from hinaa_api.providers.openai_llm import OpenAILLMProvider

    provider = OpenAILLMProvider(
        "test-claude-key",
        "claude-sonnet-4-6",
        base_url="https://api.mwapi.dev/v1",
        provider_id="claude",
    )
    response = httpx.Response(
        503,
        json={"error": {"message": "No available accounts", "type": "api_error"}},
        request=httpx.Request("POST", "https://api.mwapi.dev/v1/chat/completions"),
    )

    with pytest.raises(HinaaError) as captured:
        provider._raise_for_status(response)

    assert captured.value.code == "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE"
    assert captured.value.retryable is True
    assert captured.value.user_action_required is True
    assert "test-claude-key" not in captured.value.message


def test_claude_live_plan_emits_display_text_not_structured_json() -> None:
    import asyncio
    from hinaa_api.prompts import build_plan_from_text
    from hinaa_api.providers.base import ProviderResult

    provider = ProviderRouter(
        _settings(HINAA_CLAUDE_BASE_URL="https://api.mwapi.dev/v1")
    ).llm("claude")
    plan = build_plan_from_text(
        text="Hey babe! I am happy to see you. What would you like to do?",
        companion_id="hinaa",
        language="mixed",
        depth="conversational",
    )
    structured_contract = "```json\n" + plan.model_dump_json() + "\n```"

    async def fake_create_plan(*_args, **_kwargs):
        return ProviderResult(plan, "claude:claude-sonnet-4-6", 1)

    emitted: list[str] = []

    async def emit_delta(value: str) -> None:
        emitted.append(value)

    provider.create_plan = fake_create_plan  # type: ignore[method-assign]
    result = asyncio.run(
        provider.create_live_plan(
            "hey HINAA",
            "hinaa",
            "mixed",
            (),
            emit_delta,
            None,
        )
    )

    assert result.value.displayText == plan.displayText
    assert "".join(emitted) == plan.displayText
    assert structured_contract not in "".join(emitted)
    assert "```json" not in "".join(emitted)
