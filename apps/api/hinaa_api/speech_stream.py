"""Incremental PCM delivery for typed chat; reuse the existing ElevenLabs client."""
from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from .errors import HinaaError
from .models import SpeechRequest
from .providers.elevenlabs import ElevenLabsWebSocketStreamingProvider, choose_live_tts_model
from .voice_performance import speech_text_for_tts


def _event(**payload) -> bytes:
    return (json.dumps(payload) + "\n").encode()


async def pcm_events(provider, body: SpeechRequest, settings) -> AsyncIterator[bytes]:
    stream = None
    delivered = False
    completed = False
    try:
        async with asyncio.timeout(settings.provider_timeout_seconds):
            text = speech_text_for_tts(body.text) or body.text
            model = choose_live_tts_model(
                text, configured_model=settings.elevenlabs_model_id,
                fast_model=settings.elevenlabs_tts_model_fast,
                nepali_model=settings.elevenlabs_tts_model_nepali,
            )
            stream = await asyncio.wait_for(provider.open_speech_stream(
                voice=(settings.elevenlabs_hiro_voice_id if body.companionId == "hiro" else settings.elevenlabs_hinaa_voice_id),
                model_id=model, companion_id=body.companionId,
            ), timeout=settings.voice_socket_timeout_seconds)
            await stream.send_text_delta(text, flush=True)
            await stream.finish_input()
            async for chunk in stream.chunks():
                if not chunk.audio:
                    continue
                delivered = True
                yield _event(
                    type="audio", audioBase64=base64.b64encode(chunk.audio).decode(),
                    sampleRate=24_000, text=chunk.text_echo,
                    alignment=chunk.alignment.to_events() if chunk.alignment else [],
                )
            if stream.error is not None or not delivered:
                yield _event(type="error", code="SPEECH_STREAM_FAILED")
            else:
                completed = True
                yield _event(type="done")
    except asyncio.CancelledError:
        raise
    except Exception:
        yield _event(type="error", code="SPEECH_STREAM_FAILED")
    finally:
        if stream is not None:
            if completed:
                await stream.close()
            else:
                await asyncio.shield(stream.abort())


def register_speech_stream(app: FastAPI, service) -> None:
    # These routes retain the application's owner-auth middleware. No exemption.
    @app.post("/api/v1/speech/synthesis/stream")
    @app.post("/v1/speech/synthesis/stream")
    async def synthesize_stream(body: SpeechRequest):
        if body.providerMode in {"mock", "local"} or body.voiceEngine not in {None, "auto", "elevenlabs"}:
            raise HinaaError("STREAM_UNAVAILABLE", "Use the configured non-streaming voice route.", 409)
        if not service.settings.elevenlabs_configured:
            raise HinaaError("STREAM_UNAVAILABLE", "ElevenLabs is not configured.", 503)
        provider = ElevenLabsWebSocketStreamingProvider(service.router.elevenlabs_config())
        return StreamingResponse(
            pcm_events(provider, body, service.settings),
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no", "X-HINAA-Provider": "elevenlabs"},
        )
