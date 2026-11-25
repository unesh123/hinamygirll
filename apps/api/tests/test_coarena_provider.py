"""Targeted tests for Coarena frontier AI Gateway provider and HINAA_PRIMARY_BRAIN wiring."""

import pytest
from pydantic import SecretStr

from hinaa_api.capabilities import build_capability_registry
from hinaa_api.config import Settings
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ProviderRouter
from hinaa_api.errors import HinaaError
from hinaa_api.brain_ledger import fingerprint_for


def test_pinned_unsupported_model_does_not_silently_change():
    config = Settings(coarena_api_key=SecretStr("test-key"), coarena_allowed_models_raw="approved", coarena_model="approved", _env_file=None)
    with pytest.raises(HinaaError) as error:
        ProviderRouter(config).llm("coarena", brain_model="unsupported-model")
    assert error.value.code == "PROVIDER_MODEL_NOT_ALLOWED"


@pytest.mark.parametrize("changes", [
    {"coarena_api_key": SecretStr("new-key")},
    {"coarena_base_url": "https://another.example/v1"},
    {"coarena_model": "another-model"},
])
def test_health_evidence_is_scoped_to_connection(changes):
    config = Settings(coarena_api_key=SecretStr("original-key"), _env_file=None)
    fingerprint = fingerprint_for(config, "coarena")
    assert fingerprint
    assert fingerprint != fingerprint_for(config.model_copy(update=changes), "coarena")


def test_coarena_config_resolution():
    settings = Settings(
        coarena_api_key=SecretStr("coa_test_12345"),
        coarena_base_url="https://coarena.ai/api/v1",
        coarena_model="claude-sonnet-5-5",
        primary_brain="coarena",
        _env_file=None,
    )
    assert settings.coarena_configured is True
    assert settings.active_coarena_key is not None
    assert settings.active_coarena_key.get_secret_value() == "coa_test_12345"
    assert settings.active_coarena_base_url == "https://coarena.ai/api/v1"
    assert settings.active_coarena_model == "claude-sonnet-5-5"
    assert settings.resolve_coarena_model("gemini-4-argon") == "gemini-4-argon"

    primary_mode, reason = settings.resolve_primary_brain()
    assert primary_mode == "coarena"
    assert "selected" in reason


def test_coarena_missing_key_falls_back_to_xkiro():
    settings = Settings(
        coarena_api_key=None,
        primary_brain="coarena",
        _env_file=None,
    )
    assert settings.coarena_configured is False
    primary_mode, reason = settings.resolve_primary_brain()
    assert primary_mode == "xkiro"
    assert "not configured" in reason


def test_coarena_llm_provider_instantiation():
    settings = Settings(
        coarena_api_key=SecretStr("coa_test_12345"),
        coarena_base_url="https://coarena.ai/api/v1",
        coarena_model="claude-sonnet-5-5",
        primary_brain="coarena",
        _env_file=None,
    )
    router = ProviderRouter(settings)
    provider = router.llm(mode="coarena")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider.model == "claude-sonnet-5-5"
    assert provider.id == "coarena"


def test_coarena_capability_registry_reflection():
    settings = Settings(
        coarena_api_key=SecretStr("coa_test_12345"),
        coarena_base_url="https://coarena.ai/api/v1",
        coarena_model="claude-sonnet-5-5",
        primary_brain="coarena",
        _env_file=None,
    )
    registry = build_capability_registry(settings)
    assert registry.default_brain == "claude-sonnet-5-5"
    assert "Primary brain coarena selected" in registry.primary_brain_reason
