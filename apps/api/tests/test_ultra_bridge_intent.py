"""Unit tests for HINAA Ultra bridge tool registration and intent gating."""

from __future__ import annotations

from hinaa_api.tools import load_all_tools, registry
from hinaa_api.tools.intent_gate import sanction_tools


def test_ultra_tools_registered_and_policy_clean() -> None:
    load_all_tools()
    for name in (
        "ultra_file_write",
        "file_list",
        "video_create",
        "record_frames",
        "ffmpeg_export",
        "server_start",
        "shell_run",
        "agent_spawn",
        "browser_screenshot",
        "ultra_memory_save",
        "ultra_memory_get",
    ):
        assert registry.get_tool(name) is not None, f"Missing tool: {name}"
    assert registry.get_tool("shell_run").requires_confirmation is True
    assert registry.get_tool("agent_spawn").requires_confirmation is True
    assert registry.get_tool("ultra_file_write").requires_confirmation is False
    audit = registry.audit_registry()
    assert audit["unmapped_policy"] == []


def test_intent_gate_routes_ultra_commands_accurately() -> None:
    s1 = sanction_tools("write a file called test.txt with the content hello world")
    assert "ultra_file_write" in s1.allowed
    assert s1.parameters["ultra_file_write"] == {"filename": "test.txt", "content": "hello world"}

    s2 = sanction_tools("show files in workspace")
    assert "file_list" in s2.allowed

    s3 = sanction_tools("start a static HTML server serving exports on port 4500")
    assert "server_start" in s3.allowed
    assert s3.parameters["server_start"]["port"] == 4500
    assert s3.parameters["server_start"]["dir_path"] == "exports"

    s4 = sanction_tools("Make a 5 second gold sparkle bridal animation MP4")
    assert "video_create" in s4.allowed
    assert s4.parameters["video_create"]["duration_seconds"] == 5

    s5 = sanction_tools("Run command: echo 'tool bridge working'")
    assert "terminal_hands" in s5.allowed
    assert s5.parameters["terminal_hands"]["command"] == "echo 'tool bridge working'"

    s6 = sanction_tools("ask kira to build a quotes api on port 9001")
    assert "agent_spawn" in s6.allowed
    assert s6.parameters["agent_spawn"]["name"] == "kira"

    # Regression check: bugfix coding request still routes to coding_agent
    s7 = sanction_tools("fix the bug in auth.py")
    assert "coding_agent" in s7.allowed
    assert "ultra_file_write" not in s7.allowed
