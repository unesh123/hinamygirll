"""Full-duplex WebSocket & REST endpoints for Jarvis Live Mode (/ws/live)."""

from __future__ import annotations

import asyncio
import json
import sys
import time
from typing import Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .asr import StreamingASR, tier_a_installed
from .orchestrator import LiveOrchestrator
from .pc_control import ConfirmationRequiredError, execute_pc_action, register_pc_control_tools
from .tts import SentenceStreamer, tier_a_tts_installed
from .vad import VoiceActivityDetector
from .wake import LiveSessionLifecycle, NoiseSuppressor, WakeWordDetector


class PcControlExecuteBody(BaseModel):
    action: str = Field(..., min_length=2)
    params: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False


def create_live_router() -> APIRouter:
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
        orchestrator = LiveOrchestrator()
        tts_speaking = False

        async def _send_json(payload: dict[str, Any]) -> None:
            await websocket.send_text(json.dumps(payload, ensure_ascii=False))

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
                            outcome = await orchestrator.handle_utterance(chunk.text)
                            tts.reset()
                            await tts.push_token(outcome.spoken_intro)
                            await tts.finish()
                            tts_speaking = True
                            async for audio_chunk in tts.stream_chunks():
                                await websocket.send_bytes(audio_chunk.pcm)
                            tts_speaking = False
                            total_ms = round((time.perf_counter() - t0) * 1000.0, 2)
                            await _send_json({
                                "type": "latency",
                                "asrMs": chunk.latency_ms,
                                "totalMs": total_ms,
                                "route": outcome.route.route,
                            })
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
                    elif kind == "barge_in":
                        tts.cancel()
                        tts_speaking = False
                        await _send_json({"type": "tts.stop", "reason": "client_barge_in"})
                    elif kind == "wake_check":
                        matched = wake.matches_transcript(str(data.get("text") or ""))
                        if matched:
                            lifecycle.wake()
                        await _send_json({"type": "wake", "matched": matched, "state": lifecycle.state})
                    elif kind == "text":
                        t0 = time.perf_counter()
                        text_in = str(data.get("text") or "").strip()
                        if not text_in:
                            continue
                        lifecycle.transition("thinking")
                        await _send_json({"type": "state", "state": "thinking"})
                        outcome = await orchestrator.handle_utterance(text_in)
                        tts.reset()
                        await tts.push_token(outcome.spoken_intro)
                        await tts.finish()
                        await _send_json({
                            "type": "assistant.spoken",
                            "text": outcome.spoken_intro,
                            "route": outcome.route.route,
                        })
                        async for audio_chunk in tts.stream_chunks():
                            await websocket.send_bytes(audio_chunk.pcm)
                        await _send_json({
                            "type": "latency",
                            "totalMs": round((time.perf_counter() - t0) * 1000.0, 2),
                            "route": outcome.route.route,
                        })
                        lifecycle.transition("listening")
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
