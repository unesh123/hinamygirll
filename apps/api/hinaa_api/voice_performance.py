from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

VoiceMode = Literal[
    "neutral",
    "warm",
    "bright",
    "calm",
    "professional",
    "celebratory",
    "thoughtful",
    "apologetic",
]


class VoicePerformancePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: VoiceMode = "neutral"
    pace: Annotated[float, Field(ge=0.85, le=1.15)] = 1.0
    pitch_semitones: Annotated[float, Field(ge=-2.0, le=2.0)] = 0.0
    volume: Annotated[float, Field(ge=0.75, le=1.0)] = 1.0
    warmth: Annotated[float, Field(ge=0.0, le=1.0)] = 0.5
    energy: Annotated[float, Field(ge=0.0, le=1.0)] = 0.45


# Provider/product names (gemini, azure) are deliberately NOT tech-task
# signals: saying "gemini ai assistant made by google" or "azure" must not
# flatten her into the professional (flat, robotic) delivery — that is exactly
# the "she stops being herself when I mention AI" complaint. Only genuine
# coding/task words flip the delivery.
_TECH = re.compile(
    r"\b(code|bug|api|error|debug|typescript|fastapi|websocket|sql|http)\b",
    re.IGNORECASE,
)
_SERIOUS = re.compile(
    r"\b(sorry|error|fail|problem|issue|frustrat|anxious|help)\b|"
    r"(माफ|समस्या|गलत)",
    re.IGNORECASE,
)
_CELEBRATE = re.compile(r"\b(great|awesome|done|passed|thanks|धन्यवाद|भयो)\b", re.IGNORECASE)
_GREET = re.compile(r"\b(hi|hello|hey|namaste|नमस्ते)\b", re.IGNORECASE)


# Speech-only substitutions; display text remains unchanged.
PRONUNCIATION_MAP = (
    (re.compile(r"\bHINAA\b"), "Hee-nah"),
    (re.compile(r"\bHinaa\b"), "Hee-nah"),
    (re.compile(r"\bHiro\b"), "Hee-ro"),
    (re.compile(r"\bWebSocket\b"), "web socket"),
    (re.compile(r"\bFastAPI\b"), "fast A P I"),
    (re.compile(r"\bTypeScript\b"), "type script"),
    (re.compile(r"\bGemini\b"), "jem-in-eye"),
    (re.compile(r"\bAzure\b"), "azh-ure"),
)


def plan_voice_performance(*, user_text: str, reply_text: str, depth: str) -> VoicePerformancePlan:
    text = f"{user_text}\n{reply_text}"
    if depth in {"supportive", "safety_redirect"} or _SERIOUS.search(text):
        return VoicePerformancePlan(
            mode="calm" if "sorry" not in text.lower() else "apologetic",
            pace=0.94,
            pitch_semitones=-0.4,
            volume=0.9,
            warmth=0.75,
            energy=0.3,
        )
    if _TECH.search(text) or depth in {"procedural", "explanatory"}:
        return VoicePerformancePlan(
            mode="professional",
            pace=0.98,
            pitch_semitones=0.0,
            volume=1.0,
            warmth=0.4,
            energy=0.4,
        )
    if _CELEBRATE.search(text):
        return VoicePerformancePlan(
            mode="celebratory",
            pace=1.06,
            pitch_semitones=0.8,
            volume=1.0,
            warmth=0.75,
            energy=0.7,
        )
    if _GREET.search(text):
        return VoicePerformancePlan(
            mode="bright",
            pace=1.04,
            pitch_semitones=0.5,
            volume=1.0,
            warmth=0.7,
            energy=0.6,
        )
    if depth == "thoughtful" or "thinking" in reply_text.lower():
        return VoicePerformancePlan(
            mode="thoughtful",
            pace=0.96,
            pitch_semitones=-0.2,
            volume=0.95,
            warmth=0.6,
            energy=0.35,
        )
    return VoicePerformancePlan(mode="warm", pace=1.0, pitch_semitones=0.2, warmth=0.7, energy=0.5)


def speech_text_for_tts(display_text: str) -> str:
    spoken = display_text
    for pattern, replacement in PRONUNCIATION_MAP:
        spoken = pattern.sub(replacement, spoken)
    # Strip markdown that sounds bad in TTS.
    spoken = re.sub(r"[`*#>]+", " ", spoken)
    spoken = re.sub(r"\s+", " ", spoken).strip()
    return spoken


ALLOWED_SSML_TAGS = frozenset({"speak", "prosody", "break"})


def build_bounded_ssml(text: str, plan: VoicePerformancePlan) -> str:
    safe = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
    )
    rate = f"{plan.pace * 100:.0f}%"
    pitch = f"{plan.pitch_semitones:+.1f}st"
    volume = f"{plan.volume * 100:.0f}%"
    return (
        f'<speak version="1.0" xml:lang="hi-IN">'
        f'<prosody rate="{rate}" pitch="{pitch}" volume="{volume}">{safe}</prosody>'
        f"</speak>"
    )
