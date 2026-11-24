"""
Test suite for Frontier Cinematic Kinetic Reel Engine.
Verifies frame generation, 3D chrome sphere procedural shading,
screen-filling typography, and genuine FFmpeg MP4 export.
"""

import shutil
from pathlib import Path
import numpy as np
import pytest
from PIL import Image

from hinaa_api.creative.kinetic_engine import (
    KineticMotionRenderer,
    KineticReelCompiler,
    KineticReelSpec,
    KineticSceneSpec,
)


def test_kinetic_frame_rendering_1080x1920():
    """Verify high-resolution 1080x1920 frame rendering with chrome sphere and typography."""
    renderer = KineticMotionRenderer()
    scene = KineticSceneSpec(
        headline="TOTAL SYSTEM MASTERY",
        subhead="Autonomous agentic execution kernel with zero latency.",
        kicker="HINA / PRODUCTION",
        duration=3.0,
        accent_color="#00f0ff",
        camera_motion="dolly_in",
    )

    frame = renderer.render_frame(
        scene=scene,
        local_time=1.2,
        width=1080,
        height=1920,
        is_transitioning=False,
    )

    assert frame.size == (1080, 1920)
    assert frame.mode == "RGB"

    # Verify that frame is not blank or uniform
    extrema = frame.getextrema()
    # Check that channels have broad dynamic range
    for ch_min, ch_max in extrema:
        assert ch_max > 200, "Frame must contain bright highlight elements"
        assert ch_min < 50, "Frame must contain deep contrast background"


def test_chromatic_aberration_transition_pass():
    """Verify chromatic split occurs during scene transitions."""
    renderer = KineticMotionRenderer()
    scene = KineticSceneSpec(
        headline="THE FUTURE IS AUTONOMOUS",
        subhead="Continuous neural deliberation.",
        accent_color="#a855f7",
    )

    normal_frame = renderer.render_frame(scene, 1.0, 540, 960, is_transitioning=False)
    transition_frame = renderer.render_frame(
        scene, 1.0, 540, 960, is_transitioning=True, transition_progress=1.0
    )

    assert normal_frame.size == transition_frame.size
    # Pixels must differ between normal and chromatic transition
    arr_normal = np.array(normal_frame)
    arr_trans = np.array(transition_frame)
    diff = np.abs(arr_trans.astype(int) - arr_normal.astype(int))
    assert np.max(diff) > 0, "Transition must apply chromatic shift"


def test_full_reel_ffmpeg_compilation(tmp_path):
    """Verify end-to-end MP4 video generation via FFmpeg."""
    compiler = KineticReelCompiler()
    if not shutil.which("ffmpeg"):
        pytest.skip("FFmpeg not installed on host machine.")

    spec = KineticReelSpec(
        title="Hina Kinetic Reel Test",
        scenes=[
            KineticSceneSpec(
                headline="TOTAL SYSTEM MASTERY",
                subhead="Autonomous kernel active.",
                duration=1.0,  # 1 second for fast test
                accent_color="#00f0ff",
            ),
            KineticSceneSpec(
                headline="THE FUTURE IS AUTONOMOUS",
                subhead="Deep learning deliberation.",
                duration=1.0,
                accent_color="#ff0055",
            ),
        ],
        width=540,
        height=960,
        fps=24,
    )

    out_file = tmp_path / "test_reel.mp4"
    result_path = compiler.render_reel(spec, out_file)

    assert result_path.exists()
    assert result_path.stat().st_size > 50_000, "Generated video must be non-empty MP4"
