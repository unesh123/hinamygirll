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
    cb.record_failure("PROVIDER_UNAVAILABLE", "Error 1")
    assert cb.state == CircuitBreakerState.DEGRADED
    cb.record_failure("PROVIDER_UNAVAILABLE", "Error 2")
    assert cb.state == CircuitBreakerState.DEGRADED
    cb.record_failure("PROVIDER_UNAVAILABLE", "Error 3")
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
