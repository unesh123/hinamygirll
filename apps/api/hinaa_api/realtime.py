from __future__ import annotations

import asyncio
import base64
import logging
import re
import struct
from contextlib import suppress
from dataclasses import dataclass, field
from time import monotonic_ns, perf_counter
from typing import Annotated, Any, Literal

logger = logging.getLogger("hinaa.realtime")

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import Field, ValidationError

from .config import Settings
from .errors import HinaaError
from .response.notation import MathNotationStream, ascii_math
from . import realtime_tickets
from .models import CompanionId, Language, ProviderMode, StrictModel, TurnRequest
from .providers.elevenlabs import (
    ElevenLabsSpeechStream,
    ElevenLabsWebSocketStreamingProvider,
    choose_live_tts_model,
)
from .services import ConversationService
from .voice_performance import (
    plan_voice_performance,
    speech_text_for_tts,
    strip_greeting,
)
from .voice_profiles import resolve_calibration, resolve_voice


class ClientHello(StrictModel):
    type: Literal["session.hello"]
    protocolVersion: Literal["1.0"]
    sessionId: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
    companionId: CompanionId = "hinaa"
    providerMode: ProviderMode = "mock"
    generation: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    language: Language = "mixed"
    languageMode: Literal["fixed", "fixed-hi-IN", "fixed-ne-NP", "fixed-en-US", "auto"] = "auto"
    calibration: Literal["natural", "soft", "lively"] = "natural"
    brainModel: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None
    authTicket: Annotated[str | None, Field(min_length=16, max_length=64)] = None


class FrameDescriptor(StrictModel):
    type: Literal["audio.frame"]
    sequence: Annotated[int, Field(ge=0, le=10_000_000)]
    generation: Annotated[int, Field(ge=0, le=1_000_000)]
    capturedAtMs: Annotated[float, Field(ge=0)]
    byteLength: Annotated[int, Field(ge=640, le=1_280)]


class CommitMessage(StrictModel):
    type: Literal["audio.commit"]
    generation: Annotated[int, Field(ge=0, le=1_000_000)]
    endedAtMs: Annotated[float, Field(ge=0)]
    visibleActions: list[str] = Field(default_factory=list)
    mockTranscript: Annotated[str | None, Field(min_length=1, max_length=500)] = None


@dataclass(slots=True)
class LiveSession:
    hello: ClientHello
    user_id: str | None = None
    expected_sequence: int = 0
    audio: bytearray = field(default_factory=bytearray)
    speech_detected: bool = False
    partial_sent: bool = False
    turn: int = 0
    processing: asyncio.Task[None] | None = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)


def _timestamp_ms() -> float:
    return monotonic_ns() / 1_000_000


def _has_speech(pcm: bytes) -> bool:
    if len(pcm) < 2:
        return False
    count = len(pcm) // 2
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    energy = sum(sample * sample for sample in samples) / count
    return energy**0.5 >= 30


def _is_dead_silence(pcm: bytes) -> bool:
    """True only for effectively all-zero audio (no signal at all).

    Frontend VAD is trusted for quiet mics, but a fully digital-zero buffer is
    never speech — rejecting it before STT avoids burning a paid transcription
    call on silence and keeps the typed AUDIO_NO_SIGNAL contract.
    """
    if not pcm:
        return True
    # Sample every byte in the buffer; all-zero PCM16 (0x00 0x00) has no signal.
    return not any(pcm)



def _tts_media_type(provider_id: str, elevenlabs_output_format: str) -> str:
    """Return the real audio MIME type for the bytes a TTS provider produced.

    Previously this event field was hardcoded to "audio/wav" for every
    provider. ElevenLabs and Deepgram return MP3 (per ELEVENLABS_OUTPUT_FORMAT / encoding=mp3)
    — mislabeling those bytes as audio/wav is silently incorrect and is a real cause of
    "she isn't speaking" on stricter mobile audio decoders.
    """
    if provider_id in {"deepgram", "fish-audio"}:
        return "audio/mpeg"
    if provider_id == "elevenlabs":
        if elevenlabs_output_format.startswith("mp3"):
            return "audio/mpeg"
        if elevenlabs_output_format.startswith("pcm"):
            return "audio/pcm"
        if elevenlabs_output_format.startswith("ulaw"):
            return "audio/basic"
        return "audio/mpeg"
    return "audio/wav"


# A phrase shorter than this is a fragment, not speech: every flush is its own
# synthesis request and its own audio blip. The wrap width matches
# segment_phrases so both spoken paths cut text the same way.
SPEECH_MIN_PHRASE_CHARS = 40
SPEECH_MIN_FIRST_PHRASE_CHARS = 16
SPEECH_PHRASE_WRAP_CHARS = 160


def spoken_phrase_is_complete(buffer: str, is_first: bool = False) -> bool:
    """Whether streamed text so far should be handed to the voice vendor as one phrase.

    First phrase starts at 16+ chars on sentence boundary so Hina begins talking
    instantly while the remainder streams. Standard phrases batch at 40+ chars.
    """
    if len(buffer) >= SPEECH_PHRASE_WRAP_CHARS:
        return True
    min_chars = SPEECH_MIN_FIRST_PHRASE_CHARS if is_first else SPEECH_MIN_PHRASE_CHARS
    return any(p in buffer for p in ".!?।;\n") and len(buffer) >= min_chars


def segment_phrases(text: str, limit: int = 160) -> list[str]:
    """Split spoken text into TTS-friendly phrases without breaking technical tokens."""
    # Strip markdown markers only; preserve underscores in env vars / identifiers.
    cleaned = re.sub(r"[`*#>]+", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    if not cleaned:
        return []
    chunks = [part.strip() for part in re.split(r"(?<=[.!?।…])\s+", cleaned) if part.strip()]
    result: list[str] = []
    for chunk in chunks or [cleaned]:
        while len(chunk) > limit:
            window = chunk[:limit]
            # Prefer whitespace; avoid cutting mid URL/path/env/decimal when possible.
            split_at = window.rfind(" ")
            if split_at <= 20 or re.search(
                r"(https?:\/\/\S*|[A-Za-z]:\\|\.[0-9]+|[A-Z_]{2,}=)$", window[:split_at]
            ):
                split_at = limit
            result.append(chunk[:split_at].strip())
            chunk = chunk[split_at:].strip()
        if chunk:
            result.append(chunk)
    return result


class RealtimeGateway:
    def __init__(self, settings: Settings, service: ConversationService) -> None:
        self.settings = settings
        self.service = service

    @staticmethod
    def _resolve_identity(hello: ClientHello, handshake_user_id: str | None) -> str | None:
        """Owner of this voice session, or None when nobody proved who they are.

        The handshake header cannot be trusted from a browser, so the ticket the
        client bought over authenticated HTTP is the only real identity here. A
        ticket that no longer resolves spends the connection's claim to one
        rather than letting it inherit whatever the handshake offered.
        """
        if hello.authTicket is None:
            return handshake_user_id
        owner = realtime_tickets.consume(hello.authTicket)
        if owner is None:
            logger.warning("realtime: an identity ticket was spent, expired, or never existed")
        return owner

    async def handle(self, websocket: WebSocket, *, user_id: str | None = None) -> None:
        await websocket.accept()
        session: LiveSession | None = None
        try:
            first = await asyncio.wait_for(
                websocket.receive_json(), timeout=self.settings.realtime_idle_timeout_seconds
            )
            hello = ClientHello.model_validate(first)
            session = LiveSession(hello=hello, user_id=self._resolve_identity(hello, user_id))
            logger.info(
                "realtime: <<< session.hello mode=%s companion=%s identified=%s",
                hello.providerMode,
                hello.companionId,
                session.user_id is not None,
            )
            await self._send(
                websocket,
                session,
                "session.ready",
                {
                    "protocolVersion": self.settings.realtime_protocol_version,
                    "sampleRate": 16_000,
                    "channels": 1,
                    "sampleFormat": "pcm-s16le",
                    "frameDurationMs": [20, 40],
                    "maxFrameBytes": self.settings.realtime_max_frame_bytes,
                    "providerMode": hello.providerMode,
                    "languageMode": hello.languageMode,
                },
            )
            while True:
                # A client mid-turn sends nothing: it waits for her audio. Applying
                # the idle timer there closed the socket 35s after audio.commit, so
                # every tts.audio frame was written to a dead connection and she
                # appeared mute while synthesis kept succeeding server-side.
                turn_in_flight = session.processing is not None and not session.processing.done()
                quiet_limit = (
                    self.settings.realtime_turn_timeout_seconds
                    if turn_in_flight
                    else self.settings.realtime_idle_timeout_seconds
                )
                message = await asyncio.wait_for(websocket.receive(), timeout=quiet_limit)
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is None:
                    logger.warning("realtime: binary received without JSON descriptor — BINARY_DESCRIPTOR_REQUIRED sent")
                    await self._error(websocket, session, "BINARY_DESCRIPTOR_REQUIRED", False)
                    continue
                msg_type = ""
                try:
                    import json as _json
                    msg_type = _json.loads(message["text"]).get("type", "?")
                except Exception:
                    pass
                logger.info("realtime: <<< %s", msg_type)
                await self._control(websocket, session, message["text"])
        except WebSocketDisconnect:
            pass
        except TimeoutError:
            logger.info("realtime: no client message within the silence window; reclaiming socket")
        except ValidationError as e:
            logger.error("realtime: ClientHello validation failed: %s", e)
            await self._error(websocket, session, "PROTOCOL_MESSAGE_INVALID", False)
        finally:
            if session and session.processing:
                session.processing.cancel()
                with suppress(asyncio.CancelledError):
                    await session.processing
            with suppress(RuntimeError):
                await websocket.close()

    async def _control(self, websocket: WebSocket, session: LiveSession, raw: str) -> None:
        import json

        try:
            value = json.loads(raw)
            message_type = value.get("type")
        except (json.JSONDecodeError, AttributeError):
            await self._error(websocket, session, "PROTOCOL_MESSAGE_INVALID", False)
            return
        if message_type == "ping":
            await self._send(websocket, session, "pong", {"echo": value.get("sentAtMs")})
            return
        if message_type == "session.close":
            await websocket.close(code=1000)
            return
        if message_type == "interrupt":
            await self._interrupt(websocket, session, int(value.get("generation", -1)))
            return
        if message_type == "audio.start":
            generation = int(value.get("generation", -1))
            if generation < session.hello.generation:
                await self._send(
                    websocket, session, "event.ignored", {"reason": "stale-generation"}
                )
                return
            if session.processing and generation > session.hello.generation:
                await self._interrupt(websocket, session, generation)
            session.hello.generation = generation
            session.expected_sequence = 0
            session.audio.clear()
            session.speech_detected = False
            session.partial_sent = False
            await self._send(websocket, session, "audio.started", {})
            return
        if message_type == "audio.frame":
            descriptor = FrameDescriptor.model_validate(value)
            try:
                async with asyncio.timeout(
                    self.settings.realtime_frame_pair_timeout_seconds
                ):
                    binary_message = await websocket.receive()
            except TimeoutError:
                await self._error(websocket, session, "AUDIO_FRAME_MISSING", False)
                return
            frame = binary_message.get("bytes")
            if frame is None or len(frame) != descriptor.byteLength or len(frame) % 2:
                await self._error(websocket, session, "AUDIO_FRAME_INVALID", False)
                return
            if descriptor.generation != session.hello.generation:
                await self._send(
                    websocket, session, "event.ignored", {"reason": "stale-generation"}
                )
                return
            if descriptor.sequence < session.expected_sequence:
                await self._send(websocket, session, "event.ignored", {"reason": "duplicate-frame"})
                return
            if descriptor.sequence > session.expected_sequence:
                # A dropped frame must not end the turn. expected_sequence is
                # never advanced by the reject path, so erroring here instead
                # made every later frame gap as well — one loss killed the rest
                # of the capture. Skip ahead and keep the audio we did get.
                await self._send(
                    websocket,
                    session,
                    "event.ignored",
                    {
                        "reason": "sequence-resynced",
                        "droppedFrames": descriptor.sequence - session.expected_sequence,
                    },
                )
                session.expected_sequence = descriptor.sequence
            if len(session.audio) + len(frame) > self.settings.realtime_max_buffer_bytes:
                await self._error(websocket, session, "AUDIO_BUFFER_LIMIT", False)
                return
            session.audio.extend(frame)
            session.expected_sequence += 1
            session.speech_detected = session.speech_detected or _has_speech(frame)
            if (
                session.speech_detected
                and not session.partial_sent
                and session.hello.providerMode == "mock"
            ):
                session.partial_sent = True
                await self._send(
                    websocket,
                    session,
                    "stt.partial",
                    {"text": "नमस्ते हिना…", "provider": "mock-stt-live-v1"},
                )
            return
        if message_type == "audio.commit":
            commit = CommitMessage.model_validate(value)
            if commit.generation != session.hello.generation:
                await self._send(
                    websocket, session, "event.ignored", {"reason": "stale-generation"}
                )
                return
            turn_audio = bytes(session.audio)
            session.audio.clear()
            session.expected_sequence = 0
            session.speech_detected = False
            session.partial_sent = False
            if _is_dead_silence(turn_audio):
                # All-zero capture is never speech, even if the frontend VAD
                # fired on a glitch. Reject before any provider call.
                await self._error(
                    websocket, session, "AUDIO_NO_SIGNAL", True, commit.generation
                )
                return
            if session.processing and not session.processing.done():
                session.processing.cancel()
                with suppress(asyncio.CancelledError):
                    await session.processing
            session.turn += 1
            session.processing = asyncio.create_task(
                self._process_turn(websocket, session, commit, turn_audio), name=f"live-turn-{session.turn}"
            )
            return
        await self._error(websocket, session, "PROTOCOL_MESSAGE_UNSUPPORTED", False)

    def _live_voice_stream_enabled(self, provider_mode: str) -> bool:
        """Whether this turn may speak over the synthesis socket.

        Off for mock/local (they have no socket) and for an install that has
        configured a different voice vendor, so a preference for another voice
        is never silently overridden.
        """
        if provider_mode in {"mock", "local"}:
            return False
        return (
            self.settings.elevenlabs_transport == "websocket"
            and self.settings.elevenlabs_configured
            and self.settings.voice_provider in {"auto", "elevenlabs"}
        )

    async def _open_live_voice_stream(
        self,
        session: LiveSession,
        *,
        seed_text: str,
        rate: float,
        delivery_mode: str,
    ) -> ElevenLabsSpeechStream | None:
        """Warm one synthesis socket for this turn, or resolve to None.

        This runs concurrently with the brain. The seed text is the user's own
        words, which is what the reply is almost always written in, so the model
        that can actually pronounce the turn is chosen before the turn exists.
        A model that turns out to be wrong for the reply is corrected on the
        next turn rather than mid-utterance — changing models mid-sentence
        changes the voice the listener is already hearing.
        """
        try:
            provider = self.service.router.tts(
                session.hello.providerMode, session.hello.companionId
            )
            if not isinstance(provider, ElevenLabsWebSocketStreamingProvider):
                return None
            voice_id = (
                self.settings.elevenlabs_hiro_voice_id
                if session.hello.companionId == "hiro"
                else self.settings.elevenlabs_hinaa_voice_id
            )
            model = choose_live_tts_model(
                seed_text,
                configured_model=self.settings.elevenlabs_model_id,
                fast_model=self.settings.elevenlabs_tts_model_fast,
                nepali_model=self.settings.elevenlabs_tts_model_nepali,
            )
            stream = await asyncio.wait_for(
                provider.open_speech_stream(
                    voice=voice_id,
                    model_id=model,
                    rate=rate,
                    delivery_mode=delivery_mode,
                    companion_id=session.hello.companionId,
                ),
                timeout=self.settings.voice_socket_timeout_seconds,
            )
            logger.info(
                "realtime: voice socket ready (model=%s voice=%s)",
                model,
                voice_id[:4],
            )
            return stream
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.info(
                "realtime: voice socket unavailable; speaking phrase by phrase",
                exc_info=True,
            )
            return None

    async def _process_turn(
        self,
        websocket: WebSocket,
        session: LiveSession,
        commit: CommitMessage,
        turn_audio: bytes | None = None,
    ) -> None:
        generation = session.hello.generation
        turn_started = perf_counter()
        pcm = turn_audio if turn_audio is not None else bytes(session.audio)
        # Declared before the try so the finally below can always reach them: a
        # voice socket or speaker task that outlives its turn keeps a vendor
        # connection running after barge-in, a timeout, or a failed STT call.
        voice_socket_task: asyncio.Task[ElevenLabsSpeechStream | None] | None = None
        live_stream: ElevenLabsSpeechStream | None = None
        ws_pump: asyncio.Task[None] | None = None
        speech_tail: asyncio.Task[None] | None = None
        try:
            # Notify frontend: pipeline is processing
            await self._send_current(
                websocket, session, generation,
                "voice.pipeline",
                {"stage": "transcribing", "detail": "Audio received, transcribing…"},
            )
            stt_started = perf_counter()
            if session.hello.providerMode == "mock":
                transcript = (
                    commit.mockTranscript
                    or "Mock microphone demo transcript. Real speech recognition is not active."
                )
                stt_provider = "mock-stt-live-v1"
            elif commit.mockTranscript and session.hello.providerMode in {"local", "groq"}:
                transcript = commit.mockTranscript
                stt_provider = f"{session.hello.providerMode}-stt-scripted-v1"
            else:
                async with asyncio.timeout(self.settings.voice_stt_timeout_seconds):
                    stt_result = await self.service.transcribe(
                        pcm, session.hello.language, session.hello.providerMode
                    )
                transcript, stt_provider = stt_result.value, stt_result.provider
            if not transcript.strip():
                audio_bytes = len(pcm)
                logger.info("realtime: STT returned empty transcript (%d audio bytes, provider=%s)", audio_bytes, stt_provider)
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "voice.error",
                    {
                        "code": "STT_EMPTY_TRANSCRIPT",
                        "message": "I detected audio but could not understand the words. Try speaking closer to the microphone or use push-to-talk.",
                        "provider": stt_provider,
                        "audioBytes": audio_bytes,
                    },
                )
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "turn.cancelled",
                    {"cancelledGeneration": generation, "generation": generation, "reason": "STT_EMPTY_TRANSCRIPT"},
                )
                return
            stt_ms = int((perf_counter() - stt_started) * 1000)
            await self._send_current(
                websocket,
                session,
                generation,
                "stt.final",
                {"text": transcript, "provider": stt_provider, "latencyMs": stt_ms},
            )
            await self._send_current(websocket, session, generation, "assistant.thinking", {})
            await self._send_current(
                websocket, session, generation,
                "voice.pipeline",
                {"stage": "brain", "detail": f"Transcript: {transcript[:80]}…"},
            )
            llm_started = perf_counter()
            first_delta_ms: int | None = None
            sentence_tasks: list[tuple[str, asyncio.Task]] = []
            sentence_buffer = ""
            tts_latency_ms: list[int] = []
            # Browser fallback speech needs the final complete spoken text. Real
            # configured voice output can safely begin on a stable clause while
            # later text continues to stream, as long as delivery remains ordered.
            stream_real_audio = session.hello.providerMode in {
                "real", "openai", "custom", "cx-gateway", "agent-router", "claude", "qwen", "codecraft"
            } or (session.hello.providerMode == "groq" and self.settings.azure_configured)
            streamed_delivery_tail: asyncio.Task[None] | None = None

            voice = resolve_voice(
                session.hello.companionId,
                self.settings.azure_speech_female_voice,
                self.settings.azure_speech_male_voice,
            )
            tuning = resolve_calibration(session.hello.calibration)
            effective_rate = tuning.rate
            effective_pitch = tuning.pitch_semitones
            effective_volume = tuning.volume

            # ONE consistent delivery mode for the WHOLE turn. Per-sentence
            # modes made her voice change tone between every sentence (warm →
            # professional → celebratory) which sounds broken, not expressive.
            # A real person holds a steady tone; emotion lives in the words.
            voice_plan = plan_voice_performance(
                user_text=transcript,
                reply_text="",
                depth="conversational",
            )

            async def emit_speech(
                phrase: str,
                task: asyncio.Task,
                *,
                segment: int,
                segments: int,
                streaming: bool,
            ) -> None:
                tts_started = perf_counter()
                try:
                    speech = await task
                except Exception as err:
                    logger.error("TTS synthesis failed for segment %d: %s", segment, err)
                    return
                tts_ms = int((perf_counter() - tts_started) * 1000)
                tts_latency_ms.append(tts_ms)
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "tts.audio",
                    {
                        "segment": segment,
                        "segments": segments,
                        "streaming": streaming,
                        "text": phrase,
                        "audioBase64": base64.b64encode(speech.value).decode("ascii"),
                        "mediaType": _tts_media_type(
                            speech.provider, self.settings.elevenlabs_output_format
                        ),
                        "provider": speech.provider,
                        "requestedVoice": voice,
                        "actualVoice": voice
                        if session.hello.providerMode in {"real", "openai", "custom", "cx-gateway", "agent-router", "claude", "qwen", "codecraft"}
                        or (session.hello.providerMode == "groq" and self.settings.azure_configured)
                        else f"{session.hello.providerMode}-tone",
                        "calibration": session.hello.calibration,
                        "voiceMode": voice_plan.mode,
                        "rate": effective_rate,
                        "pitchSemitones": effective_pitch,
                        "volume": effective_volume,
                        "latencyMs": tts_ms,
                    },
                )

            def queue_streamed_speech(phrase: str, task: asyncio.Task) -> None:
                nonlocal streamed_delivery_tail
                previous = streamed_delivery_tail
                segment = len(sentence_tasks) - 1

                async def deliver_after_previous() -> None:
                    if previous is not None:
                        with suppress(Exception):
                            await previous
                    await emit_speech(
                        phrase,
                        task,
                        segment=segment,
                        segments=0,
                        streaming=True,
                    )

                streamed_delivery_tail = asyncio.create_task(deliver_after_previous())

            # ── One synthesis socket for the whole turn, opened underneath the
            # brain's first token ────────────────────────────────────────────
            # The per-phrase path can only hand over audio once a phrase has been
            # synthesized in full. This socket opens the moment STT lands, so the
            # vendor handshake and setup frame run concurrently with the model
            # thinking, and audio starts streaming the instant a clause exists.
            # A socket that cannot open resolves to None, which sends the turn
            # down the per-phrase path below — voice never depends on it.
            voice_socket_task: asyncio.Task[ElevenLabsSpeechStream | None] | None = None
            if self._live_voice_stream_enabled(session.hello.providerMode):
                voice_socket_task = asyncio.create_task(
                    self._open_live_voice_stream(
                        session,
                        seed_text=transcript,
                        rate=effective_rate,
                        delivery_mode=voice_plan.mode,
                    ),
                    name="live-voice-socket",
                )
            # Resolved on the first phrase: by then the socket task has had the
            # model's entire first-token time to finish.
            # One decision for the whole turn. Mixing transports mid-utterance
            # would let audio for a later phrase be sent before an earlier one,
            # which is exactly the seam listeners hear as a glitch.
            decided_voice_path: list[str | None] = [None]
            # How much was handed to the socket, and how much came back — the
            # status reported at turn end is counted from these, not assumed.
            ws_text_phrases = 0
            ws_audio_chunks = 0

            async def current_voice_stream() -> ElevenLabsSpeechStream | None:
                nonlocal live_stream
                if voice_socket_task is None:
                    return None
                if live_stream is None:
                    live_stream = await voice_socket_task
                return live_stream

            async def push_chunk_to_client(
                stream: ElevenLabsSpeechStream, chunk: Any
            ) -> None:
                """One socket audio frame, in order, carrying its own timing."""
                nonlocal ws_audio_chunks
                if not chunk.audio:
                    return
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "tts.audio.chunk",
                    {
                        "sequence": ws_audio_chunks,
                        "text": chunk.text_echo,
                        "audioBase64": base64.b64encode(chunk.audio).decode("ascii"),
                        "mediaType": "audio/pcm",
                        "sampleRate": 24_000,
                        # Raw vendor timing alongside the audio it describes, so
                        # the client can place words against the schedule it is
                        # actually playing instead of re-guessing from characters.
                        "vendorAlignment": (
                            chunk.alignment.to_events() if chunk.alignment else None
                        ),
                        "provider": stream.model_id,
                        "requestedVoice": stream.voice_id,
                        "actualVoice": stream.voice_id,
                        "calibration": session.hello.calibration,
                        "voiceMode": voice_plan.mode,
                        "rate": effective_rate,
                        "pitchSemitones": effective_pitch,
                        "volume": effective_volume,
                    },
                )
                ws_audio_chunks += 1

            async def pump_voice_audio(stream: ElevenLabsSpeechStream) -> None:
                """Drain socket audio to the client as it arrives."""
                try:
                    async for chunk in stream.chunks():
                        await push_chunk_to_client(stream, chunk)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning("realtime: voice socket pump stopped", exc_info=True)

            async def speak_over_socket(phrase: str) -> None:
                nonlocal ws_text_phrases
                stream = await current_voice_stream()
                if stream is None:
                    return
                try:
                    await stream.send_text_delta(phrase, flush=False)
                except Exception:
                    logger.warning(
                        "realtime: could not hand a phrase to the voice socket",
                        exc_info=True,
                    )
                    return
                ws_text_phrases += 1
                start_audio_pump(stream)

            async def speak_phrase(phrase: str) -> None:
                """Say one phrase on whichever transport this turn actually got.

                The transport is decided on the first phrase and held for the
                whole turn; ordering comes from the caller's task chain, which is
                what keeps `sentence_tasks` in phrase order for the delivery loop.
                """
                if decided_voice_path[0] is None:
                    if voice_socket_task is None:
                        decided_voice_path[0] = "http"
                    else:
                        decided_voice_path[0] = (
                            "ws" if await current_voice_stream() is not None else "http"
                        )
                if decided_voice_path[0] == "ws":
                    await speak_over_socket(phrase)
                    return
                task = asyncio.create_task(
                    self.service.synthesize_text(
                        phrase,
                        session.hello.companionId,
                        session.hello.providerMode,
                        session.hello.calibration,
                        rate=effective_rate,
                        pitch_semitones=effective_pitch,
                        volume=effective_volume,
                        delivery_mode=voice_plan.mode,
                        live=True,
                    )
                )
                sentence_tasks.append((phrase, task))
                if stream_real_audio:
                    queue_streamed_speech(phrase, task)

            def schedule_phrase(phrase: str) -> None:
                """Queue one phrase behind the previous one, never out of order."""
                nonlocal speech_tail
                previous = speech_tail

                async def run_after_previous() -> None:
                    if previous is not None:
                        with suppress(Exception):
                            await previous
                    await speak_phrase(phrase)

                speech_tail = asyncio.create_task(
                    run_after_previous(), name="live-speech-phrase"
                )

            def start_audio_pump(stream: ElevenLabsSpeechStream) -> None:
                nonlocal ws_pump
                if ws_pump is None:
                    ws_pump = asyncio.create_task(
                        pump_voice_audio(stream), name="live-voice-pump"
                    )

            # One converter for both surfaces: what he sees streaming in and what
            # she is about to speak come off the same deltas.
            notation_stream = MathNotationStream()

            async def emit_delta(delta: str) -> None:
                nonlocal first_delta_ms, sentence_buffer
                delta = ascii_math(notation_stream.feed(delta))
                if not delta:
                    return
                # She is told to address him this way, and on the measured turn it
                # landed mid-reply, so every chunk goes through the same rule the
                # audio uses rather than just the first one.
                delta = strip_greeting(delta)
                if not delta:
                    return
                if first_delta_ms is None:
                    first_delta_ms = int((perf_counter() - llm_started) * 1000)
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "assistant.text.delta",
                    {"delta": delta},
                )
                sentence_buffer += delta
                if spoken_phrase_is_complete(sentence_buffer, is_first=len(sentence_tasks) == 0):
                    phrase_text = speech_text_for_tts(sentence_buffer.strip())
                    sentence_buffer = ""
                    if phrase_text and len(phrase_text) >= 2:
                        # One ordered speaker for the whole turn: the socket path
                        # streams as she says it, the per-phrase path synthesizes
                        # concurrently and delivers in order.
                        schedule_phrase(phrase_text)

            turn_lang = "hi-IN" if session.hello.language in ("auto", "mixed") else session.hello.language
            plan_result = await self.service.create_live_plan(
                TurnRequest(
                    sessionId=session.hello.sessionId,
                    text=transcript,
                    companionId=session.hello.companionId,
                    language=turn_lang,
                    providerMode=session.hello.providerMode,
                    brainModel=session.hello.brainModel,
                    responseMode="concise_voice",
                    visibleActions=commit.visibleActions,
                ),
                emit_delta,
                user_id=session.user_id,
            )
            llm_ms = int((perf_counter() - llm_started) * 1000)
            # Whatever was still held back needs a resolving delta that never
            # came. Send it and let the trailing-phrase block below speak it.
            tail = ascii_math(notation_stream.flush())
            if tail:
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "assistant.text.delta",
                    {"delta": tail},
                )
                sentence_buffer += tail
            plan_payload = plan_result.value.model_dump()
            # A surface that paints the finished reply from the plan would put the
            # greeting right back after the deltas stopped showing it.
            if isinstance(plan_payload.get("spokenText"), str):
                plan_payload["spokenText"] = strip_greeting(
                    plan_payload["spokenText"]
                )
            await self._send_current(
                websocket,
                session,
                generation,
                "assistant.plan",
                {"plan": plan_payload, "provider": plan_result.provider},
            )

            # Pick up any trailing text buffer
            if sentence_buffer.strip():
                phrase_text = speech_text_for_tts(sentence_buffer.strip())
                sentence_buffer = ""
                if phrase_text and len(phrase_text) >= 2:
                    schedule_phrase(phrase_text)

            # Every phrase the brain produced is now queued; let the ordered
            # speaker finish handing them to the voice before deciding whether
            # anything is still missing. Reading `sentence_tasks` before this
            # drain is what used to re-speak the whole reply over the fallback.
            if speech_tail is not None:
                await speech_tail

            # Fallback if nothing has been spoken at all: a non-streaming brain,
            # a socket that opened but carried no deltas, or every phrase send
            # that failed. Nothing here runs when the voice already spoke.
            if not sentence_tasks and ws_text_phrases == 0:
                spoken = speech_text_for_tts(plan_result.value.spokenText)
                phrases = segment_phrases(spoken)[:35]
                for phrase in phrases:
                    task = asyncio.create_task(
                        self.service.synthesize_text(
                            phrase,
                            session.hello.companionId,
                            session.hello.providerMode,
                            session.hello.calibration,
                            rate=effective_rate,
                            pitch_semitones=effective_pitch,
                            volume=effective_volume,
                            delivery_mode=voice_plan.mode,
                            live=True,
                        )
                    )
                    sentence_tasks.append((phrase, task))

            if decided_voice_path[0] == "ws":
                await self._send_current(
                    websocket, session, generation,
                    "voice.pipeline",
                    {
                        "stage": "tts",
                        "detail": f"streaming {ws_text_phrases} phrases over the voice socket",
                    },
                )
                # Closing the socket flushes the tail clause the generation
                # schedule had not yet reached; the pump then delivers every
                # remaining audio frame in the order the vendor produced it.
                socket = await current_voice_stream()
                if socket is not None:
                    await socket.close()
                if ws_pump is not None:
                    await ws_pump
            else:
                await self._send_current(
                    websocket, session, generation,
                    "voice.pipeline",
                    {"stage": "tts", "detail": f"{len(sentence_tasks)} phrases to synthesize"},
                )
                if streamed_delivery_tail is not None:
                    # Wait only for the ordered delivery tail. Each real-audio clause
                    # has already been synthesized concurrently with the model stream.
                    await streamed_delivery_tail
                else:
                    total_segments = len(sentence_tasks)
                    for index, (phrase, task) in enumerate(sentence_tasks):
                        await emit_speech(
                            phrase,
                            task,
                            segment=index,
                            segments=total_segments,
                            streaming=False,
                        )

            # Determine TTS status for the frontend, from whichever transport
            # actually carried this turn — frames delivered over the socket are
            # the same truth as a synthesis task that returned audio.
            socket_stream = live_stream
            socket_error = socket_stream.error if socket_stream is not None else None
            if decided_voice_path[0] == "ws":
                tts_count = ws_text_phrases
                tts_succeeded = ws_audio_chunks
                tts_failed = 1 if socket_error is not None else 0
            else:
                tts_count = len(sentence_tasks)
                tts_succeeded = sum(
                    1 for _, t in sentence_tasks if t.done() and t.exception() is None
                )
                tts_failed = sum(
                    1 for _, t in sentence_tasks if t.done() and t.exception() is not None
                )
            tts_status = (
                "not_requested" if tts_count == 0
                else "completed" if tts_succeeded > 0 and tts_failed == 0
                else "partial" if tts_succeeded > 0 and tts_failed > 0
                else "failed"
            )
            output_mode = "text_and_audio" if tts_succeeded > 0 else "text"
            await self._send_current(
                websocket,
                session,
                generation,
                "turn.complete",
                {
                    "sttMs": stt_ms,
                    "llmMs": llm_ms,
                    "llmFirstDeltaMs": first_delta_ms,
                    "ttsMs": sum(tts_latency_ms),
                    "totalMs": int((perf_counter() - turn_started) * 1000),
                    "targetsAreGoals": True,
                    "outputMode": output_mode,
                    "ttsRequested": tts_count > 0,
                    "ttsStatus": tts_status,
                    "ttsChunksTotal": tts_count,
                    "ttsChunksSucceeded": tts_succeeded,
                    # Which transport carried the audio, so the diagnostics
                    # drawer and the latency report can attribute the numbers.
                    "ttsTransport": (
                        "websocket" if decided_voice_path[0] == "ws" else "phrases"
                    ),
                },
            )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            logger.warning("realtime: turn timed out after %.1fs", self.settings.voice_total_turn_timeout_seconds)
            await self._send_current(
                websocket, session, generation,
                "voice.error",
                {
                    "code": "VOICE_TURN_TIMEOUT",
                    "message": "The voice response took too long. Please try again.",
                },
            )
            await self._error(websocket, session, "VOICE_TURN_TIMEOUT", True, generation)
        except HinaaError as error:
            logger.warning(
                "realtime: turn failed with HinaaError code=%s retryable=%s",
                error.code,
                error.retryable,
            )
            await self._send_current(
                websocket,
                session,
                generation,
                "turn.cancelled",
                {"cancelledGeneration": generation, "generation": generation, "reason": error.code},
            )
            await self._error(websocket, session, error.code, error.retryable, generation)
        except Exception:
            logger.exception("realtime: turn failed with an unhandled exception")
            await self._send_current(
                websocket,
                session,
                generation,
                "turn.cancelled",
                {"cancelledGeneration": generation, "generation": generation, "reason": "REALTIME_TURN_FAILED"},
            )
            await self._error(websocket, session, "REALTIME_TURN_FAILED", True, generation)
        finally:
            # Nothing may outlive its turn. A socket left open keeps a vendor
            # connection — and its billing — running after barge-in or a
            # timeout, and an unfinished warm-up task would be destroyed as
            # pending by the event loop.
            if voice_socket_task is not None:
                if not voice_socket_task.done():
                    voice_socket_task.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await voice_socket_task
                elif live_stream is None:
                    # Opened but never spoken to (an empty reply, or a turn that
                    # failed first): still a live connection, so it is closed.
                    try:
                        opened = voice_socket_task.result()
                    except Exception:
                        opened = None
                    if opened is not None:
                        live_stream = opened
            if live_stream is not None and not live_stream.finished:
                with suppress(Exception):
                    await live_stream.abort()
            for helper in (ws_pump, speech_tail):
                if helper is not None and not helper.done():
                    helper.cancel()
                    with suppress(asyncio.CancelledError, Exception):
                        await helper
            session.audio.clear()
            session.processing = None

    async def _interrupt(self, websocket: WebSocket, session: LiveSession, generation: int) -> None:
        previous = session.hello.generation
        session.hello.generation = max(previous + 1, generation)
        if session.processing and not session.processing.done():
            session.processing.cancel()
            with suppress(asyncio.CancelledError):
                await session.processing
        session.processing = None
        session.audio.clear()
        await self._send(
            websocket,
            session,
            "turn.cancelled",
            {"cancelledGeneration": previous, "generation": session.hello.generation},
        )

    async def _send_current(
        self,
        websocket: WebSocket,
        session: LiveSession,
        generation: int,
        event_type: str,
        payload: dict[str, object],
    ) -> None:
        if generation != session.hello.generation:
            return
        await self._send(websocket, session, event_type, payload)

    async def _error(
        self,
        websocket: WebSocket,
        session: LiveSession | None,
        code: str,
        retryable: bool,
        generation: int | None = None,
    ) -> None:
        if session is None:
            await websocket.send_json({"type": "error", "code": code, "retryable": retryable})
            return
        await self._send(
            websocket,
            session,
            "error",
            {"code": code, "retryable": retryable, "message": self._user_message(code)},
            generation,
        )

    async def _send(
        self,
        websocket: WebSocket,
        session: LiveSession,
        event_type: str,
        payload: dict[str, object],
        generation: int | None = None,
    ) -> None:
        async with session.send_lock:
            await websocket.send_json(
                {
                    "type": event_type,
                    "protocolVersion": self.settings.realtime_protocol_version,
                    "sessionId": session.hello.sessionId,
                    "turn": session.turn,
                    "turnId": f"turn-{session.turn}-{session.hello.generation}",
                    "generation": session.hello.generation if generation is None else generation,
                    "serverAtMs": _timestamp_ms(),
                    **payload,
                }
            )

    @staticmethod
    def _user_message(code: str) -> str:
        messages = {
            "AUDIO_NO_SIGNAL": "No clear speech was detected. Try again or use text.",
            "AUDIO_SEQUENCE_GAP": "A microphone frame was lost; listening can restart safely.",
            "AUDIO_FRAME_MISSING": "One microphone frame never arrived; HINAA kept the rest of your words.",
            "AUDIO_BUFFER_LIMIT": "The live recording reached its safety limit.",
            "PROVIDER_CONFIGURATION_MISSING": (
                "The selected brain is not configured in the local backend environment."
            ),
            "PROVIDER_KEY_INVALID": "The selected brain rejected its local backend API key.",
            "PROVIDER_RATE_LIMIT": "The selected brain is rate-limited; try again shortly or choose another configured brain.",
            "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE": "The selected gateway has no available upstream account right now.",
            "PROVIDER_TIMEOUT": "The selected brain did not finish before HINAA’s live safety timeout.",
            "PROVIDER_UNAVAILABLE": "The selected brain could not complete this live turn. Check the local backend diagnostic status, then retry.",
            "MODEL_RESPONSE_INVALID": "The selected brain returned an unusable response plan; no fallback reply was spoken.",
        }
        return messages.get(
            code, "The live turn stopped safely. Mock and text controls remain available."
        )
