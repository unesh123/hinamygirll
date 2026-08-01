from __future__ import annotations

import io
import wave

import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app


def pcm_wav(seconds: float = 0.08) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(16_000)
        target.writeframes(b"\x01\x00" * int(16_000 * seconds))
    return output.getvalue()


@pytest.fixture
def settings() -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
    )


@pytest.fixture
def client(settings: Settings) -> TestClient:
    with TestClient(create_app(settings)) as value:
        yield value
