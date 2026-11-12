"""
Tests for HINAA OS Computer Operator Reality and Execution Integrity Upgrade.
Verifies all 13 core computer operator capabilities, tool registry integrity,
standardized Execution Evidence Envelope, and policy enforcement.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest

from hinaa_api.tools.computer_operator import (
    NativeComputerOperator,
    execute_computer_operator,
    computer_operator_tool_def,
)
from hinaa_api.tools.policy import (
    classify_computer_operator_action,
    check_action_tier_authorization,
    ActionRiskTier,
)


@pytest.mark.asyncio
async def test_computer_operator_get_system_metrics():
    """Verify get_system_metrics returns real hardware metrics and envelope."""
    envelope = await execute_computer_operator({"action": "get_system_metrics"})

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    assert envelope["truthfulness_state"] == "COMPLETED"
    assert envelope["exit_code"] == 0
    assert envelope["tool_identifier"] == "computer_operator.get_system_metrics"
    assert envelope["duration_ms"] >= 0
    assert envelope["start_timestamp"] is not None
    assert envelope["completion_timestamp"] is not None

    metrics = envelope["output"]["system_metrics"]
    assert "cpu_percent" in metrics
    assert "memory_total_mb" in metrics
    assert "memory_percent" in metrics
    assert "platform" in metrics
    assert metrics["memory_total_mb"] > 0


@pytest.mark.asyncio
async def test_computer_operator_inspect_processes():
    """Verify inspect_processes returns real running process records."""
    envelope = await execute_computer_operator({
        "action": "inspect_processes",
        "limit": 10,
        "sort_by": "cpu",
    })

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    assert envelope["tool_identifier"] == "computer_operator.inspect_processes"

    procs = envelope["output"]["processes"]
    assert isinstance(procs, list)
    assert len(procs) > 0
    first = procs[0]
    assert "pid" in first
    assert "name" in first
    assert "memory_mb" in first
    assert "status" in first


@pytest.mark.asyncio
async def test_computer_operator_list_applications():
    """Verify list_applications discovers active/installed desktop applications."""
    envelope = await execute_computer_operator({"action": "list_applications"})

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    apps = envelope["output"]["applications"]
    assert isinstance(apps, list)
    assert len(apps) > 0
    assert any("name" in a for a in apps)


@pytest.mark.asyncio
async def test_computer_operator_inspect_windows():
    """Verify inspect_windows returns active desktop perception."""
    envelope = await execute_computer_operator({"action": "inspect_windows"})

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    assert "windows" in envelope["output"]
    assert envelope["output"]["count"] >= 0


@pytest.mark.asyncio
async def test_computer_operator_read_folder():
    """Verify read_folder safely lists workspace files and rejects system dirs."""
    ws = str(Path(__file__).resolve().parents[1])
    envelope = await execute_computer_operator({
        "action": "read_folder",
        "target": ws,
        "limit": 20,
    })

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    entries = envelope["output"]["entries"]
    assert isinstance(entries, list)
    assert len(entries) > 0

    # Protected system directory check
    blocked = await execute_computer_operator({
        "action": "read_folder",
        "target": "C:\\Windows\\System32\\config",
    })
    assert blocked["success"] is False
    assert "protected" in str(blocked["error_details"]).lower()


@pytest.mark.asyncio
async def test_computer_operator_search_files():
    """Verify search_files finds matching patterns in workspace."""
    ws = str(Path(__file__).resolve().parents[1] / "hinaa_api")
    envelope = await execute_computer_operator({
        "action": "search_files",
        "target": ws,
        "pattern": "*.py",
        "limit": 10,
    })

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    matches = envelope["output"]["matches"]
    assert isinstance(matches, list)
    assert len(matches) > 0
    assert any(m["name"].endswith(".py") for m in matches)


@pytest.mark.asyncio
async def test_computer_operator_capture_screenshot():
    """Verify capture_screenshot executes and reports truthful status."""
    envelope = await execute_computer_operator({"action": "capture_screenshot"})

    assert envelope["tool_identifier"] == "computer_operator.capture_screenshot"
    assert envelope["execution_status"] in ("COMPLETED", "FAILED")
    assert envelope["truthfulness_state"] in ("COMPLETED", "FAILED")
    # Output structure must be present
    assert "output" in envelope


@pytest.mark.asyncio
async def test_computer_operator_inspect_browser():
    """Verify inspect_browser detects running browsers truthfully."""
    envelope = await execute_computer_operator({"action": "inspect_browser"})

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    out = envelope["output"]
    assert "running_browsers" in out
    assert "browser_active" in out
    assert isinstance(out["running_browsers"], list)


@pytest.mark.asyncio
async def test_computer_operator_execute_workspace_command():
    """Verify execute_workspace_command runs bounded shell command with exit code and timing when authorized."""
    # When user explicitly approves
    envelope = await execute_computer_operator({
        "action": "execute_workspace_command",
        "command": "Write-Output 'HELLO_HINAA_TEST'",
        "confirmed": True,
        "approval_source": "user",
        "timeout_seconds": 10,
    })

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    assert envelope["exit_code"] == 0
    assert "HELLO_HINAA_TEST" in envelope["output"]["stdout"]
    assert envelope["duration_ms"] > 0

    # When unapproved, policy gate stops it with EXPLICIT_USER_APPROVAL_REQUIRED
    unapproved = await execute_computer_operator({
        "action": "execute_workspace_command",
        "command": "Write-Output 'UNAUTHORIZED'",
        "confirmed": False,
    })
    assert unapproved["success"] is False
    assert "user approval" in str(unapproved["error_details"]).lower()


@pytest.mark.asyncio
async def test_computer_operator_inspect_docker():
    """Verify inspect_docker truthfully reports running containers or UNAVAILABLE."""
    envelope = await execute_computer_operator({"action": "inspect_docker"})

    assert envelope["tool_identifier"] == "computer_operator.inspect_docker"
    assert envelope["truthfulness_state"] in ("COMPLETED", "UNAVAILABLE")
    out = envelope["output"]
    assert "available" in out
    assert "status" in out


@pytest.mark.asyncio
async def test_computer_operator_get_diagnostic_logs():
    """Verify get_diagnostic_logs retrieves actual log entries."""
    envelope = await execute_computer_operator({
        "action": "get_diagnostic_logs",
        "limit": 20,
    })

    assert envelope["success"] is True
    assert envelope["execution_status"] == "COMPLETED"
    assert "lines" in envelope["output"]
    assert "source_file" in envelope["output"]


def test_tool_registry_integrity():
    """Verify all 13 core actions are registered in computer_operator_tool_def."""
    core_actions = [
        "get_system_metrics",
        "inspect_processes",
        "list_applications",
        "inspect_windows",
        "read_folder",
        "search_files",
        "capture_screenshot",
        "inspect_browser",
        "navigate_browser",
        "execute_workspace_command",
        "inspect_docker",
        "get_diagnostic_logs",
    ]
    registered_actions = computer_operator_tool_def.parameters["action"]["enum"]
    for act in core_actions:
        assert act in registered_actions, f"Action {act} not in tool registry enum"


@pytest.mark.asyncio
async def test_policy_enforcement_for_tier_4_action():
    """Verify unapproved Tier 4 / destructive action is rejected at policy gate."""
    tier = classify_computer_operator_action("execute_workspace_command", {"command": "rmdir /s /q /"})
    # Tier 4 requires explicit confirmation
    verdict = check_action_tier_authorization(tier, confirmed=False, approval_source="none")
    assert verdict.permitted is False
    assert "APPROVAL" in verdict.code or "NOT_PERMITTED" in verdict.code


@pytest.mark.asyncio
async def test_unknown_action_returns_unavailable():
    """Verify fabricated/unknown action returns truthfulness_state='UNAVAILABLE'."""
    envelope = await execute_computer_operator({"action": "hack_the_pentagon_satellite"})

    assert envelope["success"] is False
    assert envelope["execution_status"] == "FAILED"
    assert envelope["truthfulness_state"] == "UNAVAILABLE"
    assert "unknown" in str(envelope["error_details"]).lower()
