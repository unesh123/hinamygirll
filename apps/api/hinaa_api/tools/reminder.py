"""Reminders he sets in a sentence, kept as real rows.

"remind me to call Sile at 4:00" reached a brain that had no reminder tool to
call, so it answered with advice to use Siri. The row written here is what makes
the promise true: a restart cannot erase it, and a failed write raises instead of
returning a confident 200.
"""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Any, Callable, Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..persistence.db import get_session_factory
from ..persistence.orm import Reminder
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.reminder")

# The column keeps the wall clock he spoke, so every incoming instant is
# collapsed onto this machine's clock before it is stored.
LOCAL_ZONE_NAME = datetime.now().astimezone().tzname()


class ReminderCreateParams(BaseModel):
    model_config = {"extra": "ignore"}
    title: str
    at: str
    userId: Optional[str] = None
    conversationId: Optional[str] = None


def parse_at(value: Any) -> datetime:
    """Read a scheduled time into a local wall clock, or say that it isn't one."""
    if isinstance(value, datetime):
        moment = value
    else:
        text = str(value or "").strip()
        if not text:
            raise HinaaError("REMINDER_TIME_MISSING", "A reminder needs a time.", 422)
        try:
            moment = datetime.fromisoformat(text.replace(" ", "T", 1))
        except ValueError:
            raise HinaaError(
                "REMINDER_TIME_INVALID",
                f"I could not read that time: {value}. Try something like 'today 4:00pm'.",
                422,
            ) from None
    if moment.tzinfo is not None:
        moment = moment.astimezone().replace(tzinfo=None)
    return moment.replace(second=0, microsecond=0)


def display_time(moment: datetime, *, now: datetime | None = None) -> str:
    """Say when a reminder is, the way he would: 'Today at 4:00 PM'."""
    now = now or datetime.now()
    hour = moment.hour % 12 or 12
    clock = f"{hour}:{moment.minute:02d} {moment.strftime('%p')}"
    day = (moment.date() - now.date()).days
    if day == 0:
        return f"Today at {clock}"
    if day == 1:
        return f"Tomorrow at {clock}"
    if -1 <= day <= 7:
        return f"{moment.strftime('%A')} at {clock}"
    return f"{moment.strftime('%d %b %Y')} at {clock}"


def as_public(row: Reminder, *, now: datetime | None = None) -> dict[str, Any]:
    return {
        "id": row.id,
        "title": row.title,
        "at": row.at.isoformat(timespec="minutes"),
        "timezone": row.timezone_name,
        "display": display_time(row.at, now=now),
        "status": row.status,
        "conversationId": row.conversation_id,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def _factory(settings: Optional[Settings]) -> Callable[[], Session]:
    # Routes and tests hand in the Settings they were built with; the tool
    # handler does not have one, and falls back to the running app's.
    return get_session_factory(settings or get_settings())


def schedule_reminder(
    *,
    user_id: str,
    title: str,
    at: Any,
    conversation_id: str | None = None,
    settings: Optional[Settings] = None,
) -> dict[str, Any]:
    """Persist one reminder. A database that refuses to store it raises, because
    the alternative is her telling him it is set."""
    clean_title = (title or "").strip()
    if not clean_title:
        raise HinaaError("REMINDER_TITLE_MISSING", "A reminder needs something to remind you of.", 422)
    if len(clean_title) > 200:
        clean_title = clean_title[:200].rstrip()
    moment = parse_at(at)

    row = Reminder(
        user_id=user_id,
        conversation_id=conversation_id,
        title=clean_title,
        at=moment,
        timezone_name=LOCAL_ZONE_NAME,
        status="scheduled",
    )
    try:
        with _factory(settings)() as session:
            from ..persistence.orm import User, Conversation
            existing_user = session.scalar(select(User).where((User.id == user_id) | (User.auth_subject == user_id)))
            if existing_user is None:
                uid = user_id if len(user_id) <= 36 else _uuid()
                new_user = User(id=uid, auth_subject=user_id)
                session.add(new_user)
                session.flush()
                owner_pk = new_user.id
            else:
                owner_pk = existing_user.id

            if conversation_id:
                existing_convo = session.scalar(select(Conversation).where(Conversation.id == conversation_id))
                if existing_convo is None:
                    session.add(Conversation(id=conversation_id, user_id=owner_pk, companion_id="hinaa"))
                    session.flush()

            row.user_id = user_id
            session.add(row)
            session.commit()
            session.refresh(row)
    except HinaaError:
        raise
    except Exception as error:
        logger.exception("Failed to persist reminder")
        raise HinaaError(
            "REMINDER_NOT_PERSISTED",
            f"I could not save that reminder: {type(error).__name__}. Nothing is scheduled.",
            500,
        ) from None
    payload = as_public(row)
    payload["summaryText"] = f"Reminder set: {clean_title} — {payload['display']}."
    return payload


def list_reminders(
    *, user_id: str, status: str = "scheduled", settings: Optional[Settings] = None
) -> list[dict[str, Any]]:
    with _factory(settings)() as session:
        from ..persistence.orm import User
        u = session.scalar(select(User).where((User.id == user_id) | (User.auth_subject == user_id)))
        allowed_ids = {user_id}
        if u:
            allowed_ids.add(u.id)
            allowed_ids.add(u.auth_subject)
        query = select(Reminder).where(Reminder.user_id.in_(allowed_ids))
        if status != "all":
            query = query.where(Reminder.status == status)
        rows = session.execute(query.order_by(Reminder.at)).scalars().all()
        return [as_public(row) for row in rows]


def cancel_reminder(*, user_id: str, reminder_id: str, settings: Optional[Settings] = None) -> dict[str, Any]:
    with _factory(settings)() as session:
        row = session.get(Reminder, reminder_id)
        if row is None or row.user_id != user_id:
            raise HinaaError("REMINDER_NOT_FOUND", "There is no such reminder of yours.", 404)
        row.status = "cancelled"
        session.commit()
        session.refresh(row)
        return as_public(row)


async def handle_create(params: ReminderCreateParams) -> dict[str, Any]:
    result = schedule_reminder(
        user_id=params.userId or "anonymous",
        title=params.title,
        at=params.at,
        conversation_id=params.conversationId,
    )
    result["status"] = "success"
    return result


reminder_create_def = ToolDefinition(
    name="reminder.create",
    display_name="Set Reminder",
    description="Schedule a reminder with a title and a local time.",
    parameters={
        "title": {"type": "string", "description": "What to remind him about, in his own words."},
        "at": {"type": "string", "description": "ISO local time to fire, e.g. 2026-09-24T16:00."},
    },
    required_parameters=["title", "at"],
    # The standing-consent allowlist in /v1/tools/execute does not name this
    # tool, so requiring confirmation would make every reminder stall unanswered.
    requires_confirmation=False,
    risk_level="low",
    cancellable=True,
    voice_aliases=["remind", "reminder", "set reminder"],
)

registry.register(reminder_create_def, handle_create)
