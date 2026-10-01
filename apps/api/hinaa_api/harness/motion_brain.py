"""
HINAA Motion Brain & Semantic State Bus.

Continuous Intelligent Motion Engine modeled on hybrid neural/procedural motion systems:
1. Semantic Brain: Translates cognitive state (intent, energy, urgency, confidence, focus) into physical motion parameters.
2. Motion Policy: Maps semantic states into posture, gaze, gestures, orbit speed, and particle telemetry.
3. Spatial Navigation: Hina physically moves between stations in her workspace (Research, Code, Browser, Memory).
4. Telemetry Color Shader Bus:
   - Blue (#3B82F6): model inference activity
   - Cyan (#06B6D4): tool call & computer operator action
   - Violet (#8B5CF6): memory retrieval
   - Gold (#F59E0B): artifact generation (PDF, PPTX, Website)
   - Green (#10B981): verified output
   - Red (#EF4444): error / self-repair
   - White (#F8FAFC): direct voice dialogue
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SemanticIntent(str, Enum):
    THINKING = "thinking"
    RESEARCHING = "researching"
    CODING = "coding"
    BUILDING = "building"
    SEARCHING = "searching"
    SPEAKING = "speaking"
    WAITING = "waiting"
    SUCCESS = "success"
    ERROR = "error"
    OPERATING_COMPUTER = "operating_computer"


class SpatialStation(str, Enum):
    CENTER = "center"
    RESEARCH = "research"
    CODE = "code"
    BROWSER = "browser"
    MEMORY = "memory"
    OPERATING = "operating"


class HinaSemanticState(BaseModel):
    intent: SemanticIntent = SemanticIntent.WAITING
    energy: float = Field(default=0.6, ge=0.0, le=1.0)
    urgency: float = Field(default=0.3, ge=0.0, le=1.0)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    social: float = Field(default=0.7, ge=0.0, le=1.0)
    focus: float = Field(default=0.8, ge=0.0, le=1.0)
    active_agent: Optional[str] = None
    active_tool: Optional[str] = None
    progress: float = Field(default=0.0, ge=0.0, le=1.0)
    timestamp: float = Field(default_factory=time.time)


class MotionProfile(BaseModel):
    locomotion: str = "idle"  # "idle" | "walk" | "run"
    posture: float = 1.0       # uprightness
    gaze: float = 1.0          # focus angle
    gesture_rate: float = 0.5  # hand/body motion frequency
    head_motion: float = 0.3
    breathing: float = 1.0
    orbit_speed: float = 1.0
    particle_energy: float = 0.5
    camera_distance: float = 2.4
    spatial_station: SpatialStation = SpatialStation.CENTER
    trail_color: str = "#3B82F6"
    pulse_intensity: float = 0.5
    animation_clip_hint: str = "idle_warm"


class MotionDirector:
    """
    Translates cognitive state into live procedural motion profiles and spatial telemetry.
    """

    POLICY_MAP: Dict[SemanticIntent, Dict[str, Any]] = {
        SemanticIntent.RESEARCHING: {
            "locomotion": "walk",
            "spatial_station": SpatialStation.RESEARCH,
            "posture": 1.1,
            "gaze": 1.4,
            "gesture_rate": 0.4,
            "head_motion": 0.6,
            "orbit_speed": 1.8,
            "particle_energy": 0.8,
            "trail_color": "#06B6D4",  # Cyan (tool/reach)
            "animation_clip_hint": "inspect_panel",
        },
        SemanticIntent.CODING: {
            "locomotion": "walk",
            "spatial_station": SpatialStation.CODE,
            "posture": 1.2,
            "gaze": 1.6,
            "gesture_rate": 0.9,
            "head_motion": 0.4,
            "orbit_speed": 2.2,
            "particle_energy": 0.95,
            "trail_color": "#3B82F6",  # Blue (computation)
            "animation_clip_hint": "focus_type",
        },
        SemanticIntent.BUILDING: {
            "locomotion": "walk",
            "spatial_station": SpatialStation.CODE,
            "posture": 1.0,
            "gaze": 1.3,
            "gesture_rate": 0.8,
            "head_motion": 0.5,
            "orbit_speed": 2.5,
            "particle_energy": 1.0,
            "trail_color": "#F59E0B",  # Gold (artifact synthesis)
            "animation_clip_hint": "construct_flow",
        },
        SemanticIntent.OPERATING_COMPUTER: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.OPERATING,
            "posture": 1.15,
            "gaze": 1.8,
            "gesture_rate": 0.95,
            "head_motion": 0.7,
            "orbit_speed": 2.0,
            "particle_energy": 0.85,
            "trail_color": "#06B6D4",  # Cyan
            "animation_clip_hint": "operate_desktop",
        },
        SemanticIntent.THINKING: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.CENTER,
            "posture": 0.95,
            "gaze": 1.2,
            "gesture_rate": 0.2,
            "head_motion": 0.5,
            "orbit_speed": 1.2,
            "particle_energy": 0.6,
            "trail_color": "#8B5CF6",  # Violet (memory/reasoning)
            "animation_clip_hint": "deep_ponder",
        },
        SemanticIntent.SPEAKING: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.CENTER,
            "posture": 1.05,
            "gaze": 1.0,
            "gesture_rate": 0.7,
            "head_motion": 0.6,
            "orbit_speed": 1.0,
            "particle_energy": 0.5,
            "trail_color": "#F8FAFC",  # White (dialogue)
            "animation_clip_hint": "conversational_expressive",
        },
        SemanticIntent.SUCCESS: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.CENTER,
            "posture": 1.25,
            "gaze": 1.0,
            "gesture_rate": 0.8,
            "head_motion": 0.4,
            "orbit_speed": 3.0,
            "particle_energy": 1.0,
            "trail_color": "#10B981",  # Green (verified)
            "pulse_intensity": 1.0,
            "animation_clip_hint": "celebrate_triumph",
        },
        SemanticIntent.ERROR: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.CENTER,
            "posture": 0.9,
            "gaze": 1.1,
            "gesture_rate": 0.3,
            "head_motion": 0.8,
            "orbit_speed": 0.6,
            "particle_energy": 0.4,
            "trail_color": "#EF4444",  # Red (repair)
            "animation_clip_hint": "recalibrate_repair",
        },
        SemanticIntent.WAITING: {
            "locomotion": "idle",
            "spatial_station": SpatialStation.CENTER,
            "posture": 1.0,
            "gaze": 1.0,
            "gesture_rate": 0.2,
            "head_motion": 0.2,
            "orbit_speed": 0.8,
            "particle_energy": 0.3,
            "trail_color": "#3B82F6",
            "animation_clip_hint": "gentle_idle",
        },
    }

    def __init__(self) -> None:
        self.current_state = HinaSemanticState()
        self.current_profile = self.compile_motion_profile(self.current_state)

    def transition_state(
        self,
        intent: SemanticIntent,
        *,
        active_tool: Optional[str] = None,
        active_agent: Optional[str] = None,
        progress: float = 0.0,
        energy: Optional[float] = None,
        focus: Optional[float] = None,
    ) -> MotionProfile:
        """Transitions the semantic state bus and updates motion telemetry."""
        self.current_state = HinaSemanticState(
            intent=intent,
            active_tool=active_tool,
            active_agent=active_agent,
            progress=progress,
            energy=energy if energy is not None else self.current_state.energy,
            focus=focus if focus is not None else self.current_state.focus,
            timestamp=time.time(),
        )
        self.current_profile = self.compile_motion_profile(self.current_state)
        return self.current_profile

    def compile_motion_profile(self, state: HinaSemanticState) -> MotionProfile:
        policy = self.POLICY_MAP.get(state.intent, self.POLICY_MAP[SemanticIntent.WAITING])
        return MotionProfile(
            locomotion=policy.get("locomotion", "idle"),
            posture=policy.get("posture", 1.0) * state.confidence,
            gaze=policy.get("gaze", 1.0),
            gesture_rate=policy.get("gesture_rate", 0.5) * state.energy,
            head_motion=policy.get("head_motion", 0.3),
            breathing=1.0 + (state.energy * 0.4),
            orbit_speed=policy.get("orbit_speed", 1.0) * (0.8 + 0.4 * state.focus),
            particle_energy=policy.get("particle_energy", 0.5) * state.energy,
            spatial_station=policy.get("spatial_station", SpatialStation.CENTER),
            trail_color=policy.get("trail_color", "#3B82F6"),
            pulse_intensity=policy.get("pulse_intensity", 0.5),
            animation_clip_hint=policy.get("animation_clip_hint", "idle_warm"),
        )


_global_motion_director: Optional[MotionDirector] = None


def get_motion_director() -> MotionDirector:
    global _global_motion_director
    if _global_motion_director is None:
        _global_motion_director = MotionDirector()
    return _global_motion_director
