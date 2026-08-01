from __future__ import annotations

from ..config import Settings
from ..models import TurnRequest
from .assembly import assemble_prompt
from .models import InteractionMode, PersonalitySettings, PromptInput, PromptPackage


def personality_from_settings(settings: Settings, request: TurnRequest) -> PersonalitySettings:
    base = {
        "affection": settings.personality_affection,
        "sass": settings.personality_sass,
        "energy": settings.personality_energy,
        "humor": settings.personality_humor,
        "proactivity": settings.personality_proactivity,
    }
    if request.personality is not None:
        override = request.personality.model_dump(exclude_none=True)
        base.update(override)
    return PersonalitySettings.clamp_raw(base)


def build_turn_prompt(
    *,
    request: TurnRequest,
    history: tuple[tuple[str, str], ...],
    settings: Settings,
    interaction_mode: InteractionMode,
) -> PromptPackage:
    inp = PromptInput(
        companion_id=request.companionId,
        interaction_mode=interaction_mode,
        user_text=request.text,
        recent_turns=history,
        personality=personality_from_settings(settings, request),
        language=request.language,
        max_history_turns=settings.session_turn_limit * 2,
        max_history_chars=settings.session_history_char_limit,
    )
    return assemble_prompt(inp)
