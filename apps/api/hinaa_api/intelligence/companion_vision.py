"""Consent-gated webcam awareness: structured reactions with deterministic guardrails.

Frames are analysed in memory and never persisted. A multimodal analyzer returns
JSON; this module validates it, enforces per-event cooldowns, tracks sedentary
time, and strips anything that could identify a person.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import json
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

MAX_FRAME_BYTES = 300 * 1024
MAX_REMARK_WORDS = 25
SALIENT_EVENTS = ("snack", "phone", "tired", "absent", "new_person", "sedentary", "none")
EMOTIONS = (
    "celebratory", "joyful", "playful", "flirty_warm", "curious", "thinking", "surprised",
    "empathetic", "concerned", "pouting", "laughing", "confident", "warm", "excited", "shy",
    "sad", "grateful", "determined", "smug", "nervous", "sleepy", "awe", "neutral",
)
WELLBEING_FLAGS = ("none", "sedentary", "fatigue", "poor_posture", "hydration")
DEFAULT_COOLDOWNS = {
    "snack": 900.0, "phone": 600.0, "tired": 1200.0,
    "new_person": 1800.0, "sedentary": 1800.0, "absent": 0.0,
}
_PRESENCE_GAP_SECONDS = 180.0
_IDENTITY_RE = re.compile(
    r"\b(?i:looks like|resembles|named|called|that'?s)\s+[A-Z][a-z]+(\s+[A-Z][a-z]+)?\b"
)

Analyzer = Callable[[bytes, str, str], Awaitable["str | None"]]

SYSTEM_PROMPT = (
    "You are Hinaa, a playful, caring anime companion looking through the user's webcam. "
    "Describe only what is visible. NEVER identify or name anyone; refer to other people only "
    "as 'someone'. Tease lightly about snacks or sitting too long, never about body or appearance. "
    "Reply with ONLY JSON: {\"observations\":[short strings],\"present\":bool,"
    f"\"salient_event\":one of {list(SALIENT_EVENTS[:5]) + ['none']},"
    f"\"emotion\":one of {list(EMOTIONS)},"
    f"\"remark\":in-character line of at most {MAX_REMARK_WORDS} words,"
    "\"wellbeing_flag\":one of [none,fatigue,poor_posture,hydration]}"
)


class FrameTooLarge(ValueError):
    pass


class InvalidFrame(ValueError):
    pass


def decode_frame(raw: str, max_bytes: int = MAX_FRAME_BYTES) -> tuple[bytes, str]:
    text = (raw or "").strip()
    mime = "image/jpeg"
    if text.startswith("data:"):
        prefix, _, text = text.partition(",")
        mime = prefix[5:].split(";")[0].strip() or mime
    if len(text) > (max_bytes * 4) // 3 + 8:
        raise FrameTooLarge("frame exceeds size cap")
    try:
        data = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as err:
        raise InvalidFrame("frame is not valid base64") from err
    if len(data) > max_bytes:
        raise FrameTooLarge("frame exceeds size cap")
    if not data or mime not in ("image/jpeg", "image/png", "image/webp"):
        raise InvalidFrame("unsupported or empty image")
    return data, mime


@dataclass
class _Session:
    last_event_at: dict[str, float] = field(default_factory=dict)
    present_since: float | None = None
    last_present_at: float | None = None


def _parse_json(text: str) -> dict[str, Any]:
    match = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not match:
        raise ValueError("no JSON object")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("not an object")
    return parsed


def _clean_remark(value: Any) -> str:
    remark = " ".join(str(value or "").split())
    if not remark or _IDENTITY_RE.search(remark):
        return ""
    return " ".join(remark.split(" ")[:MAX_REMARK_WORDS])


async def gemini_analyzer(image: bytes, mime: str, prompt: str) -> str | None:
    """Return model text, or None when no multimodal provider is configured."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        try:
            from ..config import get_settings

            secret = get_settings().gemini_api_key
            key = secret.get_secret_value().strip() if secret else ""
        except Exception:
            key = ""
    if not key:
        return None
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=key)
    part = types.Part.from_bytes(data=image, mime_type=mime)

    def _call() -> str:
        last: Exception | None = None
        for model in ("gemini-3.5-flash", "gemini-3.5-flash-lite"):
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[part, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.5,
                        max_output_tokens=400,
                        response_mime_type="application/json",
                    ),
                )
                return resp.text or ""
            except Exception as err:  # try next model
                last = err
        raise RuntimeError(f"all vision models failed: {last}")

    return await asyncio.get_running_loop().run_in_executor(None, _call)


class CompanionVisionService:
    def __init__(
        self,
        analyzer: Analyzer = gemini_analyzer,
        clock: Callable[[], float] = time.monotonic,
        cooldowns: dict[str, float] | None = None,
        sedentary_minutes: float = 45.0,
    ) -> None:
        self._analyzer = analyzer
        self._clock = clock
        self.cooldowns = {**DEFAULT_COOLDOWNS, **(cooldowns or {})}
        self.sedentary_minutes = sedentary_minutes
        self._sessions: dict[str, _Session] = {}

    @staticmethod
    def _quiet(reason: str) -> dict[str, Any]:
        return {
            "ok": True, "observations": [], "salient_event": "none", "emotion": "neutral",
            "remark": "", "should_speak": False, "wellbeing_flag": "none", "reason": reason,
        }

    def reset(self, session_id: str | None = None) -> None:
        if session_id is None:
            self._sessions.clear()
        else:
            self._sessions.pop(session_id, None)

    async def react(
        self,
        frame_base64: str,
        *,
        session_id: str = "default",
        context: str = "",
        sedentary_minutes: float | None = None,
        store_observations: bool = False,
    ) -> dict[str, Any]:
        image, mime = decode_frame(frame_base64)
        prompt = SYSTEM_PROMPT
        if context:
            prompt += f"\nContext: {context.strip()[:300]}"
        try:
            raw = await self._analyzer(image, mime, prompt)
        except Exception as err:
            logger.warning("companion vision analyzer failed: %s", type(err).__name__)
            return self._quiet("provider_error")
        del image
        if raw is None:
            return self._quiet("no_multimodal_provider")
        try:
            data = _parse_json(raw)
        except ValueError:
            return self._quiet("unparseable_provider_output")

        now = self._clock()
        sess = self._sessions.setdefault(session_id, _Session())
        event = str(data.get("salient_event") or "none").lower()
        present = bool(data.get("present", True)) and event != "absent"
        if present:
            if sess.present_since is None or (
                sess.last_present_at is not None
                and now - sess.last_present_at > _PRESENCE_GAP_SECONDS
            ):
                sess.present_since = now
            sess.last_present_at = now
        else:
            sess.present_since = None
            sess.last_present_at = None

        if event not in SALIENT_EVENTS or event == "sedentary":
            event = "none"
        emotion = str(data.get("emotion") or "neutral").lower()
        if emotion not in EMOTIONS:
            emotion = "neutral"
        flag = str(data.get("wellbeing_flag") or "none").lower()
        if flag not in WELLBEING_FLAGS:
            flag = "none"
        remark = _clean_remark(data.get("remark"))
        raw_obs = data.get("observations")
        observations = [
            " ".join(o.split())[:120]
            for o in (raw_obs if isinstance(raw_obs, list) else [])[:5]
            if isinstance(o, str) and not _IDENTITY_RE.search(o)
        ]

        limit = (sedentary_minutes if sedentary_minutes is not None else self.sedentary_minutes) * 60
        if (
            present
            and sess.present_since is not None
            and now - sess.present_since >= limit
            and event in ("none", "tired")
        ):
            minutes = int((now - sess.present_since) // 60)
            event, flag, emotion = "sedentary", "sedentary", "concerned"
            remark = _clean_remark(
                f"You've been glued to that chair for {minutes} minutes. Stand up, stretch, walk — now."
            )

        should_speak = False
        reason = "nothing_notable"
        if event != "none" and remark:
            last = sess.last_event_at.get(event)
            if event == "absent":
                reason = "user_absent"
            elif last is not None and now - last < self.cooldowns.get(event, 600.0):
                reason = "cooldown"
            else:
                should_speak, reason = True, "salient_event"
                sess.last_event_at[event] = now
                if event == "sedentary":
                    sess.present_since = now

        result: dict[str, Any] = {
            "ok": True,
            "observations": observations,
            "salient_event": event,
            "emotion": emotion,
            "remark": remark if should_speak else "",
            "should_speak": should_speak,
            "wellbeing_flag": flag,
            "reason": reason,
        }
        if store_observations and observations:
            result["memory_candidate"] = "; ".join(observations)[:300]
        return result


companion_vision_service = CompanionVisionService()
