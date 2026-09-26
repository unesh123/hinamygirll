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

import asyncio
import json
import logging
import re
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import AsyncIterator

import httpx

from .base import ProviderResult, TTSProvider

logger = logging.getLogger("hinaa.elevenlabs")


def language_code_for_text(text: str) -> str:
    """Best-effort ISO 639-1 hint for models that accept language enforcement.

    Multilingual v2 performs its own language handling and rejects this field,
    so the hint is intentionally omitted for that model family below. Nepali
    and Hindi share Devanagari; common Nepali grammar markers keep the optional
    hint from incorrectly forcing Hindi on a clearly Nepali turn.
    """
    if not re.search(r"[\u0900-\u097F]", text):
        return "en"
    if re.search(r"(?:मलाई|तपाईं|हुनुहोस्|गर्नुहोस्|छु|छौ|को\s+setup)", text):
        return "ne"
    return "hi"


# language_code is enforced, not suggested. A code the model does not carry is not
# ignored, it is answered with HTTP 400 unsupported_language, and the phrase that
# asked for it never becomes audio. Measured against this account:
# eleven_turbo_v2_5 accepts "en" and "hi" and rejects "ne" with
#   {"detail":{"code":"invalid_parameters","status":"unsupported_language",
#    "message":"Model 'eleven_turbo_v2_5' does not support language_code 'ne'."}}
# which is precisely why only her Nepali phrases went silent in a live turn
# (ttsStatus=partial, 12 of 18 segments delivered). Multilingual v2 rejects the
# field for every value. So the rule is to send a hint only where it is measured
# to be accepted: an unmeasured model or code costs enforcement, never audio.
LANGUAGE_CODES_BY_MODEL: dict[str, frozenset[str]] = {
    "eleven_turbo_v2_5": frozenset({"en", "hi"}),
}


def language_code_for_model(text: str, model_id: str) -> str | None:
    """The language_code to put on the request, or None to let the model detect."""
    accepted = LANGUAGE_CODES_BY_MODEL.get(model_id)
    if not accepted:
        return None
    hint = language_code_for_text(text)
    return hint if hint in accepted else None


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
    # Measured ceiling is 5 in-flight syntheses; one slot of headroom keeps a
    # burst from being answered with 429 instead of audio.
    tts_max_concurrency: int  = 4

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


def reason_from_body(body: bytes | str) -> str:
    """ElevenLabs' own words about a rejected request, bounded and single-line.

    A 400 maps to no specific status here, so reporting only the mapped enum made a
    parameter the model refuses read as "unavailable" -- which named nothing that
    was wrong and left a partial voice turn undiagnosable in the logs.
    """
    raw = body.decode("utf-8", "replace") if isinstance(body, bytes) else body
    text = raw.strip()
    if not text:
        return "no response body"
    try:
        parsed = json.loads(text)
    except ValueError:
        parsed = None
    detail = parsed.get("detail") if isinstance(parsed, dict) else None
    if isinstance(detail, dict):
        text = " ".join(
            part
            for part in (str(detail.get("status") or ""), str(detail.get("message") or ""))
            if part
        )
    elif isinstance(detail, str):
        text = detail
    elif parsed is None:
        # A proxy page instead of an API answer. Quoting it would put markup on a
        # line meant to be read as one sentence.
        text = "upstream returned no structured reason"
    return re.sub(r"\s+", " ", text)[:200] or "no response body"


# ElevenLabs rejects the sixth simultaneous synthesis for this account with a
# 429, and a live turn spawns one synthesis per streamed phrase. The gate is
# module-level because ProviderRouter builds a new provider instance on every
# call, so an instance attribute would gate nothing. It is keyed by loop because
# an asyncio primitive reused across event loops raises instead of waiting.
_TTS_GATES: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, tuple[int, asyncio.Semaphore]]" = (
    weakref.WeakKeyDictionary()
)


def _tts_gate(limit: int) -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    entry = _TTS_GATES.get(loop)
    if entry is None or entry[0] != limit:
        entry = (limit, asyncio.Semaphore(limit))
        _TTS_GATES[loop] = entry
    return entry[1]


class ElevenLabsError(Exception):
    """Sanitized error. Carries at most a bounded, field-parsed vendor reason.

    Never the API key, an auth header, or a raw upstream body — see reason_from_body,
    which keeps the rejected-request explanation that made a silent phrase findable.
    """
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
            "voice_settings": {
                "stability": delivery["stability"],
                "similarity_boost": delivery["similarity"],
                "style": delivery["style_intensity"],
                "use_speaker_boost": True,
                "speed": 0.9,
            },
        }
        # A language_code the model does not carry is not ignored, it is a 400 and
        # the phrase loses its audio, so the hint is sent only where this account
        # is measured to accept it (see LANGUAGE_CODES_BY_MODEL). Multilingual v2,
        # the default, is absent from that map and keeps detecting the language.
        language_code = language_code_for_model(text, self._config.model_id)
        if language_code is not None:
            payload["language_code"] = language_code
        try:
            async with _tts_gate(self._config.tts_max_concurrency):
                async with httpx.AsyncClient(timeout=self._config.request_timeout_s) as client:
                    async with client.stream("POST", url, headers=headers, json=payload) as response:
                        if response.status_code != 200:
                            mapped = map_elevenlabs_http_error(response.status_code)
                            self._status = mapped
                            reason = reason_from_body(await response.aread())
                            logger.error(
                                "ElevenLabs rejected %d: %s (%s)",
                                response.status_code,
                                mapped.value,
                                reason,
                            )
                            raise ElevenLabsError(
                                mapped, f"ElevenLabs HTTP {response.status_code}: {reason}"
                            )
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
        # Explicit language code hint: ElevenLabs Scribe v2 requires "language_code"
        # for non-English audio (e.g. "hin" for Hindi/Hinglish, "nep" for Nepali).
        lang = (language or "").lower()
        if not lang or lang in ("auto", "default") or any(h in lang for h in ("hi", "hin", "mixed")):
            data["language_code"] = "hin"
        elif any(n in lang for n in ("ne", "nep")):
            data["language_code"] = "nep"
        elif "en" in lang:
            data["language_code"] = "eng"
        elif lang:
            data["language_code"] = lang[:3]
        
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

