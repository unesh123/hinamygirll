"""
Test Suite for HINAA Motion Brain and Semantic State Bus.
"""

import pytest
from hinaa_api.harness import (
    HinaSemanticState,
    MotionDirector,
    MotionProfile,
    SemanticIntent,
    SpatialStation,
    get_motion_director,
)


def test_motion_director_initialization():
    global_dir = get_motion_director()
    assert global_dir is not None
    director = MotionDirector()
    assert director is not None
    assert director.current_state.intent in (SemanticIntent.WAITING, SemanticIntent.THINKING)
    assert director.current_profile.locomotion in ("idle", "walk")


def test_motion_transition_researching():
    director = MotionDirector()
    profile = director.transition_state(
        SemanticIntent.RESEARCHING,
        active_tool="agent_reach",
        active_agent="web-researcher",
        progress=0.45,
        energy=0.85,
    )
    assert profile.spatial_station == SpatialStation.RESEARCH
    assert profile.locomotion == "walk"
    assert profile.trail_color == "#06B6D4"  # Cyan for tool/research
    assert profile.orbit_speed > 1.5


def test_motion_transition_coding():
    director = MotionDirector()
    profile = director.transition_state(
        SemanticIntent.CODING,
        active_agent="lead-coder",
        progress=0.8,
    )
    assert profile.spatial_station == SpatialStation.CODE
    assert profile.trail_color == "#3B82F6"  # Blue for computation
    assert profile.gesture_rate > 0.4


def test_motion_transition_success():
    director = MotionDirector()
    profile = director.transition_state(SemanticIntent.SUCCESS)
    assert profile.trail_color == "#10B981"  # Green
    assert profile.pulse_intensity == 1.0
    assert profile.animation_clip_hint == "celebrate_triumph"
