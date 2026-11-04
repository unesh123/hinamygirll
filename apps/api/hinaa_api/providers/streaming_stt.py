"""Per-utterance recognition: bounded audio queue, interim display, stable final.

API keys remain on the server. A failed stream returns None so the gateway can
transcribe its original PCM buffer; an interim hypothesis is never a final.
"""
from __future__ import annotations

import asyncio
import base64
import json
from contextlib import suppress
from typing import Any, Awaitable, Callable
from urllib.parse import urlencode

from .base import ProviderResult
from .elevenlabs import default_websocket_connect


class StreamingTranscription:
    def __init__(self, *, provider: str, url: str, headers: dict[str, str],
                 on_partial: Callable[[str], Awaitable[None]],
                 on_status: Callable[[str], Awaitable[None]], connect: Any = None):
        self.provider, self.url, self.headers = provider, url, headers
        self.on_partial, self.on_status = on_partial, on_status
        self.connect = connect or default_websocket_connect
        self.queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=256)
        self.socket: Any = None
        self.stable: list[str] = []
        self.finalized = False
        self.commit_sent = False
        self.failed = False
        self.failure_code = ""
        self.last_display = ""
        self.task = asyncio.create_task(self._run(), name="live-recognition")

    def offer(self, pcm: bytes) -> None:
        if self.task.done() or self.failed:
            return
        try:
            self.queue.put_nowait(pcm)
        except asyncio.QueueFull:
            # Never silently lose audio and present the remainder as complete.
            self.failed = True
            self.failure_code = "STT_STREAM_QUEUE_FULL"
            self.task.cancel()

    async def _display(self, partial: str = "") -> None:
        text = " ".join([*self.stable, partial]).strip()
        if text and text != self.last_display:
            self.last_display = text
            await self.on_partial(text)

    async def _receive(self) -> None:
        while True:
            event = json.loads(await self.socket.recv())
            kind = event.get("message_type") if self.provider == "elevenlabs-scribe-realtime" else event.get("type")
            if self.provider == "elevenlabs-scribe-realtime":
                if kind == "partial_transcript":
                    await self._display(event.get("text", ""))
                elif kind == "committed_transcript":
                    self.stable.append(event.get("text", "").strip())
                    await self._display()
                    if self.commit_sent:
                        self.finalized = True
                        return
                elif kind not in {"session_started", "warning"}:
                    allowed_errors = {"auth_error", "quota_exceeded", "rate_limited", "unaccepted_terms", "input_error", "error"}
                    raise RuntimeError("STT_STREAM_" + (kind.upper() if kind in allowed_errors else "REJECTED"))
            elif kind == "Results":
                alternatives = event.get("channel", {}).get("alternatives", [])
                text = alternatives[0].get("transcript", "") if alternatives else ""
                if event.get("is_final"):
                    if text.strip():
                        self.stable.append(text.strip())
                    await self._display()
                else:
                    await self._display(text)
            elif kind == "Metadata":
                self.finalized = self.commit_sent
                return
            elif kind == "Error":
                raise RuntimeError("STT_STREAM_REJECTED")

    async def _run(self) -> None:
        receiver = None
        try:
            self.socket = await asyncio.wait_for(self.connect(
                self.url, headers=self.headers, open_timeout=4, max_queue=32,
            ), timeout=4)
            await self.on_status("streaming")
            receiver = asyncio.create_task(self._receive())
            while True:
                # Surface receive failures promptly without blocking microphone ingestion.
                queued = asyncio.create_task(self.queue.get())
                try:
                    done, _ = await asyncio.wait({queued, receiver}, return_when=asyncio.FIRST_COMPLETED)
                    if receiver in done:
                        await receiver
                        return
                    pcm = queued.result()
                finally:
                    if not queued.done():
                        queued.cancel()
                        with suppress(asyncio.CancelledError):
                            await queued
                if self.provider == "elevenlabs-scribe-realtime":
                    if pcm is None:
                        self.commit_sent = True
                    await self.socket.send(json.dumps({
                        "message_type": "input_audio_chunk",
                        "audio_base_64": base64.b64encode(pcm or b"").decode(),
                        "sample_rate": 16000, "commit": pcm is None,
                    }))
                elif pcm is not None:
                    await self.socket.send(pcm)
                else:
                    # CloseStream flushes all remaining Results before Metadata.
                    self.commit_sent = True
                    await self.socket.send(json.dumps({"type": "CloseStream"}))
                if pcm is None:
                    await asyncio.wait_for(receiver, timeout=3)
                    return
        except asyncio.CancelledError:
            raise
        except Exception as error:
            self.failed = True
            self.failure_code = str(error) if isinstance(error, RuntimeError) and str(error).startswith("STT_STREAM_") else "STT_STREAM_CONNECTION_FAILED"
            await self.on_status("batch")
        finally:
            if receiver is not None:
                receiver.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await receiver
            if self.socket is not None:
                with suppress(Exception):
                    await asyncio.wait_for(self.socket.close(), timeout=1)

    async def finish(self) -> ProviderResult[str] | None:
        try:
            if not self.task.done() and not self.failed:
                await asyncio.wait_for(self.queue.put(None), timeout=1)
            await asyncio.wait_for(asyncio.shield(self.task), timeout=4)
        except (TimeoutError, asyncio.CancelledError):
            # A cancelled stream itself is a fallback. Cancellation of the owning
            # turn must still propagate, so don't swallow that cancellation.
            if asyncio.current_task().cancelling():
                raise
            self.failed = True
            self.failure_code = "STT_STREAM_FINAL_TIMEOUT"
            await self.abort()
        text = " ".join(self.stable).strip()
        if self.finalized and not self.failed and text:
            return ProviderResult(text, self.provider, 0)
        return None

    async def abort(self) -> None:
        self.task.cancel()
        with suppress(asyncio.CancelledError, Exception):
            await self.task


def create_streaming_transcription(settings: Any, mode: str, language: str,
                                   on_partial: Any, on_status: Any) -> StreamingTranscription | None:
    if mode in {"mock", "local"}:
        return None
    language = (language or "").split("-")[0].lower()
    # Fixed English keeps the existing Deepgram-primary recognition preference.
    # Auto/mixed and Nepali use Scribe's automatic/multilingual recognition.
    if settings.elevenlabs_configured and not (settings.deepgram_configured and language == "en"):
        base = settings.elevenlabs_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        params = {"model_id": "scribe_v2_realtime", "audio_format": "pcm_16000", "commit_strategy": "manual"}
        if language not in {"auto", "mixed", ""}:
            params["language_code"] = language
        return StreamingTranscription(provider="elevenlabs-scribe-realtime",
            url=base + "/v1/speech-to-text/realtime?" + urlencode(params),
            headers={"xi-api-key": settings.elevenlabs_api_key.get_secret_value()},
            on_partial=on_partial, on_status=on_status)
    if settings.deepgram_configured:
        # Nova-2 streaming cannot auto-detect or cover Nepali. Preserve batch
        # fallback instead of silently recognizing a different language.
        model = settings.deepgram_stt_model
        if language in {"ne", "auto", "mixed", ""} and not (model.startswith("nova-3") and language != "ne"):
            return None
        base = settings.deepgram_base_url.rstrip("/").replace("https://", "wss://").replace("http://", "ws://")
        params = {"model": model, "encoding": "linear16", "sample_rate": "16000", "channels": "1",
                  "interim_results": "true", "punctuate": "true", "endpointing": "false",
                  "language": "multi" if language in {"auto", "mixed", ""} else language}
        return StreamingTranscription(provider="deepgram-streaming", url=base + "/v1/listen?" + urlencode(params),
            headers={"Authorization": "Token " + settings.deepgram_api_key.get_secret_value()},
            on_partial=on_partial, on_status=on_status)
    return None
