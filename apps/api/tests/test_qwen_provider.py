from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

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
        "HINAA_QWEN_API_KEY": "test-qwen-key",
        "HINAA_DATABASE_URL": "sqlite+pysqlite:///:memory:",
        "HINAA_AUTH_MODE": "dev",
        "HINAA_PERSISTENCE_ENABLED": True,
        "_env_file": None,
    }
    values.update(overrides)
    return Settings(**values)


def _plan() -> AssistantTurnPlan:
    return AssistantTurnPlan(
        spokenText="I am here, Unesh. What would you like to work on?",
        displayText="I am here, Unesh. What would you like to work on?",
        language="mixed",
        emotion={"primary": "happy", "intensity": 0.24, "valence": 0.2, "arousal": 0.1},
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


def test_qwen_router_uses_official_compatible_endpoint_and_model_catalog() -> None:
    settings = _settings()

    provider = ProviderRouter(settings).llm("qwen", "qwen3.7-plus")

    assert isinstance(provider, OpenAILLMProvider)
    assert provider.id == "qwen"
    assert settings.active_qwen_base_url == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    assert settings.resolve_qwen_model() == "qwen3.7-plus"
    assert "qwen3.5-flash" in settings.qwen_allowed_models


def test_qwen_status_is_secret_safe_and_lists_models() -> None:
    with TestClient(create_app(_settings())) as client:
        response = client.get("/v1/providers")

    assert response.status_code == 200
    qwen = next(item for item in response.json() if item["id"] == "qwen")
    assert qwen["state"] == "healthy"
    assert "openai-compatible" in qwen["capabilities"]
    assert "default-model:qwen3.7-plus" in qwen["capabilities"]
    assert "test-qwen-key" not in str(qwen)


def test_qwen_live_plan_never_emits_structured_contract() -> None:
    provider = OpenAILLMProvider(
        "test-qwen-key",
        "qwen3.7-plus",
        base_url="https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        provider_id="qwen",
    )
    plan = _plan()

    async def fake_create_plan(*args: object, **kwargs: object) -> ProviderResult[AssistantTurnPlan]:
        return ProviderResult(plan, "qwen:qwen3.7-plus", 12)

    provider.create_plan = fake_create_plan  # type: ignore[method-assign]
    deltas: list[str] = []

    async def emit_delta(delta: str) -> None:
        deltas.append(delta)

    prompt = assemble_prompt(
        PromptInput(
            companion_id="hinaa",
            interaction_mode="realtime",
            user_text="Can you hear me?",
            language="mixed",
        )
    )
    result = asyncio.run(
        provider.create_live_plan("Can you hear me?", "hinaa", "mixed", (), emit_delta, prompt)
    )

    assert result.value == plan
    assert "".join(deltas) == plan.displayText
    assert all("spokenText" not in delta and "displayText" not in delta for delta in deltas)
