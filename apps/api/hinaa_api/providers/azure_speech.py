from __future__ import annotations

import asyncio
from time import perf_counter

import azure.cognitiveservices.speech as speechsdk  # type: ignore[import-untyped]

from ..errors import HinaaError, safe_error_text
from .base import ProviderResult


class AzureSpeechProvider:
    id = "azure-speech"

    def __init__(self, key: str, region: str) -> None:
        self._key = key
        self._region = region

    def _speech_config(self) -> speechsdk.SpeechConfig:
        return speechsdk.SpeechConfig(subscription=self._key, region=self._region)

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
        started = perf_counter()

        def speak() -> bytes:
            config = self._speech_config()
            config.speech_synthesis_voice_name = voice
            config.set_speech_synthesis_output_format(
                speechsdk.SpeechSynthesisOutputFormat.Riff16Khz16BitMonoPcm
            )
            synthesizer = speechsdk.SpeechSynthesizer(speech_config=config, audio_config=None)
            result = synthesizer.speak_text_async(text).get()
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
            raise HinaaError("TTS_FAILED", "Voice synthesis failed.", 502, True)

        try:
            audio = await asyncio.to_thread(speak)
        except HinaaError:
            raise
        except Exception as error:
            _ = safe_error_text(error, [self._key])
            raise HinaaError("TTS_FAILED", "Voice synthesis failed safely.", 502, True) from error
        return ProviderResult(audio, self.id, int((perf_counter() - started) * 1000))
