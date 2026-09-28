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
    r"\b(images?|pictures?|photos?|pics?|illustrations?|drawings?|art(?:work)?|wallpapers?|portraits?|sketches?|चित्र|तस्वीर)\b",
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

# A bare fetch names no subject on purpose: "fetch me some images" after
# talking about Mikasa means images of Mikasa. The subject comes from the
# conversation's active entity, compiled downstream -- the gate only has to
# recognize that the turn asks for pictures at all.
IMAGE_BARE_FETCH = re.compile(
    r"^\s*(?:please\s+)?(?:hey\s+hinaa?\s*,?\s*)?"
    r"(?:show|sho|find|search(?:\s+for)?|get|fetch|bring|see|look\s+for|"
    r"send\s+me|give\s+me)\s+"
    r"(?:me\s+)?(?:some\s+|a\s+few\s+|the\s+)?(?:\d+\s+)?"
    r"(?:images?|imges?|pictures?|photos?|pics?|imgs?|illustrations?|drawings?|"
    r"wallpapers?|posters?|artworks?)\b\s*[.!?]?\s*$",
    re.IGNORECASE,
)

IMAGE_GENERATE = re.compile(
    r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:please\s+|pls\s+|kindly\s+)?"
    r"(?:just\s+|now\s+|go\s+(?:ahead\s+and\s+|and\s+(?:f(?:uck|ucking)\s+)?)?)?"
    r"(generate|generte|genrate|generat|gnr8|draw|paint|sketch|render|illustrate|create|make|बनाओ|बनाऊ|बनाइए|बनाइदेऊ)\s+"
    r"(?:me\s+)?(.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)

IMAGE_DIRECTIVE = re.compile(
    r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?"
    r"(?:(?:can|could|would|will)\s+you\s+(?:please\s+)?)?"
    r"(?:please\s+|pls\s+|kindly\s+)?"
    r"(?:just\s+|now\s+|go\s+(?:ahead\s+and\s+|and\s+(?:f(?:uck|ucking)\s+)?)?)?"
    r"(?:generate|generte|genrate|generat|gnr8|draw|paint|render|create|make)\s+"
    r"(?:it|this|that|what\s+you\s+can|whatever\s+you\s+can|something)\b\s*[.!?]?\s*$",
    re.IGNORECASE,
)

IMAGE_WANT_GENERATE = re.compile(
    r"^\s*(?:(?:hey\s+)?hinaa?[\s,]+)?"
    r"(?:i\s+(?:want|need)|give\s+me)\s+(?:an?\s+)?(?:image|picture|photo|illustration|drawing|artwork|wallpaper|portrait)\s+"
    r"(?:of|for)\s+(.+?)\s*[.!?]?\s*$",
    re.IGNORECASE,
)

IMAGE_PROMPT_KEYWORDS = re.compile(
    r"\b(?:masterpiece|best\s+quality|highly\s+detailed|ultra\s+detailed|cinematic\s+lighting|"
    r"dramatic\s+lighting|studio\s+lighting|volumetric\s+lighting|octane\s+render|unreal\s+engine|"
    r"8k\s+resolution|4k\s+resolution|photorealistic|hyperrealistic|anime\s+style|manga\s+style|"
    r"digital\s+art|concept\s+art|character\s+design|character\s+sheet|trending\s+on\s+artstation|"
    r"pixiv|deviantart|depth\s+of\s+field|bokeh|ray\s+tracing|intricate\s+details?)\b",
    re.IGNORECASE,
)

YES_CONFIRM_PATTERN = re.compile(
    r"^\s*(?:yes|yeah|yep|yup|sure|ok(?:ay)?|do\s+it|go\s+ahead|please\s+do|just\s+do\s+it|"
    r"haan|haan\s+ji|bana\s+do|banao|yes\s+please|just\s+generate\s+it|just\s+generate|"
    r"go\s+and\s+.*generate\s+it|generate\s+it|draw\s+it|make\s+it)\b\s*[.!?]?\s*$",
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

# A document ask names the artifact. "Make me a pdf about photosynthesis",
# "turn that assignment into a docx" — the format is the request.
DOCUMENT_MENTION = re.compile(
    r"\b(?:pdf|docx?|document|report\s+file|slides?|deck|spreadsheet|excel)\b",
    re.IGNORECASE,
)
DOCUMENT_ASK = re.compile(
    r"\b(?:make|create|generate|write|prepare|build|turn\s+\w+\s+into|download)\b"
    r"[^.?!]*\b(?:pdf|docx?|document|report|deck|slides?|spreadsheet|excel)\b",
    re.IGNORECASE,
)
# A question about documents is not a request to build one.
DOCUMENT_META = re.compile(
    r"""(?ix)
    \b(?:why|how\s+come|what\s+happened|didn'?t|dont|don'?t|do\s+not|never|stop|"
    "cancel|broken|fail(?:ed|ing)?|error|wrong|not\s+working|can'?t|cannot|"
    "fix|suggest|recommend|do\s+you\s+(?:have|support|can))\b""",
    re.IGNORECASE,
)


class Intent(str, Enum):
    CHAT = "chat"
    CANCEL = "cancel"
    IMAGE_SEARCH = "image.search"
    IMAGE_GENERATE = "image.generate"
    REMINDER_CREATE = "reminders.create"
    WEB_SEARCH = "web.search"
    DOCUMENT_CREATE = "document.create"
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


def _check_image_proposal(history: list[tuple[str, str]]) -> tuple[bool, str]:
    """Check if recent conversation turns contained an unfulfilled image proposal or prompt."""
    for role, content in reversed(history[-4:]):
        if role == "assistant":
            m_prompt = re.search(r'(?:prompt|visual description)[:\s]+["“]?([^"”\n]{10,300})["”]?', content, re.I)
            if m_prompt:
                return True, m_prompt.group(1).strip()
            if re.search(
                r"\b(?:generate|draw|create)\s+(?:this|an?|the)\s+(?:image|picture|artwork|portrait)\b|"
                r"\bwould\s+you\s+like\s+me\s+to\s+(?:generate|draw|create)\b|"
                r"\bshould\s+i\s+(?:generate|draw|create)\b|"
                r"\bwant\s+me\s+to\s+(?:generate|draw|create)\b",
                content,
                re.I,
            ):
                for r2, c2 in reversed(history[-4:]):
                    if r2 == "user":
                        return True, c2.strip()
                return True, "image"
        elif role == "user":
            if re.search(r"\b(?:generate|draw|paint|picture|image|photo)\b", content, re.I):
                return True, content.strip()
    return False, ""


def decide(
    text: str,
    *,
    now: datetime | None = None,
    history: list[tuple[str, str]] | None = None,
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

    if IMAGE_BARE_FETCH.match(message) and not STOP_OR_COMPLAINT.match(message):
        return Decision(Intent.IMAGE_SEARCH)

    # Document asks are checked before the generic make/create branch: a turn
    # that names a file format is a document request even though "make" is
    # also a picture verb, and a meta question stays chat.
    if (
        DOCUMENT_ASK.search(message)
        or (DOCUMENT_MENTION.search(message) and IMAGE_GENERATE.match(message))
    ) and not DOCUMENT_META.search(message):
        return Decision(Intent.DOCUMENT_CREATE)

    # Imperative direct commands: "just generate it", "go and fuck generate it", "generate it"
    if IMAGE_DIRECTIVE.match(message):
        resolved_subject = "it"
        if history:
            is_img, pending_prompt = _check_image_proposal(history)
            if is_img and pending_prompt:
                resolved_subject = pending_prompt
        return Decision(
            Intent.IMAGE_GENERATE,
            {"prompt": resolved_subject},
        )

    # Affirmative confirmations: "yes", "do it", "sure", "go ahead" following an image discussion
    if history and YES_CONFIRM_PATTERN.match(message):
        is_img, pending_prompt = _check_image_proposal(history)
        if is_img:
            return Decision(
                Intent.IMAGE_GENERATE,
                {"prompt": pending_prompt or "image"},
            )

    # Want/Give image queries: "i want a picture of Mikasa", "give me an image of Gojo"
    want_match = IMAGE_WANT_GENERATE.match(message)
    if want_match:
        subject = _clean_subject(want_match.group(1))
        if subject:
            return Decision(
                Intent.IMAGE_GENERATE,
                {"prompt": subject},
            )

    # Raw image prompt pastes: text containing artistic quality tokens, not phrased as a question
    if (
        not re.search(r"^(?:why|what|how|who|when|where|is|are|can|could|would)\b|\?", message, re.I)
        and len(IMAGE_PROMPT_KEYWORDS.findall(message)) >= 2
    ):
        return Decision(
            Intent.IMAGE_GENERATE,
            {"prompt": message},
        )

    generate_match = IMAGE_GENERATE.match(message)
    if generate_match:
        verb, requested_subject = generate_match.groups()

        # "Make a decision" and "create a reminder" are not image jobs.
        if verb.casefold() in {"make", "create"} and not (
            IMAGE_WORDS.search(requested_subject)
            or requested_subject.strip().casefold() in ENTITY_ALIASES
            or requested_subject.strip().casefold() in {"it", "this", "that"}
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
