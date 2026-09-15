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
    "toolRequests must be []. memoryCandidates may contain learned user facts."
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
    "en": "en-US",
    "hi": "hi-IN",
    "ne": "ne-NP",
    "hindi-english": "mixed",
    "hinglish": "mixed",
    "english-hindi": "mixed",
    "hindi": "hi-IN",
    "english": "en-US",
    "nepali": "ne-NP",
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
    """Normalize harmless Claude/Gemini/gateway aliases before strict plan validation.

    Gateways sometimes return the requested HINAA shape but abbreviate optional
    affect metadata (for example `en`, `hi`, and an emotion without
    valence/arousal). These presentation-only defaults preserve the model's
    actual display/spoken text while keeping the turn safe and schema-valid.
    """
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    def _clean_str(val: str) -> str:
        # Strip thinking blocks
        val = re.sub(r"<(?:think|thought)>[\s\S]*?</(?:think|thought)>", "", val, flags=re.IGNORECASE)
        # Strip leaked XML tags
        val = re.sub(
            r"</?(?:response|spokenText|displayText|content|message|language|emotion|performance|memoryCandidates|toolRequests)[^>]*>",
            "",
            val,
            flags=re.IGNORECASE,
        )
        # P0: Strip prose-embedded JSON tool envelopes that models sometimes emit
        # as plain text instead of structured toolRequests fields.
        # Matches: toolRequests [...], "toolRequests": [...], toolRequests[{...}]
        val = re.sub(
            r'"?toolRequests"?\s*:?\s*\[[\s\S]*?\]',
            "",
            val,
            flags=re.IGNORECASE,
        )
        # Strip stage directions like *laughs*, *मुस्कुराते हुए*, *smiles*
        val = re.sub(r"\*[^*]+\*", "", val)
        val = re.sub(
            r"\(\s*(?:laughs?|chuckles?|giggles?|smiles?|smiling|मुस्कुराते हुए|हंसते हुए|धीमे से मुस्कुराते हुए)[^)]*\)",
            "",
            val,
            flags=re.IGNORECASE,
        )
        val = re.sub(r"\s*\([a-zA-Z_]+=[0-9.]+(?:,\s*[a-zA-Z_]+=[0-9.]+)*\)\s*$", "", val)
        return val.strip()

    had_laughter = any(
        bool(re.search(r"[*(\[](?:[^*()\]]*?(?:laugh|chuckle|giggle|smile|smiling|haha|hehe|हंस|मुस्कुरा|ख़ुश)[^*()\]]*?)[*)\]]", str(payload.get(k) or ""), re.IGNORECASE))
        for k in ("displayText", "spokenText")
    )

    if isinstance(normalized.get("displayText"), str):
        normalized["displayText"] = _clean_str(normalized["displayText"])
    if isinstance(normalized.get("spokenText"), str):
        normalized["spokenText"] = _clean_str(normalized["spokenText"])

    language = normalized.get("language")
    if isinstance(language, str):
        normalized["language"] = _LANGUAGE_ALIASES.get(language.strip().lower(), language)
    emotion = normalized.get("emotion")
    valid_emotions = {"neutral", "happy", "excited", "playful", "shy", "concerned", "sad", "surprised", "thinking"}
    emotion_aliases = {
        "calm": "neutral",
        "smile": "happy",
        "smiling": "happy",
        "joy": "happy",
        "love": "playful",
        "flirty": "playful",
        "worried": "concerned",
        "curious": "thinking",
    }
    if isinstance(emotion, dict):
        raw_primary = str(emotion.get("primary", "neutral")).strip().lower()
        primary = emotion_aliases.get(raw_primary, raw_primary)
        if primary not in valid_emotions:
            primary = "happy" if had_laughter else "neutral"
        defaults = _EMOTION_DEFAULTS.get(primary, (0.0, 0.0))
        raw_intensity = emotion.get("intensity")
        try:
            intensity = max(0.0, min(1.0, float(raw_intensity))) if raw_intensity is not None else 0.6
        except (TypeError, ValueError):
            intensity = 0.6
        raw_valence = emotion.get("valence")
        try:
            valence = max(-1.0, min(1.0, float(raw_valence))) if raw_valence is not None else defaults[0]
        except (TypeError, ValueError):
            valence = defaults[0]
        raw_arousal = emotion.get("arousal")
        try:
            arousal = max(-1.0, min(1.0, float(raw_arousal))) if raw_arousal is not None else defaults[1]
        except (TypeError, ValueError):
            arousal = defaults[1]
        if had_laughter:
            primary = "happy"
            intensity = max(intensity, 0.75)
            valence = 0.8
            arousal = 0.6
        normalized["emotion"] = {
            "primary": primary,
            "intensity": intensity,
            "valence": valence,
            "arousal": arousal,
        }
    else:
        primary = "happy" if had_laughter else "neutral"
        defaults = _EMOTION_DEFAULTS.get(primary, (0.0, 0.0))
        normalized["emotion"] = {
            "primary": primary,
            "intensity": 0.75 if had_laughter else 0.5,
            "valence": 0.8 if had_laughter else defaults[0],
            "arousal": 0.6 if had_laughter else defaults[1],
        }

    # Sanitize performance metadata to strictly allowed keys and values
    perf = normalized.get("performance")
    if isinstance(perf, dict):
        perf_allowed = {"facePreset", "gesture", "gazeTarget", "headMotion", "blinkRate"}
        cleaned_perf = {k: v for k, v in perf.items() if k in perf_allowed}
        if cleaned_perf.get("facePreset") not in {
            "neutral", "soft_smile", "big_smile", "blush", "pout", "concerned", "surprised", "thinking"
        }:
            cleaned_perf["facePreset"] = "soft_smile"
        if cleaned_perf.get("gesture") not in {
            "none", "small_nod", "head_shake", "gentle_head_tilt", "wave", "explain", "celebrate", "reassure", "listening_lean"
        }:
            cleaned_perf["gesture"] = "none"
        if cleaned_perf.get("gazeTarget") not in {"camera", "away", "down", "user-content"}:
            cleaned_perf["gazeTarget"] = "camera"
        if cleaned_perf.get("headMotion") not in {"none", "subtle", "nod", "shake"}:
            cleaned_perf["headMotion"] = "subtle"
        raw_blink = cleaned_perf.get("blinkRate")
        if isinstance(raw_blink, (int, float)):
            cleaned_perf["blinkRate"] = max(0.1, min(1.0, float(raw_blink)))
        else:
            cleaned_perf["blinkRate"] = 0.3
        normalized["performance"] = cleaned_perf
    else:
        normalized["performance"] = {
            "facePreset": "soft_smile",
            "gesture": "none",
            "gazeTarget": "camera",
            "headMotion": "subtle",
            "blinkRate": 0.3,
        }

    # Sanitize and conform memory candidates
    mems = normalized.get("memoryCandidates")
    if isinstance(mems, list):
        cat_map = {
            "fact": "profile",
            "task": "goal",
            "workflow": "project",
            "conversation": "other",
            "user": "profile",
            "personal": "profile",
        }
        valid_cats = {"preference", "profile", "goal", "project", "other"}
        cleaned_mems = []
        for m in mems[:3]:
            if isinstance(m, dict) and m.get("content"):
                raw_cat = str(m.get("category", "other")).strip().lower()
                cat = cat_map.get(raw_cat, raw_cat if raw_cat in valid_cats else "other")
                cleaned_mems.append({
                    "content": str(m["content"])[:500],
                    "category": cat,
                    "requiresConfirmation": True,
                    "sourceMessageId": m.get("sourceMessageId"),
                })
        normalized["memoryCandidates"] = cleaned_mems
    elif mems is None:
        normalized["memoryCandidates"] = []

    # Ensure toolRequests is a list and normalize items (handling name/tool/args/params)
    raw_tool_requests = normalized.get("toolRequests")
    if not isinstance(raw_tool_requests, list):
        for alt in ("tool_requests", "toolCalls", "tool_calls", "tools"):
            if isinstance(normalized.get(alt), list):
                raw_tool_requests = normalized.pop(alt)
                break
    if isinstance(raw_tool_requests, list):
        cleaned_tools = []
        for item in raw_tool_requests:
            if isinstance(item, dict):
                entry = dict(item)
                tool_name = entry.get("toolName") or entry.get("tool") or entry.get("name")
                if tool_name:
                    entry["toolName"] = str(tool_name)
                params = entry.get("parameters") or entry.get("arguments") or entry.get("args") or entry.get("params")
                if isinstance(params, dict):
                    entry["parameters"] = params
                elif params is None:
                    other_keys = {
                        k: v for k, v in entry.items()
                        if k not in {"toolName", "tool", "name", "id", "intent", "reason", "confirmed", "approvalSource", "userId", "conversationId"}
                    }
                    if other_keys:
                        entry["parameters"] = other_keys
                cleaned_tools.append(entry)
        normalized["toolRequests"] = cleaned_tools
    else:
        normalized["toolRequests"] = []

    if not isinstance(normalized.get("beats"), list):
        normalized["beats"] = []

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
