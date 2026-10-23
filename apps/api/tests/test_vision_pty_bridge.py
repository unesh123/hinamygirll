"""
Tests for HINAA Real-Time Vision Canvas & Streaming PTY Cross-Interaction Bridge.
"""

import os
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hinaa_api.tools.pty_session import get_pty_manager
from hinaa_api.tools.vision_canvas import get_canvas_engine
from hinaa_api.tools.vision_pty_bridge import vision_pty_cross_interact_handler


@pytest.mark.asyncio
async def test_vision_pty_cross_interaction_flow():
    session_id = f"bridge-test-{int(time.time() * 1000)}"
    pty_mgr = get_pty_manager()

    try:
        echo_cmd = 'Write-Output "CANVAS_BRIDGE_TRIGGER_OK"' if os.name == "nt" else 'echo "CANVAS_BRIDGE_TRIGGER_OK"'
        res = await vision_pty_cross_interact_handler(
            pty_command=echo_cmd,
            session_id=session_id,
            wait_seconds=1.0,
            canvas_action="click",
            canvas_norm_x=0.5,
            canvas_norm_y=0.5,
            verify_visual_change=True,
            sample_color_after=True,
        )

        assert res["success"] is True
        assert res["session_id"] == session_id
        assert "CANVAS_BRIDGE_TRIGGER_OK" in res["pty_output_delta"]
        assert res["canvas_dimensions"][0] > 0
        assert res["canvas_dimensions"][1] > 0
        assert "visual_diff" in res
        assert res["gesture_executed"] is not None
        assert res["gesture_executed"]["action"] == "click"
        assert res["sampled_color"] is not None
        assert "hex" in res["sampled_color"]
    finally:
        pty_mgr.close(session_id)
