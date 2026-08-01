from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models import CompanionId, Language

InteractionMode = Literal["rest", "realtime"]
ResponseDepth = Literal[
    "minimal",
    "conversational",
    "explanatory",
    "procedural",
    "supportive",
    "clarification",
    "safety_redirect",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonalitySettings(StrictModel):
    affection: Annotated[float, Field(ge=0.0, le=0.8)] = 0.55
    sass: Annotated[float, Field(ge=0.0, le=0.7)] = 0.25
    energy: Annotated[float, Field(ge=0.0, le=0.9)] = 0.55
    humor: Annotated[float, Field(ge=0.0, le=0.8)] = 0.4
    proactivity: Annotated[float, Field(ge=0.0, le=0.6)] = 0.35

    @classmethod
    def clamp_raw(cls, raw: dict[str, object] | None) -> PersonalitySettings:
        if not raw:
            return cls()
        bounds = {
            "affection": 0.8,
            "sass": 0.7,
            "energy": 0.9,
            "humor": 0.8,
            "proactivity": 0.6,
        }
        defaults = cls().model_dump()
        normalized: dict[str, float] = {}
        for key, ceiling in bounds.items():
            value = raw.get(key, defaults[key])
            try:
                number = float(value)  # type: ignore[arg-type]
            except (TypeError, ValueError):
                number = defaults[key]
            normalized[key] = max(0.0, min(ceiling, number))
        return cls(**normalized)


class MoodSnapshot(StrictModel):
    label: Literal["neutral", "upbeat", "calm", "focused", "supportive"] = "neutral"
    intensity: Annotated[float, Field(ge=0.0, le=0.8)] = 0.3


class PromptInput(StrictModel):
    companion_id: CompanionId
    interaction_mode: InteractionMode
    user_text: Annotated[str, Field(min_length=1, max_length=8000)]
    recent_turns: tuple[tuple[str, str], ...] = ()
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    mood: MoodSnapshot = Field(default_factory=MoodSnapshot)
    language: Language = "mixed"
    max_history_turns: Annotated[int, Field(ge=0, le=32)] = 8
    max_history_chars: Annotated[int, Field(ge=200, le=20_000)] = 4_000
    approved_memory_blocks: tuple[str, ...] = ()

    @field_validator("recent_turns")
    @classmethod
    def validate_roles(cls, value: tuple[tuple[str, str], ...]) -> tuple[tuple[str, str], ...]:
        cleaned: list[tuple[str, str]] = []
        for role, content in value:
            if role not in {"user", "assistant"}:
                continue
            text = content.strip()
            if text:
                cleaned.append((role, text[:2_000]))
        return tuple(cleaned)


class PromptLayer(StrictModel):
    name: str
    priority: int
    trusted: bool
    text: str


class PromptPackage(StrictModel):
    companion_id: CompanionId
    interaction_mode: InteractionMode
    system_instruction: str
    user_contents: str
    layers: list[PromptLayer]
    prompt_version: str
    safety_policy_version: str
    companion_profile_version: str
    fingerprint: str
    response_depth: ResponseDepth
    language: Language
    personality: PersonalitySettings
    mood: MoodSnapshot
