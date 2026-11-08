"""Clock for scheduled digests, modelled on reminder_scheduler.

Autopilot's job runner executes agent goals under budgets; a digest is a bounded,
deterministic pipeline, so it runs from this loop (started in the app lifespan)
and fires hourly or daily at a Nepal-time hour. Notifications still land in
autopilot's notification store through the in-app deliverer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from ..config import Settings, get_settings
from ..persistence.db import get_session_factory
from ..persistence.orm import NewsWatchlist
from . import service

logger = logging.getLogger("hinaa.news")


async def run_due(
    *, settings: Settings | None = None, now: datetime | None = None, **run_kwargs: Any
) -> list[dict[str, Any]]:
    """Run every enabled watchlist whose next_run_at has passed; one failure never stops the rest."""
    active = settings or get_settings()
    moment = now or datetime.now(UTC)
    with get_session_factory(active)() as session:
        due = [
            (r.id, r.user_id)
            for r in session.scalars(
                select(NewsWatchlist).where(
                    NewsWatchlist.enabled.is_(True),
                    NewsWatchlist.cadence != "manual",
                    NewsWatchlist.next_run_at.is_not(None),
                )
            )
            if service._aware(r.next_run_at) <= moment
        ]
    outcomes = []
    for watchlist_id, user_id in due:
        try:
            outcomes.append(
                {
                    "watchlistId": watchlist_id,
                    **await service.run_watchlist(
                        active, user_id, watchlist_id, now=moment, **run_kwargs
                    ),
                }
            )
        except Exception:
            logger.warning("Scheduled news run failed for %s", watchlist_id, exc_info=True)
            service.advance_after_failure(active, user_id, watchlist_id, moment)
    return outcomes


async def run_scheduler(*, settings: Settings, stop: asyncio.Event, tick_seconds: float) -> None:
    while not stop.is_set():
        try:
            await run_due(settings=settings)
        except Exception:
            logger.warning("News scheduler tick failed; retrying next tick", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=tick_seconds)
        except TimeoutError:
            continue

# ruff: noqa: E501
