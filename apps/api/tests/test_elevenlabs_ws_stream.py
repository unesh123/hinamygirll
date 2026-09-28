"""
test_elevenlabs_ws_stream.py

Offline tests for the real-time WebSocket TTS path. No network and no vendor
call: a scripted fake socket stands in for ElevenLabs, so every assertion here
is about our own contract — framing, ordering, alignment, status and shutdown.
"""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import pytest

from hinaa_api.providers import elevenlabs as el
from hinaa_api.providers.elevenlabs import (
    ElevenLabsConfig,
    ElevenLabsError,
    ElevenLabsStatus,
    ElevenLabsWebSocketStreamingProvider,
    choose_live_tts_model,
    make_elevenlabs_provider,
)


class FakeTransport:
    """A scripted vendor socket: frames out, JSON frames in, no network."""

    def __init__(self, frames: list[dict[str, Any]] | None = None) -> None:
        self.frames: asyncio.Queue[str] = asyncio.Queue()
        for frame in frames or []:
            self.frames.put_nowait(json.dumps(frame))
        self.sent: list[dict[str, Any]] = []
        self.closed = False
        self._idle = asyncio.Event()

    async def send(self, message: str) -> None:
        self.sent.append(json.loads(message))

    async def recv(self) -> str:
        if not self.frames.empty():
            return await self.frames.get()
        # No scripted frame left: behave like a vendor socket that is simply
        # quiet. Cancellation (abort/teardown) is what ends this wait.
        await self._idle.wait()
        raise AssertionError("unreachable")  # pragma: no cover

    async def close(self) -> None:
        self.closed = True

    def push(self, frame: dict[str, Any]) -> None:
        self.frames.put_nowait(json.dumps(frame))


def build_provider(
    frames: list[dict[str, Any]] | None = None, **config_kwargs: Any
) -> tuple[ElevenLabsWebSocketStreamingProvider, FakeTransport, list[dict[str, Any]]]:
    transport = FakeTransport(frames)
    connects: list[dict[str, Any]] = []

    async def connect_factory(
        url: str, *, headers: dict[str, str], **_: Any
    ) -> FakeTransport:
        connects.append({"url": url, "headers": headers})
        return transport

    config = ElevenLabsConfig(api_key="fake_key", voice_id="fake_voice", **config_kwargs)
    provider = ElevenLabsWebSocketStreamingProvider(
        config, connect_factory=connect_factory
    )
    return provider, transport, connects


def audio_frame(payload: bytes = b"\x01\x02", **extra: Any) -> dict[str, Any]:
    frame: dict[str, Any] = {"audio": base64.b64encode(payload).decode("ascii")}
    frame.update(extra)
    return frame


async def drain(
    provider: ElevenLabsWebSocketStreamingProvider, text: str = "Hello there."
) -> list[bytes]:
    collected: list[bytes] = []
    async for piece in provider.synthesize(text):
        collected.append(piece)
    return collected


def test_websocket_mode_is_a_real_provider_now() -> None:
    """The factory used to return a stub whose synthesize() raised."""
    provider = make_elevenlabs_provider(
        ElevenLabsConfig(api_key="fake_key", voice_id="fake_voice"), "websocket"
    )
    assert isinstance(provider, ElevenLabsWebSocketStreamingProvider)
    assert provider.name == "elevenlabs-websocket"
    assert provider.capability_flags()["websocket"] is True


@pytest.mark.parametrize(
    ("language_text", "expected"),
    [
        ("मलाई नेपालीमा बुझाऊ।", "eleven_v3_conversational"),
        ("सम्झाओ न setup कसरी गर्ने", "eleven_v3_conversational"),
        ("Explain the deploy plan.", "eleven_flash_v2_5"),
        ("मुझे setup समझाओ।", "eleven_flash_v2_5"),
    ],
)
def test_live_model_never_mutes_a_language(language_text: str, expected: str) -> None:
    """Nepali needs the v3 family; everything else takes the fast model."""
    assert (
        choose_live_tts_model(
            language_text,
            configured_model="eleven_turbo_v2_5",
            fast_model="eleven_flash_v2_5",
            nepali_model="eleven_v3_conversational",
        )
        == expected
    )


def test_configured_nepali_model_wins_when_it_already_qualifies() -> None:
    assert (
        choose_live_tts_model(
            "मलाई भन।",
            configured_model="eleven_v3",
            fast_model="eleven_flash_v2_5",
            nepali_model="eleven_v3_conversational",
        )
        == "eleven_v3"
    )


async def test_setup_frame_and_url_carry_the_realtime_contract() -> None:
    provider, transport, connects = build_provider()
    stream = await provider.open_speech_stream(model_id="eleven_flash_v2_5")
    try:
        assert connects[0]["url"] == (
            "wss://api.elevenlabs.io/v1/text-to-speech/fake_voice/stream-input"
            "?model_id=eleven_flash_v2_5&output_format=pcm_24000&sync_alignment=true"
        )
        assert connects[0]["headers"] == {"xi-api-key": "fake_key"}
        setup = transport.sent[0]
        assert setup["text"] == " "
        assert setup["generation_config"]["chunk_length_schedule"] == list(
            el.WS_DEFAULT_CHUNK_SCHEDULE
        )
        assert setup["xi_api_key"] == "fake_key"
        assert 0.0 <= setup["voice_settings"]["stability"] <= 1.0
    finally:
        await stream.abort()


async def test_text_deltas_end_with_a_space_and_empty_deltas_are_skipped() -> None:
    provider, transport, _ = build_provider()
    stream = await provider.open_speech_stream()
    try:
        await stream.send_text_delta("Hello")
        await stream.send_text_delta("   ")
        await stream.send_text_delta("world ", flush=True)
        body = transport.sent[1:]
        assert [frame["text"] for frame in body] == ["Hello ", "world "]
        assert body[1]["flush"] is True
    finally:
        await stream.abort()


async def test_audio_arrives_in_order_and_marks_the_provider_available() -> None:
    frames = [audio_frame(b"first"), audio_frame(b"second"), {"isFinal": True}]
    provider, transport, _ = build_provider(frames)
    assert provider.status is ElevenLabsStatus.authenticationUntested

    received = await drain(provider)

    assert received == [b"first", b"second"]
    assert provider.status is ElevenLabsStatus.available
    assert transport.closed is True
    assert transport.sent[-1]["text"] == ""  # the close frame


async def test_alignment_frame_is_exposed_for_lip_sync() -> None:
    frames = [
        {
            "alignment": {
                "characters": ["न", "म"],
                "charStartTimesMs": [0, 90],
                "charDurationsMs": [90, 70],
            }
        },
        audio_frame(b"audio"),
        {"isFinal": True},
    ]
    provider, _transport, _ = build_provider(frames)
    stream = await provider.open_speech_stream()
    seen: list[Any] = []
    try:
        await stream.send_text_delta("नम", flush=True)
        await stream.finish_input()
        async for chunk in stream.chunks():
            seen.append(chunk)
    finally:
        await stream.abort()

    timeline = [chunk for chunk in seen if chunk.alignment is not None]
    assert timeline, "vendor alignment must reach the avatar"
    assert timeline[0].alignment.to_events()[0] == {
        "char": "न",
        "startMs": 0,
        "endMs": 90,
    }
    assert timeline[0].audio == b""
    assert [chunk.audio for chunk in seen if chunk.audio] == [b"audio"]


async def test_quota_error_frame_stops_the_turn_with_the_right_status() -> None:
    frames = [{"code": "quota_exceeded", "message": "You have exceeded your quota"}]
    provider, _transport, _ = build_provider(frames, tts_retry_attempts=0)
    with pytest.raises(ElevenLabsError) as raised:
        await drain(provider)
    assert raised.value.el_status is ElevenLabsStatus.quotaFailed
    assert provider.status is ElevenLabsStatus.quotaFailed


async def test_auth_error_frame_is_reported_as_authentication_failure() -> None:
    frames = [{"code": "unauthorized", "message": "Invalid API key"}]
    provider, _transport, _ = build_provider(frames, tts_retry_attempts=0)
    with pytest.raises(ElevenLabsError) as raised:
        await drain(provider)
    assert raised.value.el_status is ElevenLabsStatus.authenticationFailed


async def test_ordinary_audio_frame_is_never_mistaken_for_an_error() -> None:
    """A frame that merely carries text must not end a healthy turn."""
    frames = [
        audio_frame(b"voice", text="Hello there."),
        {"isFinal": True},
    ]
    provider, _transport, _ = build_provider(frames)
    assert await drain(provider) == [b"voice"]
    assert provider.status is ElevenLabsStatus.available


async def test_handshake_401_maps_to_authentication_failed() -> None:
    class Response:
        status_code = 401

    class HandshakeFailure(Exception):
        response = Response()

    async def failing_connect(url: str, *, headers: dict[str, str], **_: Any) -> Any:
        raise HandshakeFailure("server rejected the upgrade")

    provider = ElevenLabsWebSocketStreamingProvider(
        ElevenLabsConfig(api_key="fake_key", voice_id="fake_voice"),
        connect_factory=failing_connect,
    )
    with pytest.raises(ElevenLabsError) as raised:
        await provider.open_speech_stream()
    assert raised.value.el_status is ElevenLabsStatus.authenticationFailed
    assert provider.status is ElevenLabsStatus.authenticationFailed
    assert provider.available is False


async def test_close_never_hangs_when_the_vendor_stops_answering(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(el, "WS_CLOSE_GRACE_SECONDS", 0.05)
    provider, transport, _ = build_provider([audio_frame(b"only")])
    stream = await provider.open_speech_stream()
    await stream.send_text_delta("Hi", flush=True)
    await asyncio.wait_for(stream.close(), timeout=2)
    assert transport.closed is True
    assert stream.finished is True


async def test_abort_cancels_the_socket_without_waiting() -> None:
    provider, transport, _ = build_provider([audio_frame(b"a")])
    stream = await provider.open_speech_stream()
    await stream.send_text_delta("Hi", flush=True)
    await asyncio.wait_for(stream.abort(), timeout=2)
    assert transport.closed is True
    assert stream.finished is True


async def test_keepalive_holds_the_socket_open_while_the_brain_thinks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An idle vendor socket is dropped after 20s; a slow sentence must not be."""
    monkeypatch.setattr(el, "WS_KEEPALIVE_SECONDS", 0.05)
    provider, transport, _ = build_provider()
    stream = await provider.open_speech_stream()
    try:
        await asyncio.sleep(0.25)
        assert transport.sent[-1] == {"text": " "}
    finally:
        await stream.abort()


async def test_unconfigured_provider_refuses_instead_of_calling_out() -> None:
    provider = ElevenLabsWebSocketStreamingProvider(ElevenLabsConfig())
    with pytest.raises(ElevenLabsError) as raised:
        await provider.open_speech_stream()
    assert raised.value.el_status is ElevenLabsStatus.unavailable


