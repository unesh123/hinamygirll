from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Literal
from uuid import uuid4

from ..config import Settings, get_settings
from ..errors import HinaaError

logger = logging.getLogger("hinaa.creative.budget")

PacingMode = Literal["economy", "balanced", "quality", "use-it-wisely"]


class MagnificBudgetManager:
    """Production-grade 45,000 credit monthly billing cycle manager for Magnific/Freepik.
    
    Dynamically adjusts daily pace based on remaining days until the 3rd-of-month renewal.
    Maintains clean separation between local HINAA API usage and manual account snapshots.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        session_factory: Any = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.session_factory = session_factory
        self.plan_credits: int = self.settings.magnific_monthly_plan_credits
        self.anchor_day: int = self.settings.magnific_billing_cycle_anchor_day
        self._manual_balance_snapshot: int | None = None
        self._manual_snapshot_time: datetime | None = None
        self._memory_spend_records: list[dict[str, Any]] = []
        self._live_verified: bool = False

    def mark_live_verified(self, verified: bool = True) -> None:
        """Mark Magnific provider as having completed live end-to-end verification."""
        self._live_verified = verified

    def get_billing_cycle_bounds(self, now: datetime | None = None) -> tuple[datetime, datetime, int]:
        """Calculate (cycle_start, cycle_end, days_remaining) anchored to anchor_day."""
        if now is None:
            now = datetime.now(timezone.utc)

        # If today is on or after anchor_day, cycle started this month on anchor_day
        if now.day >= self.anchor_day:
            cycle_start = datetime(now.year, now.month, self.anchor_day, tzinfo=timezone.utc)
            # End is next month on anchor_day
            if now.month == 12:
                cycle_end = datetime(now.year + 1, 1, self.anchor_day, tzinfo=timezone.utc)
            else:
                cycle_end = datetime(now.year, now.month + 1, self.anchor_day, tzinfo=timezone.utc)
        else:
            # Cycle started previous month on anchor_day
            if now.month == 1:
                cycle_start = datetime(now.year - 1, 12, self.anchor_day, tzinfo=timezone.utc)
            else:
                cycle_start = datetime(now.year, now.month - 1, self.anchor_day, tzinfo=timezone.utc)
            cycle_end = datetime(now.year, now.month, self.anchor_day, tzinfo=timezone.utc)

        days_remaining = max(1, (cycle_end.date() - now.date()).days)
        return cycle_start, cycle_end, days_remaining

    def get_cycle_usage(self, cycle_start: datetime) -> int:
        """Fetch total credits spent by HINAA API in current cycle."""
        if self.session_factory:
            try:
                from sqlalchemy import func
                from ..persistence.orm import ProviderUsage

                with self.session_factory() as session:
                    total = (
                        session.query(func.sum(ProviderUsage.credits))
                        .filter(
                            ProviderUsage.provider.in_(["magnific", "freepik"]),
                            ProviderUsage.created_at >= cycle_start,
                        )
                        .scalar()
                    )
                    if total is not None:
                        return int(total)
            except Exception as e:
                logger.warning("Failed to query DB for cycle usage, using memory log: %s", e)

        # Fallback to memory records
        return sum(
            r["credits"]
            for r in self._memory_spend_records
            if r["timestamp"] >= cycle_start
        )

    def get_today_usage(self, now: datetime | None = None) -> int:
        """Fetch credits spent today by HINAA API."""
        if now is None:
            now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        if self.session_factory:
            try:
                from sqlalchemy import func
                from ..persistence.orm import ProviderUsage

                with self.session_factory() as session:
                    total = (
                        session.query(func.sum(ProviderUsage.credits))
                        .filter(
                            ProviderUsage.provider.in_(["magnific", "freepik"]),
                            ProviderUsage.created_at >= start_of_day,
                        )
                        .scalar()
                    )
                    if total is not None:
                        return int(total)
            except Exception as e:
                logger.warning("Failed to query DB for today usage: %s", e)

        return sum(
            r["credits"]
            for r in self._memory_spend_records
            if r["timestamp"] >= start_of_day
        )

    def set_manual_balance_snapshot(self, balance: int) -> None:
        """Update the manual balance snapshot from user's dashboard view."""
        self._manual_balance_snapshot = max(0, int(balance))
        self._manual_snapshot_time = datetime.now(timezone.utc)
        logger.info("Manual Magnific balance snapshot updated: %d credits", self._manual_balance_snapshot)

    def get_budget_status(self) -> dict[str, Any]:
        """Comprehensive budget status with dynamic daily pace and pacing mode."""
        now = datetime.now(timezone.utc)
        cycle_start, cycle_end, days_remaining = self.get_billing_cycle_bounds(now)
        total_cycle_days = max(1, (cycle_end.date() - cycle_start.date()).days)

        hinaa_usage = self.get_cycle_usage(cycle_start)
        today_usage = self.get_today_usage(now)

        if self._manual_balance_snapshot is not None:
            effective_remaining = self._manual_balance_snapshot
        else:
            effective_remaining = max(0, self.plan_credits - hinaa_usage)

        daily_pace = max(1, int(effective_remaining / days_remaining))

        # Determine pacing mode
        if days_remaining > 20:
            pacing_mode: PacingMode = "economy"
            advice = f"Early in cycle ({days_remaining}d left). Prioritize draft models (Classic Fast 1c, Flux.1 Fast 5c) to bank credits."
        elif days_remaining >= 10:
            pacing_mode = "balanced"
            advice = f"Mid-cycle ({days_remaining}d left). Daily pace is ~{daily_pace} credits. Standard generation (Flux.1 10c) recommended."
        elif days_remaining >= 3:
            pacing_mode = "quality"
            advice = f"Late cycle ({days_remaining}d left). Quality pace active. Safe to run Mystic (45c/50c) for priority creations."
        else:
            pacing_mode = "use-it-wisely"
            advice = f"Cycle ends in {days_remaining} days! Unused monthly credits do not roll over. Use your remaining {effective_remaining} credits on Mystic renders."

        # Check API key configuration and live verification state
        has_key = self.settings.freepik_configured
        soft_target = self.settings.magnific_daily_soft_target_override
        is_live_verified = bool(has_key and (getattr(self, "_live_verified", False) or hinaa_usage > 0))
        state = "READY" if (has_key and is_live_verified) else ("ACTIVE" if has_key else "KEY_MISSING")

        return {
            "planCredits": self.plan_credits,
            "anchorDay": self.anchor_day,
            "cycleStart": cycle_start.isoformat(),
            "cycleEnd": cycle_end.isoformat(),
            "daysRemaining": days_remaining,
            "totalCycleDays": total_cycle_days,
            "hinaaApiCreditsUsed": hinaa_usage,
            "todayCreditsUsed": today_usage,
            "manualBalanceSnapshot": self._manual_balance_snapshot,
            "manualSnapshotTime": self._manual_snapshot_time.isoformat() if self._manual_snapshot_time else None,
            "effectiveRemaining": effective_remaining,
            "dailyPace": daily_pace,
            "dailySoftTargetOverride": soft_target,
            "pacingMode": pacing_mode,
            "pacingAdvice": advice,
            "videoGenerationEnabled": False,  # Strict ban
            "configured": has_key,
            "liveVerified": is_live_verified,
            "state": state,
            "implementation": "ready",
            "statusMessage": (
                "Magnific API is configured, live verified, and ready for creative workloads."
                if (has_key and is_live_verified)
                else (
                    "Magnific API is configured and ready."
                    if has_key
                    else "Magnific API key is not configured in .env.local (MAGNIFIC_API_KEY). Ready to activate once key is added."
                )
            ),
        }

    def can_spend(self, estimated_cost: int, force: bool = False) -> tuple[bool, str, dict[str, Any]]:
        """Validate if job can proceed under dynamic daily pace."""
        status = self.get_budget_status()
        daily_pace = status["dailyPace"]
        today_used = status["todayCreditsUsed"]
        effective_remaining = status["effectiveRemaining"]

        # Check hard remaining balance
        if estimated_cost > effective_remaining and not force:
            return (
                False,
                f"Insufficient credits. Job costs {estimated_cost} credits, but only {effective_remaining} remain in cycle.",
                status,
            )

        # Soft advisory daily pace
        soft_limit = self.settings.magnific_daily_soft_target_override or daily_pace
        if (today_used + estimated_cost) > soft_limit and not force:
            return (
                False,
                f"Advisory daily pace exceeded. Spending {estimated_cost} credits now brings today's spend to {today_used + estimated_cost} (recommended daily pace: {soft_limit}). Pass force=True to proceed.",
                status,
            )

        return True, "Approved", status

    def record_spend(
        self,
        user_id: str,
        model_id: str,
        credits: int,
        operation: str = "image_generation",
        latency_ms: int = 0,
    ) -> None:
        """Record credit consumption in persistent storage and memory buffer."""
        now = datetime.now(timezone.utc)
        record = {
            "id": str(uuid4()),
            "user_id": user_id,
            "provider": "magnific",
            "operation": operation,
            "model": model_id,
            "credits": credits,
            "latency_ms": latency_ms,
            "timestamp": now,
        }
        self._memory_spend_records.append(record)
        self._live_verified = True

        if self._manual_balance_snapshot is not None:
            self._manual_balance_snapshot = max(0, self._manual_balance_snapshot - credits)

        if self.session_factory:
            try:
                from ..persistence.orm import ProviderUsage

                with self.session_factory() as session:
                    usage = ProviderUsage(
                        id=record["id"],
                        user_id=user_id,
                        provider="magnific",
                        operation=operation,
                        model=model_id,
                        credits=credits,
                        status="success",
                        latency_ms=latency_ms,
                    )
                    session.add(usage)
                    session.commit()
            except Exception as e:
                logger.warning("Failed to persist ProviderUsage record to database: %s", e)