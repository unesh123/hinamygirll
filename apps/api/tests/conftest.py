from __future__ import annotations

import io
import os
import wave

import pytest
from fastapi.testclient import TestClient

from hinaa_api.brain_ledger import reset_ledger
from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.vmc_bridge import vmc_bridge


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
        GROQ_API_KEY="",
        OPENAI_API_KEY="",
        OPENAI_CODEX_API_KEY="",
        OPENAI_CODEX_BASE_URL="",
        AGENT_ROUTER_API_KEY="",
        AGENT_ROUTER_BASE_URL="",
        CX_GATEWAY_API_KEY="",
        CX_GATEWAY_BASE_URL="",
        ELEVENLABS_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_VMC_PORT=0,
        _env_file=None,
    )


@pytest.fixture(autouse=True)
def _reset_vmc_bridge():
    """Ensure the VMC singleton releases its UDP port between tests."""
    vmc_bridge.reset()
    yield
    vmc_bridge.reset()


@pytest.fixture(autouse=True)
def _isolated_brain_ledger(tmp_path):
    """Brain verdicts outlive the process by design, so the default ledger path
    is the file the running backend reads. A test must never write it."""
    previous = os.environ.get("HINAA_BRAIN_LEDGER_PATH")
    reset_ledger(tmp_path / "brain_outcomes.json")
    yield
    if previous is None:
        os.environ.pop("HINAA_BRAIN_LEDGER_PATH", None)
    else:
        os.environ["HINAA_BRAIN_LEDGER_PATH"] = previous
    reset_ledger()


@pytest.fixture
def client(settings: Settings) -> TestClient:
    # Loopback base_url so Host names the host machine: the effect policy in
    # tools/policy.py denies machine-touching tools to public-origin requests,
    # and "testserver" reads as one. tests/test_tool_policy.py passes an explicit
    # host header to cover both origins.
    # The dev identity header mirrors what the frontend sends: dev mode rejects
    # anonymous callers, so private-data routes need a named subject.
    with TestClient(
        create_app(settings),
        base_url="http://127.0.0.1:8000",
        headers={"X-HINAA-Dev-User": "test-local-user"},
    ) as value:
        yield value
