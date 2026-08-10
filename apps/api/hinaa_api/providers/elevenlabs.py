"""
hinaa_api/providers/elevenlabs.py
ElevenLabs TTS provider - architecture prepared, offline-tested, owner-gated.
Key isolation: ELEVENLABS_API_KEY server-side only, never sent to browser.

Provider status lifecycle:
  configured           -> env vars present
  authenticationUntested -> not yet called
  available            -> last call succeeded
  unavailable          -> not configured
  authenticationFailed -> 401/403 from API
  quotaFailed          -> 429/quota exceeded
  modelUnsupported     -> model rejected
  voiceUnsupported     -> voice ID rejected
  timeout              -> request exceeded deadline

Status NOT marked available merely because key is present.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator

import httpx

from .base import ProviderResult, TTSProvider

logger = logging.getLogger("hinaa.elevenlabs")


class ElevenLabsStatus(str, Enum):
    configured             = "configured"
    authenticationUntested = "authenticationUntested"
    available              = "available"
    unavailable            = "unavailable"
    authenticationFailed   = "authenticationFailed"
    quotaFailed            = "quotaFailed"
    modelUnsupported       = "modelUnsupported"
    voiceUnsupported       = "voiceUnsupported"
    timeout                = "timeout"


@dataclass(frozen=True)
class ElevenLabsVoiceEntry:
    """Candidate voice. All fields unverified until runtime-tested."""
    display_name: str
    voice_id: str
    model_id: str
    verified: bool = False
    language_review: str = "pending"
    streaming_verified: bool = False
    alignment_verified: bool = False
    commercial_use_status: str = "unknown"


@dataclass
class ElevenLabsConfig:
    """Server-side config only. Never sourced from browser."""
    api_key: str        = ""
    base_url: str       = "https://api.elevenlabs.io"
    voice_id: str       = ""
    model_id: str       = "eleven_multilingual_v2"
    output_format: str  = "mp3_44100_128"
    request_timeout_s: float = 30.0
    stream_chunk_bytes: int  = 4096
    # Transient 429 quota bursts are common on shared/paid tiers; a bounded
    # short-backoff retry keeps her voice from skipping a sentence mid-reply.
    tts_retry_attempts: int   = 2
    tts_retry_backoff_s: float = 0.6

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
            "provider": "elevenlabs",
            "label": "ElevenLabs TTS",
            "configured": self.configured,
            "voicePreview": self.safe_voice_preview if self.configured else None,
            "modelId": self.model_id if self.configured else None,
            "outputFormat": self.output_format if self.configured else None,
        }


_HTTP_STATUS_MAP: dict[int, ElevenLabsStatus] = {
    401: ElevenLabsStatus.authenticationFailed,
    403: ElevenLabsStatus.authenticationFailed,
    429: ElevenLabsStatus.quotaFailed,
    422: ElevenLabsStatus.voiceUnsupported,
}


def map_elevenlabs_http_error(status_code: int) -> ElevenLabsStatus:
    return _HTTP_STATUS_MAP.get(status_code, ElevenLabsStatus.unavailable)


class ElevenLabsError(Exception):
    """Sanitized error. Never contains the API key or raw upstream body."""
    def __init__(self, status: ElevenLabsStatus, message: str) -> None:
        super().__init__(message)
        self.el_status = status

    def to_browser_safe_dict(self) -> dict:
        return {"provider": "elevenlabs", "status": self.el_status.value, "message": str(self)}


class ElevenLabsCancellationToken:
    def __init__(self) -> None:
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    @property
    def is_cancelled(self) -> bool:
        return self._cancelled


class ElevenLabsHTTPStreamingProvider(TTSProvider):
    """Mode A: ElevenLabs HTTP streaming. Owner-gated before real calls."""

    def __init__(self, config: ElevenLabsConfig) -> None:
        self._config = config
        self._status = (
            ElevenLabsStatus.authenticationUntested
            if config.configured
            else ElevenLabsStatus.unavailable
        )

    id: str = "elevenlabs"

    @property
    def name(self) -> str:
        return "elevenlabs-http"

    async def synthesize_full(
        self,
        text: str,
        voice: str | None = None,
        delivery_mode: str = "warm",
        companion_id: str = "hinaa",
    ) -> ProviderResult[bytes]:
        import time
        import asyncio

        # Bounded retry on transient 429 quota bursts (the cause of mid-reply
        # voice gaps). Hard failures (401/422/timeout) and exhausted retries
        # raise so the realtime layer can log the segment and keep the rest of
        # the turn flowing. 429s raise pre-stream (before any chunk is yielded),
        # so a retry never double-synthesizes partial audio.
        for attempt in range(self._config.tts_retry_attempts + 1):
            start = time.time()
            chunks: list[bytes] = []
            try:
                async for chunk in self.synthesize(
                    text, voice=voice, delivery_mode=delivery_mode, companion_id=companion_id
                ):
                    chunks.append(chunk)
            except ElevenLabsError as error:
                if (
                    error.el_status is ElevenLabsStatus.quotaFailed
                    and attempt < self._config.tts_retry_attempts
                ):
                    backoff = self._config.tts_retry_backoff_s * (2 ** attempt)
                    logger.warning(
                        "ElevenLabs TTS quota burst (attempt %d); retrying in %.1fs",
                        attempt + 1,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise
            elapsed_ms = int((time.time() - start) * 1000)
            return ProviderResult(b"".join(chunks), "elevenlabs", elapsed_ms)


    @property
    def available(self) -> bool:
        return self._status == ElevenLabsStatus.available

    def capability_flags(self) -> dict:
        return {"streaming": True, "alignment": False, "websocket": False, "languagesVerified": []}

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        delivery_mode: str = "warm",
        companion_id: str = "hinaa",
        cancel: ElevenLabsCancellationToken | None = None,
    ) -> AsyncIterator[bytes]:
        if not self._config.configured:
            raise ElevenLabsError(ElevenLabsStatus.unavailable, "ElevenLabs is not configured.")
        voice_id = voice or self._config.voice_id
        url = f"{self._config.base_url}/v1/text-to-speech/{voice_id}/stream"
        headers = {
            "xi-api-key": self._config.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        }
        delivery = VoicePerformancePlanner().plan_delivery(delivery_mode, companion_id)
        # Emotion-driven voice settings: the planner maps semantic modes
        # (warm/bright/calm/celebratory/…) to bounded stability/similarity/style/
        # speed. These values were previously computed and then ignored, so every
        # companion always spoke with the same flat tone.
        payload = {
            "text": text,
            "model_id": self._config.model_id,
            "output_format": self._config.output_format,
            "language_code": "hi",
            "voice_settings": {
                "stability": delivery["stability"],
                "similarity_boost": delivery["similarity"],
                "style": delivery["style_intensity"],
                "use_speaker_boost": True,
                "speed": 0.9,
            },
        }
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout_s) as client:
                async with client.stream("POST", url, headers=headers, json=payload) as response:
                    if response.status_code != 200:
                        mapped = map_elevenlabs_http_error(response.status_code)
                        self._status = mapped
                        raise ElevenLabsError(mapped, f"ElevenLabs HTTP {response.status_code}: {mapped.value}")
                    self._status = ElevenLabsStatus.available
                    async for chunk in response.aiter_bytes(self._config.stream_chunk_bytes):
                        if cancel and cancel.is_cancelled:
                            return
                        yield chunk
        except httpx.TimeoutException as exc:
            self._status = ElevenLabsStatus.timeout
            raise ElevenLabsError(ElevenLabsStatus.timeout, "ElevenLabs request timed out.") from exc
        except ElevenLabsError:
            raise
        except Exception as exc:
            self._status = ElevenLabsStatus.unavailable
            logger.error("ElevenLabs unexpected error: %s", type(exc).__name__)
            raise ElevenLabsError(ElevenLabsStatus.unavailable, "ElevenLabs TTS failed.") from exc


class ElevenLabsWebSocketStreamingProvider(TTSProvider):
    """Mode B: WebSocket TTS. Architecture prepared; not yet implemented."""

    def __init__(self, config: ElevenLabsConfig) -> None:
        self._config = config
        self._status = ElevenLabsStatus.unavailable

    @property
    def name(self) -> str:
        return "elevenlabs-websocket"

    @property
    def available(self) -> bool:
        return False

    def capability_flags(self) -> dict:
        return {"streaming": True, "alignment": True, "websocket": True, "languagesVerified": []}

    async def synthesize(
        self, text: str, *, cancel: ElevenLabsCancellationToken | None = None
    ) -> AsyncIterator[bytes]:
        raise NotImplementedError("ElevenLabs WebSocket mode not yet implemented. Use HTTP mode.")
        yield b""  # type: ignore[misc]


def make_elevenlabs_provider(
    config: ElevenLabsConfig,
    mode: str = "http",
) -> ElevenLabsHTTPStreamingProvider | ElevenLabsWebSocketStreamingProvider:
    if mode == "websocket":
        return ElevenLabsWebSocketStreamingProvider(config)
    return ElevenLabsHTTPStreamingProvider(config)


# ── ElevenLabs Scribe v2 Realtime STT Adapter ──────────────────────────────────

class ElevenLabsSTTProvider:
    """ElevenLabs Scribe v2 Realtime STT provider adapter."""

    id: str = "elevenlabs-scribe-v2"

    def __init__(self, config: ElevenLabsConfig) -> None:
        self._config = config
        self._last_final_transcript: str = ""

    async def transcribe(self, pcm: bytes, language: str = "ne") -> ProviderResult[str]:
        import time
        import io
        import wave
        import httpx

        if not pcm:
            return ProviderResult("", "elevenlabs-scribe-v2", 0)

        start = time.time()
        
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(16000)
            wav_file.writeframes(pcm)
        
        audio_bytes = wav_io.getvalue()
        
        url = f"{self._config.base_url}/v1/speech-to-text"
        headers = {
            "xi-api-key": self._config.api_key,
        }
        files = {
            "file": ("audio.wav", audio_bytes, "audio/wav")
        }
        data = {
            "model_id": "scribe_v2",
            "tag_audio_events": "false",
            "diarize": "false",
            "num_speakers": "1",
        }
        
        from ..errors import HinaaError

        result_text = ""
        try:
            async with httpx.AsyncClient(timeout=self._config.request_timeout_s) as client:
                response = await client.post(url, headers=headers, files=files, data=data)
                if response.status_code == 200:
                    raw_text = response.json().get("text", "")
                    # Clean out non-verbal audio event markers like [tone], [laughter], [music], [sigh], etc.
                    import re
                    result_text = re.sub(r"\[[a-zA-Z0-9_\s-]+\]", "", raw_text).strip()
                    logger.info("ElevenLabs STT raw: %r -> cleaned: %r", raw_text, result_text)
                else:
                    # Previously this branch only logged and returned "", which the
                    # realtime layer treated as "the user said nothing" — making
                    # every STT failure look like Hinaa is deaf. Raise instead so
                    # the client sees the real failure code.
                    logger.error("ElevenLabs STT error %s: %s", response.status_code, response.text)
                    mapped = map_elevenlabs_http_error(response.status_code)
                    raise HinaaError(
                        f"ELEVENLABS_STT_{mapped.value.upper()}",
                        f"ElevenLabs speech recognition failed (HTTP {response.status_code}).",
                        503,
                        True,
                    )
        except HinaaError:
            raise
        except httpx.TimeoutException as exc:
            raise HinaaError(
                "ELEVENLABS_STT_TIMEOUT",
                "ElevenLabs speech recognition timed out.",
                504,
                True,
            ) from exc
        except Exception as exc:
            logger.exception("ElevenLabs STT request failed")
            raise HinaaError(
                "ELEVENLABS_STT_REQUEST_FAILED",
                "ElevenLabs speech recognition request failed.",
                503,
                True,
            ) from exc

        elapsed_ms = int((time.time() - start) * 1000)
        return ProviderResult(result_text, "elevenlabs-scribe-v2", elapsed_ms)

    def filter_transcript(self, text: str, is_final: bool = False) -> str | None:
        """Filters empty finals, duplicate finals, and preserves Devanagari/multilingual scripts."""
        cleaned = text.strip()
        if not cleaned:
            return None
        if is_final:
            if cleaned == self._last_final_transcript:
                return None
            self._last_final_transcript = cleaned
        return cleaned

# ── Voice Performance Planner ───────────────────────────────────────────────

ALLOWED_SEMANTIC_MODES = {
    "neutral",
    "warm",
    "bright",
    "calm",
    "thoughtful",
    "professional",
    "encouraging",
    "playful",
    "celebratory",
    "apologetic",
}

class VoicePerformancePlanner:
    """Server-owned bounded voice performance planner. Maps semantic modes to clamped provider parameters."""

    def plan_delivery(self, semantic_mode: str, companion_id: str = "hinaa") -> dict:
        mode = semantic_mode.lower() if semantic_mode.lower() in ALLOWED_SEMANTIC_MODES else "neutral"
        
        # Base defaults. Lower stability = more emotional range; higher style =
        # more expressive warmth; slightly slower pace reads tender and caring.
        stability = 0.50
        similarity = 0.80
        style_intensity = 0.0
        pace = 1.0

        if mode == "warm":
            stability = 0.42
            similarity = 0.82
            style_intensity = 0.28
            pace = 0.93
        elif mode == "bright":
            stability = 0.38
            style_intensity = 0.28
            pace = 1.03
        elif mode == "calm":
            stability = 0.60
            similarity = 0.85
            style_intensity = 0.12
            pace = 0.90
        elif mode == "thoughtful":
            stability = 0.58
            style_intensity = 0.10
            pace = 0.90
        elif mode == "professional":
            stability = 0.68
            similarity = 0.85
            style_intensity = 0.06
            pace = 1.0
        elif mode == "playful":
            stability = 0.33
            style_intensity = 0.38
            pace = 1.06
        elif mode == "celebratory":
            stability = 0.36
            style_intensity = 0.34
            pace = 1.04
        elif mode == "apologetic":
            stability = 0.58
            similarity = 0.85
            style_intensity = 0.16
            pace = 0.92
        elif mode == "encouraging":
            stability = 0.42
            style_intensity = 0.30
            pace = 0.98

        # Per-companion bias: Hinaa's affectionate persona speaks warmer and
        # lighter — a little more expressive, a touch slower and softer. Hiro
        # stays calmer and more grounded. Kept bounded so the semantic mode
        # remains the dominant signal.
        if companion_id == "hiro":
            stability = min(1.0, stability + 0.06)
            style_intensity = max(0.0, style_intensity - 0.04)
            pace = max(0.5, pace - 0.01)
        else:
            stability = max(0.0, stability - 0.05)
            style_intensity = min(1.0, style_intensity + 0.10)
            pace = max(0.5, pace - 0.02)

        return {
            "deliveryMode": mode,
            "stability": round(max(0.0, min(1.0, stability)), 2),
            "similarity": round(max(0.0, min(1.0, similarity)), 2),
            "style_intensity": round(max(0.0, min(1.0, style_intensity)), 2),
            "pace": round(max(0.5, min(2.0, pace)), 2),
            "pause_profile": "natural",
        }


# ── Viseme & Alignment Approximation Adapter ──────────────────────────────────

class ElevenLabsAlignmentSource:
    """Extracts character alignment timestamps from ElevenLabs alignment payloads."""

    def normalize_alignment(self, characters: list[str], start_times: list[float], end_times: list[float]) -> list[dict]:
        events = []
        for char, start, end in zip(characters, start_times, end_times):
            events.append({
                "char": char,
                "startMs": round(start * 1000),
                "endMs": round(end * 1000),
            })
        return events


class VisemeApproximationAdapter:
    """Maps character alignment events to mouth shape approximations (open, wide, rounded, neutral)."""

    def map_char_to_viseme(self, char: str) -> str:
        c = char.lower()
        if c in ("a", "ä", "ā"):
            return "open"
        if c in ("o", "u", "w"):
            return "rounded"
        if c in ("e", "i", "y"):
            return "wide"
        return "neutral"

