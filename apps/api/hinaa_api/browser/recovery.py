"""Fault Tolerance, Detached Element Recovery, and Bounded Retries.

Distinguishes transient/safe retries from non-idempotent or security blocks,
enforcing exponential backoff and cancellation awareness.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Coroutine, TypeVar

T = TypeVar("T")
logger = logging.getLogger("hinaa.browser.recovery")

# Non-retryable error substrings
_FATAL_ERROR_PATTERNS = [
    "SECURITY_POLICY_VIOLATION",
    "SSRF",
    "PROHIBITED",
    "ACCESS_DENIED",
    "APPROVAL_REQUIRED",
    "CANCELLED",
    "DANGEROUS_EXTENSION",
]


class RecoveryHandler:
    """Coordinates bounded execution retries and stale state recovery."""

    @staticmethod
    def is_retryable(error: Exception) -> bool:
        """Determines if an error is a transient DOM or network failure."""
        err_str = str(error).lower()
        for fatal in _FATAL_ERROR_PATTERNS:
            if fatal.lower() in err_str:
                return False

        retryable_keywords = [
            "element is not attached",
            "frame was detached",
            "execution context was destroyed",
            "target closed",
            "timeout",
            "navigation interrupted",
            "network changed",
        ]
        return any(kw in err_str for kw in retryable_keywords)

    @classmethod
    async def execute_with_retry(
        cls,
        operation: Callable[[], Coroutine[Any, Any, T]],
        max_retries: int = 2,
        initial_delay_seconds: float = 0.5,
        is_idempotent: bool = True,
    ) -> T:
        """Executes an async operation with bounded retries for idempotent actions."""
        attempt = 0
        delay = initial_delay_seconds

        while True:
            try:
                return await operation()
            except Exception as exc:
                attempt += 1
                if not is_idempotent or attempt > max_retries or not cls.is_retryable(exc):
                    logger.warning(
                        "Operation failed permanently (attempt %d/%d, idempotent=%s): %s",
                        attempt,
                        max_retries,
                        is_idempotent,
                        exc,
                    )
                    raise exc

                logger.info(
                    "Retrying transient failure in %.2fs (attempt %d/%d): %s",
                    delay,
                    attempt,
                    max_retries,
                    exc,
                )
                await asyncio.sleep(delay)
                delay *= 2.0
