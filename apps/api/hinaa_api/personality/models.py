"""Data models for HINAA Adaptive Mood & Presentation Engine."""

from __future__ import annotations

import time
from enum import Enum
from pydantic import BaseModel, Field


class MoodState(str, Enum):
    CALM = "calm"
    CURIOUS = "curious"
    FOCUSED = "focused"
    ENTHUSIASTIC = "enthusiastic"
    THOUGHTFUL = "thoughtful"
    PLAYFUL = "playful"
    FRUSTRATED = "frustrated"


class StimulusType(str, Enum):
    USER_PRAISE = "user_praise"
    COMPLEX_CHALLENGE = "complex_challenge"
    TOOL_FAILURE = "tool_failure"
    SUCCESSFUL_EXECUTION = "successful_execution"
    CASUAL_CHAT = "casual_chat"
    IDLE_TIME = "idle_time"


class MoodVector(BaseModel):
    valence: float = Field(default=0.6, ge=-1.0, le=1.0)     # Unpleasant (-1) to Pleasant (+1)
    arousal: float = Field(default=0.5, ge=0.0, le=1.0)       # Passive (0) to Highly Activated (1)
    dominance: float = Field(default=0.7, ge=0.0, le=1.0)     # Submissive (0) to Confident / In Control (1)
    focus: float = Field(default=0.6, ge=0.0, le=1.0)         # Diffuse (0) to Deep Technical Focus (1)


class MoodTransitionEvent(BaseModel):
    previous_state: MoodState
    new_state: MoodState
    stimulus: StimulusType
    avatar_animation: str
    voice_pitch_multiplier: float = 1.0
    voice_rate_multiplier: float = 1.0
    reason: str
    timestamp: float = Field(default_factory=time.time)
