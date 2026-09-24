import pytest
from hinaa_api.providers.fabric import (
    ModelRouter,
    TaskType,
    CircuitBreaker,
    CircuitBreakerState,
    ResilientProviderExecutor,
)


def test_model_router_task_classification():
    router = ModelRouter()

    # Simple chat
    assert router.classify_task("Hello Hina! How's your day?") == TaskType.CONVERSATION

    # Hard multi-step research / comparison
    hard_prompt = "Compare RTX 5080 and RTX 5090 laptops under $2500, calculate value per dollar, and synthesize benchmarks"
    assert router.classify_task(hard_prompt) == TaskType.HARD_PLANNING

    # Extraction / Memory
    assert router.classify_task("Remember that I prefer dark mode and Toji") == TaskType.EXTRACTION

    # Multimodal context
    assert router.classify_task("Analyze this layout", context={"has_document": True}) == TaskType.MULTIMODAL

    # Audio session
    assert router.classify_task("Hi Hina", context={"is_voice_session": True}) == TaskType.LIVE_VOICE


def test_model_router_select_model():
    router = ModelRouter()
    assert router.select_model(TaskType.HARD_PLANNING) == "gemini-3.8-flash"
    assert router.select_model(TaskType.CONVERSATION) == "gemini-3.6-flash"
    assert router.select_model(TaskType.EXTRACTION) == "gemini-3.5-flash-lite"
    assert router.select_model(TaskType.LIVE_VOICE) == "gemini-live"


def test_circuit_breaker_tripping():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout_sec=5.0)
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.allow_primary_attempt() is True

    # 1st failure - still closed
    cb.record_failure()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.allow_primary_attempt() is True

    # 2nd failure - trips to OPEN
    cb.record_failure()
    assert cb.state == CircuitBreakerState.OPEN
    assert cb.allow_primary_attempt() is False

    # Success resets breaker
    cb.record_success()
    assert cb.state == CircuitBreakerState.CLOSED
    assert cb.allow_primary_attempt() is True


@pytest.mark.asyncio
async def test_resilient_executor_failover():
    async def broken_primary(prompt: str):
        raise RuntimeError("Gateway 404: Endpoint unreachable")

    async def healthy_fallback(prompt: str):
        return f"Fallback response to: {prompt}"

    executor = ResilientProviderExecutor(
        primary_name="claude-gateway",
        primary_call=broken_primary,
        fallback_name="gemini-3.8-flash",
        fallback_call=healthy_fallback,
    )

    result, provider, did_failover = await executor.execute("Hello")
    assert did_failover is True
    assert provider == "gemini-3.8-flash"
    assert "Fallback response" in result
