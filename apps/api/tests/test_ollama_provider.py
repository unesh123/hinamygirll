from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
import httpx
import pytest

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.models import AssistantTurnPlan
from hinaa_api.prompts import assemble_prompt
from hinaa_api.prompts.models import PromptInput
from hinaa_api.providers.base import ProviderResult
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.services import ProviderRouter


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "HINAA_PROVIDER_MODE": "mock",
        "HINAA_OLLAMA_BASE_URL": "http://localhost:11434/v1",
        "HINAA_OLLAMA_MODEL": "dolphin-mistral:7b",
        "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "HINAA_AUTH_MODE": "dev",
        "HINAA_PERSISTENCE_ENABLED": True,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _plan() -> AssistantTurnPlan:
    return AssistantTurnPlan(
        spokenText="Hello Unesh, I am running completely offline on Dolphin Mistral.",
        displayText="Hello Unesh, I am running completely offline on Dolphin Mistral.",
        language="mixed",
        emotion={"primary": "happy", "intensity": 0.3, "valence": 0.3, "arousal": 0.2},
        performance={
            "facePreset": "soft_smile",
            "gesture": "none",
            "gazeTarget": "camera",
            "headMotion": "none",
            "blinkRate": 0.4,
        },
        memoryCandidates=[],
        toolRequests=[],
    )


def test_ollama_settings_defaults() -> None:
    settings = _settings()

    assert settings.ollama_configured is True
    assert settings.active_ollama_base_url == "http://localhost:11434/v1"
    assert settings.active_ollama_model == "dolphin-mistral:7b"
    assert settings.resolve_ollama_model() == "dolphin-mistral:7b"
    assert settings.resolve_ollama_model("llama2-uncensored:7b") == "llama2-uncensored:7b"


def test_provider_router_selects_ollama_adapter() -> None:
    provider = ProviderRouter(_settings()).llm("ollama", "dolphin-mistral:7b")

    assert provider.id == "ollama"
    assert isinstance(provider, OpenAILLMProvider)
    assert provider._model == "dolphin-mistral:7b"
    assert provider._base_url == "http://localhost:11434/v1"


def test_ollama_headers_omit_authorization_when_key_empty() -> None:
    provider = OpenAILLMProvider(key="ollama", model="dolphin-mistral:7b", base_url="http://localhost:11434/v1", provider_id="ollama")
    headers = provider._headers()
    assert "Authorization" not in headers

    provider_empty_key = OpenAILLMProvider(key="", model="dolphin-mistral:7b", base_url="http://localhost:11434/v1", provider_id="ollama")
    headers_empty = provider_empty_key._headers()
    assert "Authorization" not in headers_empty


def test_provider_status_detects_ollama_healthy() -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "models": [
            {"name": "dolphin-mistral:7b"},
            {"name": "llama2-uncensored:7b"},
        ]
    }

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
        with TestClient(create_app(_settings())) as client:
            response = client.get("/v1/providers")

    assert response.status_code == 200
    ollama = next(item for item in response.json() if item["id"] == "ollama")
    assert ollama["state"] == "healthy"
    assert "default-model:dolphin-mistral:7b" in ollama["capabilities"]
    assert "model:dolphin-mistral:7b" in ollama["capabilities"]
    assert "model:llama2-uncensored:7b" in ollama["capabilities"]
    assert "Ollama local engine is online" in ollama["userMessage"]


def test_provider_status_handles_ollama_unavailable() -> None:
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=httpx.ConnectError("Connection refused")):
        with TestClient(create_app(_settings())) as client:
            response = client.get("/v1/providers")

    assert response.status_code == 200
    ollama = next(item for item in response.json() if item["id"] == "ollama")
    assert ollama["state"] == "unavailable"
    assert "unreachable" in ollama["userMessage"] or "not running" in ollama["userMessage"]


def test_ollama_live_plan_never_leaks_raw_json_tokens() -> None:
    provider = OpenAILLMProvider(
        "ollama",
        "dolphin-mistral:7b",
        base_url="http://localhost:11434/v1",
        provider_id="ollama",
    )

    async def fake_stream_text(prompt: PromptPackage):
        yield "Hello Unesh! "
        yield "I am running "
        yield "on Dolphin Mistral."

    provider._stream_text = fake_stream_text  # type: ignore[method-assign]
    deltas: list[str] = []

    async def emit_delta(delta: str) -> None:
        deltas.append(delta)

    prompt = assemble_prompt(
        PromptInput(
            companion_id="hinaa",
            interaction_mode="realtime",
            user_text="Hey Hinaa!",
            language="mixed",
        )
    )
    result = asyncio.run(
        provider.create_live_plan("Hey Hinaa!", "hinaa", "mixed", (), emit_delta, prompt)
    )

    assert "".join(deltas) == "Hello Unesh! I am running on Dolphin Mistral."
    assert "Hello Unesh! I am running on Dolphin Mistral." in result.value.displayText
    assert all("spokenText" not in delta and "displayText" not in delta for delta in deltas)


@pytest.mark.asyncio
async def test_ollama_creates_plan_from_plain_prose_fallback() -> None:
    provider = OpenAILLMProvider(
        "ollama",
        "dolphin-mistral:7b",
        base_url="http://localhost:11434/v1",
        provider_id="ollama",
    )

    # When Ollama outputs plain text rather than JSON
    with patch.object(provider, "_chat_json", new_callable=AsyncMock) as mock_chat:
        mock_chat.return_value = "Hey there Unesh! Dolphin Mistral is running fast locally."
        prompt = assemble_prompt(
            PromptInput(
                companion_id="hinaa",
                interaction_mode="rest",
                user_text="Hello!",
                language="mixed",
            )
        )
        result = await provider.create_plan("Hello!", "hinaa", "mixed", (), prompt)

    assert "Hey there Unesh! Dolphin Mistral is running fast locally." in result.value.displayText
    assert result.value.language == "mixed"
