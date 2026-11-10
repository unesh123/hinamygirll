"""
HINAA OS — Character Identity & Adaptive Personality Router.
Phase 04 / Modules 02 & 03: Personality traits, mood vector, dynamic presentation, and stimuli.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body
from ..errors import HinaaError

router = APIRouter(tags=["Character Identity & Personality"])


@router.get("/api/identity")
@router.get("/v1/identity")
async def get_character_identity() -> Dict[str, Any]:
    """Returns persistent character identity profile, traits, and operational mode."""
    from ..identity import get_identity_manager
    return get_identity_manager().identity.model_dump()


@router.post("/api/identity/mode")
@router.post("/v1/identity/mode")
async def update_identity_mode(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Updates active relationship mode (companion, co_pilot, analyst, operator)."""
    from ..identity import get_identity_manager, RelationshipMode
    mode_val = body.get("mode", "co_pilot")
    try:
        mode = RelationshipMode(mode_val)
    except ValueError:
        raise HinaaError("INVALID_MODE", f"Invalid relationship mode: {mode_val}", 400)
    mgr = get_identity_manager()
    mgr.set_relationship_mode(mode)
    return mgr.identity.model_dump()


@router.post("/api/identity/traits")
@router.post("/v1/identity/traits")
async def update_identity_traits(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Updates numeric persona traits (warmth, intellect, playfulness, etc.)."""
    from ..identity import get_identity_manager
    mgr = get_identity_manager()
    mgr.update_traits(**body)
    return mgr.identity.model_dump()


@router.get("/api/personality/mood")
@router.get("/v1/personality/mood")
async def get_current_mood() -> Dict[str, Any]:
    """Returns current dynamic emotional presentation, mood vector, avatar animation, and voice cues."""
    from ..personality import get_mood_engine
    engine = get_mood_engine()
    pitch, rate = engine.get_voice_modulation()
    return {
        "currentState": engine.current_state.value,
        "vector": engine.vector.model_dump(),
        "avatarAnimation": engine.get_avatar_animation(),
        "voicePitchMultiplier": pitch,
        "voiceRateMultiplier": rate,
        "promptCue": engine.get_prompt_mood_cue(),
    }


@router.post("/api/personality/stimulus")
@router.post("/v1/personality/stimulus")
async def trigger_mood_stimulus(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Applies an emotional stimulus impulse to the mood engine."""
    from ..personality import get_mood_engine, StimulusType
    stimulus_val = body.get("stimulus", "casual_chat")
    context = body.get("context", "")
    try:
        stimulus = StimulusType(stimulus_val)
    except ValueError:
        raise HinaaError("INVALID_STIMULUS", f"Invalid stimulus: {stimulus_val}", 400)
    engine = get_mood_engine()
    event = engine.process_stimulus(stimulus, context=context)
    return event.model_dump()
