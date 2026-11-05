"""
HINAA OS — Phase 11 Budget & Resource Quota Controller
Tracks token expenditure, tool invocation limits, wall-clock time,
concurrency, and integer paisa monetary limits with hard-ceiling admission.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from .contracts import BudgetLedger

logger = logging.getLogger("hinaa.agents.budget")


class BudgetController:
    """Enforces strict resource limits, cost ceilings, and concurrency boundaries."""

    def __init__(self, ledger: Optional[BudgetLedger] = None, max_concurrency: int = 5) -> None:
        self.ledger = ledger or BudgetLedger()
        self.max_concurrency = max_concurrency
        self.active_concurrency = 0
        self.start_wall_time = time.perf_counter()

    def record_tokens(self, tokens: int, cost_usd: float = 0.0, cost_paisa: int = 0) -> None:
        """Record consumed model tokens and monetary expenditure."""
        self.ledger.consumed_tokens += max(0, tokens)
        self.ledger.consumed_cost_usd += max(0.0, cost_usd)
        self.ledger.consumed_cost_paisa += max(0, cost_paisa)

    def record_tool_call(self) -> None:
        """Record an executed tool invocation."""
        self.ledger.consumed_tool_calls += 1

    def increment_depth(self) -> None:
        """Increment current delegation depth."""
        self.ledger.current_depth += 1

    def decrement_depth(self) -> None:
        """Decrement current delegation depth upon task return."""
        self.ledger.current_depth = max(0, self.ledger.current_depth - 1)

    def update_elapsed(self) -> None:
        """Update elapsed wall-clock seconds from timer."""
        self.ledger.elapsed_seconds = round(time.perf_counter() - self.start_wall_time, 3)

    def check_admission(self) -> Tuple[bool, Optional[str]]:
        """
        Evaluate all budget dimensions against hard ceilings.
        Returns (is_admitted, rejection_reason).
        """
        self.update_elapsed()
        is_exceeded, reason = self.ledger.is_exceeded()
        if is_exceeded:
            return False, reason

        if self.active_concurrency >= self.max_concurrency:
            return False, "MAX_CONCURRENCY_REACHED"

        return True, None

    def acquire_slot(self) -> bool:
        """Attempt to acquire a concurrent execution slot."""
        if self.active_concurrency >= self.max_concurrency:
            return False
        self.active_concurrency += 1
        return True

    def release_slot(self) -> None:
        """Release an acquired concurrent execution slot."""
        self.active_concurrency = max(0, self.active_concurrency - 1)
