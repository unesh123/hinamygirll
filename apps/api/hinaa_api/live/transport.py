"""Full-duplex WebSocket & REST endpoints for Jarvis Live Mode (/ws/live)."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import sys
import time
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from ..audio import ensure_wav_or_mp3
from ..models import SpeechRequest, TurnRequest
from .asr import StreamingASR, tier_a_installed
from .orchestrator import LiveOrchestrator
from .pc_control import ConfirmationRequiredError, execute_pc_action, register_pc_control_tools
from .tts import SentenceStreamer, tier_a_tts_installed
from .vad import VoiceActivityDetector
from .wake import LiveSessionLifecycle, NoiseSuppressor, WakeWordDetector

logger = logging.getLogger("hinaa.live.transport")


class PcControlExecuteBody(BaseModel):
    action: str = Field(..., min_length=2)
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


async def _synthesize_live_audio(
    text: str,
    *,
    service: Any | None,
    voice_engine: str,
) -> tuple[bytes, str, str]:
    """Synthesize natural neural audio for live call mode with Edge Neural fallback."""
    clean = (text or "").strip()
    if not clean:
        return b"", "audio/mpeg", "empty"
    if voice_engine == "browser":
        return b"", "text/plain", "browser"
    if service is not None:
        try:
            req = SpeechRequest(
                text=clean,
                companionId="hinaa",
                providerMode="auto",
                realtime=True,
                voiceEngine=voice_engine or "thalia",
            )
            res = await service.synthesize(req)
            audio_bytes, mime_type = ensure_wav_or_mp3(res.value, sample_rate=24_000)
            return audio_bytes, mime_type, res.provider
        except Exception as err:
            logger.warning("Live TTS via service failed (%s), falling back to Edge Neural: %s", type(err).__name__, err)

    try:
        from ..providers.edge_tts_provider import EdgeNeuralTTSProvider

        edge = EdgeNeuralTTSProvider()
        res = await edge.synthesize(clean, voice=voice_engine if voice_engine.startswith(("en-", "hi-", "ne-")) else "")
        audio_bytes, mime_type = ensure_wav_or_mp3(res.value, sample_rate=24_000)
        return audio_bytes, mime_type, res.provider
    except Exception as edge_err:
        logger.warning("Live Edge Neural TTS fallback failed: %s", edge_err)
        return b"", "audio/wav", "pcm-fallback"


def create_live_router(service: Any | None = None) -> APIRouter:
    register_pc_control_tools()
    router = APIRouter()

    @router.get("/v1/live/status")
    @router.get("/api/v1/live/status")
    async def live_status() -> dict[str, Any]:
        return {
            "status": "ready",
            "wsPaths": ["/ws/live", "/api/v1/live/ws"],
            "asrTier": "faster-whisper" if tier_a_installed() else "fallback-energy",
            "ttsTier": "local-neural" if tier_a_tts_installed() else "pcm-synthesizer",
            "pcControlPlatform": sys.platform,
            "pcConfirmationRequiredForWrites": True,
        }

    @router.post("/v1/live/pc-control/execute")
    @router.post("/api/v1/live/pc-control/execute")
    async def pc_control_execute(body: PcControlExecuteBody) -> dict[str, Any]:
        try:
            return execute_pc_action(
                body.action,
                body.params,
                confirmed=body.confirmed,
            )
        except ConfirmationRequiredError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    async def _handle_live_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        vad = VoiceActivityDetector()
        asr = StreamingASR()
        tts = SentenceStreamer()
        suppressor = NoiseSuppressor()
        wake = WakeWordDetector()
        lifecycle = LiveSessionLifecycle()
        session_id = f"live_{int(time.time())}_{id(websocket) & 0xFFFF:04x}"
        selected_voice_engine = "thalia"
        tts_speaking = False

        async def _send_json(payload: dict[str, Any]) -> None:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))

        async def _live_chat_fn(utterance: str) -> str:
            clean = utterance.strip()
            if service is None:
                return f"Hey! I heard you loud and clear — {clean}"
            try:
                settings = getattr(service, "settings", None)
                preferred_mode = "auto"
                if settings is not None:
                    if getattr(settings, "gemini_configured", False):
                        preferred_mode = "gemini"
                    elif getattr(settings, "xkiro_configured", False):
                        preferred_mode = "xkiro"
                    elif getattr(settings, "claude_configured", False):
                        preferred_mode = "claude"
                req = TurnRequest(
                    sessionId=session_id,
                    text=clean,
                    companionId="hinaa",
                    providerMode=preferred_mode,
                    responseMode="conversation",
                    voiceEngine=selected_voice_engine if selected_voice_engine != "browser" else None,
                )
                async with asyncio.timeout(12.0):
                    plan_res = await service.create_plan(req)
                return plan_res.value.spokenText or plan_res.value.displayText
            except Exception as exc:
                logger.warning("Live brain turn failed, using fast fallback: %s", exc)
                return f"I caught that — {clean}"

        async def _live_tool_fn(utterance: str, decision: Any) -> str:
            await _send_json({
                "type": "tool.started",
                "toolName": str(getattr(decision, "route", "tool")),
                "label": f"Running {getattr(decision, 'route', 'task').replace('_', ' ')}",
            })
            return await _live_chat_fn(utterance)

        orchestrator = LiveOrchestrator(chat_fn=_live_chat_fn, tool_fn=_live_tool_fn)

        async def _emit_spoken_turn(
            text_in: str,
            *,
            started_t0: float,
            asr_ms: float | None = None,
        ) -> None:
            nonlocal tts_speaking
            lifecycle.transition("thinking")
            await _send_json({"type": "state", "state": "thinking"})

            async def _on_bg_tool_result(followup_text: str) -> None:
                await _send_json({
                    "type": "assistant.spoken",
                    "text": followup_text,
                    "route": "tool_followup",
                    "voice": selected_voice_engine,
                })
                audio_b, mime, prov = await _synthesize_live_audio(
                    followup_text, service=service, voice_engine=selected_voice_engine
                )
                if audio_b:
                    await _send_json({
                        "type": "assistant.audio",
                        "mimeType": mime,
                        "audioBase64": base64.b64encode(audio_b).decode("ascii"),
                        "provider": prov,
                        "voice": selected_voice_engine,
                    })

            outcome = await orchestrator.handle_utterance(text_in, on_tool_result=_on_bg_tool_result)
            spoken = outcome.spoken_intro
            lifecycle.transition("speaking")
            await _send_json({"type": "state", "state": "speaking"})
            await _send_json({
                "type": "assistant.spoken",
                "text": spoken,
                "route": outcome.route.route,
                "voice": selected_voice_engine,
            })

            tts.reset()
            await tts.push_token(spoken)
            await tts.finish()
            tts_speaking = True
            audio_task = asyncio.create_task(
                _synthesize_live_audio(spoken, service=service, voice_engine=selected_voice_engine)
            )
            async for audio_chunk in tts.stream_chunks():
                if not tts_speaking:
                    break
                await websocket.send_bytes(audio_chunk.pcm)
            audio_bytes, mime_type, provider_name = await audio_task
            if tts_speaking and audio_bytes:
                await _send_json({
                    "type": "assistant.audio",
                    "mimeType": mime_type,
                    "audioBase64": base64.b64encode(audio_bytes).decode("ascii"),
                    "provider": provider_name,
                    "voice": selected_voice_engine,
                })
            tts_speaking = False
            total_ms = round((time.perf_counter() - started_t0) * 1000.0, 2)
            payload: dict[str, Any] = {"type": "latency", "totalMs": total_ms, "route": outcome.route.route}
            if asr_ms is not None:
                payload["asrMs"] = asr_ms
            await _send_json(payload)
            lifecycle.transition("listening")
            await _send_json({"type": "state", "state": "listening"})

        await _send_json({"type": "state", "state": lifecycle.state})

        try:
            while True:
                msg = await websocket.receive()
                if msg.get("type") == "websocket.disconnect":
                    break

                if msg.get("bytes") is not None:
                    pcm = suppressor.process(msg["bytes"])
                    vad_res = vad.process_frame(pcm, is_tts_speaking=tts_speaking)
                    asr.push_audio(pcm)

                    if vad_res.event == "barge_in":
                        tts.cancel()
                        tts_speaking = False
                        lifecycle.transition("listening")
                        await _send_json({
                            "type": "tts.stop",
                            "reason": "barge_in",
                            "timestampMs": round(vad_res.timestamp_ms, 2),
                        })
                    elif vad_res.event == "speech_start":
                        lifecycle.transition("listening")
                        await _send_json({"type": "state", "state": "listening", "energy": round(vad_res.energy, 4)})
                    elif vad_res.event == "speech_end":
                        t0 = time.perf_counter()
                        chunk = await asr.flush(is_final=True)
                        await _send_json({
                            "type": "asr.final",
                            "text": chunk.text,
                            "latencyMs": chunk.latency_ms,
                            "tier": chunk.tier,
                        })
                        if chunk.text:
                            await _emit_spoken_turn(chunk.text, started_t0=t0, asr_ms=chunk.latency_ms)
                    continue

                if msg.get("text") is not None:
                    try:
                        data = json.loads(msg["text"])
                    except Exception:
                        data = {"type": "text", "text": msg["text"]}

                    kind = str(data.get("type") or "")
                    if kind == "ping":
                        await _send_json({"type": "pong", "sentAt": data.get("sentAt"), "serverMs": round(time.perf_counter() * 1000.0, 2)})
                    elif kind == "echo":
                        await _send_json({"type": "echo", "payload": data.get("payload")})
                    elif kind == "config":
                        if isinstance(data.get("voiceEngine"), str) and data["voiceEngine"].strip():
                            selected_voice_engine = data["voiceEngine"].strip()
                        await _send_json({"type": "config.ack", "voiceEngine": selected_voice_engine})
                    elif kind == "barge_in":
                        tts.cancel()
                        tts_speaking = False
                        await _send_json({"type": "tts.stop", "reason": "client_barge_in"})
                    elif kind == "wake_check":
                        matched = wake.matches_transcript(str(data.get("text") or ""))
                        if matched:
                            lifecycle.wake()
                        await _send_json({"type": "wake", "matched": matched, "state": lifecycle.state})
                    elif kind in ("text", "audio.transcript"):
                        t0 = time.perf_counter()
                        text_in = str(data.get("text") or "").strip()
                        if not text_in:
                            continue
                        if kind == "audio.transcript" and not bool(data.get("isFinal", True)):
                            await _send_json({"type": "asr.partial", "text": text_in})
                            continue
                        if kind == "audio.transcript":
                            await _send_json({"type": "asr.final", "text": text_in, "latencyMs": 0.0, "tier": "browser-speech"})
                        await _emit_spoken_turn(text_in, started_t0=t0)
        except (WebSocketDisconnect, asyncio.CancelledError):
            pass
        finally:
            tts.cancel()
            orchestrator.cancel_all()

    @router.websocket("/ws/live")
    async def ws_live(websocket: WebSocket) -> None:
        await _handle_live_ws(websocket)

    @router.websocket("/api/v1/live/ws")
    async def ws_live_v1(websocket: WebSocket) -> None:
        await _handle_live_ws(websocket)

    return router
