from __future__ import annotations

import asyncio
import json
from contextlib import suppress
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from hinaa_api.config import Settings
from hinaa_api.realtime import (
    SPEECH_MIN_PHRASE_CHARS,
    RealtimeGateway,
    segment_phrases,
    spoken_phrase_is_complete,
)

ROOT = Path(__file__).resolve().parents[3]


def hello(generation: int = 1) -> dict[str, object]:
    return {
        "type": "session.hello",
        "protocolVersion": "1.0",
        "sessionId": "phase3-test",
        "companionId": "hinaa",
        "providerMode": "mock",
        "generation": generation,
        "language": "mixed",
        "languageMode": "fixed-hi-IN",
        "calibration": "soft",
    }


def speech_frame() -> bytes:
    return (2_000).to_bytes(2, "little", signed=True) * 320


def send_frame(socket: object, sequence: int, generation: int = 1) -> None:
    descriptor = {
        "type": "audio.frame",
        "sequence": sequence,
        "generation": generation,
        "capturedAtMs": float(sequence * 20),
        "byteLength": 640,
    }
    socket.send_text(json.dumps(descriptor))  # type: ignore[attr-defined]
    socket.send_bytes(speech_frame())  # type: ignore[attr-defined]


def test_mock_live_turn_is_versioned_validated_and_voice_explicit(client: TestClient) -> None:
    with client.websocket_connect("/v1/realtime") as socket:
        socket.send_json(hello())
        ready = socket.receive_json()
        assert ready["type"] == "session.ready"
        assert ready["sampleFormat"] == "pcm-s16le"

        socket.send_json({"type": "audio.start", "generation": 1})
        assert socket.receive_json()["type"] == "audio.started"
        send_frame(socket, 0)
        assert socket.receive_json()["type"] == "stt.partial"
        socket.send_json(
            {
                "type": "audio.commit",
                "generation": 1,
                "endedAtMs": 800.0,
                "mockTranscript": "आज मुझे assignment समझा दो।",
            }
        )

        events: list[dict[str, object]] = []
        while not events or events[-1]["type"] != "turn.complete":
            events.append(socket.receive_json())

    types = [event["type"] for event in events]
    # voice.pipeline may appear before stt.final as a progress notification
    assert "stt.final" in types
    assert "assistant.thinking" in types
    assert types.index("stt.final") < types.index("assistant.thinking")
    assert "assistant.text.delta" in types
    assert "assistant.plan" in types
    audio = next(event for event in events if event["type"] == "tts.audio")
    assert audio["requestedVoice"] == "hi-IN-SwaraNeural"
    assert audio["actualVoice"] == "mock-tone"
    assert isinstance(audio["text"], str)
    assert audio["text"]
    assert audio["calibration"] == "soft"
    assert all(event["generation"] == 1 for event in events)


def test_duplicate_gap_and_stale_frames_are_rejected_without_duplication(
    client: TestClient,
) -> None:
    with client.websocket_connect("/v1/realtime") as socket:
        socket.send_json(hello())
        socket.receive_json()
        socket.send_json({"type": "audio.start", "generation": 1})
        socket.receive_json()
        send_frame(socket, 0)
        socket.receive_json()
        send_frame(socket, 0)
        assert socket.receive_json()["reason"] == "duplicate-frame"
        # A lost frame resyncs rather than faulting: the old AUDIO_SEQUENCE_GAP
        # error never advanced expected_sequence, so every later frame gapped
        # too and the client tore the session down mid-conversation.
        send_frame(socket, 2)
        assert socket.receive_json()["reason"] == "sequence-resynced"
        send_frame(socket, 1, generation=0)
        assert socket.receive_json()["reason"] == "stale-generation"
        socket.send_json({"type": "audio.commit", "generation": 1, "endedAtMs": 0})
        types = set()
        for _ in range(12):
            event = socket.receive_json()
            types.add(event["type"])
            if "assistant.plan" in types:
                break
        assert "assistant.plan" in types


def test_silence_never_reaches_the_model(client: TestClient) -> None:
    with client.websocket_connect("/v1/realtime") as socket:
        socket.send_json(hello())
        socket.receive_json()
        socket.send_json({"type": "audio.start", "generation": 1})
        socket.receive_json()
        socket.send_text(
            json.dumps(
                {
                    "type": "audio.frame",
                    "sequence": 0,
                    "generation": 1,
                    "capturedAtMs": 0,
                    "byteLength": 640,
                }
            )
        )
        socket.send_bytes(bytes(640))
        socket.send_json({"type": "audio.commit", "generation": 1, "endedAtMs": 20})
        error = socket.receive_json()
        assert error["type"] == "error"
        assert error["code"] == "AUDIO_NO_SIGNAL"


def test_interrupt_advances_generation_and_cancels_active_turn(client: TestClient) -> None:
    with client.websocket_connect("/v1/realtime") as socket:
        socket.send_json(hello())
        socket.receive_json()
        socket.send_json({"type": "audio.start", "generation": 1})
        socket.receive_json()
        send_frame(socket, 0)
        socket.receive_json()
        socket.send_json({"type": "audio.commit", "generation": 1, "endedAtMs": 20})
        # Consume events until we see stt.final (voice.pipeline may precede it)
        event = socket.receive_json()
        while event["type"] != "stt.final":
            event = socket.receive_json()
        socket.send_json({"type": "interrupt", "generation": 2})
        event = socket.receive_json()
        while event["type"] != "turn.cancelled":
            event = socket.receive_json()
        assert event["cancelledGeneration"] == 1
        assert event["generation"] == 2


def test_phrase_segmentation_is_bounded_and_ordered() -> None:
    text = "पहिलो वाक्य। Second sentence! " + ("long " * 60)
    chunks = segment_phrases(text, limit=80)
    assert chunks[:2] == ["पहिलो वाक्य।", "Second sentence!"]
    assert all(0 < len(chunk) <= 80 for chunk in chunks)


def test_a_two_word_clause_is_not_worth_a_synthesis_request() -> None:
    # Markdown list markers and version-number dots used to close a phrase each.
    assert not spoken_phrase_is_complete("Fix `agent-router` v2.5 first.")
    assert not spoken_phrase_is_complete("1. cold auth\n")
    assert spoken_phrase_is_complete(
        "cold auth on every turn, then the tool catalogue, then the fallback ladder."
    )


def test_an_unpunctuated_run_still_wraps_instead_of_stalling() -> None:
    assert not spoken_phrase_is_complete("word " * 30)
    assert spoken_phrase_is_complete("word " * 40)


def test_a_streamed_answer_splits_into_sentences_not_fragments() -> None:
    deltas = [
        "The biggest latency bottleneck ",
        "in a voice assistant is not ",
        "the model. It is the chain: ",
        "1. cold auth, 2. tool catalogue, ",
        "3. the fallback ladder. Fix `agent-router` v2.5 first.",
    ]
    buffer = ""
    phrases: list[str] = []
    for delta in deltas:
        buffer += delta
        if spoken_phrase_is_complete(buffer):
            phrases.append(buffer)
            buffer = ""
    if buffer:
        phrases.append(buffer)

    assert len(phrases) == 2
    assert all(len(phrase) >= SPEECH_MIN_PHRASE_CHARS for phrase in phrases)


def test_phase3_control_messages_validate_against_canonical_schema() -> None:
    schema = json.loads(
        (ROOT / "packages/contracts/schemas/phase-3-live-message.schema.json").read_text(
            encoding="utf-8"
        )
    )
    validator = Draft202012Validator(schema)
    validator.validate(hello())
    validator.validate(
        {
            "type": "audio.frame",
            "sequence": 0,
            "generation": 1,
            "capturedAtMs": 20,
            "byteLength": 640,
        }
    )


class SilentClientSocket:
    """Stand-in WebSocket for a browser that stops talking once he commits.

    Yields pre-built Starlette messages and never raises on an empty queue: the
    client is listening for her audio, not gone.
    """

    def __init__(self, incoming: list[dict[str, object]]) -> None:
        self._incoming = list(incoming)
        self.sent: list[dict[str, object]] = []
        self.closed_after_events: int | None = None

    async def accept(self) -> None:
        return None

    async def _silence(self) -> dict[str, object]:
        # He is waiting to hear her, not gone: park on a future nothing resolves.
        await asyncio.get_running_loop().create_future()
        raise AssertionError("unreachable")

    async def receive(self) -> dict[str, object]:
        if self._incoming:
            return self._incoming.pop(0)
        return await self._silence()

    async def receive_json(self) -> dict[str, object]:
        message = await self.receive()
        return json.loads(str(message["text"]))

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent.append(payload)

    async def close(self) -> None:
        self.closed_after_events = len(self.sent)

    def types(self) -> list[str]:
        return [str(event["type"]) for event in self.sent]


def _text(message: dict[str, object]) -> dict[str, object]:
    return {"type": "websocket.receive", "text": json.dumps(message)}


def _binary(frame: bytes) -> dict[str, object]:
    return {"type": "websocket.receive", "bytes": frame}


def _quick_gateway_settings() -> Settings:
    return Settings(
        _env_file=None,
        realtime_idle_timeout_seconds=0.05,
        realtime_turn_timeout_seconds=30.0,
    )


def _committed_client() -> SilentClientSocket:
    return SilentClientSocket(
        [
            _text(hello()),
            _text({"type": "audio.start", "generation": 1}),
            _text(
                {
                    "type": "audio.frame",
                    "sequence": 0,
                    "generation": 1,
                    "capturedAtMs": 20.0,
                    "byteLength": 640,
                }
            ),
            _binary(speech_frame()),
            _text({"type": "audio.commit", "generation": 1, "endedAtMs": 640.0}),
        ]
    )


async def test_a_live_turn_outlives_the_idle_silence_window(monkeypatch) -> None:
    """The silence window must not tear down a socket while she is still replying.

    Measured on the live gateway: audio.commit at 1.94s, clean close at 37.52s,
    zero tts.audio delivered, while ElevenLabs returned 200s for 20s more. The
    read loop was reusing the abandoned-socket timer for a client that is simply
    waiting to hear her.
    """
    gateway = RealtimeGateway(_quick_gateway_settings(), service=None)  # type: ignore[arg-type]
    replied = asyncio.Event()
    open_when_replied: list[bool] = []

    async def slow_turn(websocket, session, commit, turn_audio=None) -> None:
        await asyncio.sleep(0.4)  # 8x the idle window: brain, then synthesis
        await gateway._send(websocket, session, "turn.complete", {})
        open_when_replied.append(socket.closed_after_events is None)
        session.processing = None
        replied.set()

    monkeypatch.setattr(gateway, "_process_turn", slow_turn)
    socket = _committed_client()
    handler = asyncio.create_task(gateway.handle(socket))
    try:
        await asyncio.wait_for(replied.wait(), timeout=2)
    finally:
        handler.cancel()
        with suppress(asyncio.CancelledError):
            await handler

    assert open_when_replied == [True], "her reply must reach an open socket"


async def test_the_idle_window_still_reclaims_a_socket_with_no_turn() -> None:
    gateway = RealtimeGateway(_quick_gateway_settings(), service=None)  # type: ignore[arg-type]
    socket = SilentClientSocket([_text(hello())])

    await asyncio.wait_for(gateway.handle(socket), timeout=5)

    assert socket.types() == ["session.ready"]
    assert socket.closed_after_events == 1, "an abandoned socket is still reclaimed"


async def test_a_frame_descriptor_alone_cannot_park_the_session() -> None:
    """A microphone that sends the descriptor and loses its binary stays recoverable.

    audio.frame is two messages: JSON first, then the bytes it described. That
    second await sat inside _control, which the read loop awaits inline, so an
    unbounded wait meant the loop never returned to its own receive and the
    silence window could not reclaim the socket either — the session was parked
    with a client that had already stopped talking.
    """
    gateway = RealtimeGateway(
        Settings(
            _env_file=None,
            realtime_idle_timeout_seconds=0.05,
            realtime_turn_timeout_seconds=30.0,
            realtime_frame_pair_timeout_seconds=0.2,
        ),
        service=None,  # type: ignore[arg-type]
    )
    socket = SilentClientSocket(
        [
            _text(hello()),
            _text({"type": "audio.start", "generation": 1}),
            _text(
                {
                    "type": "audio.frame",
                    "sequence": 0,
                    "generation": 1,
                    "capturedAtMs": 20.0,
                    "byteLength": 640,
                }
            ),
            # no binary: receive() parks here, which is the whole point
        ]
    )

    await asyncio.wait_for(gateway.handle(socket), timeout=5)

    missing = [event for event in socket.sent if event.get("code") == "AUDIO_FRAME_MISSING"]
    assert missing, "the lost frame is reported instead of waited on forever"
    assert missing[0]["retryable"] is False, "one dropped frame is not a retryable turn"
