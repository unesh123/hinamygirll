from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["ne-NP", "en-US", "hi-IN", "mixed"]
ProviderMode = Literal["mock", "real"]
CompanionId = Literal["hinaa", "hiro"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Emotion(StrictModel):
    primary: Literal[
        "neutral",
        "happy",
        "excited",
        "playful",
        "shy",
        "concerned",
        "sad",
        "surprised",
        "thinking",
    ]
    intensity: Annotated[float, Field(ge=0, le=1)]
    valence: Annotated[float, Field(ge=-1, le=1)]
    arousal: Annotated[float, Field(ge=-1, le=1)]


class Performance(StrictModel):
    facePreset: Literal[
        "neutral",
        "soft_smile",
        "big_smile",
        "blush",
        "pout",
        "concerned",
        "surprised",
        "thinking",
    ]
    gesture: Literal[
        "none",
        "small_nod",
        "head_shake",
        "gentle_head_tilt",
        "wave",
        "explain",
        "celebrate",
        "reassure",
        "listening_lean",
    ]
    gazeTarget: Literal["camera", "away", "down", "user-content"]
    headMotion: Literal["none", "subtle", "nod", "shake"]
    blinkRate: Annotated[float, Field(ge=0.1, le=1)]


class Beat(StrictModel):
    anchorText: Annotated[str, Field(min_length=1, max_length=80)]
    face: Literal[
        "neutral",
        "soft_smile",
        "big_smile",
        "blush",
        "pout",
        "concerned",
        "surprised",
        "thinking",
    ]
    gesture: Literal[
        "none",
        "small_nod",
        "head_shake",
        "gentle_head_tilt",
        "wave",
        "explain",
        "celebrate",
        "reassure",
    ]
    gaze: Literal["camera", "down", "away", "user-content"]
    intensity: Annotated[float | None, Field(ge=0, le=1)] = None


class MemoryCandidate(StrictModel):
    content: Annotated[str, Field(min_length=1, max_length=500)]
    category: Literal["preference", "profile", "goal", "project", "other"]
    requiresConfirmation: Literal[True]
    sourceMessageId: str | None = None


class AssistantTurnPlan(StrictModel):
    spokenText: Annotated[str, Field(min_length=1, max_length=4000)]
    displayText: Annotated[str, Field(min_length=1, max_length=8000)]
    language: Language
    emotion: Emotion
    performance: Performance
    beats: Annotated[list[Beat], Field(max_length=12)] = Field(default_factory=list)
    memoryCandidates: Annotated[list[MemoryCandidate], Field(max_length=3)]
    toolRequests: Annotated[list[None], Field(max_length=0)]


class TurnRequest(StrictModel):
    sessionId: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    companionId: CompanionId = "hinaa"
    language: Language = "mixed"
    providerMode: ProviderMode = "mock"


class SpeechRequest(StrictModel):
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    companionId: CompanionId = "hinaa"
    providerMode: ProviderMode = "mock"


class TranscriptResponse(StrictModel):
    text: str
    language: str
    provider: str
    latencyMs: int


class ProviderStatus(StrictModel):
    id: str
    capabilities: list[str]
    state: Literal["healthy", "degraded", "unavailable", "disabled"]
    userMessage: str
