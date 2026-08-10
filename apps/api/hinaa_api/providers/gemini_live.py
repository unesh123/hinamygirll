from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import AsyncIterator, Callable, Awaitable

import websockets

from ..prompts.companions import companion_identity_layer
from ..errors import HinaaError

logger = logging.getLogger("hinaa.gemini_live")

GEMINI_BIDI_WS_URL = "wss://generativelanguage.googleapis.com/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent"


class GeminiLiveSession:
    """Persistent bidirectional WebSocket session connected to Gemini Live API."""

    def __init__(self, api_key: str, model: str = "gemini-2.5-flash", voice_name: str = "Kore") -> None:
        self.api_key = api_key
        self.model = model if model.startswith("models/") else f"models/{model}"
        self.voice_name = voice_name
        self.ws: websockets.WebSocketClientProtocol | None = None
        self.receive_task: asyncio.Task | None = None
        self._on_audio: Callable[[bytes], Awaitable[None]] | None = None
        self._on_text: Callable[[str], Awaitable[None]] | None = None
        self._on_interrupted: Callable[[], Awaitable[None]] | None = None
        self._on_complete: Callable[[], Awaitable[None]] | None = None

    async def connect(
        self,
        companion_id: str = "hinaa",
        on_audio: Callable[[bytes], Awaitable[None]] | None = None,
        on_text: Callable[[str], Awaitable[None]] | None = None,
        on_interrupted: Callable[[], Awaitable[None]] | None = None,
        on_complete: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        self._on_audio = on_audio
        self._on_text = on_text
        self._on_interrupted = on_interrupted
        self._on_complete = on_complete

        url = f"{GEMINI_BIDI_WS_URL}?key={self.api_key}"
        logger.info("Connecting to Gemini Live WebSocket: %s", self.model)
        self.ws = await websockets.connect(url, max_size=10_000_000)

        # Send Setup Handshake
        system_prompt = companion_identity_layer(companion_id)
        setup_payload = {
            "setup": {
                "model": self.model,
                "generationConfig": {
                    "responseModalities": ["AUDIO"],
                    "speechConfig": {
                        "voiceConfig": {
                            "prebuiltVoiceConfig": {
                                "voiceName": self.voice_name
                            }
                        }
                    }
                },
                "systemInstruction": {
                    "parts": [{"text": system_prompt}]
                }
            }
        }
        await self.ws.send(json.dumps(setup_payload))
        logger.info("Sent Gemini Live setup handshake for %s", companion_id)

        # Start background listener
        self.receive_task = asyncio.create_task(self._receive_loop())

    async def send_audio_chunk(self, pcm_bytes: bytes) -> None:
        if not self.ws:
            return
        b64_data = base64.b64encode(pcm_bytes).decode("ascii")
        msg = {
            "realtimeInput": {
                "mediaChunks": [
                    {
                        "mimeType": "audio/pcm;rate=16000",
                        "data": b64_data
                    }
                ]
            }
        }
        await self.ws.send(json.dumps(msg))

    async def send_end_of_turn(self) -> None:
        if not self.ws:
            return
        msg = {"clientContent": {"turnComplete": True}}
        await self.ws.send(json.dumps(msg))

    async def _receive_loop(self) -> None:
        assert self.ws
        try:
            async for raw in self.ws:
                try:
                    data = json.loads(raw)
                    server_content = data.get("serverContent", {})
                    if server_content.get("interrupted"):
                        logger.info("Gemini Live interrupted by user speech")
                        if self._on_interrupted:
                            await self._on_interrupted()

                    model_turn = server_content.get("modelTurn", {})
                    for part in model_turn.get("parts", []):
                        inline_data = part.get("inlineData")
                        if inline_data and inline_data.get("mimeType", "").startswith("audio/pcm"):
                            audio_b64 = inline_data.get("data", "")
                            if audio_b64 and self._on_audio:
                                audio_bytes = base64.b64decode(audio_b64)
                                await self._on_audio(audio_bytes)
                        text = part.get("text")
                        if text and self._on_text:
                            await self._on_text(text)

                    if server_content.get("turnComplete"):
                        logger.info("Gemini Live turn complete")
                        if self._on_complete:
                            await self._on_complete()

                except Exception as exc:
                    logger.error("Error processing Gemini Live message: %s", exc)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Gemini Live WebSocket receive loop terminated: %s", exc)

    async def close(self) -> None:
        if self.receive_task:
            self.receive_task.cancel()
        if self.ws:
            await self.ws.close()
            self.ws = None
