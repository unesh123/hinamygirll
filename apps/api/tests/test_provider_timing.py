from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.providers.timing import STAGE_ORDER, ProviderTiming
from hinaa_api.services import ConversationService


def test_provider_timing_omits_missing_stages() -> None:
    # Exact binary-friendly seconds to avoid float truncation surprises.
    ticks = iter([0.0, 0.05, 0.25])
    timing = ProviderTiming(now=lambda: next(ticks))
    timing.mark("prompt_built")
    timing.mark("first_text_delta")
    snap = timing.snapshot()
    assert snap["prompt_built"] == 50
    assert snap["first_text_delta"] == 250
    assert "plan_validated" not in snap
    assert list(snap) == [stage for stage in STAGE_ORDER if stage in snap]


@pytest.mark.asyncio
async def test_mock_live_plan_emits_sanitized_timing_stages() -> None:
    settings = Settings(
        HINAA_PROVIDER_MODE="mock",
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )
    service = ConversationService(settings)
    deltas: list[str] = []

    async def emit(delta: str) -> None:
        deltas.append(delta)

    result = await service.create_live_plan(
        TurnRequest(
            sessionId="timing-mock",
            text="Namaste explain briefly",
            companionId="hinaa",
            language="mixed",
            providerMode="mock",
        ),
        emit,
    )
    assert deltas
    assert result.stages is not None
    for key in (
        "prompt_built",
        "provider_client_ready",
        "request_sent",
        "first_text_delta",
        "text_complete",
        "plan_validated",
    ):
        assert key in result.stages
        assert isinstance(result.stages[key], int)
        assert result.stages[key] >= 0
    # Mock path synthesizes deltas after the plan exists.
    assert result.stages["first_text_delta"] >= result.stages["plan_validated"]


@pytest.mark.asyncio
async def test_live_plan_brain_timeout_engages_neutral_fallback() -> None:
    """A brain-provider timeout must never escape create_live_plan.

    The primary LLM is wrapped in ``llm_timeout_seconds`` (and the fast
    fallback is too). If both hang, the neutral fallback plan must be emitted
    instead of a raw TimeoutError killing the websocket turn.
    """
    settings = Settings(
        HINAA_PROVIDER_MODE="cx-gateway",
        CX_GATEWAY_API_KEY="test_cx_key",
        CX_GATEWAY_BASE_URL="https://cx.example.com",
        CX_GATEWAY_MODEL="cx/gpt-5.6-sol",
        CX_GATEWAY_ALLOWED_MODELS="cx/gpt-5.6-sol",
        HINAA_LLM_TIMEOUT_SECONDS=0.05,  # tiny so the fake provider always trips it
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        GEMINI_API_KEY="",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        _env_file=None,
    )
    service = ConversationService(settings)
    deltas: list[str] = []

    async def emit(delta: str) -> None:
        deltas.append(delta)

    result = await service.create_live_plan(
        TurnRequest(
            sessionId="timeout-live",
            text="hello there",
            companionId="hinaa",
            language="mixed",
            providerMode="cx-gateway",
        ),
        emit,
    )
    # The neutral fallback is served and streamed instead of raising.
    assert result.provider.startswith("fallback:")
    assert deltas
    assert result.value.displayText


def test_ordinary_api_tests_remain_provider_free(client: TestClient) -> None:
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body.get("mode") == "mock"
