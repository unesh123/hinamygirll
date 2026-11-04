"""Pytest suite for Adaptive Voice Prosody Engine."""

import pytest
from hinaa_api.personality.models import MoodState, MoodVector
from hinaa_api.voice.prosody import VoiceProsodyEngine, VoiceProsodyProfile


def test_baseline_prosody_for_mood_states():
    calm = VoiceProsodyEngine.compute_prosody(MoodState.CALM)
    assert calm.voice_mode == "calm"
    assert calm.pitch_semitones == 0.1
    assert calm.rate == 0.98

    enthusiastic = VoiceProsodyEngine.compute_prosody(MoodState.ENTHUSIASTIC)
    assert enthusiastic.voice_mode == "celebratory"
    assert enthusiastic.rate > calm.rate
    assert enthusiastic.pitch_semitones > calm.pitch_semitones
    assert enthusiastic.energy > calm.energy

    thoughtful = VoiceProsodyEngine.compute_prosody(MoodState.THOUGHTFUL)
    assert thoughtful.voice_mode == "thoughtful"
    assert thoughtful.rate < calm.rate
    assert thoughtful.pitch_semitones < 0.0

    focused = VoiceProsodyEngine.compute_prosody(MoodState.FOCUSED)
    assert focused.voice_mode == "professional"
    assert focused.pitch_semitones == 0.0


def test_continuous_vector_modulation():
    base_calm = VoiceProsodyEngine.compute_prosody(MoodState.CALM)

    # High arousal & high valence
    excited_vector = MoodVector(valence=0.9, arousal=0.9, dominance=0.8, focus=0.5)
    excited_prosody = VoiceProsodyEngine.compute_prosody(MoodState.CALM, mood_vector=excited_vector)

    assert excited_prosody.energy > base_calm.energy
    assert excited_prosody.rate >= base_calm.rate
    assert excited_prosody.warmth > base_calm.warmth

    # Deep focus suppresses erratic emotional swings
    focused_vector = MoodVector(valence=0.2, arousal=0.8, dominance=0.8, focus=0.9)
    deep_focus_prosody = VoiceProsodyEngine.compute_prosody(MoodState.CALM, mood_vector=focused_vector)
    assert 0.95 <= deep_focus_prosody.rate <= 1.05


def test_calibration_modifiers():
    natural = VoiceProsodyEngine.compute_prosody(MoodState.CALM, calibration="natural")
    soft = VoiceProsodyEngine.compute_prosody(MoodState.CALM, calibration="soft")
    lively = VoiceProsodyEngine.compute_prosody(MoodState.CALM, calibration="lively")

    assert soft.rate < natural.rate
    assert soft.pitch_semitones < natural.pitch_semitones
    assert soft.warmth >= natural.warmth

    assert lively.rate > natural.rate
    assert lively.pitch_semitones > natural.pitch_semitones
    assert lively.energy >= natural.energy
