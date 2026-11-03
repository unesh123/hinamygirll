import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from hinaa_api.config import Settings
from hinaa_api.models import SpeechRequest
from hinaa_api.speech_stream import pcm_events


def test_native_audio_configuration_does_not_claim_chat_health(client):
    response = client.get("/api/v1/providers")
    assert response.status_code == 200
    status = next(row for row in response.json() if row["id"] == "gemini-live")
    assert "llm" not in status["capabilities"]
    assert not any(cap.startswith("default-model:") for cap in status["capabilities"])
    assert status["state"] != "healthy"


def test_first_audio_is_delivered_before_synthesis_finishes_and_socket_closes():
    async def run():
        release = asyncio.Event()

        async def chunks():
            yield SimpleNamespace(audio=b"\x00\x00", text_echo="a", alignment=None)
            await release.wait()
            yield SimpleNamespace(audio=b"\x01\x00", text_echo="b", alignment=None)

        stream = SimpleNamespace(send_text_delta=AsyncMock(), finish_input=AsyncMock(), chunks=chunks, close=AsyncMock(), abort=AsyncMock(), error=None)
        provider = SimpleNamespace(open_speech_stream=AsyncMock(return_value=stream))
        frames = pcm_events(provider, SpeechRequest(text="Hello there.", providerMode="openai"), Settings(_env_file=None))
        first = json.loads(await anext(frames))
        assert first["type"] == "audio"
        assert first["sampleRate"] == 24000
        assert not release.is_set()
        stream.close.assert_not_awaited()
        release.set()
        remaining = [json.loads(frame) async for frame in frames]
        assert [frame["type"] for frame in remaining] == ["audio", "done"]
        stream.close.assert_awaited_once()

    asyncio.run(run())


def test_disconnect_closes_vendor_socket():
    async def run():
        async def chunks():
            yield SimpleNamespace(audio=b"\x00\x00", text_echo="a", alignment=None)

        stream = SimpleNamespace(send_text_delta=AsyncMock(), finish_input=AsyncMock(), chunks=chunks, close=AsyncMock(), abort=AsyncMock(), error=None)
        frames = pcm_events(SimpleNamespace(open_speech_stream=AsyncMock(return_value=stream)), SpeechRequest(text="Hello."), Settings(_env_file=None))
        await anext(frames)
        await frames.aclose()
        stream.abort.assert_awaited_once()

    asyncio.run(run())


def test_vendor_error_is_sanitized_and_cannot_report_success():
    async def run():
        provider = SimpleNamespace(open_speech_stream=AsyncMock(side_effect=RuntimeError("secret-credential")))
        result = b"".join([frame async for frame in pcm_events(provider, SpeechRequest(text="Hello."), Settings(_env_file=None))])
        assert b"secret-credential" not in result
        assert json.loads(result)["type"] == "error"

    asyncio.run(run())


def test_empty_vendor_output_is_failure():
    async def run():
        async def chunks():
            if False:
                yield

        stream = SimpleNamespace(send_text_delta=AsyncMock(), finish_input=AsyncMock(), chunks=chunks, close=AsyncMock(), abort=AsyncMock(), error=None)
        frames = [json.loads(frame) async for frame in pcm_events(SimpleNamespace(open_speech_stream=AsyncMock(return_value=stream)), SpeechRequest(text="Hello."), Settings(_env_file=None))]
        assert [frame["type"] for frame in frames] == ["error"]
        stream.abort.assert_awaited_once()

    asyncio.run(run())
