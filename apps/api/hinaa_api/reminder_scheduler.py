"""The clock behind "Reminder set".

A scheduled row is a promise, and until something advances it the promise is
kept only as long as he never closes the tab. This module is that something:
the row flips to ``fired`` in the same transaction that writes the message, so
a crash cannot leave a promise marked kept, and a row whose time passed while
the process was down fires on the next tick instead of vanishing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from .config import Settings, get_settings
from .persistence.db import get_session_factory
from .persistence.orm import Conversation, Message, Reminder
from .tools.reminder import display_time

logger = logging.getLogger("hinaa.reminders")


def fire_due(*, settings: Optional[Settings] = None, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Advance every scheduled row whose wall clock has arrived.

    ``delivered`` is False when the reminder carries no conversation to speak
    in. The row still fires -- the gap stays visible instead of being reported
    as a success.
    """
    active = settings or get_settings()
    moment = (now or datetime.now()).replace(microsecond=0)
    fired: list[dict[str, Any]] = []

    with get_session_factory(active)() as session:
        rows = session.execute(
            select(Reminder)
            .where(Reminder.status == "scheduled", Reminder.at <= moment)
            .order_by(Reminder.at)
        ).scalars().all()

        for row in rows:
            row.status = "fired"
            conversation = (
                session.get(Conversation, row.conversation_id) if row.conversation_id else None
            )
            delivered = False
            if conversation is not None:
                text = f"Reminder: {row.title}."
                # Shaped like the rest of the thread so the client reads it as a
                # reply rather than as a raw string it has to guess about.
                session.add(
                    Message(
                        conversation_id=conversation.id,
                        role="assistant",
                        content=json.dumps({"displayText": text, "spokenText": text}),
                        language="mixed",
                    )
                )
                delivered = True
            fired.append(
                {
                    "id": row.id,
                    "title": row.title,
                    "at": row.at.isoformat(timespec="minutes"),
                    "display": display_time(row.at, now=moment),
                    "delivered": delivered,
                }
            )
        session.commit()

    if fired:
        logger.info(
            "Reminder scheduler fired %s row(s): %s delivered, %s with no conversation",
            len(fired),
            sum(1 for item in fired if item["delivered"]),
            sum(1 for item in fired if not item["delivered"]),
        )
    return fired


async def run_scheduler(
    *,
    settings: Settings,
    stop: asyncio.Event,
    tick_seconds: float,
) -> None:
    """Poll the clock until asked to stop.

    A database that throws must not take the API with it, so one bad tick logs
    and the next tick runs anyway.
    """
    while not stop.is_set():
        try:
            fire_due(settings=settings)
        except Exception:
            logger.warning("Reminder scheduler tick failed; retrying next tick", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=tick_seconds)
        except (TimeoutError, asyncio.TimeoutError):
            continue
