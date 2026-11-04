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


class ProviderTier(str, Enum):
    ULTRA_FAST = "ultra_fast"         # Sub-200ms TTFT (Local Neural Lab, XKiro, Gemini Flash Lite)
    BALANCED = "balanced"             # Conversational balance (Gemini 3.6 Flash)
    REASONING_CODE = "reasoning_code" # Complex multi-step reasoning, coding, AST validation (Gemini 3.8 Flash)
    MULTIMODAL = "multimodal"         # Image, document, and screen comprehension
    LIVE_VOICE = "live_voice"         # Real-time streaming voice duplex


class ModelRouter:
    """Intelligently routes requests to the optimal AI model based on
    task type, complexity, latency priority, and tool requirements.
    """

    def score_complexity(self, text: str, context: dict[str, Any] | None = None) -> float:
        """Calculates normalized complexity score (0.0 to 1.0)."""
        ctx = context or {}
        score = 0.0
        t_lower = text.lower().strip()

        # Word length contribution (up to 0.3)
        words = len(t_lower.split())
        score += min(0.3, words / 100.0)

        # Code fences or technical tokens (up to 0.35)
        if "```" in text or any(k in t_lower for k in ("def ", "class ", "import ", "function(", "select *")):
            score += 0.35

        # Analytical keywords (up to 0.25)
        reasoning_keywords = (
            "compare", "research", "investigate", "analyze", "synthesis",
            "breakdown", "evaluate", "calculate", "audit", "code", "refactor",
            "benchmark", "architecture", "diagnose", "optimize"
        )
        keyword_hits = sum(1 for kw in reasoning_keywords if kw in t_lower)
        score += min(0.25, keyword_hits * 0.08)

        # Multi-modal context increases complexity
        if ctx.get("images") or ctx.get("has_document"):
            score += 0.2

        return min(1.0, round(score, 3))

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

    def select_optimal_tier(
        self,
        text: str,
        context: dict[str, Any] | None = None,
        use_local_neural_lab: bool = False,
    ) -> tuple[ProviderTier, str]:
        """Deep inference router mapping query complexity to provider tier and model."""
        task_type = self.classify_task(text, context)
        complexity = self.score_complexity(text, context)

        if task_type == TaskType.LIVE_VOICE:
            return ProviderTier.LIVE_VOICE, "gemini-live"
        if task_type == TaskType.MULTIMODAL:
            return ProviderTier.MULTIMODAL, "gemini-3.8-flash"

        if use_local_neural_lab and complexity < 0.6:
            # Route to local fine-tuned adapter for low-latency zero-cost inference
            return ProviderTier.ULTRA_FAST, "local:hinaa-core-v1"

        if complexity > 0.5 or task_type == TaskType.HARD_PLANNING:
            return ProviderTier.REASONING_CODE, "gemini-3.8-flash"
        elif task_type == TaskType.EXTRACTION or complexity < 0.2:
            return ProviderTier.ULTRA_FAST, "gemini-3.5-flash-lite"
        else:
            return ProviderTier.BALANCED, "gemini-3.6-flash"


class CircuitBreakerState(str, Enum):
    CLOSED = "closed"        # Healthy, routes to primary
    OPEN = "open"            # Primary broken, routes directly to fallback
    HALF_OPEN = "half_open"  # Testing primary recovery


class CircuitBreaker:
    """Manages failure thresholds and failover for external AI providers

    with exponential backoff and auto-healing recovery.
    """

    def __init__(
        self,
        failure_threshold: int = 2,
        recovery_timeout_sec: float = 60.0,
        max_recovery_timeout_sec: float = 300.0,
        success_threshold_to_close: int = 2,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.base_recovery_timeout = recovery_timeout_sec
        self.current_recovery_timeout = recovery_timeout_sec
        self.max_recovery_timeout = max_recovery_timeout_sec
        self.success_threshold = success_threshold_to_close
        
        self.failure_count = 0
        self.consecutive_successes = 0
        self.last_failure_time = 0.0
        self.state = CircuitBreakerState.CLOSED

    @property
    def recovery_timeout(self) -> float:
        """Maintains backward compatibility with tests accessing recovery_timeout directly."""
        return self.current_recovery_timeout

    @recovery_timeout.setter
    def recovery_timeout(self, value: float) -> None:
        self.current_recovery_timeout = value
        self.base_recovery_timeout = value

    def record_success(self) -> None:
        """Records a successful call and handles state transitions."""
        self.failure_count = 0
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.consecutive_successes += 1
            if self.consecutive_successes >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.current_recovery_timeout = self.base_recovery_timeout
                self.consecutive_successes = 0
                logger.info("Circuit breaker healed and reset to CLOSED.")
        else:
            self.state = CircuitBreakerState.CLOSED
            self.current_recovery_timeout = self.base_recovery_timeout

    def record_failure(self) -> None:
        """Records an error, applying exponential backoff when probing in HALF_OPEN."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.consecutive_successes = 0

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Failed during probe: double backoff timeout and re-trip to OPEN
            self.current_recovery_timeout = min(self.max_recovery_timeout, self.current_recovery_timeout * 2.0)
            self.state = CircuitBreakerState.OPEN
            logger.warning(
                "Circuit breaker probe failed in HALF_OPEN. Backoff extended to %.1fs",
                self.current_recovery_timeout,
            )
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitBreakerState.OPEN
            logger.warning("Circuit breaker tripped to OPEN (failures=%d)", self.failure_count)

    def allow_primary_attempt(self) -> bool:
        """Checks if primary call is permitted based on circuit state and recovery timer."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        if self.state == CircuitBreakerState.OPEN:
            if time.time() - self.last_failure_time > self.current_recovery_timeout:
                self.state = CircuitBreakerState.HALF_OPEN
                logger.info("Circuit breaker recovery timeout reached; transitioning to HALF_OPEN probe.")
                return True
            return False
        # HALF_OPEN allows single test attempt
        return True

    def get_health_status(self) -> dict[str, Any]:
        """Returns health telemetry metadata for observability."""
        return {
            "state": self.state.value,
            "failure_count": self.failure_count,
            "consecutive_successes": self.consecutive_successes,
            "recovery_timeout_sec": self.current_recovery_timeout,
            "seconds_since_last_failure": round(time.time() - self.last_failure_time, 2) if self.last_failure_time > 0 else None,
        }


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
