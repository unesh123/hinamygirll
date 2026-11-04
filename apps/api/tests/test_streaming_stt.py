import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from hinaa_api.providers.streaming_stt import StreamingTranscription, create_streaming_transcription
from hinaa_api.realtime import ClientHello, LiveSession, RealtimeGateway


class VendorSocket:
    def __init__(self, vendor="elevenlabs-scribe-realtime", fail=False):
        self.vendor, self.fail = vendor, fail
        self.incoming = asyncio.Queue()
        self.audio = []
        self.closed = False

    async def send(self, value):
        if self.vendor == "elevenlabs-scribe-realtime":
            event = json.loads(value)
            audio = base64.b64decode(event["audio_base_64"])
            commit = event["commit"]
        else:
            audio = value if isinstance(value, bytes) else b""
            commit = not isinstance(value, bytes)
        if audio:
            self.audio.append(audio)
            event = ({"message_type": "partial_transcript", "text": "Hello world"}
                     if self.vendor == "elevenlabs-scribe-realtime" else
                     {"type": "Results", "is_final": False, "channel": {"alternatives": [{"transcript": "Hello world"}]}})
            await self.incoming.put(event)
        if commit:
            if self.vendor == "elevenlabs-scribe-realtime":
                await self.incoming.put({"message_type": "committed_transcript", "text": "Hello world."})
            else:
                await self.incoming.put({"type": "Results", "is_final": True, "channel": {"alternatives": [{"transcript": "Hello world."}]}})
                await self.incoming.put({"type": "Metadata"})

    async def recv(self):
        if self.fail:
            raise ConnectionError("vendor disconnected")
        return json.dumps(await self.incoming.get())

    async def close(self):
        self.closed = True


async def make_stream(vendor="elevenlabs-scribe-realtime", fail=False):
    socket = VendorSocket(vendor, fail)
    partials, statuses = [], []
    received = asyncio.Event()

    async def connect(*args, **kwargs):
        return socket

    async def partial(text):
        partials.append(text)
        received.set()

    async def status(mode):
        statuses.append(mode)

    stream = StreamingTranscription(provider=vendor, url="wss://example.invalid", headers={},
        on_partial=partial, on_status=status, connect=connect)
    return stream, socket, partials, statuses, received


@pytest.mark.asyncio
@pytest.mark.parametrize("vendor", ["elevenlabs-scribe-realtime", "deepgram-streaming"])
async def test_partial_before_commit_and_stable_final_without_retranscription(vendor):
    stream, socket, partials, statuses, received = await make_stream(vendor)
    try:
        frame = b"\x01\x00" * 320
        stream.offer(frame)
        await asyncio.wait_for(received.wait(), 1)
        assert partials == ["Hello world"]
        assert not stream.finalized
        assert not stream.task.done()
        result = await stream.finish()
        assert result.value == "Hello world."
        assert result.provider == vendor
        assert socket.audio == [frame]
        assert socket.closed
        assert statuses == ["streaming"]
    finally:
        await stream.abort()


@pytest.mark.asyncio
async def test_receiver_failure_falls_back_without_promoting_partial():
    stream, socket, _, statuses, _ = await make_stream(fail=True)
    assert await stream.finish() is None
    assert "batch" in statuses
    assert socket.closed


@pytest.mark.asyncio
async def test_cancel_closes_vendor_socket():
    stream, socket, _, _, received = await make_stream()
    stream.offer(b"\x01\x00" * 320)
    await asyncio.wait_for(received.wait(), 1)
    await stream.abort()
    assert socket.closed


@pytest.mark.asyncio
async def test_queue_overflow_never_returns_an_incomplete_final():
    stream, _, _, _, _ = await make_stream()
    for _ in range(257):
        stream.offer(b"\x01\x00" * 320)
    assert stream.failed
    assert await stream.finish() is None


@pytest.mark.asyncio
async def test_final_segments_are_accumulated_across_a_pause():
    stream, socket, partials, _, received = await make_stream("deepgram-streaming")
    try:
        stream.offer(b"\x01\x00" * 320)
        await asyncio.wait_for(received.wait(), 1)
        received.clear()
        await socket.incoming.put({"type": "Results", "is_final": True, "channel": {"alternatives": [{"transcript": "First part"}]}})
        await asyncio.wait_for(received.wait(), 1)
        received.clear()
        await socket.incoming.put({"type": "Results", "is_final": False, "channel": {"alternatives": [{"transcript": "and more"}]}})
        await asyncio.wait_for(received.wait(), 1)
        assert partials[-1] == "First part and more"
        assert not stream.finalized
    finally:
        await stream.abort()


@pytest.mark.asyncio
async def test_unsupported_streaming_language_keeps_batch_fallback():
    settings = SimpleNamespace(elevenlabs_configured=False, deepgram_configured=True, deepgram_stt_model="nova-2-general")
    assert create_streaming_transcription(settings, "real", "mixed", None, None) is None
    assert create_streaming_transcription(settings, "real", "ne-NP", None, None) is None
    assert create_streaming_transcription(settings, "local", "en-US", None, None) is None


@pytest.mark.asyncio
async def test_stream_selection_preserves_fixed_english_and_multilingual_routes(monkeypatch):
    import hinaa_api.providers.streaming_stt as module
    from pydantic import SecretStr
    monkeypatch.setattr(module, "StreamingTranscription", lambda **kwargs: kwargs)
    settings = SimpleNamespace(elevenlabs_configured=True, deepgram_configured=True,
        elevenlabs_api_key=SecretStr("fixture-eleven"), elevenlabs_base_url="https://api.elevenlabs.io",
        deepgram_api_key=SecretStr("fixture-deepgram"), deepgram_base_url="https://api.deepgram.com", deepgram_stt_model="nova-2-general")
    english = create_streaming_transcription(settings, "real", "en-US", None, None)
    mixed = create_streaming_transcription(settings, "real", "mixed", None, None)
    nepali = create_streaming_transcription(settings, "real", "ne-NP", None, None)
    assert english["provider"] == "deepgram-streaming"
    assert mixed["provider"] == "elevenlabs-scribe-realtime"
    assert "language_code" not in mixed["url"]
    assert "language_code=ne" in nepali["url"]
    assert "fixture" not in english["url"]


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel", [False, True])
async def test_gateway_forwards_live_words_before_processing_a_turn(monkeypatch, cancel):
    import hinaa_api.realtime as module
    from hinaa_api.config import Settings
    socket = VendorSocket()
    stream_ref = []
    partial_ready = asyncio.Event()
    callbacks = []

    async def connect(*args, **kwargs):
        return socket

    def factory(settings, mode, language, partial, status):
        callbacks.append(partial)
        stream = StreamingTranscription(provider="elevenlabs-scribe-realtime", url="wss://example.invalid", headers={},
            on_partial=partial, on_status=status, connect=connect)
        stream_ref.append(stream)
        return stream

    monkeypatch.setattr(module, "create_streaming_transcription", factory)
    gateway = RealtimeGateway(Settings(_env_file=None), None)
    session = LiveSession(ClientHello(type="session.hello", protocolVersion="1.0", sessionId="stream-test", providerMode="real", generation=1))
    events = []

    class BrowserSocket:
        async def send_json(self, event):
            events.append(event)
            if event["type"] == "stt.partial":
                partial_ready.set()

        async def receive(self):
            return {"bytes": b"\x01\x00" * 320}

    browser = BrowserSocket()
    finalized = []

    async def process(websocket, live, commit, audio, recognition):
        finalized.append(await recognition.finish())

    monkeypatch.setattr(gateway, "_process_turn", process)
    try:
        await gateway._control(browser, session, json.dumps({"type": "audio.start", "generation": 1}))
        await gateway._control(browser, session, json.dumps({"type": "audio.frame", "sequence": 0, "generation": 1, "capturedAtMs": 0, "byteLength": 640}))
        await asyncio.wait_for(partial_ready.wait(), 1)
        assert next(e for e in events if e["type"] == "stt.partial")["text"] == "Hello world"
        assert session.processing is None
        assert finalized == []
        if cancel:
            await gateway._interrupt(browser, session, 2)
            before = len(events)
            await callbacks[0]("late words from cancelled speech")
            assert len(events) == before
            assert finalized == []
            assert socket.closed
            return
        await gateway._control(browser, session, json.dumps({"type": "audio.commit", "generation": 1, "endedAtMs": 1000}))
        await session.processing
        assert len(finalized) == 1
        assert finalized[0].value == "Hello world."
        assert socket.closed
    finally:
        for stream in stream_ref:
            await stream.abort()


@pytest.mark.asyncio
@pytest.mark.parametrize("stream_succeeds", [True, False])
async def test_actual_turn_reuses_stable_stream_result_or_falls_back(stream_succeeds):
    from unittest.mock import AsyncMock
    from hinaa_api.config import Settings
    from hinaa_api.providers.base import ProviderResult
    from hinaa_api.providers.mock import MockLLMProvider
    from hinaa_api.realtime import CommitMessage

    async def plan(request, emit, user_id=None):
        result = await MockLLMProvider().create_plan(request.text, "hinaa", "en-US", ())
        await emit(result.value.spokenText)
        return result

    service = SimpleNamespace(
        transcribe=AsyncMock(return_value=ProviderResult("Fallback final.", "batch-test", 1)),
        create_live_plan=plan,
        synthesize_text=AsyncMock(return_value=ProviderResult(b"test-audio", "mock", 1)),
    )
    recognition = SimpleNamespace(
        finish=AsyncMock(return_value=ProviderResult("Stable final.", "stream-test", 0) if stream_succeeds else None),
        abort=AsyncMock(), failure_code="STT_STREAM_CONNECTION_FAILED",
    )
    gateway = RealtimeGateway(Settings(_env_file=None), service)
    session = LiveSession(ClientHello(type="session.hello", protocolVersion="1.0", sessionId="process-test", providerMode="real", generation=1), turn=1)
    events = []

    class Browser:
        async def send_json(self, event):
            events.append(event)

    await gateway._process_turn(Browser(), session, CommitMessage(type="audio.commit", generation=1, endedAtMs=1), b"\x01\x00" * 320, recognition)
    finals = [event for event in events if event["type"] == "stt.final"]
    assert len(finals) == 1
    assert finals[0]["text"] == ("Stable final." if stream_succeeds else "Fallback final.")
    assert events[-1]["type"] == "turn.complete"
    if stream_succeeds:
        service.transcribe.assert_not_called()
    else:
        service.transcribe.assert_awaited_once()
        assert any(e["type"] == "stt.status" and e["mode"] == "batch" for e in events)
    recognition.abort.assert_awaited_once()


@pytest.mark.asyncio
async def test_unconfirmed_partial_cannot_become_final_on_timeout():
    stream, socket, _, _, received = await make_stream()
    original_send = socket.send

    async def no_commit_response(value):
        event = json.loads(value)
        if not event.get("commit"):
            await original_send(value)

    socket.send = no_commit_response
    stream.offer(b"\x01\x00" * 320)
    await asyncio.wait_for(received.wait(), 1)
    assert stream.last_display == "Hello world"
    assert await stream.finish() is None
    assert not stream.finalized
    assert socket.closed


@pytest.mark.asyncio
async def test_vendor_quota_error_exposes_code_without_using_partial_as_final():
    stream, socket, _, statuses, received = await make_stream()
    stream.offer(b"\x01\x00" * 320)
    await asyncio.wait_for(received.wait(), 1)
    await socket.incoming.put({"message_type": "quota_exceeded", "error": "test quota failure"})
    assert await stream.finish() is None
    assert stream.failure_code == "STT_STREAM_QUOTA_EXCEEDED"
    assert statuses[-1] == "batch"
    assert socket.closed
