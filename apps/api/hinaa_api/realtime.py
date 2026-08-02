from __future__ import annotations

import asyncio
import base64
import re
import struct
from contextlib import suppress
from dataclasses import dataclass, field
from time import monotonic_ns, perf_counter
from typing import Annotated, Literal

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import Field, ValidationError

from .config import Settings
from .errors import HinaaError
from .models import CompanionId, Language, ProviderMode, StrictModel, TurnRequest
from .providers.azure_speech import AzureContinuousRecognizer
from .services import ConversationService
from .voice_profiles import resolve_calibration, resolve_voice


class ClientHello(StrictModel):
    type: Literal["session.hello"]
    protocolVersion: Literal["1.0"]
    sessionId: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
    companionId: CompanionId = "hinaa"
    providerMode: ProviderMode = "mock"
    generation: Annotated[int, Field(ge=0, le=1_000_000)] = 0
    language: Language = "mixed"
    languageMode: Literal["fixed-ne-NP", "auto"] = "fixed-ne-NP"
    calibration: Literal["natural", "soft", "lively"] = "natural"
    brainModel: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None


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
    mockTranscript: Annotated[str | None, Field(min_length=1, max_length=500)] = None


@dataclass(slots=True)
class LiveSession:
    hello: ClientHello
    expected_sequence: int = 0
    audio: bytearray = field(default_factory=bytearray)
    speech_detected: bool = False
    partial_sent: bool = False
    turn: int = 0
    processing: asyncio.Task[None] | None = None
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    live_stt: AzureContinuousRecognizer | None = None


def _timestamp_ms() -> float:
    return monotonic_ns() / 1_000_000


def _has_speech(pcm: bytes) -> bool:
    if len(pcm) < 2:
        return False
    count = len(pcm) // 2
    samples = struct.unpack(f"<{count}h", pcm[: count * 2])
    energy = sum(sample * sample for sample in samples) / count
    return energy**0.5 >= 220


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

    async def handle(self, websocket: WebSocket) -> None:
        await websocket.accept()
        session: LiveSession | None = None
        try:
            first = await asyncio.wait_for(
                websocket.receive_json(), timeout=self.settings.realtime_idle_timeout_seconds
            )
            hello = ClientHello.model_validate(first)
            session = LiveSession(hello=hello)
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
                message = await asyncio.wait_for(
                    websocket.receive(), timeout=self.settings.realtime_idle_timeout_seconds
                )
                if message.get("type") == "websocket.disconnect":
                    break
                if message.get("text") is None:
                    await self._error(websocket, session, "BINARY_DESCRIPTOR_REQUIRED", False)
                    continue
                await self._control(websocket, session, message["text"])
        except WebSocketDisconnect, TimeoutError:
            pass
        except ValidationError:
            await self._error(websocket, session, "PROTOCOL_MESSAGE_INVALID", False)
        finally:
            if session and session.processing:
                session.processing.cancel()
                with suppress(asyncio.CancelledError):
                    await session.processing
            if session and session.live_stt:
                with suppress(Exception):
                    await session.live_stt.cancel()
            with suppress(RuntimeError):
                await websocket.close()

    async def _control(self, websocket: WebSocket, session: LiveSession, raw: str) -> None:
        import json

        try:
            value = json.loads(raw)
            message_type = value.get("type")
        except json.JSONDecodeError, AttributeError:
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
            if session.processing:
                await self._interrupt(websocket, session, generation)
            session.hello.generation = generation
            session.expected_sequence = 0
            session.audio.clear()
            session.speech_detected = False
            session.partial_sent = False
            if session.hello.providerMode in {"real", "openai", "custom"} or (
                session.hello.providerMode == "groq" and self.settings.azure_configured
            ):
                session.live_stt = await self.service.start_live_stt(
                    session.hello.language,
                    session.hello.languageMode,
                    session.hello.providerMode,
                )
            await self._send(websocket, session, "audio.started", {})
            return
        if message_type == "audio.frame":
            descriptor = FrameDescriptor.model_validate(value)
            binary_message = await websocket.receive()
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
                await self._error(websocket, session, "AUDIO_SEQUENCE_GAP", True)
                return
            if len(session.audio) + len(frame) > self.settings.realtime_max_buffer_bytes:
                await self._error(websocket, session, "AUDIO_BUFFER_LIMIT", False)
                return
            session.audio.extend(frame)
            if session.live_stt:
                session.live_stt.write(frame)
                await asyncio.sleep(0)
                for event in session.live_stt.pending_events():
                    if event.kind == "partial" and event.text:
                        await self._send(
                            websocket,
                            session,
                            "stt.partial",
                            {"text": event.text, "provider": "azure-speech-continuous"},
                        )
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
            if not session.speech_detected:
                await self._error(websocket, session, "AUDIO_NO_SIGNAL", True)
                return
            if session.processing and not session.processing.done():
                await self._error(websocket, session, "TURN_ALREADY_ACTIVE", True)
                return
            session.turn += 1
            session.processing = asyncio.create_task(
                self._process_turn(websocket, session, commit), name=f"live-turn-{session.turn}"
            )
            return
        await self._error(websocket, session, "PROTOCOL_MESSAGE_UNSUPPORTED", False)

    async def _process_turn(
        self, websocket: WebSocket, session: LiveSession, commit: CommitMessage
    ) -> None:
        generation = session.hello.generation
        turn_started = perf_counter()
        try:
            stt_started = perf_counter()
            if session.hello.providerMode == "mock":
                transcript = (
                    commit.mockTranscript
                    or "Mock microphone demo transcript. Real speech recognition is not active."
                )
                stt_provider = "mock-stt-live-v1"
            elif session.hello.providerMode in {"local", "groq"} and session.live_stt is None:
                if not commit.mockTranscript:
                    raise HinaaError(
                        "LOCAL_STT_UNAVAILABLE",
                        "Local microphone recognition is not installed yet. "
                        "Use text, mock voice mode, or configure HINAA_LOCAL_STT_COMMAND.",
                        503,
                        retryable=False,
                        user_action_required=True,
                    )
                transcript = commit.mockTranscript
                stt_provider = f"{session.hello.providerMode}-stt-scripted-v1"
            else:
                if session.live_stt is None:
                    raise HinaaError(
                        "STT_FAILED", "Live speech recognition is not active.", 409, True
                    )
                stt_result = await session.live_stt.finish()
                session.live_stt = None
                transcript, stt_provider = stt_result.value, stt_result.provider
            if not transcript.strip():
                raise HinaaError("AUDIO_NO_SIGNAL", "No speech was recognized.", 422, True)
            stt_ms = int((perf_counter() - stt_started) * 1000)
            await self._send_current(
                websocket,
                session,
                generation,
                "stt.final",
                {"text": transcript, "provider": stt_provider, "latencyMs": stt_ms},
            )
            await self._send_current(websocket, session, generation, "assistant.thinking", {})
            llm_started = perf_counter()
            first_delta_ms: int | None = None

            async def emit_delta(delta: str) -> None:
                nonlocal first_delta_ms
                if first_delta_ms is None:
                    first_delta_ms = int((perf_counter() - llm_started) * 1000)
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "assistant.text.delta",
                    {"delta": delta},
                )

            plan_result = await self.service.create_live_plan(
                TurnRequest(
                    sessionId=session.hello.sessionId,
                    text=transcript,
                    companionId=session.hello.companionId,
                    language=session.hello.language,
                    providerMode=session.hello.providerMode,
                    brainModel=session.hello.brainModel,
                ),
                emit_delta,
            )
            llm_ms = int((perf_counter() - llm_started) * 1000)
            await self._send_current(
                websocket,
                session,
                generation,
                "assistant.plan",
                {"plan": plan_result.value.model_dump(), "provider": plan_result.provider},
            )
            from .voice_performance import plan_voice_performance, speech_text_for_tts

            voice = resolve_voice(
                session.hello.companionId,
                self.settings.azure_speech_female_voice,
                self.settings.azure_speech_male_voice,
            )
            tuning = resolve_calibration(session.hello.calibration)
            voice_plan = plan_voice_performance(
                user_text=transcript,
                reply_text=plan_result.value.spokenText,
                depth="conversational",
            )
            # Blend session calibration with bounded voice-performance plan.
            effective_rate = max(0.85, min(1.15, tuning.rate * voice_plan.pace))
            effective_pitch = max(
                -2.0, min(2.0, tuning.pitch_semitones + voice_plan.pitch_semitones)
            )
            effective_volume = max(0.75, min(1.0, tuning.volume * voice_plan.volume))
            tts_total = 0
            spoken = speech_text_for_tts(plan_result.value.spokenText)
            phrases = segment_phrases(spoken)
            # Bound queue: avoid unbounded TTS backlog on long replies.
            phrases = phrases[:8]
            for index, phrase in enumerate(phrases):
                tts_started = perf_counter()
                speech = await self.service.synthesize_text(
                    phrase,
                    session.hello.companionId,
                    session.hello.providerMode,
                    session.hello.calibration,
                    rate=effective_rate,
                    pitch_semitones=effective_pitch,
                    volume=effective_volume,
                )
                tts_ms = int((perf_counter() - tts_started) * 1000)
                tts_total += tts_ms
                await self._send_current(
                    websocket,
                    session,
                    generation,
                    "tts.audio",
                    {
                        "segment": index,
                        "segments": len(phrases),
                        "audioBase64": base64.b64encode(speech.value).decode("ascii"),
                        "mediaType": "audio/wav",
                        "provider": speech.provider,
                        "requestedVoice": voice,
                        "actualVoice": voice
                        if session.hello.providerMode in {"real", "openai", "custom"}
                        or (
                            session.hello.providerMode == "groq"
                            and self.settings.azure_configured
                        )
                        else f"{session.hello.providerMode}-tone",
                        "calibration": session.hello.calibration,
                        "voiceMode": voice_plan.mode,
                        "rate": effective_rate,
                        "pitchSemitones": effective_pitch,
                        "volume": effective_volume,
                        "latencyMs": tts_ms,
                    },
                )
            await self._send_current(
                websocket,
                session,
                generation,
                "turn.complete",
                {
                    "sttMs": stt_ms,
                    "llmMs": llm_ms,
                    "llmFirstDeltaMs": first_delta_ms,
                    "ttsMs": tts_total,
                    "totalMs": int((perf_counter() - turn_started) * 1000),
                    "targetsAreGoals": True,
                },
            )
        except asyncio.CancelledError:
            raise
        except HinaaError as error:
            await self._error(websocket, session, error.code, error.retryable, generation)
        except Exception:
            await self._error(websocket, session, "REALTIME_TURN_FAILED", True, generation)

    async def _interrupt(self, websocket: WebSocket, session: LiveSession, generation: int) -> None:
        previous = session.hello.generation
        session.hello.generation = max(previous + 1, generation)
        if session.processing and not session.processing.done():
            session.processing.cancel()
            with suppress(asyncio.CancelledError):
                await session.processing
        if session.live_stt:
            await session.live_stt.cancel()
            session.live_stt = None
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
            "AUDIO_BUFFER_LIMIT": "The live recording reached its safety limit.",
            "PROVIDER_CONFIGURATION_MISSING": (
                "Real providers are not ready; mock mode remains available."
            ),
        }
        return messages.get(
            code, "The live turn stopped safely. Mock and text controls remain available."
        )
