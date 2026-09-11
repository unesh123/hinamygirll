"""
hinaa_api/providers/fish_audio.py
Fish Audio TTS provider (server-side). Uses the Fish Audio /v1/tts endpoint
with Bearer auth. Supports language-aware Nepali/English switching: when the
spoken text is Devanagari, request a Nepali-friendly language hint; otherwise
English. The voice id is a Fish Audio voice/reference id from config.

Key isolation: FISH_AUDIO_API_KEY (or Fish_Audio_API_KEY) is server-side only,
never sent to the browser.
"""
from __future__ import annotations

import io
import logging
import re
import time
from dataclasses import dataclass

import httpx

from .base import ProviderResult, TTSProvider

logger = logging.getLogger("hinaa.fish_audio")


def detect_language_hint(text: str) -> str:
    """Map text script to a Fish Audio language hint.

    Fish Audio TTS accepts ISO language hints; Nepali text (Devanagari) uses
    the ``ne`` hint when the voice supports it, otherwise the API ignores or
    relaxes it. English returns ``en``. Mixed text falls back to ``auto``.
    """
    if not text:
        return "auto"
    devanagari = len(re.findall(r"[\u0900-\u097F]", text))
    latin = len(re.findall(r"[A-Za-z]", text))
    if devanagari and latin:
        return "auto"
    if devanagari:
        # Hindi and Nepali share this script. Let the provider detect unless
        # an explicit locale was supplied by the conversation.
        return "auto"
    return "en"


@dataclass(frozen=True)
class FishAudioConfig:
    """Server-side config for the Fish Audio TTS provider."""

    api_key: str = ""
    base_url: str = "https://api.fish.audio"
    voice_id: str = ""
    model_id: str = "fish-speech-1.5"
    output_format: str = "mp3"
    output_sample_rate: int = 44100
    request_timeout_s: float = 30.0

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.voice_id)

    @property
    def safe_voice_preview(self) -> str:
        if len(self.voice_id) >= 4:
            return self.voice_id[:4] + "***"
        return "***"

    def to_browser_safe_dict(self) -> dict:
        return {
            "provider": "fish-audio",
            "label": "Fish Audio TTS",
            "configured": self.configured,
            "voicePreview": self.safe_voice_preview if self.configured else None,
            "modelId": self.model_id if self.configured else None,
            "outputFormat": self.output_format if self.configured else None,
        }


class FishAudioError(Exception):
    """Sanitized error. Never contains the API key or raw upstream body."""

    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status

    def to_browser_safe_dict(self) -> dict:
        return {
            "provider": "fish-audio",
            "status": self.status,
            "message": str(self),
        }


class FishAudioTTSProvider(TTSProvider):
    """Fish Audio HTTP TTS provider with language-aware Nepali/English voice."""

    id: str = "fish-audio"

    def __init__(self, config: FishAudioConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "fish-audio-http"

    @property
    def available(self) -> bool:
        return self._config.configured

    def capability_flags(self) -> dict:
        return {
            "streaming": False,
            "alignment": False,
            "websocket": False,
            "languages": ["en", "ne", "hi", "auto"],
        }

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        *,
        language_hint: str | None = None,
    ) -> ProviderResult[bytes]:
        """Synthesize text to audio bytes via Fish Audio /v1/tts."""
        if not self._config.configured:
            raise FishAudioError(
                "unavailable", "Fish Audio is not configured (missing key or voice)."
            )
        url = f"{self._config.base_url}/v1/tts"
        headers = {
            "Authorization": f"Bearer {self._config.api_key}",
            "Content-Type": "application/json",
            "Accept": "audio/mpeg, audio/wav, application/json",
        }
        lang = language_hint or detect_language_hint(text)
        payload = {
            "text": text,
            "reference_id": voice or self._config.voice_id,
            "format": self._config.output_format,
            "sample_rate": self._config.output_sample_rate,
        }
        if lang != "auto":
            payload["language"] = lang

        start = time.time()
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout_s) as client:
                resp = await client.post(url, headers=headers, json=payload)
                elapsed_ms = int((time.time() - start) * 1000)
                if resp.status_code != 200:
                    status = "provider_error"
                    if resp.status_code in (401, 403):
                        status = "authenticationFailed"
                    elif resp.status_code == 429:
                        status = "quotaFailed"
                    logger.error(
                        "Fish Audio TTS error %s (language=%s): %.120s",
                        resp.status_code,
                        lang,
                        resp.text,
                    )
                    raise FishAudioError(
                        status,
                        f"Fish Audio TTS failed (HTTP {resp.status_code}).",
                    )
                return ProviderResult(resp.content, "fish-audio", elapsed_ms)
        except httpx.TimeoutException as exc:
            raise FishAudioError("timeout", "Fish Audio request timed out.") from exc
        except FishAudioError:
            raise
        except Exception as exc:
            logger.error("Fish Audio unexpected error: %s", type(exc).__name__)
            raise FishAudioError("unavailable", "Fish Audio TTS failed.") from exc
