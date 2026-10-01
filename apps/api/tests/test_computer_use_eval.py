"""
Comprehensive Computer-Use Evaluation Benchmark Suite (10 Real-World Tasks).

Evaluates the HINAA Computer-Use Engine v2 across:
- Perception (Three Eyes: Accessibility, Process/DOM, Vision)
- Primitive Actuators (click, type, hotkey, scroll, open_application)
- Safety Confirmation Gate (Splits draft_message from send_message)
- Bounded Execution Budget & Multi-Step Loops
- Motion Brain Telemetry Event Bus Synchronization
"""

import pytest
from hinaa_api.tools.registry import registry
from hinaa_api.tools.computer_operator import (
    NativeComputerOperator,
    ComputerActionResult,
    ComputerBudget,
    ComputerLoopReport,
    execute_computer_operator,
)
from hinaa_api.harness.motion_brain import get_motion_director, SemanticIntent


@pytest.mark.asyncio
async def test_eval_01_spotify_playback():
    """Test 01: Semantic media control and deep link search on Spotify."""
    res = await NativeComputerOperator.media_control("toggle")
    assert isinstance(res, ComputerActionResult)
    assert res.success is True
    assert res.verified is True
    assert "media" in res.detail.lower()


@pytest.mark.asyncio
async def test_eval_02_browser_navigation():
    """Test 02: Open browser and navigate to target destination."""
    res = await NativeComputerOperator.open_application("https://www.youtube.com")
    assert isinstance(res, ComputerActionResult)
    assert res.success is True
    assert res.verified is True
    assert res.observation is not None


@pytest.mark.asyncio
async def test_eval_03_whatsapp_draft_safety_gate():
    """Test 03: Open chat app and draft message WITHOUT sending (Safety Gate)."""
    res = await NativeComputerOperator.draft_message(
        app_name="whatsapp",
        text="Hey, checking on the deployment status",
        recipient="Team Lead",
    )
    assert isinstance(res, ComputerActionResult)
    assert res.success is True
    assert res.requires_confirmation is True
    assert res.confirmation_token is not None
    assert res.confirmation_token.startswith("tok_")
    assert "awaiting send confirmation" in res.detail.lower()


@pytest.mark.asyncio
async def test_eval_04_message_confirmation_send():
    """Test 04: Authorize and confirm sending message using token."""
    # First draft
    draft_res = await NativeComputerOperator.draft_message(
        app_name="whatsapp",
        text="Confirmed message body",
        recipient="Priya",
    )
    token = draft_res.confirmation_token

    # Second send with token
    send_res = await NativeComputerOperator.send_message(
        app_name="whatsapp",
        text="Confirmed message body",
        recipient="Priya",
        confirmed=True,
        confirmation_token=token,
    )
    assert send_res.success is True
    assert send_res.requires_confirmation is False
    assert "sent message" in send_res.detail.lower()


@pytest.mark.asyncio
async def test_eval_05_primitive_click_and_hotkey():
    """Test 05: Primitive coordinate mouse click and keyboard hotkeys."""
    click_ok = await NativeComputerOperator.click(x=100, y=100, button="left")
    assert click_ok is True

    hotkey_ok = await NativeComputerOperator.press_hotkey("escape")
    assert hotkey_ok is True


@pytest.mark.asyncio
async def test_eval_06_type_text_and_scroll():
    """Test 06: Primitive keyboard text typing and mouse wheel scroll."""
    type_ok = await NativeComputerOperator.type_text("Autonomous Computer Operator", clear_first=False)
    assert type_ok is True

    scroll_ok = await NativeComputerOperator.scroll(direction="down", amount=2)
    assert scroll_ok is True


@pytest.mark.asyncio
async def test_eval_07_three_eyes_perception_observation():
    """Test 07: Three Eyes perception fusing Accessibility, Process, and Display metrics."""
    obs = NativeComputerOperator.observe()
    assert obs is not None
    assert isinstance(obs.active_window_title, str)
    assert isinstance(obs.running_apps, list)
    assert len(obs.ax_elements) > 0
    assert obs.vision.screen_width > 0
    assert obs.vision.screen_height > 0


@pytest.mark.asyncio
async def test_eval_08_multi_step_operator_loop():
    """Test 08: Multi-step perception-action-verification loop."""
    plan = [
        {"action": "click", "x": 50, "y": 50},
        {"action": "press_hotkey", "target": "escape"},
        {"action": "scroll", "direction": "up", "amount": 1},
    ]
    report = await NativeComputerOperator.run_operator_loop(
        goal="Test UI Inspection",
        plan_steps=plan,
        budget=ComputerBudget(max_steps=5, max_wall_time_seconds=10.0),
    )
    assert isinstance(report, ComputerLoopReport)
    assert report.success is True
    assert report.steps_taken == 3
    assert len(report.history) == 3
    assert report.verified is True


@pytest.mark.asyncio
async def test_eval_09_budget_guard_enforcement():
    """Test 09: Bounded budget aborts cleanly when step limit is reached."""
    plan = [
        {"action": "press_hotkey", "target": "escape"},
        {"action": "press_hotkey", "target": "escape"},
        {"action": "press_hotkey", "target": "escape"},
    ]
    # Set max_steps to 2 so 3rd step triggers budget abort
    report = await NativeComputerOperator.run_operator_loop(
        goal="Over-budget test",
        plan_steps=plan,
        budget=ComputerBudget(max_steps=2, max_wall_time_seconds=10.0),
    )
    assert report.steps_taken == 3
    assert report.history[-1].action == "budget_abort"
    assert "budget" in report.history[-1].detail.lower()


@pytest.mark.asyncio
async def test_eval_10_motion_brain_event_bus_synchronization():
    """Test 10: Computer operator actions publish events that drive Motion Brain telemetry."""
    director = get_motion_director()

    # Trigger action event
    NativeComputerOperator.emit_motion_event("computer_action")
    assert director.current_state.intent == SemanticIntent.OPERATING_COMPUTER
    assert director.current_profile.trail_color == "#06B6D4"

    # Trigger verification failure
    NativeComputerOperator.emit_motion_event("verification_failed")
    assert director.current_state.intent == SemanticIntent.ERROR
    assert director.current_profile.trail_color == "#EF4444"

    # Trigger verification success
    NativeComputerOperator.emit_motion_event("verification_success")
    assert director.current_state.intent == SemanticIntent.SUCCESS
    assert director.current_profile.trail_color == "#10B981"

    # Reset to WAITING to prevent cross-test state leakage
    director.transition_state(SemanticIntent.WAITING)
