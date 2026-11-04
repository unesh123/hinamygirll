"""Tests for Module 03: Adaptive Mood & Presentation Engine."""

import pytest
from hinaa_api.personality.models import (
    MoodState,
    StimulusType,
    MoodVector,
)
from hinaa_api.personality.mood_engine import AdaptiveMoodEngine


def test_mood_engine_initial_state():
    engine = AdaptiveMoodEngine()
    assert engine.current_state == MoodState.CALM
    assert engine.vector.valence > 0.0


def test_mood_engine_praise_stimulus():
    engine = AdaptiveMoodEngine()
    event = engine.process_stimulus(StimulusType.USER_PRAISE, context="User praised deep inference routing")
    assert event.new_state in (MoodState.ENTHUSIASTIC, MoodState.PLAYFUL)
    assert event.avatar_animation in ("nod_cheer_bright", "winking_smile")
    assert event.voice_pitch_multiplier > 1.0


def test_mood_engine_complex_challenge():
    engine = AdaptiveMoodEngine()
    event = engine.process_stimulus(StimulusType.COMPLEX_CHALLENGE, context="Challenging bug in ADB daemon")
    assert event.new_state == MoodState.FOCUSED
    assert event.avatar_animation == "concentrated_terminal_glance"
    assert "FOCUSED" in engine.get_prompt_mood_cue()


def test_mood_engine_tool_failure_recovery():
    engine = AdaptiveMoodEngine()
    event = engine.process_stimulus(StimulusType.TOOL_FAILURE, context="Port 5555 refused")
    assert event.new_state in (MoodState.THOUGHTFUL, MoodState.FRUSTRATED)
    assert event.avatar_animation in ("hand_on_chin_ponder", "determined_frown_recover")


def test_mood_engine_equilibrium_decay():
    engine = AdaptiveMoodEngine(decay_rate=0.5)
    # Excite to maximum
    engine.process_stimulus(StimulusType.USER_PRAISE)
    assert engine.vector.valence > 0.8

    # Apply idle decay steps
    for _ in range(5):
        engine.decay()

    # Should decay back near baseline equilibrium (0.6)
    assert engine.vector.valence < 0.75
