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
            "Ma yahi chu. Tyaha kehi technical glitch bhayo, tara tapaiko message safe cha. "
            "Text bata feri try garna saknu huncha—kasari madat garau?"
        )
    else:
        spoken = (
            "Thik cha—response plan clean bhaena, tara tapaiko message safe cha. "
            "Text bata feri try gara; ma clear steps dinchu. Ke bata start garne?"
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


def parse_turn_plan(raw: str) -> AssistantTurnPlan:
    payload = json.loads(extract_json_object(raw))
    return AssistantTurnPlan.model_validate(payload)


def schema_repair_contents(invalid_raw: str) -> str:
    clipped = invalid_raw[:6_000]
    return (
        "The previous model output was invalid against AssistantTurnPlan.\n"
        "Correct it into valid JSON only. Do not add new user facts.\n"
        f"{_SCHEMA_HINT}\n"
        f"<invalid_output trusted=\"false\">\n{clipped}\n</invalid_output>"
    )


def validate_or_none(raw: str) -> AssistantTurnPlan | None:
    try:
        return parse_turn_plan(raw)
    except (json.JSONDecodeError, ValidationError, ValueError):
        return None
