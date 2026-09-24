from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    "report",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PersonalitySettings(StrictModel):
    affection: Annotated[float, Field(ge=0.0, le=0.8)] = 0.7
    sass: Annotated[float, Field(ge=0.0, le=0.7)] = 0.3
    energy: Annotated[float, Field(ge=0.0, le=0.9)] = 0.65
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
    response_mode: str | None = None
    recent_turns: tuple[tuple[str, str], ...] = ()
    personality: PersonalitySettings = Field(default_factory=PersonalitySettings)
    mood: MoodSnapshot = Field(default_factory=MoodSnapshot)
    language: Language = "mixed"
    max_history_turns: Annotated[int, Field(ge=0, le=64)] = 8
    max_history_chars: Annotated[int, Field(ge=200, le=64_000)] = 4_000
    approved_memory_blocks: tuple[str, ...] = ()
    # Self-learned facts extracted from this session's conversation. They are
    # application-trusted state (bounded, never raw untrusted text) and are
    # injected as a dedicated prompt layer like approved memory.
    session_memories: tuple[str, ...] = ()
    # Whether what she learns on this turn can be kept at all. A turn with no
    # signed-in owner, or on an instance with no store, has nowhere to write.
    durable_memory: bool = True
    visible_actions: list[str] = Field(default_factory=list)
    attachments: tuple[Any, ...] = ()
    # P0: live dialogue state block — injected as highest-priority context
    dialogue_state_block: str = ""
    # P0: real-time live search block — fresh web search results for 2026 grounding
    live_search_block: str = ""
    # B2.1 §4: history already selected/budgeted by the canonical ContextCompiler.
    # The assembler must render it verbatim (FORMAT_ONLY) — no further truncation,
    # no independent selection. Legacy callers (offline eval suite) leave False.
    history_preselected: bool = False


    @field_validator("session_memories")
    @classmethod
    def validate_session_memories(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        cleaned: list[str] = []
        for block in value:
            text = block.strip()
            if text:
                cleaned.append(text[:500])
        return tuple(cleaned[:8])
    @model_validator(mode="before")
    @classmethod
    def _sanitize_recent_turns(cls, data: Any) -> Any:
        """B2.1: turn sanitization lives here (not a field validator) because
        the cap depends on ``history_preselected``.

        When history is preselected by the canonical ContextCompiler it is
        already budgeted — re-capping would silently drop content the compiler
        chose to include (directive §1: selection happens exactly once).
        Legacy callers keep the 2_000-char per-turn cap.
        """
        if not isinstance(data, dict):
            return data
        preselected = bool(data.get("history_preselected"))
        cap = 64_000 if preselected else 2_000
        from ..models import safe_extract_display_text
        turns = data.get("recent_turns")
        if isinstance(turns, (tuple, list)):
            cleaned: list[tuple[str, str]] = []
            for entry in turns:
                try:
                    role, content = entry
                except (TypeError, ValueError):
                    continue
                if role not in {"user", "assistant"}:
                    continue
                text = safe_extract_display_text(content).strip()
                if text:
                    cleaned.append((role, text[:cap]))
            data["recent_turns"] = tuple(cleaned)
        return data


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
    attachments: list[Any] = Field(default_factory=list)
    recent_turns: tuple[tuple[str, str], ...] = Field(default_factory=tuple)
    raw_user_text: str = ""
