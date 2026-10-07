from unittest.mock import AsyncMock

import pytest
from hinaa_api.models import SpeechRequest
from hinaa_api.services import ConversationService
from hinaa_api.providers.elevenlabs import ElevenLabsConfig, ElevenLabsHTTPStreamingProvider
from hinaa_api.providers.base import ProviderResult


@pytest.mark.asyncio
@pytest.mark.parametrize("realtime, expected_model", [(True, "eleven_flash_v2_5"), (False, "eleven_multilingual_v2")])
async def test_progressive_voice_selects_fast_model_without_changing_identity(settings, realtime, expected_model):
    settings.elevenlabs_model_id = "eleven_multilingual_v2"
    settings.elevenlabs_tts_model_fast = "eleven_flash_v2_5"
    service = ConversationService(settings)
    provider = ElevenLabsHTTPStreamingProvider(ElevenLabsConfig(api_key="fixture", voice_id="fixture-voice"))
    service.router.tts = lambda *args: provider
    service._voice_with_fallback = AsyncMock(return_value=ProviderResult(value=b"audio", provider="elevenlabs", latency_ms=1))
    await service.synthesize(SpeechRequest(text="Hello, I am ready to help.", realtime=realtime))
    call = service._voice_with_fallback.await_args.kwargs
    assert call["model_id"] == expected_model
    assert call["voice_id"] == settings.elevenlabs_hinaa_voice_id
    if realtime:
        assert call["rate"] == 1.12
