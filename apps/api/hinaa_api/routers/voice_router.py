"""
HINAA OS — Real-Time Voice Intelligence Router.
Phase 05: Voice lifecycle status, multilingual normalization, dynamic prosody, and barge-in interrupts.
"""

from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, Body, Request

router = APIRouter(tags=["Voice Intelligence"])


@router.get("/api/voice/status")
@router.get("/v1/voice/status")
async def get_voice_status(request: Request) -> Dict[str, Any]:
    """Returns the real-time voice intelligence status, turn metrics, and fallback status."""
    from ..voice import VoiceLifecycleManager
    from ..voice_fallback import voice_on_cooldown
    active_lifecycle: VoiceLifecycleManager = getattr(
        request.app.state, "active_voice_lifecycle", None
    )
    return {
        "status": "ready",
        "activeSession": active_lifecycle.get_status() if active_lifecycle else None,
        "providers": {
            "elevenlabs_on_cooldown": voice_on_cooldown("elevenlabs"),
            "azure_on_cooldown": voice_on_cooldown("azure"),
            "deepgram_on_cooldown": voice_on_cooldown("deepgram"),
        },
    }


@router.post("/api/voice/normalize")
@router.post("/v1/voice/normalize")
async def normalize_voice_text(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Phonetically normalizes multilingual text and detects dominant language."""
    from ..voice import MultilingualNormalizer
    text = str(body.get("text", ""))
    dominant = MultilingualNormalizer.detect_dominant_language(text)
    normalized = MultilingualNormalizer.normalize_transcript(text)
    tts_pronunciation = MultilingualNormalizer.prepare_tts_pronunciation(normalized)
    return {
        "original": text,
        "dominantLanguage": dominant.value,
        "normalized": normalized,
        "ttsPronunciation": tts_pronunciation,
    }


@router.post("/api/voice/prosody")
@router.post("/v1/voice/prosody")
async def preview_voice_prosody(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Calculates dynamic prosody modulation from personality mood and calibration."""
    from ..voice import VoiceProsodyEngine
    from ..personality import get_mood_engine, MoodState
    mood_str = body.get("mood")
    calibration = body.get("calibration", "natural")
    engine = get_mood_engine()
    mood_state = MoodState(mood_str) if mood_str else engine.current_state
    prosody = VoiceProsodyEngine.compute_prosody(
        mood_state=mood_state,
        mood_vector=engine.vector,
        calibration=calibration,
    )
    return {
        "mood": prosody.mood_state.value,
        "calibration": calibration,
        "rate": prosody.rate,
        "pitchSemitones": prosody.pitch_semitones,
        "volume": prosody.volume,
        "warmth": prosody.warmth,
        "energy": prosody.energy,
        "voiceMode": prosody.voice_mode,
    }


@router.post("/api/voice/interrupt")
@router.post("/v1/voice/interrupt")
async def trigger_voice_interrupt(request: Request, body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """REST trigger to cancel active voice turn and execute barge-in."""
    from ..voice import VoiceLifecycleManager
    target_gen = body.get("generation")
    active_lifecycle: VoiceLifecycleManager = getattr(
        request.app.state, "active_voice_lifecycle", None
    )
    if active_lifecycle:
        new_gen, cancelled_turn = active_lifecycle.trigger_barge_in(target_gen)
        return {
            "interrupted": True,
            "newGeneration": new_gen,
            "cancelledTurn": cancelled_turn.to_dict() if cancelled_turn else None,
        }
    return {"interrupted": True, "newGeneration": (target_gen or 0) + 1}
