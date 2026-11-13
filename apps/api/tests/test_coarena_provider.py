"""Targeted tests for Coarena frontier AI Gateway provider and HINAA_PRIMARY_BRAIN wiring."""

import pytest
from pydantic import SecretStr

from hinaa_api.capabilities import build_capability_registry
from hinaa_api.config import Settings
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ProviderRouter


def test_coarena_config_resolution():
    settings = Settings(
        coarena_api_key=SecretStr("coa_test_12345"),
        coarena_base_url="https://coarena.ai/api/v1",
        coarena_model="claude-sonnet-5-5",
        primary_brain="coarena",
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
    )
    registry = build_capability_registry(settings)
    assert registry.default_brain == "claude-sonnet-5-5"
    assert "Primary brain coarena selected" in registry.primary_brain_reason
