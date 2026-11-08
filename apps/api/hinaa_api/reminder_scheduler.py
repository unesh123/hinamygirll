"""The clock behind "Reminder set".

A scheduled row is a promise, and until something advances it the promise is
kept only as long as he never closes the tab. This module is that something:
the row flips to ``fired`` in the same transaction that writes the message, so
a crash cannot leave a promise marked kept, and a row whose time passed while
the process was down catches up on the next tick -- until it is too late to be
worth announcing, at which point it is marked ``missed`` instead.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

from sqlalchemy import select

from .config import Settings, get_settings
from .errors import HinaaError
from .persistence.db import get_session_factory
from .persistence.orm import Conversation, Message, Reminder
from .tools.reminder import display_time

logger = logging.getLogger("hinaa.reminders")


def fire_due(*, settings: Optional[Settings] = None, now: Optional[datetime] = None) -> list[dict[str, Any]]:
    """Advance every scheduled row whose wall clock has arrived.

    A row that came due inside the grace window fires; one older than the window
    is marked ``missed`` with no message, because announcing an appointment hours
    late as if it were news is its own kind of wrong.

    ``delivered`` is False when the reminder carries no conversation to speak
    in. The row still fires -- the gap stays visible instead of being reported
    as a success.
    """
    active = settings or get_settings()
    moment = (now or datetime.now()).replace(microsecond=0)
    deadline = moment - timedelta(seconds=active.reminder_fire_grace_seconds)
    fired: list[dict[str, Any]] = []

    with get_session_factory(active)() as session:
        rows = session.execute(
            select(Reminder)
            .where(Reminder.status == "scheduled", Reminder.at <= moment)
            .order_by(Reminder.at)
        ).scalars().all()

        for row in rows:
            outcome = {
                "id": row.id,
                "title": row.title,
                "at": row.at.isoformat(timespec="minutes"),
                "display": display_time(row.at, now=moment),
            }
            if row.at < deadline:
                row.status = "missed"
                fired.append({**outcome, "status": "missed", "delivered": False})
                continue
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
                {**outcome, "status": "fired", "delivered": delivered, "call": bool(row.place_call)}
            )
        session.commit()

    if fired:
        logger.info(
            "Reminder scheduler fired %s row(s) (%s delivered, %s with no conversation), missed %s",
            sum(1 for item in fired if item["status"] == "fired"),
            sum(1 for item in fired if item["status"] == "fired" and item["delivered"]),
            sum(1 for item in fired if item["status"] == "fired" and not item["delivered"]),
            sum(1 for item in fired if item["status"] == "missed"),
        )
    return fired


async def place_due_calls(
    fired: list[dict[str, Any]],
    *,
    settings: Settings,
    caller: Optional[Callable[..., Awaitable[dict[str, Any]]]] = None,
) -> list[dict[str, Any]]:
    """Phone for each fired reminder flagged ``call``, when proactive calls are on.

    Opt-in, never when telephony is unconfigured, and placement goes through
    ``place_outbound_call`` so the allow-list and hourly cap still decide. A
    refused or failed call is logged and never raises into the scheduler.
    """
    wanted = [item for item in fired if item.get("status") == "fired" and item.get("call")]
    if not wanted or not settings.telephony_proactive:
        return []
    from .telephony import twilio

    if twilio.missing_settings(settings):
        logger.info("Proactive reminder call skipped: telephony is not configured")
        return []
    if caller is None:
        from .telephony.calls import place_outbound_call as caller

    results: list[dict[str, Any]] = []
    for item in wanted:
        try:
            placed = await caller(settings, reason=f"Reminder: {item['title']}")
            logger.info("Reminder %s call placed (%s)", item["id"], placed.get("status"))
            results.append({"id": item["id"], "called": True})
        except HinaaError as error:
            logger.warning("Reminder %s call not placed: %s", item["id"], error.code)
            results.append({"id": item["id"], "called": False, "code": error.code})
        except Exception:
            logger.warning("Reminder %s call failed", item["id"], exc_info=True)
            results.append({"id": item["id"], "called": False, "code": "CALL_FAILED"})
    return results


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
            await place_due_calls(fire_due(settings=settings), settings=settings)
        except Exception:
            logger.warning("Reminder scheduler tick failed; retrying next tick", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=tick_seconds)
        except (TimeoutError, asyncio.TimeoutError):
            continue
