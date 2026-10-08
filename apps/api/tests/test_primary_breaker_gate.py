"""The dead-primary bench: a hung gateway must not be paid a full turn
timeout of silence on every message.

Measured on the live deployment: the configured primary (agent-router)
accepted every request and then never answered, so each typed turn burned the
full 30s ``HINAA_LLM_TIMEOUT_SECONDS`` — and each live voice turn up to the
120s stream idle window — before the fallback chain was even consulted. These
tests pin the three mechanisms that ended that:

1. The breaker benches a provider from its first hang, escalating on repeats.
2. The turn layer records hang outcomes into the breaker (providers never see
   a turn-layer ``asyncio.timeout`` themselves, so they could never learn).
3. The turn paths consult the breaker before trying the primary at all.
"""
from __future__ import annotations

from time import monotonic

import pytest

from hinaa_api.circuit_breaker import (
    CircuitBreakerState,
    ProviderCircuitBreaker,
    get_circuit_breaker,
    peek_circuit_breaker,
    reset_circuit_breakers,
)
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.services import ConversationService


@pytest.fixture(autouse=True)
def clean_breakers():
    reset_circuit_breakers()
    yield
    reset_circuit_breakers()


def _settings() -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=False,
        HINAA_AGENT_RUNTIME_ENABLED=False,
        _env_file=None,
    )


def test_first_hang_benches_the_provider() -> None:
    cb = ProviderCircuitBreaker("agent-router")

    cb.record_failure("PROVIDER_TIMEOUT", "Primary brain timed out after 30s.")

    assert cb.state == CircuitBreakerState.TIMEOUT
    assert cb.cooldown_remaining() > 25.0  # ~30s bench, not the old 3-strikes DEGRADED
    can_exec, reason, _ = cb.can_execute()
    assert can_exec is False
    assert "timeout" in reason


def test_repeated_hangs_escalate_the_bench() -> None:
    cb = ProviderCircuitBreaker("agent-router")

    cb.record_failure("PROVIDER_TIMEOUT", "hang 1")
    first = cb.cooldown_remaining()
    cb.record_failure("PROVIDER_TIMEOUT", "hang 2")
    second = cb.cooldown_remaining()

    assert cb.state == CircuitBreakerState.TIMEOUT
    # 30s -> 60s escalation; consecutive hangs are not a blip.
    assert 25.0 < first <= 30.0
    assert 55.0 < second <= 60.0


def test_cooloff_expiry_allows_one_recovery_probe() -> None:
    cb = ProviderCircuitBreaker("agent-router")
    cb.record_failure("PROVIDER_TIMEOUT", "hang")

    cb.cooloff_until = monotonic() - 1.0
    can_exec, _, _ = cb.can_execute()

    assert can_exec is True
    assert cb.state == CircuitBreakerState.HALF_OPEN


def test_turn_layer_records_hangs_into_the_breaker() -> None:
    service = ConversationService(_settings())

    service._record_brain_call(
        "agent-router",
        ok=False,
        error=HinaaError("PROVIDER_TIMEOUT", "hung", 504, True),
    )

    breaker = peek_circuit_breaker("agent-router")
    assert breaker is not None
    assert breaker.state == CircuitBreakerState.TIMEOUT
    assert breaker.cooldown_remaining() > 0


def test_turn_layer_recording_dedupes_the_providers_own_note() -> None:
    """Providers with their own breaker record the failure themselves; the
    turn layer observing the same call a moment later must not count it twice."""
    service = ConversationService(_settings())
    breaker = get_circuit_breaker("xkiro")
    breaker.record_failure("PROVIDER_UNAVAILABLE", "503 from gateway")

    service._record_brain_call(
        "xkiro",
        ok=False,
        error=HinaaError("PROVIDER_UNAVAILABLE", "503 from gateway", 503, True),
    )

    assert breaker.consecutive_failures == 1


def test_turn_layer_success_clears_the_bench() -> None:
    service = ConversationService(_settings())
    breaker = get_circuit_breaker("xkiro")
    breaker.record_failure("PROVIDER_TIMEOUT", "hung")
    breaker.cooloff_until = 0.0  # cooloff expired; a probe turn ran and answered

    service._record_brain_call("xkiro", ok=True, model="qwen/qwen3.8-max:free")

    assert breaker.state == CircuitBreakerState.READY
    assert breaker.consecutive_failures == 0
    assert breaker.cooldown_remaining() == 0.0


def test_primary_gate_helpers_read_the_breaker() -> None:
    service = ConversationService(_settings())

    # An untried brain has no breaker at all and is always allowed.
    assert service._primary_cooloff_remaining("agent-router") == 0.0
    assert service._primary_probing("agent-router") is False

    get_circuit_breaker("agent-router").record_failure("PROVIDER_TIMEOUT", "hung")
    assert service._primary_cooloff_remaining("agent-router") > 0
    assert service._primary_probing("agent-router") is False

    # Past cooloff but unproven: allowed, on a probe budget.
    get_circuit_breaker("agent-router").cooloff_until = 0.0
    assert service._primary_cooloff_remaining("agent-router") == 0.0
    assert service._primary_probing("agent-router") is True

    # A healthy brain is neither benched nor probing.
    get_circuit_breaker("agent-router").record_success(latency_ms=800)
    assert service._primary_cooloff_remaining("agent-router") == 0.0
    assert service._primary_probing("agent-router") is False


def test_live_idle_default_is_thirty_seconds() -> None:
    """The idle deadline measures silence between tokens; 120s of quiet let a
    hung gateway hold a live voice turn for two minutes before failover."""
    assert _settings().llm_stream_idle_timeout_seconds == 30.0
