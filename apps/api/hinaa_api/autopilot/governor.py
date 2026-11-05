"""
HINAA OS — Phase 13: Resource, Cost & Latency Governor
Enforces token ceilings, integer paisa minor-unit budgeting, GPU VRAM admission,
browser/sandbox concurrency bounds, fair multi-tenant queueing, and timestamped latency metrics.
"""

from __future__ import annotations

import asyncio
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TenantBudget:
    tenant_id: str
    max_tokens: int = 1_000_000
    used_tokens: int = 0
    max_paisa: int = 250_000  # NPR 2,500.00
    used_paisa: int = 0
    actual_provider_paisa: int = 0
    estimated_synthetic_paisa: int = 0
    max_concurrent_jobs: int = 5
    active_jobs: int = 0


@dataclass
class LatencyRecord:
    job_id: str
    queue_lag_ms: float
    execution_duration_ms: float
    total_latency_ms: float
    timestamp_utc: float


class ResourceGovernor:
    """
    Central resource, cost, and concurrency controller for persistent autonomous tasks.
    """

    def __init__(
        self,
        max_gpu_vram_mb: int = 16384,  # 16 GB default
        max_concurrent_browsers: int = 3,
        max_concurrent_sandboxes: int = 5,
    ):
        self._lock = threading.RLock()
        self.max_gpu_vram_mb = max_gpu_vram_mb
        self.used_gpu_vram_mb = 0

        self.max_concurrent_browsers = max_concurrent_browsers
        self.active_browsers = 0

        self.max_concurrent_sandboxes = max_concurrent_sandboxes
        self.active_sandboxes = 0

        self._tenant_budgets: Dict[str, TenantBudget] = {}
        self._latency_history: List[LatencyRecord] = []

    def get_or_create_tenant_budget(
        self,
        tenant_id: str,
        max_tokens: int = 1_000_000,
        max_paisa: int = 250_000,
        max_concurrent_jobs: int = 5,
    ) -> TenantBudget:
        with self._lock:
            if tenant_id not in self._tenant_budgets:
                self._tenant_budgets[tenant_id] = TenantBudget(
                    tenant_id=tenant_id,
                    max_tokens=max_tokens,
                    max_paisa=max_paisa,
                    max_concurrent_jobs=max_concurrent_jobs,
                )
            return self._tenant_budgets[tenant_id]

    # -------------------------------------------------------------------------
    # TOKEN & PAISA BUDGET CHECKS
    # -------------------------------------------------------------------------
    def check_and_reserve_budget(
        self,
        tenant_id: str,
        requested_tokens: int,
        requested_paisa: int,
    ) -> Tuple[bool, str]:
        with self._lock:
            budget = self.get_or_create_tenant_budget(tenant_id)

            if budget.active_jobs >= budget.max_concurrent_jobs:
                return False, f"Tenant {tenant_id} reached max concurrent jobs ({budget.max_concurrent_jobs})"

            if budget.used_tokens + requested_tokens > budget.max_tokens:
                return False, f"Token budget exceeded: {budget.used_tokens + requested_tokens} > {budget.max_tokens}"

            if budget.used_paisa + requested_paisa > budget.max_paisa:
                return False, f"Paisa budget exceeded: {budget.used_paisa + requested_paisa} > {budget.max_paisa} paisa"

            budget.active_jobs += 1
            return True, "Budget reserved"

    def record_usage(
        self,
        tenant_id: str,
        tokens_consumed: int,
        paisa_consumed: int,
        is_actual_provider: bool = False,
    ) -> None:
        with self._lock:
            budget = self.get_or_create_tenant_budget(tenant_id)
            budget.used_tokens += tokens_consumed
            budget.used_paisa += paisa_consumed
            if is_actual_provider:
                budget.actual_provider_paisa += paisa_consumed
            else:
                budget.estimated_synthetic_paisa += paisa_consumed

    def release_job_slot(self, tenant_id: str) -> None:
        with self._lock:
            budget = self.get_or_create_tenant_budget(tenant_id)
            budget.active_jobs = max(0, budget.active_jobs - 1)

    # -------------------------------------------------------------------------
    # GPU VRAM ADMISSION CONTROL
    # -------------------------------------------------------------------------
    def check_gpu_admission(self, requested_vram_mb: int) -> Tuple[bool, str]:
        with self._lock:
            if self.used_gpu_vram_mb + requested_vram_mb > self.max_gpu_vram_mb:
                return False, (
                    f"Insufficient GPU VRAM: requested {requested_vram_mb}MB, "
                    f"currently allocated {self.used_gpu_vram_mb}/{self.max_gpu_vram_mb}MB"
                )
            self.used_gpu_vram_mb += requested_vram_mb
            return True, "GPU VRAM allocated"

    def release_gpu_vram(self, released_vram_mb: int) -> None:
        with self._lock:
            self.used_gpu_vram_mb = max(0, self.used_gpu_vram_mb - released_vram_mb)

    # -------------------------------------------------------------------------
    # CONCURRENCY CONTROL: BROWSERS & SANDBOXES
    # -------------------------------------------------------------------------
    def acquire_browser_slot(self) -> Tuple[bool, str]:
        with self._lock:
            if self.active_browsers >= self.max_concurrent_browsers:
                return False, f"Max concurrent browsers ({self.max_concurrent_browsers}) reached"
            self.active_browsers += 1
            return True, "Browser slot acquired"

    def release_browser_slot(self) -> None:
        with self._lock:
            self.active_browsers = max(0, self.active_browsers - 1)

    def acquire_sandbox_slot(self) -> Tuple[bool, str]:
        with self._lock:
            if self.active_sandboxes >= self.max_concurrent_sandboxes:
                return False, f"Max concurrent sandboxes ({self.max_concurrent_sandboxes}) reached"
            self.active_sandboxes += 1
            return True, "Sandbox slot acquired"

    def release_sandbox_slot(self) -> None:
        with self._lock:
            self.active_sandboxes = max(0, self.active_sandboxes - 1)

    # -------------------------------------------------------------------------
    # FAIR MULTI-TENANT QUEUE DISPATCH
    # -------------------------------------------------------------------------
    def select_next_job_fair(self, ready_jobs_by_tenant: Dict[str, List[Any]]) -> Optional[Any]:
        """
        Deficit Round Robin / Fair-share job selection across multiple tenants.
        Prevents large tenants with burst queues from starving small tenants.
        """
        with self._lock:
            active_tenants = [t for t, jobs in ready_jobs_by_tenant.items() if jobs]
            if not active_tenants:
                return None

            # Pick tenant with lowest active jobs ratio
            def score(t: str) -> float:
                b = self.get_or_create_tenant_budget(t)
                return b.active_jobs / max(1, b.max_concurrent_jobs)

            sorted_tenants = sorted(active_tenants, key=score)
            best_tenant = sorted_tenants[0]
            return ready_jobs_by_tenant[best_tenant].pop(0)

    # -------------------------------------------------------------------------
    # TELEMETRY & LATENCY AUDIT
    # -------------------------------------------------------------------------
    def record_job_timings(
        self,
        job_id: str,
        scheduled_for_utc: float,
        started_at_utc: float,
        completed_at_utc: float,
    ) -> None:
        queue_lag_ms = max(0.0, (started_at_utc - scheduled_for_utc) * 1000.0)
        execution_duration_ms = max(0.0, (completed_at_utc - started_at_utc) * 1000.0)
        total_latency_ms = max(0.0, (completed_at_utc - scheduled_for_utc) * 1000.0)

        record = LatencyRecord(
            job_id=job_id,
            queue_lag_ms=queue_lag_ms,
            execution_duration_ms=execution_duration_ms,
            total_latency_ms=total_latency_ms,
            timestamp_utc=completed_at_utc,
        )
        with self._lock:
            self._latency_history.append(record)
            if len(self._latency_history) > 1000:
                self._latency_history = self._latency_history[-1000:]

    def get_latency_stats(self) -> Dict[str, float]:
        with self._lock:
            if not self._latency_history:
                return {
                    "count": 0,
                    "avg_queue_lag_ms": 0.0,
                    "p50_duration_ms": 0.0,
                    "p95_duration_ms": 0.0,
                    "p99_duration_ms": 0.0,
                }

            durations = sorted(r.execution_duration_ms for r in self._latency_history)
            lags = [r.queue_lag_ms for r in self._latency_history]
            n = len(durations)

            def percentile(p: float) -> float:
                k = (n - 1) * (p / 100.0)
                f = math.floor(k)
                c = math.ceil(k)
                if f == c:
                    return durations[int(k)]
                return durations[int(f)] * (c - k) + durations[int(c)] * (k - f)

            return {
                "count": n,
                "avg_queue_lag_ms": sum(lags) / max(1, len(lags)),
                "p50_duration_ms": percentile(50),
                "p95_duration_ms": percentile(95),
                "p99_duration_ms": percentile(99),
            }
