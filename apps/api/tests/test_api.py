from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from .conftest import pcm_wav

ROOT = Path(__file__).resolve().parents[3]


def test_health_and_provider_readiness_are_safe(client: TestClient) -> None:
    assert client.get("/health/live").json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json() == {"status": "ok", "mode": "mock", "missingConfiguration": []}
    providers = client.get("/v1/providers").json()
    assert providers[0]["state"] == "healthy"
    assert providers[1]["state"] == "unavailable"


def test_mock_transcription_accepts_valid_bounded_pcm_wav(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/transcriptions",
        files={"audio": ("turn.wav", pcm_wav(), "audio/wav")},
        data={"language": "ne-NP", "provider_mode": "mock"},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "mock-stt-v1"
    assert "assignment" in response.json()["text"]


def test_audio_validation_rejects_unknown_or_oversized_formats(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/transcriptions",
        files={"audio": ("turn.webm", b"not audio", "audio/webm")},
        data={"provider_mode": "mock"},
    )
    assert response.status_code == 415
    assert response.json()["code"] == "AUDIO_FORMAT_UNSUPPORTED"
    assert response.headers["x-correlation-id"] == response.json()["correlationId"]


def test_mock_turn_streams_validated_plan_and_bounded_context(client: TestClient) -> None:
    payload = {
        "sessionId": "test-session",
        "text": "Assignment explain gara na",
        "companionId": "hinaa",
        "language": "mixed",
        "providerMode": "mock",
    }
    response = client.post("/v1/conversations/turns:stream", json=payload)
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    assert events[0]["type"] == "thinking"
    assert any(event["type"] == "text.delta" for event in events)
    plan = next(event["plan"] for event in events if event["type"] == "plan")
    schema = json.loads(
        (ROOT / "packages/contracts/schemas/assistant-turn-plan.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(schema).validate(plan)
    assert plan["toolRequests"] == []
    assert client.delete("/v1/sessions/test-session").status_code == 204


def test_mock_synthesis_returns_playable_pcm_wav(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/synthesis",
        json={"text": "Namaste", "companionId": "hinaa", "providerMode": "mock"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("audio/wav")
    assert response.content[:4] == b"RIFF"
    assert response.headers["x-hinaa-provider"] == "mock-tts-v1"


def test_real_mode_missing_configuration_returns_typed_stream_error(client: TestClient) -> None:
    response = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "real-gate",
            "text": "Namaste",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "real",
        },
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    error = events[-1]
    assert error["type"] == "error"
    assert error["code"] == "PROVIDER_CONFIGURATION_MISSING"
    assert "AZURE_SPEECH_KEY" in error["message"]
    assert "GEMINI_API_KEY" in error["message"]
