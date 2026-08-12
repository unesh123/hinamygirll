from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from xml.sax.saxutils import escape

try:
    import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]
except Exception as import_error:  # pragma: no cover - exercised via mapper tests
    speechsdk = None  # type: ignore[assignment]
    _SPEECH_SDK_IMPORT_ERROR = import_error
else:
    _SPEECH_SDK_IMPORT_ERROR = None

from ..errors import HinaaError, safe_error_text
from .azure_errors import (
    azure_failure_to_error,
    extract_recognition_cancellation,
    extract_synthesis_cancellation,
)
from .base import ProviderResult


def _require_speech_sdk() -> object:
    if speechsdk is None:
        raise HinaaError(
            "AZURE_SDK_UNAVAILABLE",
            "Azure Speech SDK is unavailable in this environment.",
            503,
            user_action_required=True,
        )
    return speechsdk


@dataclass(frozen=True, slots=True)
class RecognitionEvent:
    kind: str
    text: str = ""


class AzureContinuousRecognizer:
    """Owns one Azure push stream and exposes callbacks through an asyncio queue."""

    def __init__(self, key: str, region: str, language: str, language_mode: str) -> None:
        self._key = key
        self._region = region
        self._language = language if language != "mixed" else "hi-IN"
        self._language_mode = language_mode
        self._events: asyncio.Queue[RecognitionEvent] = asyncio.Queue()
        self._final_texts: list[str] = []
        self._stream: object | None = None
        self._recognizer: object | None = None
        self._started = perf_counter()

    async def start(self) -> None:
        sdk = _require_speech_sdk()
        loop = asyncio.get_running_loop()

        def configure() -> None:
            config = sdk.SpeechConfig(subscription=self._key, region=self._region)
            auto_language = None
            if self._language_mode == "auto":
                auto_language = sdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=["en-US", "hi-IN"]
                )
            else:
                config.speech_recognition_language = self._language
            stream_format = sdk.audio.AudioStreamFormat(
                samples_per_second=16_000, bits_per_sample=16, channels=1
            )
            stream = sdk.audio.PushAudioInputStream(stream_format=stream_format)
            recognizer = sdk.SpeechRecognizer(
                speech_config=config,
                audio_config=sdk.audio.AudioConfig(stream=stream),
                auto_detect_source_language_config=auto_language,
            )

            def recognized(_sender: object, event: object) -> None:
                result = event.result  # type: ignore[attr-defined]
                text = str(result.text or "").strip()
                if text:
                    self._final_texts.append(text)
                    loop.call_soon_threadsafe(
                        self._events.put_nowait, RecognitionEvent("final", text)
                    )

            def recognizing(_sender: object, event: object) -> None:
                text = str(event.result.text or "").strip()  # type: ignore[attr-defined]
                if text:
                    loop.call_soon_threadsafe(
                        self._events.put_nowait, RecognitionEvent("partial", text)
                    )

            def canceled(_sender: object, _event: object) -> None:
                loop.call_soon_threadsafe(self._events.put_nowait, RecognitionEvent("cancelled"))

            recognizer.recognizing.connect(recognizing)
            recognizer.recognized.connect(recognized)
            recognizer.canceled.connect(canceled)
            recognizer.start_continuous_recognition_async().get()
            self._stream = stream
            self._recognizer = recognizer

        try:
            await asyncio.to_thread(configure)
        except HinaaError:
            raise
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError(
                "AZURE_NETWORK_FAILED",
                "Live speech recognition could not start.",
                502,
                True,
            ) from error

    def write(self, frame: bytes) -> None:
        if self._stream is None:
            raise HinaaError("STT_FAILED", "Live speech recognition is not active.", 409, True)
        self._stream.write(frame)  # type: ignore[attr-defined]

    def pending_events(self) -> list[RecognitionEvent]:
        result: list[RecognitionEvent] = []
        while not self._events.empty():
            result.append(self._events.get_nowait())
        return result

    async def finish(self) -> ProviderResult[str]:
        if self._stream is None or self._recognizer is None:
            raise HinaaError("STT_FAILED", "Live speech recognition is not active.", 409, True)
        stream = self._stream
        recognizer = self._recognizer

        def stop() -> None:
            stream.close()  # type: ignore[attr-defined]
            recognizer.stop_continuous_recognition_async().get()  # type: ignore[attr-defined]

        try:
            await asyncio.to_thread(stop)
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError(
                "STT_FAILED", "Live speech recognition stopped safely.", 502, True
            ) from error
        text = " ".join(self._final_texts).strip()
        if not text:
            raise HinaaError("AUDIO_NO_SIGNAL", "No speech was recognized.", 422, True)
        return ProviderResult(
            text, "azure-speech-continuous", int((perf_counter() - self._started) * 1000)
        )

    async def cancel(self) -> None:
        if self._stream is not None:
            self._stream.close()  # type: ignore[attr-defined]
        if self._recognizer is not None:
            await asyncio.to_thread(self._recognizer.stop_continuous_recognition_async().get)  # type: ignore[attr-defined]
        self._stream = None
        self._recognizer = None


class AzureSpeechProvider:
    id = "azure-speech"

    def __init__(self, key: str, region: str) -> None:
        if not key:
            raise HinaaError(
                "AZURE_KEY_MISSING",
                "Azure Speech key is not configured.",
                503,
                user_action_required=True,
            )
        if not region:
            raise HinaaError(
                "AZURE_REGION_MISSING",
                "Azure Speech region is not configured.",
                503,
                user_action_required=True,
            )
        self._key = key
        self._region = region

    def _speech_config(self) -> object:
        sdk = _require_speech_sdk()
        # Exact Speech resource authentication method: subscription key + region.
        return sdk.SpeechConfig(subscription=self._key, region=self._region)

    def continuous_recognizer(self, language: str, language_mode: str) -> AzureContinuousRecognizer:
        return AzureContinuousRecognizer(self._key, self._region, language, language_mode)

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]:
        sdk = _require_speech_sdk()
        started = perf_counter()

        def recognize() -> str:
            config = self._speech_config()
            config.speech_recognition_language = language if language != "mixed" else "hi-IN"
            stream_format = sdk.audio.AudioStreamFormat(
                samples_per_second=16_000, bits_per_sample=16, channels=1
            )
            stream = sdk.audio.PushAudioInputStream(stream_format=stream_format)
            stream.write(pcm)
            stream.close()
            recognizer = sdk.SpeechRecognizer(
                speech_config=config,
                audio_config=sdk.audio.AudioConfig(stream=stream),
            )
            result = recognizer.recognize_once_async().get()
            if result.reason == sdk.ResultReason.RecognizedSpeech and result.text:
                return str(result.text)
            if result.reason == sdk.ResultReason.NoMatch:
                raise HinaaError(
                    "AUDIO_NO_SIGNAL", "I couldn't hear anything. Try again?", 422, True
                )
            details = sdk.CancellationDetails(result)
            raise azure_failure_to_error(extract_recognition_cancellation(details, [self._key]))

        try:
            text = await asyncio.to_thread(recognize)
        except HinaaError:
            raise
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError(
                "STT_FAILED", "Speech transcription failed safely.", 502, True
            ) from error
        return ProviderResult(text, self.id, int((perf_counter() - started) * 1000))

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        return await self._synthesize(text, voice, False)

    async def synthesize_calibrated(
        self, text: str, voice: str, rate: float, pitch_semitones: float, volume: float
    ) -> ProviderResult[bytes]:
        rate_percent = round((rate - 1) * 100)
        volume_percent = round(volume * 100)
        ssml = (
            "<speak version='1.0' xml:lang='hi-IN' "
            "xmlns='http://www.w3.org/2001/10/synthesis'>"
            f"<voice name='{escape(voice)}'><prosody rate='{rate_percent:+d}%' "
            f"pitch='{pitch_semitones:+.1f}st' volume='{volume_percent}%'>"
            f"{escape(text)}</prosody></voice></speak>"
        )
        return await self._synthesize(ssml, voice, True)

    async def _synthesize(self, text: str, voice: str, is_ssml: bool) -> ProviderResult[bytes]:
        sdk = _require_speech_sdk()
        started = perf_counter()

        def speak() -> bytes:
            config = self._speech_config()
            config.speech_synthesis_voice_name = voice
            config.set_speech_synthesis_output_format(
                sdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            synthesizer = sdk.SpeechSynthesizer(speech_config=config, audio_config=None)
            result = (
                synthesizer.speak_ssml_async(text).get()
                if is_ssml
                else synthesizer.speak_text_async(text).get()
            )
            if result.reason == sdk.ResultReason.SynthesizingAudioCompleted:
                audio = bytes(result.audio_data or b"")
                if not audio:
                    raise HinaaError(
                        "AZURE_OUTPUT_WRITE_FAILED",
                        "Synthesized audio was empty; no WAV was kept.",
                        502,
                        True,
                    )
                return audio
            details = sdk.SpeechSynthesisCancellationDetails(result)
            raise azure_failure_to_error(extract_synthesis_cancellation(details, [self._key]))

        try:
            audio = await asyncio.to_thread(speak)
        except HinaaError:
            raise
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError(
                "AZURE_SYNTHESIS_CANCELLED",
                "Voice synthesis failed safely.",
                502,
                True,
            ) from error
        return ProviderResult(audio, self.id, int((perf_counter() - started) * 1000))
