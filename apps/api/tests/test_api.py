from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

from hinaa_api.config import Settings
from hinaa_api.main import create_app

from .conftest import pcm_wav

ROOT = Path(__file__).resolve().parents[3]


def test_health_and_provider_readiness_are_safe(client: TestClient) -> None:
    assert client.get("/health/live").json()["status"] == "ok"
    ready = client.get("/health/ready")
    assert ready.status_code == 200
    body = ready.json()
    assert body["status"] == "ok"
    assert body["mode"] == "mock"
    assert body["missingConfiguration"] == []
    assert body["persistenceEnabled"] is True
    assert "promptVersion" in body
    providers = client.get("/v1/providers").json()
    by_id = {provider["id"]: provider for provider in providers}
    assert by_id["mock"]["state"] == "healthy"
    assert by_id["local"]["state"] == "degraded"
    assert by_id["groq"]["state"] == "unavailable"
    assert by_id["openai"]["state"] == "unavailable"
    assert "model:gpt-5-mini" in by_id["openai"]["capabilities"]
    assert by_id["azure-speech"]["state"] in ("disabled", "unavailable")
    assert "elevenlabs" in by_id
    assert by_id["gemini"]["state"] == "unavailable"


def test_voice_profiles_disclose_standard_nepali_voices(client: TestClient) -> None:
    profiles = client.get("/v1/voice-profiles").json()
    assert profiles[0]["requestedVoice"] == "ne-NP-HemkalaNeural"
    assert profiles[1]["requestedVoice"] == "ne-NP-SagarNeural"
    assert "not a custom anime" in profiles[0]["identityDisclosure"]
    assert [item["id"] for item in profiles[0]["calibrations"]] == [
        "natural",
        "soft",
        "lively",
    ]


def test_mock_transcription_accepts_valid_bounded_pcm_wav(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/transcriptions",
        files={"audio": ("turn.wav", pcm_wav(), "audio/wav")},
        data={"language": "ne-NP", "provider_mode": "mock"},
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "mock-stt-v1"
    assert "Real speech recognition is not active" in response.json()["text"]


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


def test_local_mode_is_zero_credit_text_and_placeholder_voice(client: TestClient) -> None:
    response = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "local-gate",
            "text": "bro make Hinaa perfect without Azure credits",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "local",
        },
    )
    assert response.status_code == 200
    events = [json.loads(line) for line in response.text.splitlines()]
    plan_event = next(event for event in events if event["type"] == "plan")
    assert plan_event["provider"] == "local-zero-credit-llm-v1"
    assert "zero-credit local mode" in plan_event["plan"]["displayText"]

    speech = client.post(
        "/v1/speech/synthesis",
        json={"text": "Namaste", "companionId": "hinaa", "providerMode": "local"},
    )
    assert speech.status_code == 200
    assert speech.content[:4] == b"RIFF"
    assert speech.headers["x-hinaa-provider"] == "local-placeholder-tts-v1"


def test_local_stt_fails_truthfully_without_cloud_or_silent_mock(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/transcriptions",
        files={"audio": ("turn.wav", pcm_wav(), "audio/wav")},
        data={"language": "ne-NP", "provider_mode": "local"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_STT_UNAVAILABLE"


def test_groq_mode_missing_key_returns_typed_stream_error(client: TestClient) -> None:
    response = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "groq-gate",
            "text": "Namaste",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "groq",
        },
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    error = events[-1]
    assert error["type"] == "error"
    assert error["code"] == "PROVIDER_CONFIGURATION_MISSING"
    assert "GROQ_API_KEY" in error["message"]


def test_groq_stt_uses_local_gate_without_cloud_fallback(client: TestClient) -> None:
    response = client.post(
        "/v1/speech/transcriptions",
        files={"audio": ("turn.wav", pcm_wav(), "audio/wav")},
        data={"language": "ne-NP", "provider_mode": "groq"},
    )
    assert response.status_code == 503
    assert response.json()["code"] == "LOCAL_STT_UNAVAILABLE"


def test_openai_text_mode_missing_configuration_returns_typed_stream_error(
    client: TestClient,
) -> None:
    response = client.post(
        "/v1/conversations/turns:stream",
        json={
            "sessionId": "openai-gate",
            "text": "Namaste",
            "companionId": "hinaa",
            "language": "mixed",
            "providerMode": "openai",
        },
    )
    events = [json.loads(line) for line in response.text.splitlines()]
    error = events[-1]
    assert error["type"] == "error"
    assert error["code"] == "PROVIDER_CONFIGURATION_MISSING"
    assert "OPENAI_API_KEY" in error["message"]
    assert "AZURE_SPEECH_KEY" not in error["message"]


def test_custom_provider_uses_codex_gateway_key_without_exposing_secret() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="azure-placeholder",
        AZURE_SPEECH_REGION="eastus",
        OPENAI_API_KEY="",
        OPENAI_CODEX_API_KEY="codex-placeholder",
        OPENAI_CODEX_BASE_URL="https://custom-gateway.example/v1",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        providers = client.get("/v1/providers").json()
    openai = next(provider for provider in providers if provider["id"] == "openai")
    custom = next(provider for provider in providers if provider["id"] == "custom")
    assert openai["state"] == "unavailable"
    assert custom["state"] == "healthy"
    assert "codex-placeholder" not in openai["userMessage"]
    assert "codex-placeholder" not in custom["userMessage"]


def test_openai_and_custom_gateway_keys_are_separate_without_exposing_secret() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="azure-placeholder",
        AZURE_SPEECH_REGION="eastus",
        OPENAI_API_KEY="primary-placeholder",
        OPENAI_CODEX_API_KEY="codex-placeholder",
        OPENAI_CODEX_BASE_URL="https://custom-gateway.example/v1",
        HINAA_OPENAI_KEY_SOURCE="auto",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )
    assert settings.active_openai_key_label == "primary"
    assert settings.active_openai_model == settings.openai_model
    assert settings.custom_configured is True
    with TestClient(create_app(settings)) as client:
        providers = client.get("/v1/providers").json()
    openai = next(provider for provider in providers if provider["id"] == "openai")
    custom = next(provider for provider in providers if provider["id"] == "custom")
    assert "Key source: primary" in openai["userMessage"]
    assert custom["state"] == "healthy"
    assert "primary-placeholder" not in openai["userMessage"]
    assert "codex-placeholder" not in openai["userMessage"]
    assert "codex-placeholder" not in custom["userMessage"]


def test_openai_model_switcher_rejects_unapproved_models_without_provider_call() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="azure-placeholder",
        AZURE_SPEECH_REGION="eastus",
        OPENAI_API_KEY="openai-placeholder",
        HINAA_OPENAI_ALLOWED_MODELS="gpt-5-mini,gpt-5.6-luna",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/v1/conversations/turns:stream",
            json={
                "sessionId": "bad-model",
                "text": "Namaste",
                "companionId": "hinaa",
                "language": "mixed",
                "providerMode": "openai",
                "brainModel": "not-approved-model",
            },
        )
    events = [json.loads(line) for line in response.text.splitlines()]
    error = events[-1]
    assert error["type"] == "error"
    assert error["code"] == "OPENAI_MODEL_NOT_ALLOWED"
    assert "gpt-5.6-luna" in error["message"]
    assert "openai-placeholder" not in error["message"]


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
