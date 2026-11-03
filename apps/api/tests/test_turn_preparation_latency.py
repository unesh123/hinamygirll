"""Offline regressions for work performed before the first model token."""

import asyncio
from unittest.mock import Mock

import pytest

from hinaa_api.config import Settings
from hinaa_api.models import TurnRequest
from hinaa_api.services import ConversationService


@pytest.mark.parametrize("live", [False, True])
@pytest.mark.parametrize("text,recall_count", [("hello", 0), ("Explain binary search in detail.", 1)])
def test_fast_turn_skips_historical_recall_but_detailed_turn_retains_it(live, text, recall_count):
    service = ConversationService(Settings(HINAA_PROVIDER_MODE="mock", _env_file=None))
    service.rag_service = None
    memory = Mock()
    memory.assemble_memory_context.return_value = {"graph_facts": [], "recalled_episodes": []}
    service.advanced_memory = memory
    request = TurnRequest(text=text, sessionId="latency-test", providerMode="mock")

    async def run():
        if live:
            async def emit(_delta):
                pass
            return await service.create_live_plan(request, emit)
        return await service.create_plan(request)

    result = asyncio.run(run())
    assert result.value.displayText
    assert memory.assemble_memory_context.call_count == recall_count


def test_live_prompt_timing_includes_context_preparation(monkeypatch):
    from hinaa_api.providers.timing import ProviderTiming

    clock = [0.0]
    monkeypatch.setattr(
        "hinaa_api.providers.timing.ProviderTiming",
        lambda: ProviderTiming(now=lambda: clock[0]),
    )
    service = ConversationService(Settings(HINAA_PROVIDER_MODE="mock", _env_file=None))
    service.rag_service = None
    service.advanced_memory = None
    capture = service._capture_turn_facts

    def capture_with_preparation(*args, **kwargs):
        clock[0] += 0.25
        return capture(*args, **kwargs)

    monkeypatch.setattr(service, "_capture_turn_facts", capture_with_preparation)

    async def emit(_delta):
        pass

    result = asyncio.run(service.create_live_plan(
        TurnRequest(text="hello", sessionId="timing-test", providerMode="mock"), emit,
    ))
    assert result.stages["prompt_built"] == 250
