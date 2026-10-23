"""
Tests for HINAA Persistent Bidirectional Streaming PTY Session Manager.
"""

import os
import sys
import time
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hinaa_api.tools.pty_session import (
    PTYSessionManager,
    get_pty_manager,
    strip_ansi,
    pty_session_run_handler,
    pty_session_interact_handler,
)


def test_strip_ansi():
    raw = "\x1b[31mRed text\x1b[0m and \x1b[1;34mBold Blue\x1b[0m"
    cleaned = strip_ansi(raw)
    assert cleaned == "Red text and Bold Blue"


@pytest.mark.asyncio
async def test_pty_session_run_basic_command(tmp_path):
    mgr = get_pty_manager()
    session_id = f"test-session-{int(time.time() * 1000)}"

    try:
        session = mgr.get_or_create(session_id=session_id, cwd=tmp_path)
        assert session.is_alive
        assert session.session_id == session_id

        # Write echo command
        echo_cmd = 'echo "HINAA_PTY_STREAM_OK"' if os.name != "nt" else 'Write-Output "HINAA_PTY_STREAM_OK"'
        res = await pty_session_run_handler(
            command=echo_cmd,
            session_id=session_id,
            wait_seconds=1.5,
            cwd=str(tmp_path),
        )

        assert res["success"] is True
        assert res["session_id"] == session_id
        assert "HINAA_PTY_STREAM_OK" in res["output"]
    finally:
        mgr.close(session_id)


@pytest.mark.asyncio
async def test_pty_session_interactive_flow(tmp_path):
    mgr = get_pty_manager()
    session_id = f"test-interactive-{int(time.time() * 1000)}"

    try:
        session = mgr.get_or_create(session_id=session_id, cwd=tmp_path)
        # Test interact handler with a command
        res = await pty_session_interact_handler(
            session_id=session_id,
            input_text='Write-Output "INTERACTIVE_PING"' if os.name == "nt" else 'echo "INTERACTIVE_PING"',
            wait_seconds=1.0,
        )
        assert res["success"] is True
        assert "INTERACTIVE_PING" in res["output"]
    finally:
        mgr.close(session_id)


def test_pty_session_lifecycle_and_listing(tmp_path):
    mgr = PTYSessionManager()
    sid_a = f"life-a-{int(time.time() * 1000)}"
    sid_b = f"life-b-{int(time.time() * 1000)}"

    try:
        s_a = mgr.get_or_create(sid_a, cwd=tmp_path)
        s_b = mgr.get_or_create(sid_b, cwd=tmp_path)
        sessions = mgr.list_sessions()
        ids = [s["session_id"] for s in sessions]
        assert sid_a in ids
        assert sid_b in ids

        assert mgr.close(sid_a) is True
        sessions_after = mgr.list_sessions()
        ids_after = [s["session_id"] for s in sessions_after]
        assert sid_a not in ids_after
        assert sid_b in ids_after
    finally:
        mgr.close_all()
