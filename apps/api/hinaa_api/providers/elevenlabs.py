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
import base64
import binascii
import contextlib
import json
import logging
import re
import weakref
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from time import perf_counter
from typing import Any, AsyncIterator, Protocol

import httpx

from .base import ProviderResult, TTSProvider

logger = logging.getLogger("hinaa.elevenlabs")


# Devanagari decides nothing by itself: Nepali and Hindi share the script, and a
# Nepali turn answered in a Hindi voice is the kind of wrongness nobody can
# unhear. These are the words each language uses where the other does not, and
# they are counted instead of pattern-matched one at a time. The old single-regex
# check missed ordinary Nepali sentences ("सम्झाओ न setup कसरी गर्ने") and reported
# them as Hindi, which is exactly the turn that then loses its audio.
NEPALI_MARKERS = (
    "मलाई",
    "तिमी",
    "तपाईं",
    "हजुर",
    "हुन्छ",
    "हुन्",
    "हुनुहोस्",
    "गर्ने",
    "गर्नु",
    "गरौं",
    "गरेको",
    "भएको",
    "छ",
    "छु",
    "छौ",
    "छन्",
    "होइन",
    "हैन",
    "पर्छ",
    "पर्दैन",
    "कस्तो",
    "कसरी",
    "किन",
    "अहिले",
    "नमस्ते",
    "भन्नु",
    "दिनु",
    "राम्रो",
    "सक्छु",
    "लाई",
    "बाट",
    "सँग",
    "ठीक",
    "कृपया",
    "धन्यवाद",
    "बुझाऊ",
    "सम्झाओ",
)
HINDI_MARKERS = (
    "मुझे",
    "मैं",
    "हूँ",
    "हूं",
    "है",
    "हैं",
    "नहीं",
    "आप",
    "तुम्हें",
    "क्या",
    "कैसे",
    "क्यों",
    "करना",
    "करनी",
    "करें",
    "करो",
    "मेरा",
    "मेरी",
    "अच्छा",
    "बहुत",
    "होगा",
    "चाहिए",
    "बताओ",
    "समझाओ",
)


def _has_devanagari_word(text: str, word: str) -> bool:
    """Whole-word Devanagari match, so "है" is not found inside "हैन"."""
    return (
        re.search(rf"(?<![\u0900-\u097F]){re.escape(word)}(?![\u0900-\u097F])", text)
        is not None
    )


def language_code_for_text(text: str) -> str:
    """Best-effort ISO 639-1 hint for models that accept language enforcement.

    Multilingual v2 performs its own language handling and rejects this field,
    so the hint is intentionally omitted for that model family below. Nepali
    and Hindi share Devanagari; when both marker sets fire, the Nepali reading
    wins, because a Nepali turn sent to a Hindi-only model produces no audio at
    all while the reverse only costs a slightly heavier model.
    """
    if not re.search(r"[\u0900-\u097F]", text):
        return "en"
    nepali = sum(1 for word in NEPALI_MARKERS if _has_devanagari_word(text, word))
    hindi = sum(1 for word in HINDI_MARKERS if _has_devanagari_word(text, word))
    if nepali and nepali >= hindi:
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


# voice_settings.speed is validated, not rounded. Measured against this account
# on eleven_turbo_v2_5: 0.7 through 1.2 are accepted, 1.25 and 1.5 are answered
# with HTTP 400 {"detail":{"code":"invalid_voice_settings","message":"speed
# expected to be greater or equal to 0.7 and less or equal to 1.2"}}. The
# performance planner is free to emit 0.5 to 2.0, so anything that reaches the
# wire without this clamp silently costs the phrase its audio.
ELEVENLABS_SPEED_MIN = 0.7
ELEVENLABS_SPEED_MAX = 1.2


def clamp_elevenlabs_speed(value: float) -> float:
    """Keep a requested rate inside the range the vendor will actually accept."""
    return max(ELEVENLABS_SPEED_MIN, min(ELEVENLABS_SPEED_MAX, float(value)))


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
        rate: float | None = None,
        model_id: str | None = None,
    ) -> ProviderResult[bytes]:
        import time
        import asyncio

        # A model choice is an addition to the existing contract, not a rewrite
        # of it: callers — and the offline fakes that stand in for synthesize —
        # that say nothing about a model keep their signature untouched.
        synthesize_kwargs: dict[str, Any] = {
            "voice": voice,
            "delivery_mode": delivery_mode,
            "companion_id": companion_id,
            "rate": rate,
        }
        if model_id is not None:
            synthesize_kwargs["model_id"] = model_id

        # Bounded retry on transient 429 quota bursts (the cause of mid-reply
        # voice gaps). Hard failures (401/422/timeout) and exhausted retries
        # raise so the realtime layer can log the segment and keep the rest of
        # the turn flowing. 429s raise pre-stream (before any chunk is yielded),
        # so a retry never double-synthesizes partial audio.
        for attempt in range(self._config.tts_retry_attempts + 1):
            start = time.time()
            chunks: list[bytes] = []
            try:
                async for chunk in self.synthesize(text, **synthesize_kwargs):
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
        rate: float | None = None,
        model_id: str | None = None,
        cancel: ElevenLabsCancellationToken | None = None,
    ) -> AsyncIterator[bytes]:
        if not self._config.configured:
            raise ElevenLabsError(ElevenLabsStatus.unavailable, "ElevenLabs is not configured.")
        voice_id = voice or self._config.voice_id
        # The turn decides the model, not the process: a Nepali turn needs the
        # v3 family while an English one can take the fast model. Falling back to
        # the configured model keeps every other caller behaving as before.
        resolved_model = model_id or self._config.model_id
        url = f"{self._config.base_url}/v1/text-to-speech/{voice_id}/stream"
        # output_format is a query parameter. Sent inside the JSON body it is
        # ignored without any error, so this account answered every request with
        # its mp3 default whatever ELEVENLABS_OUTPUT_FORMAT asked for -- and the
        # media type that labels these bytes for the browser is chosen from that
        # same setting, so the label was right only by coincidence.
        params = {"output_format": self._config.output_format}
        headers = {
            "xi-api-key": self._config.api_key,
            "Content-Type": "application/json",
            "Accept": (
                "audio/mpeg"
                if self._config.output_format.startswith("mp3")
                else "application/octet-stream"
            ),
        }
        delivery = VoicePerformancePlanner().plan_delivery(delivery_mode, companion_id)
        # Emotion-driven voice settings: the planner maps semantic modes
        # (warm/bright/calm/celebratory/…) to bounded stability/similarity/style/
        # speed. These values were previously computed and then ignored, so every
        # companion always spoke with the same flat tone.
        payload = {
            "text": text,
            "model_id": resolved_model,
            "voice_settings": {
                "stability": delivery["stability"],
                "similarity_boost": delivery["similarity"],
                "style": delivery["style_intensity"],
                "use_speaker_boost": True,
                # Speed used to be pinned at 0.9 here -- the slowest value the
                # system holds -- while the caller's rate was dropped on the floor
                # by services, so no server-side pacing decision could reach the
                # wire. The caller's rate now wins; the planner's pace is only a
                # fallback for a caller that expresses no pacing at all.
                "speed": clamp_elevenlabs_speed(
                    rate if rate is not None else delivery["pace"]
                ),
            },
        }
        # A language_code the model does not carry is not ignored, it is a 400 and
        # the phrase loses its audio, so the hint is sent only where this account
        # is measured to accept it (see LANGUAGE_CODES_BY_MODEL). Multilingual v2,
        # the default, is absent from that map and keeps detecting the language.
        language_code = language_code_for_model(text, resolved_model)
        if language_code is not None:
            payload["language_code"] = language_code
        try:
            async with _tts_gate(self._config.tts_max_concurrency):
                async with httpx.AsyncClient(timeout=self._config.request_timeout_s) as client:
                    async with client.stream(
                        "POST", url, headers=headers, params=params, json=payload
                    ) as response:
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


# ── Real-time WebSocket synthesis (Mode B) ───────────────────────────────────
#
# Why this exists next to the HTTP path: the HTTP path accumulates a whole
# phrase before it hands over a single byte (`synthesize_full` above), so a live
# turn waits for the vendor to finish the sentence it is answering with. The
# WebSocket path streams PCM while the sentence is still being generated and
# returns word alignment with it, which is what makes a voice agent feel live:
# first audio inside the first clause, and a mouth that follows the audio the
# vendor actually produced instead of a text approximation.
#
# Vendor contract (measured against this account): one socket per utterance,
# every `text` chunk must end with a single space, `flush` forces generation
# without ending the socket, an empty string closes it, and an idle socket is
# dropped after 20 seconds — which is what the keepalive below answers.
WS_OUTPUT_FORMAT = "pcm_24000"
WS_SAMPLE_RATE = 24_000
# Characters that trigger generation. Lower = faster first audio, higher =
# better prosody. This schedule starts audio on the first short clause.
WS_DEFAULT_CHUNK_SCHEDULE: tuple[int, ...] = (50, 80, 120, 160)
WS_KEEPALIVE_SECONDS = 12.0
# Bounded queue: the vendor socket applies backpressure instead of the process
# growing without limit when the speaker task is slower than the vendor.
WS_CHUNK_QUEUE_MAX = 96
# The vendor can be slow to answer the close frame; a turn must never hang on it.
WS_CLOSE_GRACE_SECONDS = 1.5
WS_OPEN_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class SpeechAlignment:
    """Word/character timing the vendor measured for the audio it just sent."""

    characters: tuple[str, ...]
    start_times_ms: tuple[int, ...]
    durations_ms: tuple[int, ...]

    def to_events(self) -> list[dict]:
        return ElevenLabsAlignmentSource().normalize_alignment(
            list(self.characters),
            [value / 1000 for value in self.start_times_ms],
            [
                (start + duration) / 1000
                for start, duration in zip(
                    self.start_times_ms, self.durations_ms, strict=True
                )
            ],
        )


@dataclass(frozen=True, slots=True)
class SpeechChunk:
    """One piece of vendor audio plus whatever alignment arrived with it."""

    audio: bytes
    alignment: SpeechAlignment | None = None
    is_final: bool = False
    # Characters the vendor echoed back for this chunk (drives chunk-relative
    # alignment offsetting on the client).
    text_echo: str = ""


class WebSocketTransport(Protocol):
    """The slice of a socket this provider needs, so tests can fake it."""

    async def send(self, message: str) -> None: ...
    async def recv(self) -> str | bytes: ...
    async def close(self) -> None: ...


def default_websocket_connect(
    url: str,
    *,
    headers: dict[str, str],
    open_timeout: float,
    max_queue: int,
) -> Any:
    """Open a vendor socket with whichever websockets major version is installed.

    Imported lazily so the HTTP voice path keeps working on an install that has
    no websocket library at all.
    """
    try:
        from websockets.asyncio.client import connect as _connect  # websockets >= 13
    except ImportError:  # pragma: no cover - older install
        from websockets.client import connect as _connect  # type: ignore[attr-defined,no-redef]

        return _connect(
            url,
            extra_headers=headers,
            open_timeout=open_timeout,
            max_size=None,
        )

    return _connect(
        url,
        additional_headers=headers,
        open_timeout=open_timeout,
        max_queue=max_queue,
        max_size=None,
    )


# ── Which model can actually speak this turn (measured, not guessed) ─────────

# Nepali is carried by the v3 family only. Flash v2.5, Turbo v2.5 and
# Multilingual v2 answer a Nepali turn with silence or with Hindi-inflected
# audio, so a Nepali-first companion that pins one non-v3 model loses exactly
# the sentences she exists to say.
NEPALI_CAPABLE_MODELS = frozenset({"eleven_v3", "eleven_v3_conversational"})
# Vendor-measured latency by model, lowest first. Used to pick the fastest model
# that can still pronounce the turn.
MODEL_LATENCY_ORDER: tuple[str, ...] = (
    "eleven_flash_v2_5",
    "eleven_flash_v2",
    "eleven_turbo_v2_5",
    "eleven_turbo_v2",
    "eleven_v3_conversational",
    "eleven_multilingual_v2",
    "eleven_v3",
)


def model_speaks_language(model_id: str, language: str) -> bool:
    """Whether a model carries a language.

    Only the measured gap is encoded: Nepali needs the v3 family. Every other
    language is left to the vendor, because inventing a support table would
    silently mute a language the vendor does carry.
    """
    if language.lower().startswith("ne"):
        return model_id in NEPALI_CAPABLE_MODELS
    return True


def choose_live_tts_model(
    text: str,
    *,
    configured_model: str,
    fast_model: str,
    nepali_model: str,
) -> str:
    """Fastest model that can pronounce this text, for a live (voice) turn.

    Order of truth:
      1. A Nepali turn always goes to a Nepali-capable model — the configured
         model first if it qualifies, otherwise the dedicated Nepali model.
      2. Any other turn takes the configured model when the configured model is
         already the fast one, otherwise the fast model.
      3. A model that cannot carry the detected language never wins.
    """
    language = language_code_for_text(text)
    if language == "ne":
        if model_speaks_language(configured_model, "ne"):
            return configured_model
        return nepali_model
    if model_speaks_language(fast_model, language):
        return fast_model
    return configured_model


def choose_text_tts_model(
    text: str,
    *,
    configured_model: str,
    nepali_model: str,
) -> str:
    """Text-chat voice: keep the configured model unless it cannot pronounce it.

    Unlike a live turn, typed chat has no latency to buy back, so the configured
    voice stays; only a language the model does not carry forces a swap.
    """
    language = language_code_for_text(text)
    if model_speaks_language(configured_model, language):
        return configured_model
    return nepali_model



class ElevenLabsSpeechStream:
    """One live synthesis socket: text in, PCM + alignment out, in order.

    The caller pushes clause text while the brain is still generating it and
    pulls audio from `chunks()`. Ordering is guaranteed by a single queue, so
    what a listener hears always follows the words the vendor actually spoke.
    """

    def __init__(
        self,
        *,
        provider: ElevenLabsWebSocketStreamingProvider,
        transport: WebSocketTransport,
        voice_id: str,
        model_id: str,
        output_format: str,
        cancel: ElevenLabsCancellationToken | None = None,
    ) -> None:
        self._provider = provider
        self._transport = transport
        self.voice_id = voice_id
        self.model_id = model_id
        self.output_format = output_format
        self._cancel = cancel
        self._queue: asyncio.Queue[SpeechChunk | None] = asyncio.Queue(
            maxsize=WS_CHUNK_QUEUE_MAX
        )
        self._receiver: asyncio.Task[None] | None = None
        self._keepalive: asyncio.Task[None] | None = None
        self._input_closed = False
        self._finished = asyncio.Event()
        self._last_send = perf_counter()
        self._started = perf_counter()
        self.first_audio_ms: int | None = None
        self.error: ElevenLabsError | None = None

    @property
    def session_id(self) -> str:
        return f"elevenlabs-ws-{self.voice_id[:4]}"

    @property
    def finished(self) -> bool:
        return self._finished.is_set()

    # ── input ────────────────────────────────────────────────────────────────

    async def send_text_delta(self, text_delta: str, *, flush: bool = False) -> None:
        """Push generated text to the vendor.

        The vendor requires every text chunk to end with a single space, and a
        chunk carrying no text is not a chunk at all — sending one can close the
        socket early, so an empty non-flush delta is skipped.
        """
        if not text_delta.strip() and not flush:
            return
        chunk = text_delta if text_delta.endswith(" ") else f"{text_delta} "
        await self._transport.send(json.dumps({"text": chunk, "flush": flush}))
        self._last_send = perf_counter()

    async def finish_input(self) -> None:
        """End the utterance: the vendor flushes the tail and closes."""
        if self._input_closed:
            return
        self._input_closed = True
        with contextlib.suppress(Exception):
            await self._transport.send(json.dumps({"text": ""}))

    # ── output ───────────────────────────────────────────────────────────────

    async def chunks(self) -> AsyncIterator[SpeechChunk]:
        while True:
            item = await self._queue.get()
            if item is None:
                return
            if self._cancel is not None and self._cancel.is_cancelled:
                return
            yield item

    async def close(self) -> None:
        await self.finish_input()
        # Bounded grace for the tail audio. A turn must never hang because the
        # vendor stopped answering after the close frame.
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._finished.wait(), WS_CLOSE_GRACE_SECONDS)
        await self._teardown()

    async def abort(self) -> None:
        """Barge-in: stop the vendor now and stop feeding the speaker."""
        self._input_closed = True
        await self._teardown()

    def start_receiver(self) -> None:
        self._receiver = asyncio.create_task(
            self._receiver_loop(), name=f"elevenlabs-ws-{self.voice_id[:4]}"
        )
        self._keepalive = asyncio.create_task(
            self._keepalive_loop(), name=f"elevenlabs-ws-keepalive-{self.voice_id[:4]}"
        )

    async def _teardown(self) -> None:
        for task in (self._receiver, self._keepalive):
            if task is not None and not task.done():
                task.cancel()
        for task in (self._receiver, self._keepalive):
            if task is not None:
                with contextlib.suppress(asyncio.CancelledError, Exception):
                    await task
        self._receiver = None
        self._keepalive = None
        with contextlib.suppress(Exception):
            await self._transport.close()
        # "Finished" means no further audio can arrive — true after an abort as
        # much as after a final frame, so a barge-in can never be mistaken for a
        # socket still about to speak.
        self._finished.set()
        self._enqueue_sentinel()

    def _enqueue_sentinel(self) -> None:
        try:
            self._queue.put_nowait(None)
        except asyncio.QueueFull:
            # A full queue means nobody is draining; make room for the sentinel
            # so a waiting consumer can never block on a socket that is gone.
            with contextlib.suppress(asyncio.QueueEmpty):
                self._queue.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                self._queue.put_nowait(None)

    # ── internals ────────────────────────────────────────────────────────────

    async def _receiver_loop(self) -> None:
        try:
            while not self._finished.is_set():
                raw = await self._transport.recv()
                text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else raw
                await self._handle_message(text)
        except asyncio.CancelledError:
            raise
        except Exception as error:  # the socket dropped mid-utterance
            self.error = ElevenLabsError(
                ElevenLabsStatus.unavailable,
                f"ElevenLabs websocket stopped: {type(error).__name__}",
            )
            self._provider.note_failure(type(error).__name__)
            logger.warning(
                "ElevenLabs websocket closed mid-utterance: %s", type(error).__name__
            )
        finally:
            self._finished.set()
            self._enqueue_sentinel()

    async def _handle_message(self, raw: str) -> None:
        try:
            payload = json.loads(raw)
        except ValueError:
            logger.debug("ElevenLabs websocket sent a non-JSON frame; ignored")
            return
        if not isinstance(payload, dict):
            return

        failure = self._status_from_error(payload)
        if failure is not None:
            self._provider.note_failure(failure)
            self.error = ElevenLabsError(failure, f"ElevenLabs websocket: {failure.value}")
            logger.error("ElevenLabs websocket rejected the session: %s", failure.value)
            # A rejected session has no further frames coming, and the vendor may
            # simply stop answering. Ending the stream here is what keeps a failed
            # turn from waiting on a socket that will never speak again.
            self._finished.set()
            self._enqueue_sentinel()
            return

        alignment = _parse_alignment(payload.get("alignment"))
        echo = payload.get("text") if isinstance(payload.get("text"), str) else ""
        audio_base64 = payload.get("audio")
        audio = b""
        if isinstance(audio_base64, str) and audio_base64:
            try:
                audio = base64.b64decode(audio_base64)
            except (ValueError, binascii.Error):
                logger.debug("ElevenLabs websocket frame carried undecodable audio")

        if audio:
            if self.first_audio_ms is None:
                self.first_audio_ms = int((perf_counter() - self._started) * 1000)
            self._provider.note_audio()
            await self._queue.put(
                SpeechChunk(audio=audio, alignment=alignment, text_echo=echo)
            )
        elif alignment is not None:
            # Timing-only frame: the words are known before their audio is, and a
            # client that lip-syncs from real timing is better off for it.
            await self._queue.put(
                SpeechChunk(audio=b"", alignment=alignment, text_echo=echo)
            )

        if payload.get("isFinal") is True:
            self._finished.set()

    async def _keepalive_loop(self) -> None:
        while not self._finished.is_set() and not self._input_closed:
            await asyncio.sleep(WS_KEEPALIVE_SECONDS)
            if self._finished.is_set() or self._input_closed:
                return
            if perf_counter() - self._last_send < WS_KEEPALIVE_SECONDS - 0.5:
                continue
            try:
                await self._transport.send(json.dumps({"text": " "}))
                self._last_send = perf_counter()
            except Exception as error:
                logger.debug("ElevenLabs keepalive gave up: %s", type(error).__name__)
                return

    @staticmethod
    def _status_from_error(payload: dict[str, Any]) -> ElevenLabsStatus | None:
        """Map a vendor error frame to a status, or None when the frame is fine.

        Only frames that name a failure are treated as failures: an ordinary
        audio frame carries no code, and guessing one would end a healthy turn.
        """
        code = str(payload.get("code") or payload.get("message_type") or "")
        detail = str(payload.get("message") or payload.get("error") or "")
        blob = f"{code} {detail}".lower()
        if not blob.strip():
            return None
        if "quota" in blob or "exceed" in blob or "rate limit" in blob or "throttl" in blob:
            return ElevenLabsStatus.quotaFailed
        if "unauthor" in blob or "auth" in blob or "api key" in blob:
            return ElevenLabsStatus.authenticationFailed
        if "voice" in blob:
            return ElevenLabsStatus.voiceUnsupported
        if "model" in blob:
            return ElevenLabsStatus.modelUnsupported
        if "timeout" in blob:
            return ElevenLabsStatus.timeout
        if "error" in blob or "failed" in blob or "invalid" in blob:
            return ElevenLabsStatus.unavailable
        return None


def _parse_alignment(raw: Any) -> SpeechAlignment | None:
    """Vendor alignment payload → timing, or None when it is not usable.

    Field names differ between the socket and the REST paths (`characters` vs
    `chars`), and a length mismatch is corruption rather than a short list, so it
    is dropped instead of silently mis-timing her mouth.
    """
    if not isinstance(raw, dict):
        return None
    characters = raw.get("characters") or raw.get("chars")
    starts = raw.get("charStartTimesMs")
    durations = raw.get("charDurationsMs")
    if (
        not isinstance(characters, list)
        or not isinstance(starts, list)
        or not isinstance(durations, list)
        or not characters
        or len(characters) != len(starts)
        or len(characters) != len(durations)
    ):
        return None
    try:
        return SpeechAlignment(
            characters=tuple(str(char) for char in characters),
            start_times_ms=tuple(int(value) for value in starts),
            durations_ms=tuple(int(value) for value in durations),
        )
    except (TypeError, ValueError):
        return None


class ElevenLabsWebSocketStreamingProvider(TTSProvider):
    """Mode B: real WebSocket streaming TTS with vendor word alignment.

    One socket carries one utterance: text goes in as the brain generates it,
    PCM comes back as the vendor generates it, and `sync_alignment` returns the
    word timing that lets the avatar's mouth follow the audio instead of a guess
    made from characters.
    """

    id: str = "elevenlabs"

    def __init__(
        self,
        config: ElevenLabsConfig,
        *,
        connect_factory: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config
        self._status = (
            ElevenLabsStatus.authenticationUntested
            if config.configured
            else ElevenLabsStatus.unavailable
        )
        self._connect_factory = connect_factory or default_websocket_connect
        # Last measured time-to-first-audio, for diagnostics. 0 until measured.
        self.last_first_audio_ms: int = 0

    @property
    def name(self) -> str:
        return "elevenlabs-websocket"

    @property
    def available(self) -> bool:
        return self._status == ElevenLabsStatus.available

    @property
    def status(self) -> ElevenLabsStatus:
        return self._status

    @property
    def api_key(self) -> str:
        return self._config.api_key

    def capability_flags(self) -> dict:
        return {"streaming": True, "alignment": True, "websocket": True, "languagesVerified": []}

    def note_audio(self) -> None:
        self._status = ElevenLabsStatus.available

    def note_failure(self, reason: ElevenLabsStatus | str) -> None:
        """Record what the vendor actually said, so diagnostics never lie.

        A websocket failure used to be a debug line only, which left a provider
        that had just been rejected still reporting `authenticationUntested` to
        `/v1/providers`.
        """
        if isinstance(reason, ElevenLabsStatus):
            self._status = reason
            return
        logger.debug("ElevenLabs websocket failure noted: %s", reason)
        self._status = ElevenLabsStatus.unavailable

    def speech_url(
        self,
        voice_id: str,
        *,
        model_id: str,
        output_format: str,
        auto_mode: bool = False,
    ) -> str:
        """Build the vendor socket URL for one utterance."""
        base = self._config.base_url.rstrip("/")
        if base.startswith("https://"):
            base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            base = "ws://" + base[len("http://") :]
        query = [
            f"model_id={model_id}",
            f"output_format={output_format}",
            "sync_alignment=true",
        ]
        if auto_mode:
            # Automatic chunk scheduling suits text that arrives faster than the
            # model can read it; an explicit schedule wins when we are choosing
            # where her sentences end.
            query.append("auto_mode=true")
        return f"{base}/v1/text-to-speech/{voice_id}/stream-input?" + "&".join(query)

    def _voice_settings(
        self, delivery_mode: str, companion_id: str, rate: float | None
    ) -> dict[str, Any]:
        delivery = VoicePerformancePlanner().plan_delivery(delivery_mode, companion_id)
        return {
            "stability": delivery["stability"],
            "similarity_boost": delivery["similarity"],
            "style": delivery["style_intensity"],
            "use_speaker_boost": True,
            "speed": clamp_elevenlabs_speed(
                rate if rate is not None else delivery["pace"]
            ),
        }

    async def open_speech_stream(
        self,
        *,
        voice: str | None = None,
        delivery_mode: str = "warm",
        companion_id: str = "hinaa",
        rate: float | None = None,
        model_id: str | None = None,
        output_format: str = WS_OUTPUT_FORMAT,
        chunk_schedule: tuple[int, ...] = WS_DEFAULT_CHUNK_SCHEDULE,
        auto_mode: bool = False,
        cancel: ElevenLabsCancellationToken | None = None,
    ) -> ElevenLabsSpeechStream:
        """Open the vendor socket and return a stream ready for text."""
        if not self._config.configured:
            raise ElevenLabsError(
                ElevenLabsStatus.unavailable, "ElevenLabs is not configured."
            )
        voice_id = voice or self._config.voice_id
        resolved_model = model_id or self._config.model_id
        url = self.speech_url(
            voice_id,
            model_id=resolved_model,
            output_format=output_format,
            auto_mode=auto_mode,
        )
        try:
            transport = await self._connect_factory(
                url,
                headers={"xi-api-key": self._config.api_key},
                open_timeout=WS_OPEN_TIMEOUT_SECONDS,
                max_queue=WS_CHUNK_QUEUE_MAX,
            )
        except Exception as error:
            status = _status_from_handshake(error)
            self._status = status
            logger.error("ElevenLabs websocket handshake failed: %s", type(error).__name__)
            raise ElevenLabsError(
                status, f"ElevenLabs websocket handshake failed ({status.value})."
            ) from error

        stream = ElevenLabsSpeechStream(
            provider=self,
            transport=transport,
            voice_id=voice_id,
            model_id=resolved_model,
            output_format=output_format,
            cancel=cancel,
        )
        try:
            await transport.send(
                json.dumps(
                    {
                        "text": " ",
                        "voice_settings": self._voice_settings(
                            delivery_mode, companion_id, rate
                        ),
                        "generation_config": {
                            "chunk_length_schedule": list(chunk_schedule)
                        },
                        "xi_api_key": self._config.api_key,
                    }
                )
            )
        except Exception as error:
            with contextlib.suppress(Exception):
                await transport.close()
            raise ElevenLabsError(
                ElevenLabsStatus.unavailable,
                "ElevenLabs websocket rejected the setup frame.",
            ) from error
        stream.start_receiver()
        return stream

    async def synthesize(
        self,
        text: str,
        *,
        voice: str | None = None,
        delivery_mode: str = "warm",
        companion_id: str = "hinaa",
        rate: float | None = None,
        model_id: str | None = None,
        cancel: ElevenLabsCancellationToken | None = None,
    ) -> AsyncIterator[bytes]:
        """Whole-text path over the same socket: one flush at the end."""
        stream = await self.open_speech_stream(
            voice=voice,
            delivery_mode=delivery_mode,
            companion_id=companion_id,
            rate=rate,
            model_id=model_id,
            cancel=cancel,
        )
        delivered = False
        try:
            await stream.send_text_delta(text, flush=True)
            await stream.finish_input()
            async for chunk in stream.chunks():
                if chunk.audio:
                    delivered = True
                    yield chunk.audio
        finally:
            await stream.close()
        # A session the vendor rejected must surface as a failure — but only when
        # it cost the caller audio. Half a sentence that was spoken is a partial
        # turn, not an error to raise over the audio already delivered.
        if stream.error is not None and not delivered:
            raise stream.error

    async def synthesize_full(
        self,
        text: str,
        voice: str | None = None,
        delivery_mode: str = "warm",
        companion_id: str = "hinaa",
        rate: float | None = None,
        model_id: str | None = None,
    ) -> ProviderResult[bytes]:
        """Router-compatible full synthesis, with the HTTP path's retry rule.

        Status only becomes `available` after audio actually arrived, so this can
        never report a working voice on the strength of a key alone.
        """
        for attempt in range(self._config.tts_retry_attempts + 1):
            started = perf_counter()
            chunks: list[bytes] = []
            try:
                async for chunk in self.synthesize(
                    text,
                    voice=voice,
                    delivery_mode=delivery_mode,
                    companion_id=companion_id,
                    rate=rate,
                    model_id=model_id,
                ):
                    chunks.append(chunk)
            except ElevenLabsError as error:
                if (
                    error.el_status is ElevenLabsStatus.quotaFailed
                    and attempt < self._config.tts_retry_attempts
                ):
                    backoff = self._config.tts_retry_backoff_s * (2**attempt)
                    logger.warning(
                        "ElevenLabs websocket quota burst (attempt %d); retrying in %.1fs",
                        attempt + 1,
                        backoff,
                    )
                    await asyncio.sleep(backoff)
                    continue
                raise
            if chunks:
                self.note_audio()
            return ProviderResult(
                b"".join(chunks),
                "elevenlabs",
                int((perf_counter() - started) * 1000),
            )
        raise ElevenLabsError(
            ElevenLabsStatus.quotaFailed, "ElevenLabs quota exhausted."
        )


def _status_from_handshake(error: Exception) -> ElevenLabsStatus:
    """Map a failed handshake to the same statuses the HTTP path uses."""
    response = getattr(error, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return map_elevenlabs_http_error(status_code)
    if isinstance(error, TimeoutError):
        return ElevenLabsStatus.timeout
    return ElevenLabsStatus.unavailable


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

