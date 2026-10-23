"""
Tests for HINAA Real-Time Vision Canvas & Spatial Grounding Engine.
"""

import io
import sys
import pytest
from pathlib import Path
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hinaa_api.tools.vision_canvas import (
    VisionCanvasEngine,
    compute_visual_diff,
    vision_canvas_inspect_handler,
    vision_canvas_interact_handler,
)


def _create_mock_image(color=(255, 0, 0), text: str = "Test Canvas") -> bytes:
    img = Image.new("RGB", (400, 300), color=color)
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), text, fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_visual_diff_computation():
    img_a = _create_mock_image((255, 0, 0), "Frame A")
    img_b = _create_mock_image((255, 0, 0), "Frame A")
    img_c = _create_mock_image((0, 0, 255), "Frame B")

    # Identical frames
    diff_same = compute_visual_diff(img_a, img_b)
    assert diff_same["diff_detected"] is False
    assert diff_same["diff_ratio"] == 0.0

    # Differing frames
    diff_diff = compute_visual_diff(img_a, img_c)
    assert diff_diff["diff_detected"] is True
    assert diff_diff["diff_ratio"] > 0.5


def test_coordinate_grounding():
    engine = VisionCanvasEngine()
    engine.last_dimensions = (1920, 1080)

    # Center
    cx, cy = engine.ground_coordinates(0.5, 0.5)
    assert cx == 960
    assert cy == 540

    # Top-left corner
    tx, ty = engine.ground_coordinates(0.0, 0.0)
    assert tx == 0
    assert ty == 0

    # Bottom-right corner with clamping
    bx, by = engine.ground_coordinates(1.5, -0.5)
    assert bx == 1920
    assert by == 0


def test_sample_pixel_color():
    engine = VisionCanvasEngine()
    # Mock red canvas
    engine.last_frame = _create_mock_image((200, 50, 50), "Red Box")
    engine.last_dimensions = (400, 300)

    sample = engine.sample_pixel_color(0.5, 0.5)
    assert "hex" in sample
    assert "rgb" in sample
    # Should sample near red
    r, g, b = sample["rgb"]
    assert r > 150
    assert g < 100


def test_gesture_execution_trajectory():
    engine = VisionCanvasEngine()
    engine.last_frame = _create_mock_image((30, 30, 40), "Trajectory Test")
    engine.last_dimensions = (800, 600)

    res = engine.execute_gesture(
        action="stroke",
        start_norm=(0.1, 0.1),
        end_norm=(0.9, 0.9),
        steps=5,
    )

    assert res["success"] is True
    assert res["action"] == "stroke"
    assert res["start_pixel"] == (80, 60)
    assert res["end_pixel"] == (720, 540)
    assert res["steps_count"] >= 5


@pytest.mark.asyncio
async def test_vision_canvas_tool_handlers():
    # Test inspection handler
    inspect_res = await vision_canvas_inspect_handler(sample_norm_x=0.5, sample_norm_y=0.5)
    assert inspect_res["success"] is True
    assert inspect_res["width"] > 0
    assert inspect_res["height"] > 0

    # Test interaction handler
    interact_res = await vision_canvas_interact_handler(
        action="click",
        norm_x=0.2,
        norm_y=0.3,
    )
    assert interact_res["success"] is True
    assert interact_res["action"] == "click"
