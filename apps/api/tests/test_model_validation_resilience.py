import pytest
from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest, SpeechRequest, TextHumanizerRequest
from hinaa_api.realtime import ClientHello


def test_turn_request_engine_sanitization():
    # Valid model ID
    req1 = TurnRequest(sessionId="test-1", text="hello", brainModel="gemini-2.5-flash-lite")
    assert req1.brainModel == "gemini-2.5-flash-lite"

    # String with spaces / parentheses (e.g., label sent instead of ID)
    req2 = TurnRequest(sessionId="test-2", text="hello", brainModel="ElevenLabs (Aisha / Sweet Girlfriend)")
    assert req2.brainModel is None

    # Dash placeholder
    req3 = TurnRequest(sessionId="test-3", text="hello", brainModel="—", voiceEngine="auto")
    assert req3.brainModel is None
    assert req3.voiceEngine is None

    # Empty string
    req4 = TurnRequest(sessionId="test-4", text="hello", brainModel="", imageEngine="   ")
    assert req4.brainModel is None
    assert req4.imageEngine is None


def test_client_hello_sanitization():
    hello = ClientHello(
        type="session.hello",
        protocolVersion="1.0",
        sessionId="sess-123",
        brainModel="—",
        voiceEngine="auto",
    )
    assert hello.brainModel is None
    assert hello.voiceEngine is None


def test_resolve_gemini_model_resilience():
    settings = Settings(
        GEMINI_API_KEY="test-key",
        GEMINI_MODEL="gemini-3.5-flash",
    )
    # Standard models from UI
    assert settings.resolve_gemini_model("gemini-2.5-flash-lite") == "gemini-2.5-flash-lite"
    assert settings.resolve_gemini_model("gemini-3.8-flash") == "gemini-3.8-flash"

    # Unknown / deprecated model falls back safely to default instead of crashing
    assert settings.resolve_gemini_model("unknown-custom-model") == "gemini-3.5-flash"
    assert settings.resolve_gemini_model(None) == "gemini-3.5-flash"
