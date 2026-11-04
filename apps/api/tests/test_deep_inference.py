"""Tests for Phase 03: Deep Inference & Backend Optimization."""

import pytest
import time
from hinaa_api.providers.fabric import (
    ModelRouter,
    TaskType,
    ProviderTier,
    CircuitBreaker,
    CircuitBreakerState,
)


def test_model_router_complexity_scoring():
    router = ModelRouter()

    # Low complexity casual greeting
    casual_score = router.score_complexity("Hello Hina! How's your day?")
    assert casual_score < 0.25

    # High complexity code and architectural query
    hard_prompt = (
        "Refactor this Python FastAPI backend service to use connection pooling, "
        "audit memory leaks in BlueStacks ADB executor, and benchmark AST generation:\n"
        "```python\ndef test(): pass\n```"
    )
    hard_score = router.score_complexity(hard_prompt)
    assert hard_score >= 0.60


def test_model_router_select_optimal_tier():
    router = ModelRouter()

    # Casual query -> Balanced or Ultra-Fast tier
    tier, model = router.select_optimal_tier("Good morning Hina!")
    assert tier in (ProviderTier.BALANCED, ProviderTier.ULTRA_FAST)

    # Complex architecture query -> Reasoning & Code tier
    tier, model = router.select_optimal_tier(
        "Analyze the latency bottlenecks in our distributed tracing spans, optimize sqlite queries, and refactor code."
    )
    assert tier == ProviderTier.REASONING_CODE
    assert "3.8-flash" in model or "reasoning" in model

    # Local Neural Lab preference for low-complexity turns
    tier, model = router.select_optimal_tier("How are you feeling?", use_local_neural_lab=True)
    assert tier == ProviderTier.ULTRA_FAST
    assert "local" in model


def test_circuit_breaker_auto_healing_and_backoff():
    cb = CircuitBreaker(
        failure_threshold=2,
        recovery_timeout_sec=0.1,  # Fast timeout for test
        max_recovery_timeout_sec=2.0,
        success_threshold_to_close=2,
    )

    # Fail twice to trip OPEN
    cb.record_failure()
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.allow_primary_attempt() is False

    # Wait for recovery timeout to transition to HALF_OPEN
    time.sleep(0.12)
    assert cb.allow_primary_attempt() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # 1st success in HALF_OPEN (needs 2)
    cb.record_success()
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # 2nd success in HALF_OPEN -> Healed to CLOSED
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED

    # Telemetry health status
    status = cb.get_health_status()
    assert status["state"] == "closed"
    assert status["failure_count"] == 0
    assert status["recovery_timeout_sec"] == 0.1


def test_circuit_breaker_probe_failure_exponential_backoff():
    cb = CircuitBreaker(
        failure_threshold=1,
        recovery_timeout_sec=0.1,
        max_recovery_timeout_sec=2.0,
    )

    # Trip OPEN
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN

    # Wait for recovery timeout
    time.sleep(0.12)
    assert cb.allow_primary_attempt() is True
    assert cb.state == CircuitBreakerState.HALF_OPEN

    # Probe fails! Should double timeout and return to OPEN
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.recovery_timeout == pytest.approx(0.2, rel=1e-2)
