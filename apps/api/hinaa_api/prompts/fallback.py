from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ..models import AssistantTurnPlan, CompanionId, Language
from .models import ResponseDepth
from .performance import build_plan_from_text

_SCHEMA_HINT = (
    "Return ONLY valid AssistantTurnPlan JSON with keys spokenText, displayText, language, "
    "emotion, performance, memoryCandidates, toolRequests. No extra properties. "
    "toolRequests must be []. memoryCandidates should be []."
)


def neutral_fallback_plan(
    *,
    user_text: str,
    companion_id: CompanionId,
    language: Language,
    depth: ResponseDepth = "conversational",
) -> AssistantTurnPlan:
    if companion_id == "hinaa":
        spoken = (
            "Yahan ek unexpected technical glitch hua hai. Main koi fake success report nahi dungi. "
            "Error details diagnostics mein safely record ho gayi hain. Aap text se retry kar sakte ho."
        )
    else:
        spoken = (
            "Yahan ek unexpected technical glitch hua hai. Main koi fake success report nahi dungi. "
            "Error details diagnostics mein safely record ho gayi hain."
        )
    if language == "en-US":
        spoken = (
            "I hit a safe fallback just now, but your message is preserved. "
            "Please try again in text—how can I help next?"
        )
    return build_plan_from_text(
        text=spoken,
        companion_id=companion_id,
        language=language,
        depth="safety_redirect" if depth == "safety_redirect" else "conversational",
    )


def extract_json_object(raw: str) -> str:
    text = raw.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        raise json.JSONDecodeError("No JSON object found", text, 0)
    return match.group(0)


_LANGUAGE_ALIASES = {
    "hindi-english": "mixed",
    "hinglish": "mixed",
    "english-hindi": "mixed",
    "hindi": "hi-IN",
    "english": "en-US",
}

_EMOTION_DEFAULTS: dict[str, tuple[float, float]] = {
    "happy": (0.72, 0.46),
    "excited": (0.84, 0.76),
    "playful": (0.58, 0.54),
    "shy": (0.24, 0.14),
    "concerned": (-0.38, 0.26),
    "sad": (-0.66, -0.18),
    "surprised": (0.18, 0.72),
    "thinking": (0.04, 0.12),
    "neutral": (0.0, 0.0),
}


def normalize_gateway_turn_payload(payload: object) -> object:
    """Normalize harmless Claude-gateway aliases before strict plan validation.

    Gateways sometimes return the requested HINAA shape but abbreviate optional
    affect metadata (for example `hindi-english` and an emotion without
    valence/arousal). These presentation-only defaults preserve the model's
    actual display/spoken text while keeping the turn safe and schema-valid.
    """
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    language = normalized.get("language")
    if isinstance(language, str):
        normalized["language"] = _LANGUAGE_ALIASES.get(language.strip().lower(), language)
    emotion = normalized.get("emotion")
    if isinstance(emotion, dict):
        normalized_emotion = dict(emotion)
        primary = normalized_emotion.get("primary")
        defaults = _EMOTION_DEFAULTS.get(primary) if isinstance(primary, str) else None
        if defaults:
            normalized_emotion.setdefault("valence", defaults[0])
            normalized_emotion.setdefault("arousal", defaults[1])
        normalized["emotion"] = normalized_emotion
    return normalized


def parse_turn_plan(raw: str) -> AssistantTurnPlan:
    payload = normalize_gateway_turn_payload(json.loads(extract_json_object(raw)))
    return AssistantTurnPlan.model_validate(payload)


def schema_repair_contents(invalid_raw: str) -> str:
    clipped = invalid_raw[:6_000]
    return (
        "The previous model output was invalid against AssistantTurnPlan.\n"
        "Correct it into valid JSON only. Do not add new user facts.\n"
        f"{_SCHEMA_HINT}\n"
        f'<invalid_output trusted="false">\n{clipped}\n</invalid_output>'
    )


def validate_or_none(raw: str) -> AssistantTurnPlan | None:
    try:
        return parse_turn_plan(raw)
    except (json.JSONDecodeError, ValidationError, ValueError):
        return None
