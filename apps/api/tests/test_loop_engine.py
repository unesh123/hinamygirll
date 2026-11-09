"""
Unit tests for HINAA OS Loop Engineering Harness (sorrycc 2026 principles).
"""

import sys
import pytest
from pathlib import Path

from hinaa_api.harness.loop_engine import LoopEngine, LoopTaskSpec, LoopExecutionReport


@pytest.mark.asyncio
async def test_loop_engine_already_satisfied(tmp_path):
    engine = LoopEngine(base_dir=tmp_path)
    # python -c "exit(0)" will succeed immediately
    spec = LoopTaskSpec(
        task_id="task_already_done",
        goal_title="Verify baseline success",
        verification_command=[sys.executable, "-c", "import sys; sys.exit(0)"],
    )

    called = False

    async def dummy_agent(turn, receipt):
        nonlocal called
        called = True
        return "repaired"

    report = await engine.run_loop(spec, dummy_agent)
    assert report.status == "COMPLETED"
    assert report.total_turns == 0
    assert not called
    assert len(report.receipts) == 1
    assert report.receipts[0].passed

    # Verify disk files
    state_file = tmp_path / "task_already_done_state.json"
    progress_md = tmp_path / "task_already_done_PROGRESS.md"
    assert state_file.exists()
    assert progress_md.exists()
    assert "Verify baseline success" in progress_md.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_loop_engine_repairs_and_passes(tmp_path):
    engine = LoopEngine(base_dir=tmp_path)
    flag_file = tmp_path / "success.flag"

    # Command tests whether flag_file exists
    check_code = f"import os, sys; sys.exit(0 if os.path.exists(r'{flag_file}') else 1)"
    spec = LoopTaskSpec(
        task_id="task_repair",
        goal_title="Create flag file to pass gate",
        verification_command=[sys.executable, "-c", check_code],
        max_turns=3,
    )

    turn_count = 0

    async def repairing_agent(turn, receipt):
        nonlocal turn_count
        turn_count += 1
        if turn == 1:
            # Create flag file on turn 1
            flag_file.write_text("fixed", encoding="utf-8")
        return "created flag file"

    report = await engine.run_loop(spec, repairing_agent)
    assert report.status == "COMPLETED"
    assert report.total_turns == 1
    assert turn_count == 1
    assert len(report.receipts) == 2  # baseline (fail) + turn 1 (pass)
    assert not report.receipts[0].passed
    assert report.receipts[1].passed


@pytest.mark.asyncio
async def test_loop_engine_stops_on_consecutive_identical_failures(tmp_path):
    engine = LoopEngine(base_dir=tmp_path)
    # Command always fails with the exact same error
    fail_code = "import sys; sys.stderr.write('Exact persistent syntax error\\n'); sys.exit(1)"
    spec = LoopTaskSpec(
        task_id="task_stuck",
        goal_title="Handle stuck agent",
        verification_command=[sys.executable, "-c", fail_code],
        max_turns=10,
        consecutive_failure_limit=2,
    )

    async def stuck_agent(turn, receipt):
        return "tried but failed"

    report = await engine.run_loop(spec, stuck_agent)
    assert report.status == "STOPPED_CONSECUTIVE_FAILURES"
    assert report.total_turns == 2  # turn 1 + turn 2 stuck -> halt
