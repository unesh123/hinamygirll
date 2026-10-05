"""Tests for Experiential Gateway routing for claude-opus-5.5.

Verifies:
1. Experiential Gateway configuration in Settings.
2. Missing EXPLABS_API_KEY raises user-actionable HinaaError advising to create and export it.
3. Configured EXPLABS_API_KEY routes claude-opus-5.5 to https://api.experientiallabs.ai/v1 using OpenAILLMProvider.
4. Provider intercept across modes (mode='claude', mode='experiential', mode='cavoti').
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from pydantic import SecretStr

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ProviderRouter


def test_missing_explabs_key_raises_actionable_error():
    """When EXPLABS_API_KEY is not set, requesting claude-opus-5.5 raises the exact expected error."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.explabs_configured = False
    mock_settings.active_explabs_key = None
    mock_settings.active_explabs_base_url = "https://api.experientiallabs.ai/v1"

    router = ProviderRouter.__new__(ProviderRouter)
    router.settings = mock_settings

    with pytest.raises(HinaaError) as exc_info:
        router.llm(mode="claude", brain_model="claude-opus-5.5")

    assert exc_info.value.code == "EXPLABS_API_KEY_MISSING"
    assert "EXPLABS_API_KEY is not set. Please create one under Settings -> API Keys and export it." in exc_info.value.message


def test_configured_explabs_key_routes_to_gateway():
    """When EXPLABS_API_KEY is set, claude-opus-5.5 builds an OpenAILLMProvider with Experiential base URL."""
    mock_settings = MagicMock(spec=Settings)
    mock_settings.explabs_configured = True
    mock_settings.active_explabs_key = SecretStr("exp-test-token-12345")
    mock_settings.active_explabs_base_url = "https://api.experientiallabs.ai/v1"
    mock_settings.active_explabs_model = "claude-opus-5.5"
    mock_settings.resolve_explabs_model.return_value = "claude-opus-5.5"

    router = ProviderRouter.__new__(ProviderRouter)
    router.settings = mock_settings

    # Test via direct brain_model override
    provider = router.llm(mode="claude", brain_model="claude-opus-5.5")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider._model == "claude-opus-5.5"
    assert provider._base_url == "https://api.experientiallabs.ai/v1"
    assert provider._provider_id == "experiential"
    assert provider._key == "exp-test-token-12345"

    # Test via experiential mode
    provider_exp = router.llm(mode="experiential", brain_model=None)
    assert isinstance(provider_exp, OpenAILLMProvider)
    assert provider_exp._model == "claude-opus-5.5"
    assert provider_exp._base_url == "https://api.experientiallabs.ai/v1"
    assert provider_exp._provider_id == "experiential"

    # Test via cavoti mode with claude-opus-5.5
    provider_cavoti = router.llm(mode="cavoti", brain_model="claude-opus-5.5")
    assert isinstance(provider_cavoti, OpenAILLMProvider)
    assert provider_cavoti._model == "claude-opus-5.5"
    assert provider_cavoti._base_url == "https://api.experientiallabs.ai/v1"


def test_openai_llm_gateway_recognition():
    """Verify experiential is recognized as a gateway provider."""
    from hinaa_api.providers.openai_llm import _GATEWAY_PROVIDERS
    assert "experiential" in _GATEWAY_PROVIDERS

    provider = OpenAILLMProvider(
        key="exp-test-token",
        model="claude-opus-5.5",
        base_url="https://api.experientiallabs.ai/v1",
        provider_id="experiential",
    )
    assert provider.id == "experiential"
    assert provider.model == "claude-opus-5.5"
    assert provider._base_url == "https://api.experientiallabs.ai/v1"


