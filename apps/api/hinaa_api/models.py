from __future__ import annotations

from typing import Annotated, Literal, Any

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["ne-NP", "en-US", "hi-IN", "mixed"]
ProviderMode = Literal["mock", "local", "groq", "openai", "custom", "real", "agent-router", "cx-gateway", "gemini-live"]
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


class ToolRequest(StrictModel):
    toolName: Annotated[str, Field(min_length=1, max_length=100)]
    parameters: dict[str, Any]

class AssistantTurnPlan(StrictModel):
    spokenText: Annotated[str, Field(min_length=1, max_length=4000)]
    displayText: Annotated[str, Field(min_length=1, max_length=8000)]
    language: Language
    emotion: Emotion
    performance: Performance
    beats: Annotated[list[Beat], Field(max_length=12)] = Field(default_factory=list)
    memoryCandidates: Annotated[list[MemoryCandidate], Field(max_length=3)]
    toolRequests: Annotated[list[ToolRequest], Field(max_length=5)]


class PersonalityRequest(StrictModel):
    affection: Annotated[float, Field(ge=0, le=0.8)] | None = None
    sass: Annotated[float, Field(ge=0, le=0.7)] | None = None
    energy: Annotated[float, Field(ge=0, le=0.9)] | None = None
    humor: Annotated[float, Field(ge=0, le=0.8)] | None = None
    proactivity: Annotated[float, Field(ge=0, le=0.6)] | None = None


class TurnRequest(StrictModel):
    sessionId: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    companionId: CompanionId = "hinaa"
    language: Language = "mixed"
    providerMode: ProviderMode = "mock"
    brainModel: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None
    visibleActions: list[str] = Field(default_factory=list)
    personality: PersonalityRequest | None = None


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


class VoiceCalibration(StrictModel):
    id: Literal["natural", "soft", "lively"]
    label: str
    rate: Annotated[float, Field(ge=0.8, le=1.2)]
    pitchSemitones: Annotated[float, Field(ge=-3, le=3)]
    volume: Annotated[float, Field(ge=0.7, le=1)]


class VoiceProfile(StrictModel):
    companionId: CompanionId
    provider: Literal["azure-speech"]
    requestedVoice: str
    locale: Literal["ne-NP"]
    identityDisclosure: str
    calibrations: list[VoiceCalibration]
