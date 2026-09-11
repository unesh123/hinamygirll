from __future__ import annotations

import logging
import re
import time
from enum import Enum
from typing import Any, Protocol
from .base import ProviderResult

logger = logging.getLogger("hinaa.providers.fabric")


class TaskType(str, Enum):
    HARD_PLANNING = "hard_planning"
    CONVERSATION = "conversation"
    EXTRACTION = "extraction"
    MULTIMODAL = "multimodal"
    LIVE_VOICE = "live_voice"


class ModelRouter:
    """Intelligently routes requests to the optimal AI model based on

    task type, complexity, latency priority, and tool requirements.
    """

    def classify_task(self, text: str, context: dict[str, Any] | None = None) -> TaskType:
        """Classifies the task type based on intent and lexical complexity."""
        ctx = context or {}
        t_lower = text.lower().strip()

        # Multimodal check
        if ctx.get("images") or ctx.get("has_document") or ctx.get("file_type") in ("pdf", "image"):
            return TaskType.MULTIMODAL

        # Voice session check
        if ctx.get("is_voice_session") or ctx.get("modality") == "audio":
            return TaskType.LIVE_VOICE

        # Extraction / Classification (fact remembering, entity extraction)
        if re.match(r"(?i)^(?:remember\s+that|extract|tag|categorize|classify)\b", t_lower):
            return TaskType.EXTRACTION

        # Hard reasoning & multi-step planning
        is_hard_reasoning = bool(
            re.search(
                r"\b(compare|research|investigate|analyze|synthesis|breakdown|evaluate|calculate|audit|code|refactor|benchmark|best\s+\w+\s+under)\b",
                t_lower,
            )
            or len(t_lower.split()) > 25
        )
        if is_hard_reasoning:
            return TaskType.HARD_PLANNING

        # Default standard conversation
        return TaskType.CONVERSATION

    def select_model(
        self,
        task_type: TaskType,
        custom_override: str | None = None,
    ) -> str:
        """Returns the recommended model identifier for the given task."""
        if custom_override:
            return custom_override

        if task_type == TaskType.HARD_PLANNING:
            return "gemini-3.8-flash"
        elif task_type == TaskType.CONVERSATION:
            return "gemini-3.6-flash"
        elif task_type == TaskType.EXTRACTION:
            return "gemini-3.5-flash-lite"
        elif task_type == TaskType.MULTIMODAL:
            return "gemini-3.8-flash"
        elif task_type == TaskType.LIVE_VOICE:
            return "gemini-live"
        return "gemini-3.6-flash"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"      # Healthy, routes to primary
    OPEN = "open"          # Primary broken, routes directly to fallback
    HALF_OPEN = "half_open"# Testing primary recovery


class CircuitBreaker:
    """Manages failure thresholds and failover for external AI providers."""

    def __init__(self, failure_threshold: int = 2, recovery_timeout_sec: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout_sec
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.state = CircuitBreakerState.CLOSED

    def record_success(self) -> None:
        self.failure_count = 0
        self.state = CircuitBreakerState.CLOSED

    def record_failure(self) -> None:
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker tripped to OPEN (failures=%d)", self.failure_count)

    def allow_primary_attempt(self) -> bool:
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                return True
            return False
        # HALF_OPEN allows single test attempt
        return True


class ResilientProviderExecutor:
    """Executes requests against a primary provider with seamless circuit-breaker

    failover to a secondary provider when errors occur.
    """

    def __init__(
        self,
        primary_name: str,
        primary_call: Any,
        fallback_name: str,
        fallback_call: Any,
        breaker: CircuitBreaker | None = None,
    ) -> None:
        self.primary_name = primary_name
        self.primary_call = primary_call
        self.fallback_name = fallback_name
        self.fallback_call = fallback_call
        self.breaker = breaker or CircuitBreaker()

    async def execute(self, *args, **kwargs) -> tuple[Any, str, bool]:
        """Returns (result, provider_used, did_failover)."""
        if self.breaker.allow_primary_attempt():
            try:
                res = await self.primary_call(*args, **kwargs)
                self.breaker.record_success()
                return res, self.primary_name, False
            except Exception as exc:
                logger.warning("Primary provider %s failed: %s. Tripping failover.", self.primary_name, exc)
                self.breaker.record_failure()

        # Fallback path
        logger.info("Executing via fallback provider: %s", self.fallback_name)
        res = await self.fallback_call(*args, **kwargs)
        return res, self.fallback_name, True
