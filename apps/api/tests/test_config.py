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
    assert settings.missing_real_configuration() == [
        "AZURE_SPEECH_KEY",
        "AZURE_SPEECH_REGION",
        "GEMINI_API_KEY",
    ]
    assert settings.allowed_origins == ["http://127.0.0.1:5173", "http://localhost:5173"]
