"""Adaptive Emotion & Mood-Driven Voice Prosody Engine for HINAA OS.

Dynamically modulates speech synthesis parameters (rate, pitch, warmth, energy)
based on Hinaa's active mood vector (valence, arousal, dominance, focus) and
user calibration profile.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from ..personality.models import MoodState, MoodVector


@dataclass(slots=True)
class VoiceProsodyProfile:
    rate: float
    pitch_semitones: float
    volume: float
    warmth: float
    energy: float
    voice_mode: str
    mood_state: MoodState


# Baseline prosody lookup per discrete mood
_MOOD_BASELINES: dict[MoodState, VoiceProsodyProfile] = {
    MoodState.CALM: VoiceProsodyProfile(
        rate=0.98,
        pitch_semitones=0.1,
        volume=0.95,
        warmth=0.80,
        energy=0.40,
        voice_mode="calm",
        mood_state=MoodState.CALM,
    ),
    MoodState.CURIOUS: VoiceProsodyProfile(
        rate=1.02,
        pitch_semitones=0.5,
        volume=1.00,
        warmth=0.70,
        energy=0.60,
        voice_mode="bright",
        mood_state=MoodState.CURIOUS,
    ),
    MoodState.FOCUSED: VoiceProsodyProfile(
        rate=0.98,
        pitch_semitones=0.0,
        volume=1.00,
        warmth=0.45,
        energy=0.50,
        voice_mode="professional",
        mood_state=MoodState.FOCUSED,
    ),
    MoodState.ENTHUSIASTIC: VoiceProsodyProfile(
        rate=1.07,
        pitch_semitones=0.9,
        volume=1.00,
        warmth=0.75,
        energy=0.85,
        voice_mode="celebratory",
        mood_state=MoodState.ENTHUSIASTIC,
    ),
    MoodState.THOUGHTFUL: VoiceProsodyProfile(
        rate=0.94,
        pitch_semitones=-0.3,
        volume=0.92,
        warmth=0.65,
        energy=0.35,
        voice_mode="thoughtful",
        mood_state=MoodState.THOUGHTFUL,
    ),
    MoodState.PLAYFUL: VoiceProsodyProfile(
        rate=1.04,
        pitch_semitones=0.7,
        volume=1.00,
        warmth=0.85,
        energy=0.70,
        voice_mode="warm",
        mood_state=MoodState.PLAYFUL,
    ),
    MoodState.FRUSTRATED: VoiceProsodyProfile(
        rate=0.92,
        pitch_semitones=-0.5,
        volume=0.90,
        warmth=0.40,
        energy=0.30,
        voice_mode="apologetic",
        mood_state=MoodState.FRUSTRATED,
    ),
}


class VoiceProsodyEngine:
    """Computes fine-grained vocal delivery parameters from mood state and vector."""

    @classmethod
    def compute_prosody(
        cls,
        mood_state: MoodState = MoodState.CALM,
        mood_vector: MoodVector | None = None,
        calibration: Literal["natural", "soft", "lively"] = "natural",
    ) -> VoiceProsodyProfile:
        baseline = _MOOD_BASELINES.get(mood_state, _MOOD_BASELINES[MoodState.CALM])

        rate = baseline.rate
        pitch = baseline.pitch_semitones
        warmth = baseline.warmth
        energy = baseline.energy
        volume = baseline.volume

        # Continuous vector fine-tuning if vector provided
        if mood_vector is not None:
            # High arousal increases energy and slightly increases pace
            energy = min(1.0, max(0.1, energy + (mood_vector.arousal - 0.5) * 0.3))
            rate = min(1.15, max(0.85, rate + (mood_vector.arousal - 0.5) * 0.08))

            # High valence increases warmth and lifts pitch slightly
            warmth = min(1.0, max(0.1, warmth + (mood_vector.valence - 0.5) * 0.2))
            pitch = min(2.0, max(-2.0, pitch + (mood_vector.valence - 0.5) * 0.4))

            # Deep focus dampens emotional swing towards clarity
            if mood_vector.focus > 0.7:
                energy = max(0.35, min(0.65, energy))
                rate = max(0.95, min(1.02, rate))

        # User calibration adjustments
        if calibration == "soft":
            rate = max(0.85, rate - 0.05)
            pitch = max(-2.0, pitch - 0.2)
            warmth = min(1.0, warmth + 0.1)
            volume = max(0.80, volume - 0.05)
        elif calibration == "lively":
            rate = min(1.15, rate + 0.04)
            pitch = min(2.0, pitch + 0.4)
            energy = min(1.0, energy + 0.1)

        return VoiceProsodyProfile(
            rate=round(rate, 3),
            pitch_semitones=round(pitch, 2),
            volume=round(volume, 2),
            warmth=round(warmth, 2),
            energy=round(energy, 2),
            voice_mode=baseline.voice_mode,
            mood_state=mood_state,
        )
