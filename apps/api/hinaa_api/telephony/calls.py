"""Call state, persistence, outbound placement and the per-turn conversation logic."""

from __future__ import annotations

import asyncio
import json
import logging
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select

from ..config import Settings
from ..errors import HinaaError
from ..persistence.db import get_session_factory
from ..persistence.orm import PhoneCall
from . import twilio

logger = logging.getLogger("hinaa.telephony")

VOICE_PATH = "/v1/telephony/voice"
GATHER_PATH = "/v1/telephony/gather"
STATUS_PATH = "/v1/telephony/status-callback"
AUDIO_PREFIX = "/v1/telephony/audio/"

PHONE_INSTRUCTION = (
    "[LIVE PHONE CALL: answer like a person on the phone. Maximum two short spoken sentences, "
    "plain words only: no markdown, lists, emojis or links. Ask at most one question.] "
)
DEFAULT_OPENING = "Hello boss, are you busy?"
INBOUND_OPENING = "Hey, it's Hina. What's up?"
_GOODBYE = re.compile(r"\b(bye|goodbye|hang up|talk (to you )?later|that'?s all)\b", re.I)


@dataclass
class CallState:
    call_sid: str
    direction: str
    opening: str
    user_id: str = ""
    history: list[dict[str, str]] = field(default_factory=list)
    empty_gathers: int = 0
    turns: int = 0
    conversation_id: str | None = None


_states: dict[str, CallState] = {}
_audio: dict[str, tuple[bytes, str, float]] = {}
_AUDIO_TTL = 600.0
_AUDIO_MAX = 64
_table_ready: set[int] = set()


def reset_runtime_state() -> None:
    _states.clear()
    _audio.clear()


def _factory(settings: Settings):
    factory = get_session_factory(settings)
    bind = factory.kw["bind"]
    if id(bind) not in _table_ready:
        PhoneCall.__table__.create(bind, checkfirst=True)
        _table_ready.add(id(bind))
    return factory


def store_audio(data: bytes) -> str:
    now = time.monotonic()
    for token in [t for t, (_, _, exp) in _audio.items() if exp < now]:
        _audio.pop(token, None)
    while len(_audio) >= _AUDIO_MAX:
        _audio.pop(next(iter(_audio)))
    ctype = "audio/wav" if data[:4] == b"RIFF" else "audio/mpeg"
    token = secrets.token_urlsafe(24)
    _audio[token] = (data, ctype, now + _AUDIO_TTL)
    return token


def fetch_audio(token: str) -> tuple[bytes, str] | None:
    entry = _audio.get(token)
    if entry is None or entry[2] < time.monotonic():
        return None
    return entry[0], entry[1]


def _public(row: PhoneCall) -> dict[str, Any]:
    return {
        "id": row.id,
        "callSid": row.call_sid,
        "direction": row.direction,
        "to": twilio.mask_number(row.to_number),
        "from": twilio.mask_number(row.from_number),
        "status": row.status,
        "reason": row.reason,
        "transcript": json.loads(row.transcript_json or "[]"),
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def record_call(settings: Settings, state: CallState, *, to: str, from_: str, reason: str = "", status: str = "initiated") -> None:
    with _factory(settings)() as session:
        row = session.scalar(select(PhoneCall).where(PhoneCall.call_sid == state.call_sid))
        if row is None:
            session.add(PhoneCall(
                call_sid=state.call_sid, direction=state.direction, to_number=to,
                from_number=from_, status=status, reason=reason[:500],
            ))
            session.commit()


def update_call(settings: Settings, call_sid: str, *, status: str | None = None, transcript: list[dict[str, str]] | None = None) -> None:
    with _factory(settings)() as session:
        row = session.scalar(select(PhoneCall).where(PhoneCall.call_sid == call_sid))
        if row is None:
            return
        if status:
            row.status = status
        if transcript is not None:
            row.transcript_json = json.dumps(transcript, ensure_ascii=False)
        session.commit()


def list_calls(settings: Settings, limit: int = 20) -> list[dict[str, Any]]:
    with _factory(settings)() as session:
        rows = session.scalars(
            select(PhoneCall).order_by(PhoneCall.created_at.desc()).limit(max(1, min(limit, 100)))
        ).all()
        return [_public(r) for r in rows]


def outbound_calls_last_hour(settings: Settings) -> int:
    # server_default func.now() on SQLite is naive UTC.
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
    with _factory(settings)() as session:
        return int(session.scalar(
            select(func.count()).select_from(PhoneCall).where(
                PhoneCall.direction == "outbound", PhoneCall.created_at >= cutoff
            )
        ) or 0)


def get_state(settings: Settings, call_sid: str, direction: str = "inbound") -> CallState:
    state = _states.get(call_sid)
    if state is None:
        state = CallState(
            call_sid, direction,
            DEFAULT_OPENING if direction == "outbound" else INBOUND_OPENING,
            user_id=settings.telephony_user_id,
        )
        _states[call_sid] = state
    return state


def opening_for(reason: str | None, opening_line: str | None) -> str:
    if opening_line and opening_line.strip():
        return opening_line.strip()[:300]
    if reason and reason.strip():
        return f"{DEFAULT_OPENING} {reason.strip()[:200]}"
    return DEFAULT_OPENING


async def place_outbound_call(
    settings: Settings,
    *,
    to: str | None = None,
    reason: str | None = None,
    opening_line: str | None = None,
    transport=None,
) -> dict[str, Any]:
    twilio.require_configured(settings)
    target = twilio.normalize_number(to) if to else twilio.normalize_number(settings.hinaa_owner_phone_number)
    if not target:
        raise HinaaError("TELEPHONY_NUMBER_INVALID", "No valid destination number (E.164) was given or configured.", 422, False)
    if target not in twilio.allowed_numbers(settings):
        raise HinaaError("TELEPHONY_NUMBER_NOT_ALLOWED", "Destination number is not on the telephony allow-list.", 403, False)
    if outbound_calls_last_hour(settings) >= settings.telephony_max_calls_per_hour:
        raise HinaaError("TELEPHONY_RATE_LIMITED", "Hourly outbound call limit reached.", 429, True)
    result = await twilio.create_call(
        settings, to=target,
        twiml_url=twilio.public_url(settings, VOICE_PATH),
        status_callback_url=twilio.public_url(settings, STATUS_PATH),
        transport=transport,
    )
    sid = str(result.get("sid") or "")
    if not sid:
        raise HinaaError("TELEPHONY_PROVIDER_ERROR", "Twilio did not return a call id.", 502, False)
    state = CallState(sid, "outbound", opening_for(reason, opening_line), user_id=settings.telephony_user_id)
    _states[sid] = state
    record_call(settings, state, to=target, from_=twilio.normalize_number(settings.twilio_from_number), reason=reason or "")
    return {"callSid": sid, "status": str(result.get("status") or "queued"), "to": twilio.mask_number(target)}


def _clean_reply(text: str, limit: int = 320) -> str:
    text = re.sub(r"[*_`#>]+", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    end = max(cut.rfind(". "), cut.rfind("? "), cut.rfind("! "))
    return cut[: end + 1] if end > 60 else cut.rsplit(" ", 1)[0] + "."


async def generate_reply(settings: Settings, service: Any, state: CallState, user_text: str) -> str:
    """Run one phone turn through the normal chat pipeline."""
    from ..models import TurnRequest

    safe_sid = re.sub(r"[^A-Za-z0-9_-]", "", state.call_sid)[:60] or "x"
    request = TurnRequest(
        sessionId="call-" + safe_sid,
        text=PHONE_INSTRUCTION + user_text,
        providerMode=settings.provider_mode,
        language=settings.telephony_speech_language if settings.telephony_speech_language in ("en-US", "hi-IN", "ne-NP") else "mixed",
        userId=state.user_id or None,
        history=list(state.history[-12:]),
    )
    plan_text = ""
    deltas: list[str] = []
    async for raw in service.stream_turn(request, "call-" + safe_sid, user_id=state.user_id or None):
        try:
            event = json.loads(raw)
        except (ValueError, TypeError):
            continue
        kind = event.get("type")
        if kind == "text.delta":
            deltas.append(str(event.get("delta") or ""))
        elif kind == "plan" and isinstance(event.get("plan"), dict):
            plan = event["plan"]
            plan_text = str(plan.get("spokenText") or plan.get("displayText") or "")
    return _clean_reply(plan_text or "".join(deltas)) or "Sorry, I lost my train of thought. Could you say that again?"


def remember_turn(settings: Settings, memory_service: Any, state: CallState, user_text: str, reply: str) -> None:
    """Persist the exchange: call transcript row plus the user's conversation memory."""
    state.history += [{"role": "user", "content": user_text}, {"role": "assistant", "content": reply}]
    try:
        update_call(settings, state.call_sid, transcript=state.history)
    except Exception:
        logger.exception("telephony transcript persist failed")
    if memory_service is None or not state.user_id:
        return
    try:
        state.conversation_id = (
            memory_service.append_turn(state.user_id, "hinaa", state.conversation_id, user_text, reply, "en")
            or state.conversation_id
        )
    except Exception:
        logger.warning("telephony memory append failed", exc_info=True)


def is_goodbye(text: str) -> bool:
    return bool(_GOODBYE.search(text))


async def synthesize_for_call(settings: Settings, service: Any, text: str) -> str | None:
    """Audio token for <Play>, or None so the caller falls back to <Say>."""
    if settings.provider_mode == "mock" or not (
        settings.elevenlabs_configured or settings.azure_configured or settings.deepgram_configured
    ):
        return None
    from ..models import SpeechRequest

    try:
        result = await asyncio.wait_for(
            service.synthesize(SpeechRequest(
                text=text[:600], companionId="hinaa", providerMode=settings.provider_mode, realtime=True,
            )),
            timeout=8.0,
        )
        return store_audio(result.value) if result.value else None
    except Exception:
        logger.warning("telephony TTS failed; falling back to <Say>", exc_info=True)
        return None
