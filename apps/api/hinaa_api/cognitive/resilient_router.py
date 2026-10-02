"""
HINAA Enterprise Resilient Model Router & Circuit Breaker.

Provides fault-tolerant model dispatching across multi-provider tiers:
1. Circuit Breaker State Machine (CLOSED, OPEN, HALF_OPEN)
2. Autonomous Multi-Tier Fallback Cascade
3. Provider Health & Latency Telemetry
4. Zero-Downtime Graceful Degradation
"""

from __future__ import annotations

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("hinaa.cognitive.router")


class CircuitState(str, Enum):
    CLOSED = "closed"        # Healthy, traffic flows normally
    OPEN = "open"            # Degraded, traffic diverted to backup provider
    HALF_OPEN = "half_open"  # Probing recovery with limited traffic


class ProviderStatus(BaseModel):
    name: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    avg_latency_ms: float = 0.0
    consecutive_failures: int = 0


class ResilientProviderRouter:
    """Enterprise Model Router with Circuit Breaker and Cascading Fallbacks."""

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 60.0,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self._providers: Dict[str, ProviderStatus] = {
            "claude": ProviderStatus(name="claude"),
            "custom": ProviderStatus(name="custom"),
            "agent_router": ProviderStatus(name="agent_router"),
            "gemini": ProviderStatus(name="gemini"),
            "local_rule": ProviderStatus(name="local_rule"),
        }
        self._provider_order = ["claude", "custom", "agent_router", "gemini", "local_rule"]

    def get_provider_status(self, provider_name: str) -> ProviderStatus:
        if provider_name not in self._providers:
            self._providers[provider_name] = ProviderStatus(name=provider_name)
        status = self._providers[provider_name]

        # Check if an OPEN circuit has expired and should transition to HALF_OPEN
        if status.state == CircuitState.OPEN and status.last_failure_time:
            if time.time() - status.last_failure_time > self.recovery_timeout_seconds:
                status.state = CircuitState.HALF_OPEN
                logger.info("Provider '%s' circuit transitioned from OPEN to HALF_OPEN (probing)", provider_name)

        return status

    def record_success(self, provider_name: str, latency_ms: float) -> None:
        status = self.get_provider_status(provider_name)
        status.success_count += 1
        status.consecutive_failures = 0
        status.last_success_time = time.time()
        status.state = CircuitState.CLOSED

        # Exponential moving average for latency
        if status.avg_latency_ms == 0.0:
            status.avg_latency_ms = latency_ms
        else:
            status.avg_latency_ms = round(0.8 * status.avg_latency_ms + 0.2 * latency_ms, 1)

    def record_failure(self, provider_name: str, error: Exception) -> None:
        status = self.get_provider_status(provider_name)
        status.failure_count += 1
        status.consecutive_failures += 1
        status.last_failure_time = time.time()

        if status.consecutive_failures >= self.failure_threshold:
            status.state = CircuitState.OPEN
            logger.warning(
                "Provider '%s' tripped circuit breaker -> OPEN (%d consecutive failures: %s)",
                provider_name,
                status.consecutive_failures,
                error,
            )

    def select_healthy_provider_chain(self, preferred_provider: Optional[str] = None) -> List[str]:
        """Order available providers based on health and circuit state."""
        chain = []
        if preferred_provider and preferred_provider in self._providers:
            pref_status = self.get_provider_status(preferred_provider)
            if pref_status.state != CircuitState.OPEN:
                chain.append(preferred_provider)

        for p_name in self._provider_order:
            if p_name not in chain:
                st = self.get_provider_status(p_name)
                if st.state != CircuitState.OPEN:
                    chain.append(p_name)

        # If all circuits are open, fallback to the last-ditch local rule or gemini
        if not chain:
            chain = ["gemini", "local_rule"]

        return chain

    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        return {
            name: {
                "state": self.get_provider_status(name).state.value,
                "consecutiveFailures": self.get_provider_status(name).consecutive_failures,
                "avgLatencyMs": self.get_provider_status(name).avg_latency_ms,
                "successCount": self.get_provider_status(name).success_count,
                "failureCount": self.get_provider_status(name).failure_count,
            }
            for name in self._providers
        }


# Global resilient router singleton
_global_resilient_router: Optional[ResilientProviderRouter] = None


def get_resilient_router() -> ResilientProviderRouter:
    global _global_resilient_router
    if _global_resilient_router is None:
        _global_resilient_router = ResilientProviderRouter()
    return _global_resilient_router
