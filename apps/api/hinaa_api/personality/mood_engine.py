"""Adaptive Mood Engine for HINAA.

Calculates real-time emotional state transitions, equilibrium decay,
avatar animation triggers, and speech modulation multipliers.
"""

from __future__ import annotations

import time
import logging
from typing import Any
from hinaa_api.personality.models import (
    MoodState,
    MoodVector,
    StimulusType,
    MoodTransitionEvent,
)

logger = logging.getLogger("hinaa.personality.mood_engine")

# Baseline equilibrium coordinates
BASELINE_VECTOR = MoodVector(valence=0.6, arousal=0.4, dominance=0.65, focus=0.5)


class AdaptiveMoodEngine:
    """Manages dynamic emotional presentation, stimulus reactions, and equilibrium decay."""

    def __init__(self, decay_rate: float = 0.15) -> None:
        self.vector = MoodVector()
        self.current_state = MoodState.CALM
        self.decay_rate = decay_rate
        self.last_transition_time = time.time()
        self.history: list[MoodTransitionEvent] = []

    def _determine_state(self) -> MoodState:
        """Resolves the discrete mood state from continuous dimensional vector."""
        v = self.vector
        if v.focus > 0.75:
            return MoodState.FOCUSED
        if v.valence > 0.6 and v.arousal > 0.6:
            return MoodState.ENTHUSIASTIC if v.focus > 0.4 else MoodState.PLAYFUL
        if v.valence > 0.3 and v.arousal > 0.4:
            return MoodState.CURIOUS
        if v.valence < 0.0 and v.focus > 0.5:
            return MoodState.THOUGHTFUL
        if v.valence < -0.3 and v.arousal > 0.5:
            return MoodState.FRUSTRATED
        return MoodState.CALM

    def process_stimulus(self, stimulus: StimulusType, context: str = "") -> MoodTransitionEvent:
        """Applies stimulus impulse to mood vector and derives state change."""
        prev_state = self.current_state
        v = self.vector

        if stimulus == StimulusType.USER_PRAISE:
            v.valence = min(1.0, v.valence + 0.35)
            v.arousal = min(1.0, v.arousal + 0.25)
            v.dominance = min(1.0, v.dominance + 0.1)
        elif stimulus == StimulusType.COMPLEX_CHALLENGE:
            v.focus = min(1.0, v.focus + 0.45)
            v.arousal = min(1.0, v.arousal + 0.2)
            v.dominance = min(1.0, v.dominance + 0.15)
        elif stimulus == StimulusType.TOOL_FAILURE:
            v.valence = max(-0.5, v.valence - 0.25)
            v.focus = min(1.0, v.focus + 0.35)
        elif stimulus == StimulusType.SUCCESSFUL_EXECUTION:
            v.valence = min(1.0, v.valence + 0.4)
            v.dominance = min(1.0, v.dominance + 0.2)
            v.arousal = min(1.0, v.arousal + 0.15)
        elif stimulus == StimulusType.CASUAL_CHAT:
            v.arousal = max(0.2, min(0.6, v.arousal))
            v.valence = max(0.4, v.valence)
        elif stimulus == StimulusType.IDLE_TIME:
            self.decay()

        new_state = self._determine_state()
        self.current_state = new_state
        self.last_transition_time = time.time()

        anim = self.get_avatar_animation()
        pitch, rate = self.get_voice_modulation()

        event = MoodTransitionEvent(
            previous_state=prev_state,
            new_state=new_state,
            stimulus=stimulus,
            avatar_animation=anim,
            voice_pitch_multiplier=pitch,
            voice_rate_multiplier=rate,
            reason=context or f"Triggered by {stimulus.value}",
        )
        self.history.append(event)
        if len(self.history) > 50:
            self.history.pop(0)

        logger.info("Mood transition: %s -> %s (stimulus: %s)", prev_state.value, new_state.value, stimulus.value)
        return event

    def decay(self) -> None:
        """Gradually pulls the mood vector back towards baseline equilibrium."""
        rate = self.decay_rate
        self.vector.valence += rate * (BASELINE_VECTOR.valence - self.vector.valence)
        self.vector.arousal += rate * (BASELINE_VECTOR.arousal - self.vector.arousal)
        self.vector.dominance += rate * (BASELINE_VECTOR.dominance - self.vector.dominance)
        self.vector.focus += rate * (BASELINE_VECTOR.focus - self.vector.focus)
        self.current_state = self._determine_state()

    def get_avatar_animation(self) -> str:
        """Returns the corresponding 3D avatar animation state trigger."""
        mapping = {
            MoodState.CALM: "idle_gentle_breath",
            MoodState.CURIOUS: "head_tilt_questioning",
            MoodState.FOCUSED: "concentrated_terminal_glance",
            MoodState.ENTHUSIASTIC: "nod_cheer_bright",
            MoodState.THOUGHTFUL: "hand_on_chin_ponder",
            MoodState.PLAYFUL: "winking_smile",
            MoodState.FRUSTRATED: "determined_frown_recover",
        }
        return mapping.get(self.current_state, "idle_gentle_breath")

    def get_voice_modulation(self) -> tuple[float, float]:
        """Returns (pitch_multiplier, rate_multiplier) for TTS synthesis."""
        mapping = {
            MoodState.CALM: (1.0, 1.0),
            MoodState.CURIOUS: (1.04, 1.02),
            MoodState.FOCUSED: (0.98, 0.96),
            MoodState.ENTHUSIASTIC: (1.07, 1.08),
            MoodState.THOUGHTFUL: (0.96, 0.92),
            MoodState.PLAYFUL: (1.06, 1.05),
            MoodState.FRUSTRATED: (0.97, 0.98),
        }
        return mapping.get(self.current_state, (1.0, 1.0))

    def get_prompt_mood_cue(self) -> str:
        """Returns prompt guidance cue reflecting current mood for generation."""
        mapping = {
            MoodState.CALM: "Express yourself with calm, poised clarity and gentle warmth.",
            MoodState.CURIOUS: "Show engaged curiosity, ask perceptive questions, and explore nuances.",
            MoodState.FOCUSED: "Deliver razor-sharp, technically precise analysis with direct efficiency.",
            MoodState.ENTHUSIASTIC: "Communicate with high energy, enthusiasm, and proactive momentum.",
            MoodState.THOUGHTFUL: "Reflect carefully, analyze trade-offs, and suggest sound structural fixes.",
            MoodState.PLAYFUL: "Infuse witty, lighthearted banter while maintaining crisp technical accuracy.",
            MoodState.FRUSTRATED: "Acknowledge obstacles candidly and pivot immediately to concrete solutions.",
        }
        return f"Current Mood: {self.current_state.value.upper()}. {mapping.get(self.current_state, '')}"


_global_mood_engine: AdaptiveMoodEngine | None = None


def get_mood_engine() -> AdaptiveMoodEngine:
    global _global_mood_engine
    if _global_mood_engine is None:
        _global_mood_engine = AdaptiveMoodEngine()
    return _global_mood_engine
