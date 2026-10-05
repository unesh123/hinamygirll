"""Regression coverage for provider discovery, configuration and image routing.

All credentials are test values; status probes are intercepted and no paid calls
are made. Adapter construction verifies the model actually sent on the wire.
"""
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from hinaa_api.brain_ledger import fingerprint_for, newest_verdict, record_call
from hinaa_api.capabilities import brain_accepts_images
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService, ProviderRouter


def configured_settings(settings, **updates):
    return settings.model_copy(update={
        "agent_runtime_enabled": False,
        "persistence_enabled": False,
        "explabs_api_key": SecretStr("test-explabs-key"),
        **updates,
    })


@pytest.mark.parametrize("mode", [
    "experiential", "ollama", "pgsgrove", "seekai", "tokentable", "xkiro", "cavoti", "apmix",
])
def test_newer_providers_are_valid_defaults_and_request_modes(mode):
    config = Settings(_env_file=None, HINAA_PROVIDER_MODE=mode)
    request = TurnRequest(sessionId="test-session", text="hello", providerMode=mode)
    assert config.provider_mode == request.providerMode == mode


def test_gemini_discovery_id_resolves_to_its_request_mode():
    assert TurnRequest(sessionId="test-session", text="hello", providerMode="gemini").providerMode == "real"


def test_gemini_text_brain_does_not_require_a_cloud_voice(settings):
    config = configured_settings(settings, gemini_api_key=SecretStr("test-gemini-key"),
                                 elevenlabs_api_key=None, azure_speech_key=None,
                                 deepgram_api_key=None, fish_audio_api_key=None)
    assert ProviderRouter(config).llm("real").id == "gemini"


@pytest.mark.parametrize("mode,prefix", [
    ("custom", "openai_codex"), ("qwen", "qwen"), ("agent-router", "agent_router"),
    ("codecraft", "codecraft"), ("pgsgrove", "pgsgrove"), ("seekai", "seekai"),
    ("tokentable", "tokentable"), ("xkiro", "xkiro"), ("cavoti", "cavoti"), ("apmix", "apmix"),
])
def test_each_openai_compatible_gateway_uses_its_own_key_model_and_endpoint(settings, mode, prefix):
    config = configured_settings(settings, **{
        f"{prefix}_api_key": SecretStr("test-provider-key"),
        f"{prefix}_base_url": "https://gateway.example.test/v1",
        f"{prefix}_model": "configured-model",
        f"{prefix}_allowed_models_raw": "configured-model,pinned-model",
    })
    provider = ProviderRouter(config).llm(mode, "pinned-model")
    assert provider.model == "pinned-model"
    assert provider._key == "test-provider-key"
    assert provider._base_url == "https://gateway.example.test/v1"


def test_experiential_uses_configured_model_and_enforces_allow_list(settings):
    config = configured_settings(settings, explabs_model="claude-sonnet-5",
                                 explabs_allowed_models_raw="claude-sonnet-5,claude-opus-5.5")
    router = ProviderRouter(config)
    assert router.llm("experiential").model == "claude-sonnet-5"
    assert router.llm("experiential", "claude-opus-5.5").model == "claude-opus-5.5"
    assert router.llm("experiential", "claude-opus-5-5").model == "claude-opus-5.5"
    with pytest.raises(HinaaError) as invalid:
        router.llm("experiential", "not-on-this-plan")
    assert invalid.value.code == "EXPLABS_MODEL_NOT_ALLOWED"
    assert invalid.value.status_code == 422


@pytest.mark.parametrize("mode", ["mock", "local"])
def test_stale_cloud_model_cannot_turn_offline_mode_into_paid_call(settings, mode):
    router = ProviderRouter(settings)
    assert router.llm(mode, "claude-opus-5.5").id.startswith(mode)


@pytest.mark.parametrize("mode,field,model", [
    ("experiential", "explabs_model", "claude-opus-5.5"),
    ("pgsgrove", "pgsgrove_model", "gpt-5-test"),
    ("seekai", "seekai_model", "claude-sonnet-test"),
    ("tokentable", "tokentable_model", "gpt-5-test"),
    ("xkiro", "xkiro_model", "qwen-test-vl"),
    ("cavoti", "cavoti_model", "claude-opus-test"),
    ("apmix", "apmix_model", "deepseek-vision-test"),
    ("ollama", "ollama_model", "local-test-vision"),
])
def test_newer_vision_adapters_resolve_unnamed_default(settings, mode, field, model):
    service = ConversationService.__new__(ConversationService)
    service.settings = configured_settings(settings, **{field: model})
    assert service._brain_model(mode, None) == model
    assert brain_accepts_images(mode, model)
    assert not brain_accepts_images(mode, "text-only-model")


async def test_experiential_participates_in_text_and_image_fallbacks(settings):
    service = ConversationService.__new__(ConversationService)
    service.settings = configured_settings(settings)
    assert ("experiential", service.settings.active_explabs_model) in await service._fallback_candidate_modes("groq")
    assert ("experiential", service.settings.active_explabs_model) in await service._fallback_candidate_modes("groq", requires_vision=True)
    assert all(mode != "experiential" for mode, _ in await service._fallback_candidate_modes("experiential"))


def test_experiential_health_is_bound_to_current_key(settings):
    config = configured_settings(settings)
    first = fingerprint_for(config, "experiential")
    assert first
    changed = configured_settings(settings, explabs_api_key=SecretStr("different-test-key"))
    assert first != fingerprint_for(changed, "experiential")
    record_call("experiential", ok=True, model=config.active_explabs_model, fingerprint=first)
    assert newest_verdict(["experiential"], fingerprints={"experiential": first}).state == "healthy"
    assert newest_verdict(["experiential"], fingerprints={"experiential": fingerprint_for(changed, "experiential")}) is None


def test_rate_limit_alias_remains_transient():
    record_call("test-gateway", ok=False, code="PROVIDER_RATE_LIMITED")
    assert newest_verdict(["test-gateway"]).state == "degraded"


def test_discovery_agrees_with_configured_models_and_measured_health(settings, monkeypatch):
    response = MagicMock(status_code=200)
    response.json.return_value = {"models": [{"name": "local-test"}]}
    monkeypatch.setattr("httpx.AsyncClient.get", AsyncMock(return_value=response))
    config = configured_settings(settings, gemini_api_key=SecretStr("test-gemini-key"),
                                 gemini_model="gemini-test-custom",
                                 gemini_allowed_models_raw="gemini-test-custom,gemini-test-other")
    with TestClient(create_app(config)) as client:
        statuses = client.get("/v1/providers").json()
        capabilities = client.get("/v1/capabilities").json()
        exp = next(p for p in statuses if p["id"] == "experiential")
        assert exp["state"] == "untested"
        assert f"default-model:{config.active_explabs_model}" in exp["capabilities"]
        exp_catalog = next(p for p in capabilities["providers"] if p["id"] == "experiential")
        assert exp_catalog["health"] == "untested"
        assert exp_catalog["allowedModels"] == config.explabs_allowed_models
        gemini = next(p for p in capabilities["providers"] if p["id"] == "gemini")
        assert gemini["defaultModel"] == config.gemini_model
        assert gemini["allowedModels"] == config.gemini_allowed_models
        record_call("experiential", ok=True, model=config.active_explabs_model,
                    fingerprint=fingerprint_for(config, "experiential"))
        assert next(p for p in client.get("/v1/providers").json() if p["id"] == "experiential")["state"] == "healthy"
