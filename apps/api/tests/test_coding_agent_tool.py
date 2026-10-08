"""Offline tests for the coding_agent tool.

The LLM is faked at the _llm_text boundary; everything else — patch application,
hash verification, sandbox verification, path escape rejection — runs for real
against a temporary workspace.
"""
from __future__ import annotations

import pytest

from hinaa_api.tools import coding_agent_tool
from hinaa_api.tools.coding_agent_tool import (
    CodingAgentParams,
    _extract_json_object,
    coding_agent_handler,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_backends(monkeypatch):
    monkeypatch.setattr(
        coding_agent_tool, "_configured_code_backends", lambda settings: [{"name": "fake"}]
    )


def _fake_llm(monkeypatch, replies):
    queue = list(replies)

    async def fake(backends, system, user):
        return queue.pop(0), "fake:model"

    monkeypatch.setattr(coding_agent_tool, "_llm_text", fake)


def test_extracts_json_from_fenced_reply():
    raw = 'Sure! Here you go:\n```json\n{"file_path": "a.py", "target_content": "x", "replacement_content": "y"}\n```'
    parsed = _extract_json_object(raw)
    assert parsed["target_content"] == "x"


def test_extracts_json_with_braces_inside_strings():
    raw = '{"full_content": "def f():\\n    return {1: 2}", "summary": "ok"}'
    parsed = _extract_json_object(raw)
    assert "def f():" in parsed["full_content"]


@pytest.mark.asyncio
async def test_no_backend_is_an_honest_error(workspace, monkeypatch):
    monkeypatch.setattr(coding_agent_tool, "_configured_code_backends", lambda settings: [])
    result = await coding_agent_handler(CodingAgentParams(task="fix it", file_path="a.py"))
    assert result["status"] == "error"
    assert result["code"] == "CODING_BRAIN_UNAVAILABLE"


@pytest.mark.asyncio
async def test_path_escape_is_rejected(workspace, fake_backends, monkeypatch):
    _fake_llm(monkeypatch, ['{"full_content": "print(1)"}'])
    result = await coding_agent_handler(
        CodingAgentParams(task="evil", file_path="../../outside.py")
    )
    assert result["status"] == "error"
    assert result["code"] == "WORKSPACE_ESCAPE"


@pytest.mark.asyncio
async def test_creates_new_file_and_verifies_syntax(workspace, fake_backends, monkeypatch):
    _fake_llm(monkeypatch, [
        '{"file_path": "hello.py", "full_content": "def greet():\\n    return \\"hi\\"\\n", "summary": "greeting module"}'
    ])
    result = await coding_agent_handler(
        CodingAgentParams(task="create a greeting module", file_path="hello.py")
    )
    assert result["status"] == "success"
    assert result["mode"] == "create"
    assert (workspace / "hello.py").read_text().startswith("def greet")
    assert any("Verification passed" in e for e in result["evidence"])


@pytest.mark.asyncio
async def test_refuses_to_write_syntax_broken_new_file(workspace, fake_backends, monkeypatch):
    _fake_llm(monkeypatch, ['{"full_content": "def broken(:\\n"}'])
    result = await coding_agent_handler(
        CodingAgentParams(task="create something", file_path="broken.py")
    )
    assert result["status"] == "error"
    assert result["code"] == "SYNTAX_FAILURE"
    assert not (workspace / "broken.py").exists()


@pytest.mark.asyncio
async def test_edit_loop_applies_patch_and_verifies(workspace, fake_backends, monkeypatch):
    target = workspace / "calc.py"
    target.write_text("def add(a, b):\n    return a - b  # BUG: subtracts\n")
    _fake_llm(monkeypatch, [
        '{"file_path": "calc.py", "target_content": "return a - b  # BUG: subtracts", '
        '"replacement_content": "return a + b", "summary": "fix subtraction bug"}'
    ])
    result = await coding_agent_handler(
        CodingAgentParams(task="fix add() so it adds", file_path="calc.py")
    )
    assert result["status"] == "success"
    assert result["mode"] == "edit"
    assert "return a + b" in (workspace / "calc.py").read_text()
    assert "return a - b" in result["diff"]
    assert "+    return a + b" in result["diff"]


@pytest.mark.asyncio
async def test_edit_loop_repairs_after_a_failed_attempt(workspace, fake_backends, monkeypatch):
    target = workspace / "mod.py"
    target.write_text("VALUE = 1\n")
    _fake_llm(monkeypatch, [
        # Attempt 1: target does not exist in the file -> apply fails
        '{"file_path": "mod.py", "target_content": "NONEXISTENT", "replacement_content": "x"}',
        # Attempt 2: correct patch
        '{"file_path": "mod.py", "target_content": "VALUE = 1", "replacement_content": "VALUE = 2"}',
    ])
    result = await coding_agent_handler(
        CodingAgentParams(task="bump VALUE to 2", file_path="mod.py")
    )
    assert result["status"] == "success"
    assert result["attempts"] == 2
    assert (workspace / "mod.py").read_text() == "VALUE = 2\n"


@pytest.mark.asyncio
async def test_empty_target_content_is_refused(workspace, fake_backends, monkeypatch):
    target = workspace / "mod.py"
    target.write_text("VALUE = 1\n")
    _fake_llm(monkeypatch, ['{"file_path": "mod.py", "target_content": "", "replacement_content": "x"}'])
    result = await coding_agent_handler(
        CodingAgentParams(task="change it", file_path="mod.py", max_attempts=1)
    )
    assert result["status"] == "error"
    assert (workspace / "mod.py").read_text() == "VALUE = 1\n"  # untouched
