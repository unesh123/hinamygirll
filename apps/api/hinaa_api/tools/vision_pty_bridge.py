"""
Real-Time Vision Canvas & Streaming PTY Cross-Interaction Bridge for HINAA.

Fuses persistent terminal command execution with real-time visual canvas feedback:
- Executes shell / dev / script commands inside an active persistent PTY session.
- Captures pre- and post-execution visual frames from the vision canvas.
- Optionally performs grounded spatial gestures on the canvas (click, stroke, drag, inspect).
- Computes perceptual visual diff to verify that terminal operations caused the intended visual state changes.
- Delivers unified multimodal feedback: terminal log deltas + high-res visual verification in one atomic call.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from .pty_session import get_pty_manager
from .registry import ToolDefinition, registry
from .vision_canvas import compute_visual_diff, get_canvas_engine

logger = logging.getLogger("hinaa.tools.vision_pty_bridge")


async def vision_pty_cross_interact_handler(
    pty_command: str,
    session_id: str = "default",
    wait_seconds: float = 1.5,
    canvas_action: Optional[str] = None,
    canvas_norm_x: Optional[float] = None,
    canvas_norm_y: Optional[float] = None,
    canvas_end_norm_x: Optional[float] = None,
    canvas_end_norm_y: Optional[float] = None,
    verify_visual_change: bool = True,
    sample_color_after: bool = False,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Atomically cross-interact a terminal command with the real-time vision canvas.
    """
    pty_mgr = get_pty_manager()
    canvas_engine = get_canvas_engine()

    # 1. Capture baseline pre-execution canvas frame
    frame_before_info = canvas_engine.capture_frame()
    frame_before_bytes = canvas_engine.last_frame

    # 2. Execute command in persistent PTY session
    pty_session = pty_mgr.get_or_create(session_id=session_id)
    cmd_start_ts = time.time()
    write_ok = pty_session.write(pty_command)

    # Wait for execution and stream delta
    elapsed = 0.0
    poll_step = 0.1
    last_text = ""
    while elapsed < wait_seconds:
        await asyncio.sleep(poll_step)
        elapsed += poll_step
        curr_text = pty_session.read_delta(since_timestamp=cmd_start_ts)
        if curr_text and curr_text == last_text and elapsed >= 0.4:
            break
        last_text = curr_text

    pty_output_delta = pty_session.read_delta(since_timestamp=cmd_start_ts)

    # 3. Optional canvas spatial interaction
    gesture_result = None
    if canvas_action and canvas_norm_x is not None and canvas_norm_y is not None:
        end_coord = (
            (canvas_end_norm_x, canvas_end_norm_y)
            if (canvas_end_norm_x is not None and canvas_end_norm_y is not None)
            else None
        )
        gesture_result = canvas_engine.execute_gesture(
            action=canvas_action,
            start_norm=(canvas_norm_x, canvas_norm_y),
            end_norm=end_coord,
        )

    # 4. Capture post-execution canvas frame
    await asyncio.sleep(0.1)
    frame_after_info = canvas_engine.capture_frame()
    frame_after_bytes = canvas_engine.last_frame

    # 5. Compute perceptual visual diff
    diff_result = (
        compute_visual_diff(frame_before_bytes, frame_after_bytes)
        if verify_visual_change
        else {"diff_detected": False, "verified": False}
    )

    # 6. Sample color if requested
    color_sample = None
    if sample_color_after and canvas_norm_x is not None and canvas_norm_y is not None:
        color_sample = canvas_engine.sample_pixel_color(canvas_norm_x, canvas_norm_y)

    return {
        "success": write_ok,
        "session_id": session_id,
        "pty_command": pty_command,
        "pty_output_delta": pty_output_delta,
        "duration_seconds": round(elapsed, 2),
        "canvas_dimensions": (frame_after_info["width"], frame_after_info["height"]),
        "canvas_preview_uri": frame_after_info["data_uri"],
        "visual_diff": diff_result,
        "gesture_executed": gesture_result,
        "sampled_color": color_sample,
    }


cross_interact_def = ToolDefinition(
    name="vision_pty_cross_interact",
    display_name="Vision Canvas + PTY Cross-Interact",
    description=(
        "Executes a command or code inside a persistent PTY terminal session, waits for execution output, "
        "and immediately cross-interacts with or verifies the real-time visual canvas. "
        "Returns both streaming terminal output and high-resolution visual diff verification."
    ),
    parameters={
        "pty_command": {
            "type": "string",
            "description": "Terminal command, script execution, or input to run in the PTY session",
        },
        "session_id": {
            "type": "string",
            "description": "Persistent terminal session ID (default: 'default')",
        },
        "wait_seconds": {
            "type": "number",
            "description": "Seconds to wait for PTY output and visual repaint (default: 1.5)",
        },
        "canvas_action": {
            "type": "string",
            "description": "Optional canvas gesture to perform after command: 'click', 'stroke', 'drag', 'hover'",
        },
        "canvas_norm_x": {
            "type": "number",
            "description": "Normalized X coordinate [0.0 - 1.0] for canvas gesture or inspection",
        },
        "canvas_norm_y": {
            "type": "number",
            "description": "Normalized Y coordinate [0.0 - 1.0] for canvas gesture or inspection",
        },
        "verify_visual_change": {
            "type": "boolean",
            "description": "If true, calculates perceptual visual diff before and after execution to confirm UI changes",
        },
        "sample_color_after": {
            "type": "boolean",
            "description": "If true, samples the RGBA pixel color at canvas coordinates after execution",
        },
    },
    required_parameters=["pty_command"],
    permission_level="elevated",
    requires_confirmation=False,
    risk_level="high",
    cancellable=True,
    voice_aliases=["cross interact terminal canvas", "pty canvas bridge", "verify terminal on canvas"],
)

registry.register(cross_interact_def, vision_pty_cross_interact_handler)
