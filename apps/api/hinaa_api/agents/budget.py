"""
HINAA OS — Phase 11 & Phase 12 Budget & Resource Quota Controller
Tracks token expenditure, tool invocation limits, wall-clock time,
concurrency, integer paisa monetary limits with hard-ceiling admission,
and nested budget slicing with automated unused allocation refunds.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple

from .contracts import BudgetLedger

logger = logging.getLogger("hinaa.agents.budget")


class BudgetController:
    """Enforces strict resource limits, cost ceilings, concurrency boundaries, and nested budget slicing."""

    def __init__(self, ledger: Optional[BudgetLedger] = None, max_concurrency: int = 5) -> None:
        self.ledger = ledger or BudgetLedger()
        self.max_concurrency = max_concurrency
        self.active_concurrency = 0
        self.start_wall_time = time.perf_counter()
        self._active_allocated_tokens: int = 0
        self._active_allocated_tool_calls: int = 0
        self._active_allocated_paisa: int = 0

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

    def allocate_slice(
        self,
        tokens: int = 8192,
        tool_calls: int = 15,
        cost_paisa: int = 5000,
        seconds: float = 60.0,
    ) -> BudgetLedger:
        """
        Allocate a bounded child budget slice ensuring sum(child_slices) <= parent budget.
        """
        rem_tokens = max(0, self.ledger.allocated_tokens - self.ledger.consumed_tokens - self._active_allocated_tokens)
        rem_tool_calls = max(0, self.ledger.allocated_tool_calls - self.ledger.consumed_tool_calls - self._active_allocated_tool_calls)
        rem_paisa = max(0, self.ledger.allocated_cost_paisa - self.ledger.consumed_cost_paisa - self._active_allocated_paisa)
        rem_seconds = max(0.0, self.ledger.allocated_seconds - self.ledger.elapsed_seconds)

        slice_tokens = min(tokens, rem_tokens) if rem_tokens > 0 else min(tokens, self.ledger.allocated_tokens)
        slice_tool_calls = min(tool_calls, rem_tool_calls) if rem_tool_calls > 0 else min(tool_calls, self.ledger.allocated_tool_calls)
        slice_paisa = min(cost_paisa, rem_paisa) if rem_paisa > 0 else min(cost_paisa, self.ledger.allocated_cost_paisa)
        slice_seconds = min(seconds, rem_seconds) if rem_seconds > 0 else min(seconds, self.ledger.allocated_seconds)

        self._active_allocated_tokens += slice_tokens
        self._active_allocated_tool_calls += slice_tool_calls
        self._active_allocated_paisa += slice_paisa

        return BudgetLedger(
            allocated_tokens=slice_tokens,
            consumed_tokens=0,
            allocated_tool_calls=slice_tool_calls,
            consumed_tool_calls=0,
            allocated_cost_paisa=slice_paisa,
            consumed_cost_paisa=0,
            allocated_seconds=slice_seconds,
            elapsed_seconds=0.0,
            max_recursion_depth=max(1, self.ledger.max_recursion_depth - 1),
            current_depth=self.ledger.current_depth + 1,
        )

    def reconcile_slice(self, child_ledger: BudgetLedger) -> None:
        """
        Reconcile a child budget slice upon team completion:
        Adds child consumed amounts to parent consumed totals and refunds unused allocation headroom.
        """
        self.record_tokens(
            tokens=child_ledger.consumed_tokens,
            cost_paisa=child_ledger.consumed_cost_paisa,
        )
        for _ in range(child_ledger.consumed_tool_calls):
            self.record_tool_call()

        self._active_allocated_tokens = max(0, self._active_allocated_tokens - child_ledger.allocated_tokens)
        self._active_allocated_tool_calls = max(0, self._active_allocated_tool_calls - child_ledger.allocated_tool_calls)
        self._active_allocated_paisa = max(0, self._active_allocated_paisa - child_ledger.allocated_cost_paisa)
