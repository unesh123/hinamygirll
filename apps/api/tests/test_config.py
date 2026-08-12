from __future__ import annotations

from hinaa_api.config import Settings


def test_missing_credentials_keep_mock_mode_safe() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        HINAA_ALLOWED_ORIGINS="http://127.0.0.1:5173,http://localhost:5173",
        _env_file=None,
    )
    assert settings.provider_mode == "mock"
    missing = settings.missing_real_configuration()
    # Without ElevenLabs or Azure, voice provider is missing
    assert any("ELEVENLABS" in m or "AZURE" in m for m in missing)
    assert "GEMINI_API_KEY" in missing
    assert settings.allowed_origins == ["http://127.0.0.1:5173", "http://localhost:5173"]


def test_default_database_is_private_and_durable() -> None:
    settings = Settings(_env_file=None, HINAA_PROVIDER_MODE="mock")
    assert settings.database_url.startswith("sqlite+pysqlite:///")
    assert not settings.database_url.endswith(":memory:")
    assert ".hinaa/hinaa.db" in settings.database_url


def test_llm_timeout_is_independent_of_media_timeout() -> None:
    """The brain (LLM) gets a large timeout budget while media calls fail fast.

    Reasoning models (cx/gpt-5.6-sol) spend hidden ``reasoning_content``
    tokens before the first visible token, so the 8s media timeout must never
    apply to the LLM turn or the reply gets cut mid-thought.
    """
    settings = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
    )
    assert settings.provider_timeout_seconds == 8.0
    assert settings.llm_timeout_seconds == 60.0
    assert settings.llm_timeout_seconds > settings.provider_timeout_seconds

    overridden = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_LLM_TIMEOUT_SECONDS=45,
    )
    assert overridden.llm_timeout_seconds == 45.0
    assert overridden.provider_timeout_seconds == 8.0


def test_real_mode_passes_when_elevenlabs_configured() -> None:
    """ElevenLabs alone (no Azure) satisfies real mode voice requirement."""
    settings = Settings(
        HINAA_PROVIDER_MODE="real",
        ELEVENLABS_API_KEY="sk-test-key-123",
        ELEVENLABS_VOICE_ID="TRnaQb7q41oL7sV0w6Bu",
        GEMINI_API_KEY="sk-gemini-test-key",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        HINAA_ALLOWED_ORIGINS="http://127.0.0.1:5173",
        _env_file=None,
    )
    assert settings.elevenlabs_configured is True
    assert settings.missing_real_configuration() == []



def test_agent_router_requires_key_and_base_url() -> None:
    key_only = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        AGENT_ROUTER_API_KEY="test-agent-key",
    )
    assert key_only.agent_router_configured is False

    configured = Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        AGENT_ROUTER_API_KEY="test-agent-key",
        AGENT_ROUTER_BASE_URL="https://router.example.test",
    )
    assert configured.agent_router_configured is True
    assert configured.active_agent_router_base_url == "https://router.example.test/v1"
