from __future__ import annotations

from typing import Annotated, Literal, Any

from pydantic import BaseModel, ConfigDict, Field, AliasChoices

Language = Literal[
    "en-US",
    "hi-IN",
    "ne-NP",
    "mixed",
]
ProviderMode = Literal[
    "mock",
    "local",
    "groq",
    "openai",
    "custom",
    "real",
    "claude",
    "qwen",
    "agent-router",
    "cx-gateway",
    "gemini-live",
    "codecraft",
    "ollama",
    "omniroute",
]
CompanionId = Literal["hinaa", "hiro"]
ResponseMode = Literal[
    "conversation",
    "professional",
    "technical",
    "research",
    "automation",
    "academic",
    "creative",
    "concise_voice",
]


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


class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)
    toolName: Annotated[str, Field(min_length=1, max_length=100, validation_alias=AliasChoices("toolName", "tool", "name"))]
    parameters: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("parameters", "arguments", "args", "params"))
    id: str | None = None
    intent: str | None = None
    reason: str | None = None
    confirmed: bool = False
    approvalSource: Literal["none", "standing-consent", "user", "policy-engine"] = "none"
    idempotencyKey: str | None = Field(default=None, max_length=160)
    userId: str | None = None
    conversationId: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, validation_alias=AliasChoices("attachment_ids", "attachmentIds"))
    reference_images: list[str] = Field(default_factory=list, validation_alias=AliasChoices("reference_images", "referenceImages"))
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    imageUrl: str | None = None


class ToolExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    toolName: Annotated[str, Field(min_length=1, max_length=100, validation_alias=AliasChoices("toolName", "tool", "name"))]
    parameters: dict[str, Any] = Field(default_factory=dict, validation_alias=AliasChoices("parameters", "arguments", "args", "params"))
    confirmed: bool = False
    approvalSource: Literal["none", "standing-consent", "user", "policy-engine"] = "standing-consent"
    authorizationToken: str | None = None
    userId: str | None = None
    conversationId: str | None = None
    id: str | None = None
    intent: str | None = None
    reason: str | None = None
    description: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, validation_alias=AliasChoices("attachment_ids", "attachmentIds"))
    reference_images: list[str] = Field(default_factory=list, validation_alias=AliasChoices("reference_images", "referenceImages"))
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    imageUrl: str | None = None
    imageEngine: str | None = None
    voiceEngine: str | None = None


class AssistantTurnPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    spokenText: Annotated[str, Field(min_length=1, max_length=8000)]
    displayText: Annotated[str, Field(min_length=1, max_length=150000)]
    language: Language
    emotion: Emotion
    performance: Performance
    beats: Annotated[list[Beat], Field(max_length=12)] = Field(default_factory=list)
    memoryCandidates: Annotated[list[MemoryCandidate], Field(max_length=3)]
    toolRequests: Annotated[list[ToolRequest], Field(max_length=5)]

    # Transparent brain fallback & attribution metadata
    requestedProvider: str | None = None
    requestedModel: str | None = None
    resolvedProvider: str | None = None
    resolvedModel: str | None = None
    fallback: bool = False
    fallbackReason: str | None = None
    latencyMs: int | None = None


def safe_extract_display_text(content: str) -> str:
    if not content:
        return content
    try:
        import json
        data = json.loads(content)
        if isinstance(data, dict) and "displayText" in data:
            return data["displayText"]
        return content
    except (json.JSONDecodeError, TypeError):
        return content


class PersonalityRequest(StrictModel):
    affection: Annotated[float, Field(ge=0, le=0.8)] | None = None
    sass: Annotated[float, Field(ge=0, le=0.7)] | None = None
    energy: Annotated[float, Field(ge=0, le=0.9)] | None = None
    humor: Annotated[float, Field(ge=0, le=0.8)] | None = None
    proactivity: Annotated[float, Field(ge=0, le=0.6)] | None = None


class TurnRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    sessionId: Annotated[str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9_-]+$")]
    text: Annotated[str, Field(min_length=1, max_length=8000)]
    companionId: CompanionId = "hinaa"
    language: Language = "mixed"
    providerMode: ProviderMode = "mock"
    responseMode: ResponseMode | None = None
    brainModel: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None
    imageEngine: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None
    voiceEngine: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None
    visibleActions: list[str] = Field(default_factory=list)
    personality: PersonalityRequest | None = None
    userId: str | None = None
    conversationId: str | None = None
    imageUrl: str | None = None
    attachment_ids: list[str] = Field(default_factory=list, validation_alias=AliasChoices("attachment_ids", "attachmentIds"))
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    reference_images: list[str] = Field(default_factory=list, validation_alias=AliasChoices("reference_images", "referenceImages"))


class SpeechRequest(StrictModel):
    language: Language = "mixed"
    text: Annotated[str, Field(min_length=1, max_length=4000)]
    companionId: CompanionId = "hinaa"
    providerMode: ProviderMode = "mock"


class TranscriptResponse(StrictModel):
    text: str
    language: str
    provider: str
    latencyMs: int


class ProviderStatus(StrictModel):
    """`state` is derived per capability: for a brain, "healthy" requires a live
    call that answered — configuration alone can only ever earn "untested"."""

    id: str
    capabilities: list[str]
    state: Literal["healthy", "degraded", "unavailable", "untested", "disabled"]
    userMessage: str


class VoiceCalibration(StrictModel):
    id: Literal["natural", "soft", "lively"]
    label: str
    rate: Annotated[float, Field(ge=0.8, le=1.2)]
    pitchSemitones: Annotated[float, Field(ge=-3, le=3)]
    volume: Annotated[float, Field(ge=0.7, le=1)]


class VoiceProfile(StrictModel):
    companionId: CompanionId
    provider: Literal["azure-speech", "fish-audio", "elevenlabs"]
    requestedVoice: str
    locale: Literal["hi-IN", "ne-NP", "en-US", "mixed"]
    identityDisclosure: str
    calibrations: list[VoiceCalibration]


class TextHumanizerRequest(StrictModel):
    text: Annotated[str, Field(min_length=1, max_length=20000)]
    mode: Literal["natural", "warm", "professional", "concise"] = "natural"
    providerMode: ProviderMode = "local"
    action: Literal["humanize", "review"] = "humanize"
    brainModel: Annotated[
        str | None,
        Field(max_length=80, pattern=r"^[A-Za-z0-9._:/-]+$"),
    ] = None


class ReviewMetrics(StrictModel):
    wordCount: int
    englishWordCount: int
    sentenceCount: int
    longEnglishSentences: int
    denseParagraphs: int


class TextHumanizerResponse(StrictModel):
    originalText: str
    humanizedText: str
    protectedSpans: int
    externalTextTransfer: bool
    mode: str
    reviewMetrics: ReviewMetrics | None = None
    reviewIdeas: list[str] | None = None
