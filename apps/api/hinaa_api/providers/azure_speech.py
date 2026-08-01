from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from xml.sax.saxutils import escape

import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]

from ..errors import HinaaError, safe_error_text
from .base import ProviderResult


@dataclass(frozen=True, slots=True)
class RecognitionEvent:
    kind: str
    text: str = ""


class AzureContinuousRecognizer:
    """Owns one Azure push stream and exposes callbacks through an asyncio queue."""

    def __init__(self, key: str, region: str, language: str, language_mode: str) -> None:
        self._key = key
        self._region = region
        self._language = language if language != "mixed" else "ne-NP"
        self._language_mode = language_mode
        self._events: asyncio.Queue[RecognitionEvent] = asyncio.Queue()
        self._final_texts: list[str] = []
        self._stream: object | None = None
        self._recognizer: object | None = None
        self._started = perf_counter()

    async def start(self) -> None:
        loop = asyncio.get_running_loop()

        def configure() -> None:
            config = speechsdk.SpeechConfig(subscription=self._key, region=self._region)
            auto_language = None
            if self._language_mode == "auto":
                auto_language = speechsdk.languageconfig.AutoDetectSourceLanguageConfig(
                    languages=["ne-NP", "en-US", "hi-IN"]
                )
            else:
                config.speech_recognition_language = self._language
            stream_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=16_000, bits_per_sample=16, channels=1
            )
            stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=config,
                audio_config=speechsdk.audio.AudioConfig(stream=stream),
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
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError(
                "STT_FAILED", "Live speech recognition could not start.", 502, True
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
        self._key = key
        self._region = region

    def _speech_config(self) -> speechsdk.SpeechConfig:
        return speechsdk.SpeechConfig(subscription=self._key, region=self._region)

    def continuous_recognizer(self, language: str, language_mode: str) -> AzureContinuousRecognizer:
        return AzureContinuousRecognizer(self._key, self._region, language, language_mode)

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]:
        started = perf_counter()

        def recognize() -> str:
            config = self._speech_config()
            config.speech_recognition_language = language if language != "mixed" else "ne-NP"
            stream_format = speechsdk.audio.AudioStreamFormat(
                samples_per_second=16_000, bits_per_sample=16, channels=1
            )
            stream = speechsdk.audio.PushAudioInputStream(stream_format=stream_format)
            stream.write(pcm)
            stream.close()
            recognizer = speechsdk.SpeechRecognizer(
                speech_config=config,
                audio_config=speechsdk.audio.AudioConfig(stream=stream),
            )
            result = recognizer.recognize_once_async().get()
            if result.reason == speechsdk.ResultReason.RecognizedSpeech and result.text:
                return str(result.text)
            if result.reason == speechsdk.ResultReason.NoMatch:
                raise HinaaError(
                    "AUDIO_NO_SIGNAL", "I couldn't hear anything. Try again?", 422, True
                )
            details = speechsdk.CancellationDetails(result)
            reason = str(details.reason)
            if "Authentication" in reason or "401" in str(details.error_details):
                raise HinaaError(
                    "PROVIDER_KEY_INVALID",
                    "Azure Speech needs its backend connection fixed.",
                    503,
                    user_action_required=True,
                )
            raise HinaaError("STT_FAILED", "Speech transcription failed.", 502, True)

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
            "<speak version='1.0' xml:lang='ne-NP' "
            "xmlns='http://www.w3.org/2001/10/synthesis'>"
            f"<voice name='{escape(voice)}'><prosody rate='{rate_percent:+d}%' "
            f"pitch='{pitch_semitones:+.1f}st' volume='{volume_percent}%'>"
            f"{escape(text)}</prosody></voice></speak>"
        )
        return await self._synthesize(ssml, voice, True)

    async def _synthesize(self, text: str, voice: str, is_ssml: bool) -> ProviderResult[bytes]:
        started = perf_counter()

        def speak() -> bytes:
            config = self._speech_config()
            config.speech_synthesis_voice_name = voice
            config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
            result = (
                synthesizer.speak_ssml_async(text).get()
                if is_ssml
                else synthesizer.speak_text_async(text).get()
            )
            if result.reason == speechsdk.ResultReason.SynthesizingAudioCompleted:
                return bytes(result.audio_data)
            details = speechsdk.SpeechSynthesisCancellationDetails(result)
            if "Authentication" in str(details.reason) or "401" in str(details.error_details):
                raise HinaaError(
                    "PROVIDER_KEY_INVALID",
                    "Azure Speech needs its backend connection fixed.",
                    503,
                    user_action_required=True,
                )
            lowered = str(details.error_details).lower()
            if "voice" in lowered or "not found" in lowered:
                raise HinaaError(
                    "TTS_VOICE_UNAVAILABLE",
                    "The selected Nepali voice is unavailable; no fallback voice was used.",
                    503,
                    True,
                )
            raise HinaaError("TTS_FAILED", "Voice synthesis failed.", 502, True)

        try:
            audio = await asyncio.to_thread(speak)
        except HinaaError:
            raise
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError("TTS_FAILED", "Voice synthesis failed safely.", 502, True) from error
        return ProviderResult(audio, self.id, int((perf_counter() - started) * 1000))
