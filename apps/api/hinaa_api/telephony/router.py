"""Telephony HTTP surface: owner-facing API plus Twilio-signed TwiML webhooks."""

from __future__ import annotations

import logging
from typing import Any, Callable
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings
from ..errors import HinaaError
from . import calls, twilio

logger = logging.getLogger("hinaa.telephony")

# Only these are exempt from user auth; each authenticates by Twilio signature
# (audio instead relies on an unguessable, expiring token, because Twilio's
# <Play> fetch carries no signature).
WEBHOOK_PATHS = frozenset({calls.VOICE_PATH, calls.GATHER_PATH, calls.STATUS_PATH})
WEBHOOK_PATHS_ALL = WEBHOOK_PATHS | {"/api" + p for p in WEBHOOK_PATHS}
AUDIO_PREFIXES = (calls.AUDIO_PREFIX, "/api" + calls.AUDIO_PREFIX)


def is_webhook_path(path: str) -> bool:
    return path in WEBHOOK_PATHS_ALL or path.startswith(AUDIO_PREFIXES)


class CallBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    to: str | None = Field(None, max_length=32)
    reason: str | None = Field(None, max_length=500)
    opening_line: str | None = Field(None, max_length=300)


def _twiml(*parts: str) -> Response:
    return Response('<?xml version="1.0" encoding="UTF-8"?><Response>' + "".join(parts) + "</Response>", media_type="text/xml")


def _hangup(message: str) -> Response:
    return _twiml("<Say>" + escape(message) + "</Say><Hangup/>")


def build_telephony_router(
    settings: Settings,
    service: Any,
    memory_service: Any,
    conversation_auth: Callable[..., Any],
    transport: Any = None,
) -> APIRouter:
    router = APIRouter(tags=["Telephony"])

    def _require_auth(auth: Any) -> None:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for telephony", 401, True)

    @router.get("/v1/telephony/status")
    @router.get("/api/v1/telephony/status")
    async def telephony_status(auth: Any = Depends(conversation_auth)) -> dict[str, Any]:
        _require_auth(auth)
        missing = twilio.missing_settings(settings)
        owner = twilio.normalize_number(settings.hinaa_owner_phone_number)
        return {
            "configured": not missing,
            "missing": missing,
            "ownerNumber": twilio.mask_number(owner) if owner else None,
            "allowedNumberCount": len(twilio.allowed_numbers(settings)),
            "maxCallsPerHour": settings.telephony_max_calls_per_hour,
            "mediaStreams": False,
        }

    @router.get("/v1/telephony/calls")
    @router.get("/api/v1/telephony/calls")
    async def telephony_calls(limit: int = 20, auth: Any = Depends(conversation_auth)) -> list[dict[str, Any]]:
        _require_auth(auth)
        return calls.list_calls(settings, limit)

    @router.post("/v1/telephony/calls")
    @router.post("/api/v1/telephony/calls")
    async def telephony_place_call(body: CallBody, auth: Any = Depends(conversation_auth)) -> dict[str, Any]:
        _require_auth(auth)
        return await calls.place_outbound_call(
            settings, to=body.to, reason=body.reason, opening_line=body.opening_line, transport=transport
        )

    # ---- Twilio webhooks -------------------------------------------------

    async def _verified_form(request: Request) -> dict[str, str]:
        twilio.require_configured(settings)
        form = await request.form()
        items = [(k, str(v)) for k, v in form.multi_items()]
        url = twilio.public_url(settings, request.url.path)
        if request.url.query:
            url += "?" + request.url.query
        token = settings.twilio_auth_token.get_secret_value()
        if not twilio.validate_signature(token, url, items, request.headers.get("X-Twilio-Signature")):
            raise HinaaError("TELEPHONY_BAD_SIGNATURE", "Invalid Twilio signature.", 403, False)
        return dict(items)

    def _play_or_say(text: str, token: str | None) -> str:
        if token:
            return "<Play>" + escape(twilio.public_url(settings, calls.AUDIO_PREFIX + token)) + "</Play>"
        return '<Say voice="{}" language="{}">{}</Say>'.format(
            escape(settings.telephony_say_voice, {'"': "&quot;"}),
            escape(settings.telephony_speech_language, {'"': "&quot;"}),
            escape(text),
        )

    async def _gather(text: str) -> Response:
        token = await calls.synthesize_for_call(settings, service, text)
        gather = (
            '<Gather input="speech" speechTimeout="auto" actionOnEmptyResult="true" method="POST" '
            'language="{}" action="{}">{}</Gather>'
        ).format(
            escape(settings.telephony_speech_language, {'"': "&quot;"}),
            escape(twilio.public_url(settings, calls.GATHER_PATH), {chr(34): "&quot;"}),
            _play_or_say(text, token),
        )
        return _twiml(gather)

    @router.post(calls.VOICE_PATH)
    @router.post("/api" + calls.VOICE_PATH)
    async def voice_webhook(request: Request) -> Response:
        form = await _verified_form(request)
        sid = form.get("CallSid", "")
        if not sid:
            raise HinaaError("TELEPHONY_BAD_REQUEST", "Missing CallSid.", 400, False)
        inbound = form.get("Direction", "").startswith("inbound")
        if inbound:
            caller = twilio.normalize_number(form.get("From"))
            if caller not in twilio.allowed_numbers(settings):
                return _hangup("Sorry, this number is private. Goodbye.")
        state = calls.get_state(settings, sid, "inbound" if inbound else "outbound")
        if inbound:
            calls.record_call(
                settings, state, to=form.get("To", ""), from_=form.get("From", ""), status="in-progress"
            )
        return await _gather(state.opening)

    @router.post(calls.GATHER_PATH)
    @router.post("/api" + calls.GATHER_PATH)
    async def gather_webhook(request: Request) -> Response:
        form = await _verified_form(request)
        sid = form.get("CallSid", "")
        if not sid:
            raise HinaaError("TELEPHONY_BAD_REQUEST", "Missing CallSid.", 400, False)
        state = calls.get_state(settings, sid)
        heard = (form.get("SpeechResult") or "").strip()
        if not heard:
            state.empty_gathers += 1
            if state.empty_gathers >= 2:
                return _hangup("I can't hear you, so I'll let you go. Talk soon.")
            return await _gather("Sorry, I didn't catch that. Could you say it again?")
        state.empty_gathers = 0
        state.turns += 1
        if state.turns > settings.telephony_max_call_turns:
            return _hangup("We've been talking a while, so I'll let you go. Talk soon.")
        try:
            reply = await calls.generate_reply(settings, service, state, heard)
        except Exception:
            logger.exception("telephony turn failed")
            reply = "Sorry, I hit a problem on my side. Let's try again in a bit."
            return _hangup(reply)
        calls.remember_turn(settings, memory_service, state, heard, reply)
        if calls.is_goodbye(heard):
            token = await calls.synthesize_for_call(settings, service, reply)
            return _twiml(_play_or_say(reply, token), "<Hangup/>")
        return await _gather(reply)

    @router.post(calls.STATUS_PATH)
    @router.post("/api" + calls.STATUS_PATH)
    async def status_webhook(request: Request) -> Response:
        form = await _verified_form(request)
        sid, status = form.get("CallSid", ""), form.get("CallStatus", "")
        if sid and status:
            calls.update_call(settings, sid, status=status[:24])
            if status in {"completed", "failed", "busy", "no-answer", "canceled"}:
                calls._states.pop(sid, None)
        return Response(status_code=204)

    @router.get(calls.AUDIO_PREFIX + "{token}")
    @router.get("/api" + calls.AUDIO_PREFIX + "{token}")
    async def audio(token: str) -> Response:
        found = calls.fetch_audio(token)
        if found is None:
            return Response(status_code=404)
        return Response(found[0], media_type=found[1], headers={"Cache-Control": "no-store"})

    return router
