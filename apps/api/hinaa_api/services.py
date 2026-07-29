from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from .config import Settings
from .errors import HinaaError
from .memory import SessionMemory
from .models import AssistantTurnPlan, SpeechRequest, TurnRequest
from .providers.azure_speech import AzureSpeechProvider
from .providers.base import LLMProvider, ProviderResult, STTProvider, TTSProvider
from .providers.gemini import GeminiLLMProvider
from .providers.mock import MockLLMProvider, MockSTTProvider, MockTTSProvider


class ProviderRouter:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.mock_stt = MockSTTProvider()
        self.mock_llm = MockLLMProvider()
        self.mock_tts = MockTTSProvider()

    def _require_real(self) -> None:
        if missing := self.settings.missing_real_configuration():
            raise HinaaError(
                "PROVIDER_CONFIGURATION_MISSING",
                f"Real mode is not configured. Missing backend variables: {', '.join(missing)}.",
                503,
                user_action_required=True,
            )

    def stt(self, mode: str) -> STTProvider:
        if mode == "mock":
            return self.mock_stt
        self._require_real()
        assert self.settings.azure_speech_key and self.settings.azure_speech_region
        return AzureSpeechProvider(
            self.settings.azure_speech_key.get_secret_value(), self.settings.azure_speech_region
        )

    def llm(self, mode: str) -> LLMProvider:
        if mode == "mock":
            return self.mock_llm
        self._require_real()
        assert self.settings.gemini_api_key
        return GeminiLLMProvider(
            self.settings.gemini_api_key.get_secret_value(), self.settings.gemini_model
        )

    def tts(self, mode: str) -> TTSProvider:
        if mode == "mock":
            return self.mock_tts
        self._require_real()
        assert self.settings.azure_speech_key and self.settings.azure_speech_region
        return AzureSpeechProvider(
            self.settings.azure_speech_key.get_secret_value(), self.settings.azure_speech_region
        )


class ConversationService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.router = ProviderRouter(settings)
        self.memory = SessionMemory(settings.session_limit, settings.session_turn_limit)

    async def transcribe(self, pcm: bytes, language: str, mode: str) -> ProviderResult[str]:
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                return await self.router.stt(mode).transcribe(pcm, language)
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Speech transcription took too long.", 504, True
            ) from error

    async def create_plan(self, request: TurnRequest) -> ProviderResult[AssistantTurnPlan]:
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                result = await self.router.llm(request.providerMode).create_plan(
                    request.text,
                    request.companionId,
                    request.language,
                    self.memory.context(request.sessionId),
                )
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "The response took too long.", 504, True
            ) from error
        self.memory.append_turn(request.sessionId, request.text, result.value.displayText)
        return result

    async def stream_turn(self, request: TurnRequest, correlation_id: str) -> AsyncIterator[bytes]:
        yield self._event("thinking", {"correlationId": correlation_id})
        result = await self.create_plan(request)
        words = result.value.displayText.split(" ")
        for index, word in enumerate(words):
            delta = word if index == len(words) - 1 else f"{word} "
            yield self._event("text.delta", {"delta": delta})
            if request.providerMode == "mock":
                await asyncio.sleep(0.012)
        yield self._event("plan", {"plan": result.value.model_dump(), "provider": result.provider})
        yield self._event("usage", {"latencyMs": result.latency_ms})

    async def synthesize(self, request: SpeechRequest) -> ProviderResult[bytes]:
        voice = (
            self.settings.azure_speech_female_voice
            if request.companionId == "hinaa"
            else self.settings.azure_speech_male_voice
        )
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                return await self.router.tts(request.providerMode).synthesize(request.text, voice)
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Voice synthesis took too long.", 504, True
            ) from error

    @staticmethod
    def _event(event_type: str, payload: dict[str, object]) -> bytes:
        return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode()
