"""Tests for Phase 1 bounded workspace coding tools: read, edit, glob, grep."""

from __future__ import annotations

import pytest

from hinaa_api.tools import load_all_tools, registry
from hinaa_api.tools.workspace_coding_tools import (
    WorkspaceEditFileParams,
    WorkspaceGlobParams,
    WorkspaceGrepParams,
    WorkspaceReadFileParams,
    workspace_edit_file_handler,
    workspace_glob_handler,
    workspace_grep_handler,
    workspace_read_file_handler,
)


@pytest.fixture
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    return tmp_path


@pytest.mark.asyncio
async def test_workspace_read_file_line_numbers_hash_and_truncation(ws):
    target = ws / "sample.py"
    target.write_text("\n".join(f"line_{i} = {i}" for i in range(1, 26)) + "\n", encoding="utf-8")

    res = await workspace_read_file_handler(
        WorkspaceReadFileParams(file_path="sample.py", start_line=5, end_line=10)
    )
    assert res["status"] == "success"
    assert res["startLine"] == 5
    assert res["endLine"] == 10
    assert res["totalLines"] == 25
    assert res["truncated"] is True
    assert "showing lines 5-10 of 25" in res["truncationNotice"]
    assert res["content"].startswith("5: line_5 = 5")
    assert "10: line_10 = 10" in res["content"]
    assert len(res["baseHash"]) == 64


@pytest.mark.asyncio
async def test_workspace_read_and_edit_reject_escape(ws):
    r1 = await workspace_read_file_handler(WorkspaceReadFileParams(file_path="../secret.txt"))
    r2 = await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path="../../outside.py",
            target_content="a",
            replacement_content="b",
        )
    )
    assert r1["code"] == "WORKSPACE_ESCAPE"
    assert r2["code"] == "WORKSPACE_ESCAPE"


@pytest.mark.asyncio
async def test_workspace_edit_file_exact_hash_and_syntax_guards(ws):
    target = ws / "app.py"
    target.write_text("def add(x, y):\n    return x - y\n", encoding="utf-8")

    read_res = await workspace_read_file_handler(WorkspaceReadFileParams(file_path="app.py"))
    base_hash = read_res["baseHash"]

    # Stale base hash rejected
    stale = await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path="app.py",
            target_content="return x - y",
            replacement_content="return x + y",
            base_hash="0" * 64,
        )
    )
    assert stale["status"] == "error"
    assert stale["code"] == "CONCURRENT_EDIT"

    # Syntax-broken edit rejected without touching disk
    broken = await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path="app.py",
            target_content="return x - y",
            replacement_content="return x +",
            base_hash=base_hash,
        )
    )
    assert broken["status"] == "error"
    assert "return x - y" in target.read_text(encoding="utf-8")

    # Valid edit returns diff and updates file atomically
    ok = await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path="app.py",
            target_content="return x - y",
            replacement_content="return x + y",
            base_hash=base_hash,
        )
    )
    assert ok["status"] == "success"
    assert "+    return x + y" in ok["diff"]
    assert "return x + y" in target.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_workspace_edit_refuses_ambiguous_snippet(ws):
    target = ws / "dup.py"
    target.write_text("x = 1\ny = 2\nx = 1\n", encoding="utf-8")
    res = await workspace_edit_file_handler(
        WorkspaceEditFileParams(
            file_path="dup.py",
            target_content="x = 1",
            replacement_content="x = 99",
        )
    )
    assert res["status"] == "error"
    assert "Multiple occurrences" in res["error"]


@pytest.mark.asyncio
async def test_workspace_glob_and_grep_skip_vendor_dirs(ws):
    (ws / "src").mkdir()
    (ws / "src" / "main.py").write_text("def hello_world():\n    return 42\n", encoding="utf-8")
    (ws / "node_modules" / "pkg").mkdir(parents=True)
    (ws / "node_modules" / "pkg" / "index.py").write_text("def hello_world():\n    pass\n", encoding="utf-8")
    (ws / "src" / "bin.dat").write_bytes(b"\x00\x01\x02hello_world")

    g = await workspace_glob_handler(WorkspaceGlobParams(pattern="**/*.py"))
    assert g["status"] == "success"
    assert g["files"] == ["src/main.py"]

    s = await workspace_grep_handler(WorkspaceGrepParams(pattern="hello_world"))
    assert s["status"] == "success"
    assert s["count"] == 1
    assert s["matches"][0]["formatted"] == "src/main.py:1: def hello_world():"


def test_workspace_coding_tools_policy_audit():
    load_all_tools()
    audit = registry.audit_registry()
    assert audit["unmapped_policy"] == []
    for tool_name in ("workspace_read_file", "workspace_edit_file", "workspace_glob", "workspace_grep"):
        assert registry.get_tool(tool_name) is not None
