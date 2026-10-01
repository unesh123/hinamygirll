"""
Test Suite for HINAA Native Desktop Computer Operator.
"""

import pytest
from hinaa_api.tools.registry import registry
from hinaa_api.tools.computer_operator import NativeComputerOperator, ComputerActionResult


@pytest.mark.asyncio
async def test_computer_operator_tool_registered():
    tool = registry.get_tool("computer_operator")
    assert tool is not None
    assert "action" in tool.required_parameters
    assert tool.risk_level == "medium"
    assert tool.requires_confirmation is False


@pytest.mark.asyncio
async def test_observe_desktop():
    obs = NativeComputerOperator.get_active_window()
    assert obs is not None
    assert isinstance(obs.active_window_title, str)
    assert isinstance(obs.running_apps, list)


@pytest.mark.asyncio
async def test_semantic_media_control_dispatch():
    res = await NativeComputerOperator.media_control("toggle")
    assert isinstance(res, ComputerActionResult)
    assert res.action == "media_control"
    assert res.target == "toggle"
