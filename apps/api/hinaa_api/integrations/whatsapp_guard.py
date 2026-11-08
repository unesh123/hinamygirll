"""WhatsApp recipient allow-list: the single definition every layer shares.

Owner rule: Hina may only message the chat named exactly "Unesh" or the group
named exactly "AI Hub". Matching is exact and case-sensitive after Unicode NFKC
and whitespace normalisation, so lookalikes ("Unesh" with a Cyrillic "е"),
case variants and substrings never match. Zero-width/format characters are
rejected outright rather than stripped, so a name that looks right but is not
byte-equal is refused.
"""

from __future__ import annotations

import os
import re
import unicodedata

from ..errors import HinaaError

DEFAULT_ALLOWED_CHATS: tuple[str, ...] = ("Unesh", "AI Hub")
ALLOWED_CHATS_ENV = "HINAA_WHATSAPP_ALLOWED_CHATS"
AUTOSEND_ENV = "HINAA_WHATSAPP_AUTOSEND_TO_ALLOWED"
MAX_MESSAGE_CHARS = 2000

_WILDCARD_CHARS = set("*?%[]")
_WS = re.compile(r"\s+")


class WhatsAppPolicyError(HinaaError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(code, message, 403, False, True)


def normalize_chat_name(value: object) -> str:
    """NFKC + collapse whitespace + strip. Case is preserved."""
    text = unicodedata.normalize("NFKC", str(value if value is not None else ""))
    return _WS.sub(" ", text).strip()


def _has_invisible(text: str) -> bool:
    # Cf = zero-width/bidi/format controls; Cc = control chars.
    return any(unicodedata.category(ch) in {"Cf", "Cc"} and not ch.isspace() for ch in text)


def configured_allowed_chats(env: dict[str, str] | None = None) -> tuple[str, ...]:
    """Parse HINAA_WHATSAPP_ALLOWED_CHATS (comma or newline separated).

    Unset/blank falls back to the defaults. A set value that contains an empty
    entry, a wildcard, or normalises to nothing is refused (fail closed) rather
    than silently widened or ignored.
    """
    source = os.environ if env is None else env
    raw = source.get(ALLOWED_CHATS_ENV)
    if raw is None or not raw.strip():
        return DEFAULT_ALLOWED_CHATS
    names: list[str] = []
    for part in re.split(r"[,\n]", raw):
        if _has_invisible(part):
            raise WhatsAppPolicyError(
                "WHATSAPP_ALLOWLIST_INVALID", "Allow-list contains invisible characters."
            )
        name = normalize_chat_name(part)
        if not name or name == "*" or _WILDCARD_CHARS & set(name):
            raise WhatsAppPolicyError(
                "WHATSAPP_ALLOWLIST_INVALID",
                "HINAA_WHATSAPP_ALLOWED_CHATS must list explicit chat names (no empty entries or wildcards).",
            )
        if name not in names:
            names.append(name)
    return tuple(names)


def validate_recipient(recipient: object, allowed: tuple[str, ...] | None = None) -> str:
    """Return the canonical allowed name or raise. Exact, case-sensitive match."""
    allowed = configured_allowed_chats() if allowed is None else allowed
    if not isinstance(recipient, str) or not recipient:
        raise WhatsAppPolicyError(
            "WHATSAPP_RECIPIENT_NOT_ALLOWED", "A recipient chat name is required."
        )
    if _has_invisible(recipient):
        raise WhatsAppPolicyError(
            "WHATSAPP_RECIPIENT_NOT_ALLOWED", "Recipient contains invisible characters."
        )
    name = normalize_chat_name(recipient)
    if name not in allowed:
        raise WhatsAppPolicyError(
            "WHATSAPP_RECIPIENT_NOT_ALLOWED",
            "Hina may only message the allow-listed WhatsApp chats; this recipient is not one of them.",
        )
    return name


def validate_message(text: object) -> str:
    if not isinstance(text, str) or not text.strip():
        raise WhatsAppPolicyError("WHATSAPP_MESSAGE_INVALID", "Message text is required.")
    if len(text) > MAX_MESSAGE_CHARS:
        raise WhatsAppPolicyError(
            "WHATSAPP_MESSAGE_TOO_LONG", f"Message exceeds {MAX_MESSAGE_CHARS} characters."
        )
    return text


def autosend_enabled(env: dict[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return source.get(AUTOSEND_ENV, "").strip().lower() in {"1", "true", "yes"}
