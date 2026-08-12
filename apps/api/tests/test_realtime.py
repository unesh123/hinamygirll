from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from hinaa_api.realtime import segment_phrases

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
    assert types[:2] == ["stt.final", "assistant.thinking"]
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
        send_frame(socket, 2)
        assert socket.receive_json()["code"] == "AUDIO_SEQUENCE_GAP"
        send_frame(socket, 1, generation=0)
        assert socket.receive_json()["reason"] == "stale-generation"


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
        assert socket.receive_json()["type"] == "stt.final"
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
