from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.models import TurnRequest
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ConversationService


@pytest.fixture
def settings() -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        AUTO_FALLBACK_ENABLED=True,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        _env_file=None,
    )


@pytest.mark.asyncio
async def test_create_plan_never_falls_back_on_safety_refusal(settings: Settings) -> None:
    service = ConversationService(settings)
    mock_provider = MagicMock()
    mock_provider.create_plan = AsyncMock(
        side_effect=HinaaError("SAFETY_REFUSAL", "Declined due to safety policy", 400, False)
    )

    call_modes = []

    def mock_router(mode: str, model: str | None = None):
        call_modes.append(mode)
        return mock_provider

    service.router.llm = mock_router

    request = TurnRequest(
        sessionId="safety-test-session",
        text="Harmful instruction",
        companionId="hinaa",
        language="en-US",
        providerMode="cx-gateway",
    )

    with pytest.raises(HinaaError) as exc_info:
        await service.create_plan(request)

    assert exc_info.value.code == "SAFETY_REFUSAL"
    # Verify ONLY the primary provider mode was queried, zero fallback modes invoked!
    assert call_modes == ["cx-gateway"]


@pytest.mark.asyncio
async def test_create_live_plan_never_falls_back_on_safety_refusal(settings: Settings) -> None:
    service = ConversationService(settings)
    mock_provider = MagicMock(spec=OpenAILLMProvider)
    mock_provider.id = "cx-gateway"
    mock_provider.create_live_plan = AsyncMock(
        side_effect=HinaaError("SAFETY_REFUSAL", "Refused in live mode", 400, False)
    )

    call_modes = []

    def mock_router(mode: str, model: str | None = None):
        call_modes.append(mode)
        return mock_provider

    service.router.llm = mock_router

    request = TurnRequest(
        sessionId="safety-live-test-session",
        text="Harmful live instruction",
        companionId="hinaa",
        language="en-US",
        providerMode="cx-gateway",
    )

    async def dummy_emit(delta: str) -> None:
        pass

    with pytest.raises(HinaaError) as exc_info:
        await service.create_live_plan(request, dummy_emit)

    assert exc_info.value.code == "SAFETY_REFUSAL"
    assert call_modes == ["cx-gateway"]


def test_openai_safety_refusal_mapping() -> None:
    from hinaa_api.providers.openai_llm import OpenAILLMProvider
    provider = OpenAILLMProvider("test-key", "gpt-4o", base_url="https://api.openai.com/v1", provider_id="openai")
    err = Exception("Request failed: content_filter triggered by safety system")
    mapped = provider._map_provider_error(err)
    assert mapped.code == "SAFETY_REFUSAL"
    assert not mapped.retryable


def test_groq_safety_refusal_mapping() -> None:
    from hinaa_api.providers.groq import GroqLLMProvider
    provider = GroqLLMProvider("test-key", "llama3-70b-8192")
    err = Exception("Error: refusal due to safety violation")
    mapped = provider._map_provider_error(err)
    assert mapped.code == "SAFETY_REFUSAL"
    assert not mapped.retryable


def test_gemini_safety_refusal_mapping() -> None:
    from hinaa_api.providers.gemini import GeminiLLMProvider
    provider = GeminiLLMProvider("test-key", "gemini-2.0-flash")
    err = Exception("Candidate blocked due to SAFETY: harm_category HARM_CATEGORY_DANGEROUS_CONTENT")
    mapped = provider._map_provider_error(err)
    assert mapped.code == "SAFETY_REFUSAL"
    assert not mapped.retryable

