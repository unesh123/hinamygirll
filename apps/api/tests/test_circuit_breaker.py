from __future__ import annotations

import pytest
from time import monotonic
from hinaa_api.circuit_breaker import (
    CircuitBreakerState,
    ProviderCircuitBreaker,
    get_circuit_breaker,
    reset_circuit_breakers,
)
from hinaa_api.reachability import probe_gateway_3stage, reset_inference_cache


@pytest.fixture(autouse=True)
def clean_circuit_breakers():
    reset_circuit_breakers()
    reset_inference_cache()
    yield
    reset_circuit_breakers()
    reset_inference_cache()


def test_circuit_breaker_lifecycle():
    cb = ProviderCircuitBreaker("test-provider", failure_threshold=3, base_cooldown_seconds=10.0)

    # 1. Starts in READY
    assert cb.state == CircuitBreakerState.READY
    can_exec, _, _ = cb.can_execute()
    assert can_exec is True

    # 2. Record success
    cb.record_success(latency_ms=120)
    assert cb.state == CircuitBreakerState.READY
    assert cb.last_latency_ms == 120

    # 3. Record rate limit (429)
    cb.record_failure("PROVIDER_RATE_LIMIT", "Too many requests", retry_after=5.0)
    assert cb.state == CircuitBreakerState.RATE_LIMITED
    can_exec, reason, remaining = cb.can_execute()
    assert can_exec is False
    assert "rate_limited cooldown" in reason
    assert remaining > 0

    # 4. Simulate cooldown expiration -> transitions to HALF_OPEN
    cb.cooloff_until = monotonic() - 1.0
    can_exec, _, _ = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # 5. Success in HALF_OPEN resets to READY
    cb.record_success(latency_ms=90)
    assert cb.state == CircuitBreakerState.READY

    # 6. Consecutive failures trip CIRCUIT_OPEN
    cb.record_failure("SERVER_ERROR", "Error 1")
    assert cb.state == CircuitBreakerState.DEGRADED
    cb.record_failure("SERVER_ERROR", "Error 2")
    assert cb.state == CircuitBreakerState.DEGRADED
    cb.record_failure("SERVER_ERROR", "Error 3")
    assert cb.state == CircuitBreakerState.CIRCUIT_OPEN
    can_exec, reason, _ = cb.can_execute()
    assert can_exec is False
    assert "circuit_open cooldown" in reason


@pytest.mark.asyncio
async def test_3stage_health_unconfigured():
    reset_inference_cache()
    outcome = await probe_gateway_3stage(
        base_url=None,
        api_key=None,
        model="gpt-5.6-sol",
        provider_id="cx-gateway",
    )
    assert outcome.configured is False
    assert outcome.state == "unavailable"
    assert "requires both base URL and API key" in outcome.user_message


@pytest.mark.asyncio
async def test_3stage_health_rate_limited_circuit_breaker():
    reset_circuit_breakers()
    reset_inference_cache()
    cb = get_circuit_breaker("cx-gateway")
    cb.record_failure("PROVIDER_RATE_LIMIT", "Upstream 429", retry_after=30.0)

    outcome = await probe_gateway_3stage(
        base_url="https://example.com/v1",
        api_key="sk-test",
        model="cx/gpt-5.6-sol",
        provider_id="cx-gateway",
    )
    assert outcome.configured is True
    assert outcome.inference is False
    assert outcome.state == "rate_limited"
    assert outcome.retry_after_seconds > 0


def test_provider_unavailable_recovers_after_cooldown(tmp_path) -> None:
    """Transient 5xx PROVIDER_UNAVAILABLE must not lock a provider in AUTH_ERROR."""
    import json
    from time import time as wall_time
    from hinaa_api.circuit_breaker import disable_persistence, enable_persistence

    cb = ProviderCircuitBreaker("claude")
    cb.record_failure("PROVIDER_UNAVAILABLE", "503 from gateway")
    assert cb.state == CircuitBreakerState.MODEL_UNAVAILABLE
    cb.cooloff_until = monotonic() - 1.0
    can_exec, _, _ = cb.can_execute()
    assert can_exec is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Legacy persisted AUTH_ERROR caused by PROVIDER_UNAVAILABLE is healed on restore.
    state_file = tmp_path / "breakers.json"
    state_file.write_text(
        json.dumps({
            "claude": {
                "state": "auth_error",
                "consecutiveFailures": 1,
                "cooloffUntilWall": wall_time() + 100,
                "lastFailureCode": "PROVIDER_UNAVAILABLE",
                "lastFailureMessage": "503",
            }
        }),
        encoding="utf-8",
    )
    reset_circuit_breakers()
    enable_persistence(state_file)
    try:
        healed = get_circuit_breaker("claude")
        assert healed.state == CircuitBreakerState.READY
    finally:
        disable_persistence()


@pytest.mark.asyncio
async def test_xkiro_stream_retries_transient_overloaded_sse(monkeypatch) -> None:
    """Inline SSE overload errors on HTTP 200 retry on the same pinned model."""
    import asyncio
    from contextlib import asynccontextmanager
    from hinaa_api.prompts.assembly import assemble_prompt
    from hinaa_api.prompts.models import PromptInput
    from hinaa_api.providers.openai_llm import OpenAILLMProvider

    prompt = assemble_prompt(PromptInput(companion_id="hinaa", interaction_mode="realtime", user_text="hi"))
    calls = 0

    class FakeResp:
        def __init__(self, lines: list[str]) -> None:
            self.status_code = 200
            self.headers: dict[str, str] = {}
            self._lines = lines
            self.text = ""

        async def aiter_lines(self):
            for ln in self._lines:
                yield ln

    class FakeClient:
        @asynccontextmanager
        async def stream(self, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                yield FakeResp([
                    'data: {"error":{"message":"This model is temporarily overloaded upstream. Please retry in a few seconds.","type":"server_error"}}',
                ])
            else:
                yield FakeResp([
                    'data: {"choices":[{"delta":{"content":"56"}}]}',
                    "data: [DONE]",
                ])

    @asynccontextmanager
    async def fake_pooled_client():
        yield FakeClient()

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("hinaa_api.providers.openai_llm._pooled_client", fake_pooled_client)
    monkeypatch.setattr(asyncio, "sleep", no_sleep)

    provider = OpenAILLMProvider(
        "test-key",
        "openai/gpt-6.2-sol",
        base_url="https://api.xkiro.com/v1",
        provider_id="xkiro",
    )
    chunks = [chunk async for chunk in provider._stream_text(prompt)]
    assert calls == 2
    assert "".join(chunks) == "56"
