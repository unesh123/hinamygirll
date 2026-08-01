from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable

from .config import Settings
from .errors import HinaaError
from .memory import SessionMemory
from .models import AssistantTurnPlan, CompanionId, ProviderMode, SpeechRequest, TurnRequest
from .prompts import PROMPT_VERSION, neutral_fallback_plan
from .prompts.turn_prompt import build_turn_prompt
from .providers.azure_speech import AzureContinuousRecognizer, AzureSpeechProvider
from .providers.base import LLMProvider, ProviderResult, STTProvider, TTSProvider
from .providers.gemini import GeminiLLMProvider
from .providers.mock import MockLLMProvider, MockSTTProvider, MockTTSProvider
from .voice_profiles import resolve_calibration, resolve_voice

logger = logging.getLogger("hinaa.conversation")


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
        history = self.memory.context(request.sessionId)
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="rest",
        )
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "rest")
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                result = await self.router.llm(request.providerMode).create_plan(
                    request.text,
                    request.companionId,
                    request.language,
                    history,
                    prompt,
                )
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "The response took too long.", 504, True
            ) from error
        except HinaaError as error:
            if error.code == "MODEL_RESPONSE_INVALID":
                plan = neutral_fallback_plan(
                    user_text=request.text,
                    companion_id=request.companionId,
                    language=request.language,
                    depth=prompt.response_depth,
                )
                result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)
            else:
                raise
        self.memory.append_turn(request.sessionId, request.text, result.value.displayText)
        return result

    async def create_live_plan(
        self, request: TurnRequest, emit_delta: Callable[[str], Awaitable[None]]
    ) -> ProviderResult[AssistantTurnPlan]:
        history = self.memory.context(request.sessionId)
        prompt = build_turn_prompt(
            request=request,
            history=history,
            settings=self.settings,
            interaction_mode="realtime",
        )
        self._log_prompt_meta(request.sessionId, prompt.fingerprint, "realtime")
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                provider = self.router.llm(request.providerMode)
                if isinstance(provider, GeminiLLMProvider):
                    result = await provider.create_live_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        emit_delta,
                        prompt,
                    )
                else:
                    result = await provider.create_plan(
                        request.text,
                        request.companionId,
                        request.language,
                        history,
                        prompt,
                    )
                    for start in range(0, len(result.value.displayText), 7):
                        await emit_delta(result.value.displayText[start : start + 7])
                        await asyncio.sleep(0.006)
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "The response took too long.", 504, True
            ) from error
        except HinaaError as error:
            if error.code == "MODEL_RESPONSE_INVALID":
                plan = neutral_fallback_plan(
                    user_text=request.text,
                    companion_id=request.companionId,
                    language=request.language,
                    depth=prompt.response_depth,
                )
                await emit_delta(plan.displayText)
                result = ProviderResult(plan, f"fallback:{PROMPT_VERSION}", 0)
            else:
                raise
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
        plan_payload: dict[str, object] = {
            "plan": result.value.model_dump(),
            "provider": result.provider,
        }
        if self.settings.prompt_debug_metadata:
            plan_payload["promptVersion"] = PROMPT_VERSION
        yield self._event("plan", plan_payload)
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

    async def synthesize_text(
        self,
        text: str,
        companion_id: CompanionId,
        mode: ProviderMode,
        calibration: str = "natural",
    ) -> ProviderResult[bytes]:
        if mode == "mock":
            return await self.synthesize(
                SpeechRequest(text=text, companionId=companion_id, providerMode=mode)
            )
        provider = self.router.tts(mode)
        if not isinstance(provider, AzureSpeechProvider):
            raise HinaaError("TTS_FAILED", "Speech synthesis provider is unavailable.", 503, True)
        voice = resolve_voice(
            companion_id,
            self.settings.azure_speech_female_voice,
            self.settings.azure_speech_male_voice,
        )
        tuning = resolve_calibration(calibration)
        try:
            async with asyncio.timeout(self.settings.provider_timeout_seconds):
                return await provider.synthesize_calibrated(
                    text, voice, tuning.rate, tuning.pitch_semitones, tuning.volume
                )
        except TimeoutError as error:
            raise HinaaError(
                "PROVIDER_TIMEOUT", "Voice synthesis took too long.", 504, True
            ) from error

    async def start_live_stt(self, language: str, language_mode: str) -> AzureContinuousRecognizer:
        provider = self.router.stt("real")
        if not isinstance(provider, AzureSpeechProvider):
            raise HinaaError("STT_FAILED", "Continuous speech provider is unavailable.", 503, True)
        recognizer = provider.continuous_recognizer(language, language_mode)
        await recognizer.start()
        return recognizer

    def _log_prompt_meta(self, session_id: str, fingerprint: str, mode: str) -> None:
        logger.info(
            "prompt_assembled",
            extra={
                "session_id": session_id,
                "prompt_version": PROMPT_VERSION,
                "fingerprint": fingerprint,
                "interaction_mode": mode,
            },
        )

    @staticmethod
    def _event(event_type: str, payload: dict[str, object]) -> bytes:
        return (json.dumps({"type": event_type, **payload}, ensure_ascii=False) + "\n").encode()
