"""HINAA Intent Gate.

Classify one user turn before any model or tool receives it.
The returned arguments are the only arguments permitted to cross
the tool boundary. The original utterance is never an image prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any
from zoneinfo import ZoneInfo


try:
    KATHMANDU = ZoneInfo("Asia/Kathmandu")
except Exception:
    from datetime import timezone
    KATHMANDU = timezone(timedelta(hours=5, minutes=45), name="Asia/Kathmandu")

ENTITY_ALIASES = {
    "mikasa": "Mikasa Ackerman",
}

IMAGE_WORDS = re.compile(
    r"\b(images?|pictures?|photos?|illustrations?|drawings?)\b",
    re.IGNORECASE,
)

STOP_OR_COMPLAINT = re.compile(
    r"""
^\s*(?:
stop\b
|cancel\b
|don't\s+(?:generate|make|draw|search)\b
|do\s+not\s+(?:generate|make|draw|search)\b
|why\s+did\s+you\b
|you\s+keep\s+(?:generating|searching)\b
|i\s+didn['’]?t\s+ask\b
|again[,:\s]+(?:you|stop|i\s+didn['’]?t)
)
""",
    re.IGNORECASE | re.VERBOSE,
)

IMAGE_SEARCH = re.compile(
    r"^\s*(?:please\s+)?(?:show|find|search\s+for)\s+"
    r"(?:me\s+)?(?:images?|pictures?|photos?)\s+"
    r"(?:of|for)\s+(.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)

IMAGE_GENERATE = re.compile(
    r"^\s*(?:please\s+)?(generate|draw|create|make)\s+"
    r"(?:me\s+)?(.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)

REMINDER_PREFIX = re.compile(r"^\s*remind\s+me\b", re.IGNORECASE)

REMINDER_TIME_FIRST = re.compile(
    r"^\s*remind\s+me\s+"
    r"(?:(today|tomorrow)\s+)?"
    r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\s+"
    r"(?:to\s+)?(.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)

REMINDER_TASK_FIRST = re.compile(
    r"^\s*remind\s+me\s+(?:to\s+)?(.+?)\s+"
    r"(?:(today|tomorrow)\s+)?"
    r"(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)

WEB_SEARCH_PATTERN = re.compile(
    r"^\s*(?:please\s+)?(?:(?:hey\s+)?hinaa?\s*,?\s*)?"
    r"(?:"
    r"(?:search(?:\s+(?:for|the\s+web\s+for|online\s+for))?|find|look\s+up)\s+"
    r"(?:me\s+)?"
    r"(?:the\s+)?"
    r"(?:latest|current|recent|today['’]?s|new)?\s*(.+)"
    r"|(?:what\s+(?:is|are)\s+(?:the\s+)?(?:latest|current|recent|new)\s+(.+))"
    r"|(?:the\s+)?(?:latest|current|today['’]?s)\s+(?:news|headlines|updates|releases|anime|animes)\b.*"
    r")\s*[.!?]?\s*$",
    re.IGNORECASE,
)


class Intent(str, Enum):
    CHAT = "chat"
    CANCEL = "cancel"
    IMAGE_SEARCH = "image.search"
    IMAGE_GENERATE = "image.generate"
    REMINDER_CREATE = "reminders.create"
    WEB_SEARCH = "web.search"
    CLARIFY = "clarify"


@dataclass(frozen=True)
class Decision:
    intent: Intent
    arguments: dict[str, Any] = field(default_factory=dict)
    reason: str = ""


def _clean_subject(value: str) -> str:
    value = value.strip().rstrip(" .!?")
    value = re.sub(
        r"^(?:an?\s+)?(?:image|picture|photo|illustration|drawing)"
        r"\s+(?:of\s+)?",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = re.sub(
        r"\s+(?:images?|pictures?|photos?)$",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip()


def _canonical_search_subject(value: str) -> str:
    subject = _clean_subject(value)
    return ENTITY_ALIASES.get(subject.casefold(), subject)


def _reminder_decision(text: str, now: datetime) -> Decision:
    match = REMINDER_TIME_FIRST.match(text)

    if match:
        day, hour_text, minute_text, period, task = match.groups()
    else:
        match = REMINDER_TASK_FIRST.match(text)
        if not match:
            return Decision(
                Intent.CLARIFY,
                reason="A reminder needs a task and a time.",
            )

        task, day, hour_text, minute_text, period = match.groups()

    task = re.sub(r"\s+", " ", task).strip().rstrip(" .!?")
    hour = int(hour_text)
    minute = int(minute_text or "0")

    if not task or minute > 59 or hour > 23:
        return Decision(
            Intent.CLARIFY,
            reason="The reminder task or time is invalid.",
        )

    if period:
        if hour < 1 or hour > 12:
            return Decision(
                Intent.CLARIFY,
                reason="Use a valid 12-hour time with AM or PM.",
            )
        hour = hour % 12 + (12 if period.casefold() == "pm" else 0)
    elif hour <= 6:
        return Decision(
            Intent.CLARIFY,
            reason="Specify AM or PM for this reminder time.",
        )

    local_now = now.astimezone(KATHMANDU)
    target_date = local_now.date()

    if day and day.casefold() == "tomorrow":
        target_date += timedelta(days=1)

    due = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        hour,
        minute,
        tzinfo=KATHMANDU,
    )

    if day and day.casefold() == "today" and due <= local_now:
        return Decision(
            Intent.CLARIFY,
            reason="That time has already passed today.",
        )

    if not day and due <= local_now:
        due += timedelta(days=1)

    return Decision(
        Intent.REMINDER_CREATE,
        {
            "title": task,
            "due_at": due.isoformat(),
            "timezone": "Asia/Kathmandu",
        },
    )


def decide(
    text: str,
    *,
    now: datetime | None = None,
) -> Decision:
    """
    Classify one user turn before any model or tool receives it.

    The returned arguments are the only arguments permitted to cross
    the tool boundary. The original utterance is never an image prompt.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    message = re.sub(r"\s+", " ", text).strip()

    if not message:
        return Decision(Intent.CHAT)

    if len(message) > 10_000:
        return Decision(
            Intent.CLARIFY,
            reason="The message is too long for an action.",
        )

    if STOP_OR_COMPLAINT.match(message):
        return Decision(Intent.CANCEL)

    if REMINDER_PREFIX.match(message):
        return _reminder_decision(
            message,
            now or datetime.now(KATHMANDU),
        )

    search_match = IMAGE_SEARCH.match(message)
    if search_match:
        subject = _canonical_search_subject(search_match.group(1))
        if subject:
            return Decision(
                Intent.IMAGE_SEARCH,
                {"query": subject},
            )

    generate_match = IMAGE_GENERATE.match(message)
    if generate_match:
        verb, requested_subject = generate_match.groups()

        # "Make a decision" and "create a reminder" are not image jobs.
        if verb.casefold() in {"make", "create"} and not IMAGE_WORDS.search(
            requested_subject
        ):
            return Decision(Intent.CHAT)

        subject = _clean_subject(requested_subject)
        if subject:
            return Decision(
                Intent.IMAGE_GENERATE,
                {"prompt": subject},
            )

    web_match = WEB_SEARCH_PATTERN.match(message)
    if web_match:
        groups = [g for g in web_match.groups() if g]
        query = groups[0].strip() if groups else message
        return Decision(
            Intent.WEB_SEARCH,
            {"query": query or message},
        )

    return Decision(Intent.CHAT)
