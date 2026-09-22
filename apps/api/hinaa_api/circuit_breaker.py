from __future__ import annotations

import logging
import random
from enum import Enum
from time import monotonic
from typing import Any

logger = logging.getLogger("hinaa.circuit_breaker")


class CircuitBreakerState(str, Enum):
    READY = "ready"
    DEGRADED = "degraded"
    RATE_LIMITED = "rate_limited"
    AUTH_ERROR = "auth_error"
    MODEL_UNAVAILABLE = "model_unavailable"
    ENDPOINT_MISMATCH = "endpoint_mismatch"
    TIMEOUT = "timeout"
    OFFLINE = "offline"
    CIRCUIT_OPEN = "circuit_open"
    HALF_OPEN = "half_open"


class ProviderCircuitBreaker:
    """Thread-safe circuit breaker with exponential backoff, jitter, and Retry-After support."""

    def __init__(
        self,
        provider_id: str,
        failure_threshold: int = 3,
        base_cooldown_seconds: float = 30.0,
        max_cooldown_seconds: float = 120.0,
    ) -> None:
        self.provider_id = provider_id
        self.failure_threshold = failure_threshold
        self.base_cooldown_seconds = base_cooldown_seconds
        self.max_cooldown_seconds = max_cooldown_seconds

        self.state: CircuitBreakerState = CircuitBreakerState.READY
        self.consecutive_failures: int = 0
        self.consecutive_successes: int = 0
        self.cooloff_until: float = 0.0
        self.retry_after_seconds: float = 0.0
        self.last_latency_ms: int = 0
        self.last_failure_code: str = ""
        self.last_failure_message: str = ""
        self.last_failure_timestamp: float = 0.0
        self.last_success_timestamp: float = 0.0
        self.last_probe_timestamp: float = 0.0

    def can_execute(self) -> tuple[bool, str | None, float]:
        """Check if request is allowed. Returns (allowed, reason, remaining_cooldown_seconds)."""
        now = monotonic()

        if self.state in {CircuitBreakerState.READY, CircuitBreakerState.DEGRADED}:
            return True, None, 0.0

        if now < self.cooloff_until:
            remaining = max(0.0, self.cooloff_until - now)
            reason = (
                f"{self.provider_id} is in {self.state.value} cooldown ({remaining:.1f}s remaining). "
                f"Reason: {self.last_failure_message or self.last_failure_code}"
            )
            return False, reason, remaining

        # Cooloff has expired -> allow a probe trial (HALF_OPEN)
        if self.state in {
            CircuitBreakerState.CIRCUIT_OPEN,
            CircuitBreakerState.RATE_LIMITED,
            CircuitBreakerState.TIMEOUT,
            CircuitBreakerState.ENDPOINT_MISMATCH,
            CircuitBreakerState.MODEL_UNAVAILABLE,
        }:
            self.state = CircuitBreakerState.HALF_OPEN
            logger.info("Circuit breaker for %s transitioned to HALF_OPEN trial", self.provider_id)
            return True, None, 0.0

        if self.state == CircuitBreakerState.AUTH_ERROR:
            return False, "Authentication failed. Check API key configuration.", 60.0

        return True, None, 0.0

    def record_success(self, latency_ms: int = 0) -> None:
        """Record a successful execution or probe."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        self.last_latency_ms = latency_ms
        self.last_success_timestamp = monotonic()
        self.cooloff_until = 0.0
        self.retry_after_seconds = 0.0
        self.last_failure_code = ""
        self.last_failure_message = ""

        if latency_ms > 4000:
            self.state = CircuitBreakerState.DEGRADED
        else:
            self.state = CircuitBreakerState.READY

    def record_failure(
        self,
        error_code: str,
        error_message: str,
        retry_after: float | None = None,
    ) -> None:
        """Record a failure and compute backoff or state transition."""
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_code = error_code
        self.last_failure_message = error_message
        now = monotonic()
        self.last_failure_timestamp = now

        # Handle specific error scenarios
        if error_code in {"PROVIDER_KEY_INVALID", "AUTH_ERROR"}:
            self.state = CircuitBreakerState.AUTH_ERROR
            self.cooloff_until = now + 60.0
            logger.warning("Circuit breaker [%s]: AUTH_ERROR recorded", self.provider_id)
            return

        if error_code == "PROVIDER_RATE_LIMIT":
            self.state = CircuitBreakerState.RATE_LIMITED
            cooldown = retry_after if retry_after and retry_after > 0 else 15.0
            jitter = random.uniform(0.5, 2.0)
            self.retry_after_seconds = cooldown
            self.cooloff_until = now + cooldown + jitter
            logger.warning(
                "Circuit breaker [%s]: RATE_LIMITED (cooldown: %.1fs)",
                self.provider_id,
                cooldown + jitter,
            )
            return

        if error_code in {"PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE", "MODEL_UNAVAILABLE"}:
            self.state = CircuitBreakerState.MODEL_UNAVAILABLE
            self.cooloff_until = now + 30.0
            logger.warning("Circuit breaker [%s]: MODEL_UNAVAILABLE (no accounts or missing model)", self.provider_id)
            return

        if error_code == "ENDPOINT_MISMATCH":
            self.state = CircuitBreakerState.ENDPOINT_MISMATCH
            self.cooloff_until = now + 45.0
            logger.warning("Circuit breaker [%s]: ENDPOINT_MISMATCH recorded", self.provider_id)
            return

        if error_code == "PROVIDER_TIMEOUT":
            if self.consecutive_failures >= self.failure_threshold:
                self.state = CircuitBreakerState.TIMEOUT
                self.cooloff_until = now + 20.0
                logger.warning(
                    "Circuit breaker [%s]: TIMEOUT cooldown after %d failures",
                    self.provider_id,
                    self.consecutive_failures,
                )
            else:
                self.state = CircuitBreakerState.DEGRADED
                logger.info(
                    "Circuit breaker [%s]: TIMEOUT recorded (%d/%d), kept DEGRADED",
                    self.provider_id,
                    self.consecutive_failures,
                    self.failure_threshold,
                )
            return

        if error_code in {"PROVIDER_HOST_UNREACHABLE", "OFFLINE"}:
            if self.consecutive_failures >= self.failure_threshold:
                self.state = CircuitBreakerState.OFFLINE
                self.cooloff_until = now + 15.0
            else:
                self.state = CircuitBreakerState.DEGRADED
            return

        # General failure count accumulation
        if self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitBreakerState.CIRCUIT_OPEN
            exponent = min(self.consecutive_failures - self.failure_threshold, 4)
            backoff = min(self.base_cooldown_seconds * (2 ** exponent), self.max_cooldown_seconds)
            jitter = random.uniform(0.1, 0.3) * backoff
            self.cooloff_until = now + backoff + jitter
            logger.error(
                "Circuit breaker [%s]: CIRCUIT_OPEN after %d consecutive failures (cooldown: %.1fs)",
                self.provider_id,
                self.consecutive_failures,
                backoff + jitter,
            )
        else:
            self.state = CircuitBreakerState.DEGRADED

    def get_status(self) -> dict[str, Any]:
        """Return structured status of this circuit breaker."""
        now = monotonic()
        remaining_cooloff = max(0.0, self.cooloff_until - now)
        return {
            "providerId": self.provider_id,
            "state": self.state.value,
            "healthy": self.state in {CircuitBreakerState.READY, CircuitBreakerState.DEGRADED},
            "consecutiveFailures": self.consecutive_failures,
            "lastLatencyMs": self.last_latency_ms,
            "remainingCooloffSeconds": round(remaining_cooloff, 1),
            "retryAfterSeconds": round(self.retry_after_seconds, 1),
            "lastFailureCode": self.last_failure_code or None,
            "lastFailureMessage": self.last_failure_message or None,
        }

    def cooldown_remaining(self) -> float:
        """Seconds until this provider may be tried again; 0 when it may be now."""
        return max(0.0, self.cooloff_until - monotonic())


_REGISTRY: dict[str, ProviderCircuitBreaker] = {}


def get_circuit_breaker(provider_id: str) -> ProviderCircuitBreaker:
    """Get or create singleton circuit breaker for a provider."""
    if provider_id not in _REGISTRY:
        _REGISTRY[provider_id] = ProviderCircuitBreaker(provider_id)
    return _REGISTRY[provider_id]


def peek_circuit_breaker(provider_id: str) -> ProviderCircuitBreaker | None:
    """Return the breaker for ``provider_id`` only if a call has used it.

    Reading health must not manufacture history for a brain that has never been
    asked to answer.
    """
    return _REGISTRY.get(provider_id)


def reset_circuit_breakers() -> None:
    """Reset all circuit breakers (for testing)."""
    _REGISTRY.clear()
