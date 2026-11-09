"""
HINAA OS — Loop Engineering Harness (sorrycc / 2026 Autonomous Agent Best Practice).

Implements the 3 Iron Rules of Loop Engineering:
1. "上限看模型，下限看架构" (Upper bound is model, lower bound is harness architecture).
2. "Done 是声明，不是证明" ("Done is a claim, not proof"). Objective hard gate is sole arbiter.
3. "Agent 会忘，repo 不会" (The Agent forgets, the repo remembers). State & ledger must be written to disk.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from ..runtime_paths import project_root

logger = logging.getLogger("hinaa.harness.loop_engine")


class EvidenceReceipt(BaseModel):
    """Immutable proof receipt from an objective execution gate."""
    receipt_id: str
    turn_index: int
    command: str
    exit_code: int
    stdout_snippet: str = ""
    stderr_snippet: str = ""
    duration_ms: float = 0.0
    files_changed: List[str] = Field(default_factory=list)
    timestamp_utc: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    passed: bool = False


class LoopTaskSpec(BaseModel):
    """Specification for an autonomous unattended loop."""
    task_id: str
    goal_title: str
    description: str = ""
    verification_command: List[str]
    target_files: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    max_turns: int = 10
    consecutive_failure_limit: int = 3
    pre_script: Optional[List[str]] = None
    post_script: Optional[List[str]] = None
    timeout_per_turn_seconds: float = 60.0
    workspace_dir: Optional[str] = None


class LoopExecutionReport(BaseModel):
    """Summary of a completed or stopped autonomous loop execution."""
    task_id: str
    status: str  # COMPLETED | FAILED | STOPPED_MAX_TURNS | STOPPED_CONSECUTIVE_FAILURES | BLOCKED
    total_turns: int = 0
    receipts: List[EvidenceReceipt] = Field(default_factory=list)
    summary: str = ""
    state_file_path: Optional[str] = None
    duration_seconds: float = 0.0


class LoopEngine:
    """
    Autonomous Loop Engine that continuously executes, verifies via objective gates,
    and updates progress ledgers on disk until the hard gate succeeds or budget halts.
    """

    def __init__(self, base_dir: Optional[Path | str] = None) -> None:
        if base_dir is None:
            self.base_dir = project_root() / ".runtime" / "loop_state"
        else:
            self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _get_git_changed_files(self, cwd: Path) -> List[str]:
        """Collect current uncommitted git changes."""
        try:
            res = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=5.0,
            )
            if res.returncode == 0:
                lines = [line.strip().split(None, 1)[-1] for line in res.stdout.strip().splitlines() if line.strip()]
                return lines
        except Exception:
            pass
        return []

    def _write_ledger_disk(self, spec: LoopTaskSpec, receipts: List[EvidenceReceipt], status: str) -> Path:
        """Write structured STATE.json and markdown PROGRESS.md to disk for cross-session survival."""
        state_file = self.base_dir / f"{spec.task_id}_state.json"
        progress_md = self.base_dir / f"{spec.task_id}_PROGRESS.md"

        data = {
            "task_id": spec.task_id,
            "goal_title": spec.goal_title,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "verification_command": spec.verification_command,
            "receipts": [r.model_dump() for r in receipts],
        }
        state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

        # Markdown ledger (sorrycc's progress ledger design: Current Goal / Completed / Changed Files / Decisions / Next)
        md_lines = [
            f"# Loop Progress Ledger: {spec.goal_title}",
            f"- **Task ID**: `{spec.task_id}`",
            f"- **Status**: `{status}`",
            f"- **Updated**: `{datetime.now(timezone.utc).isoformat()}`",
            "",
            "## Verification Receipts",
            "| Turn | Command | Exit Code | Passed | Duration (ms) |",
            "| :---: | :--- | :---: | :---: | :---: |",
        ]
        for r in receipts:
            mark = "PASS" if r.passed else "FAIL"
            cmd_str = r.command[:50] + ("..." if len(r.command) > 50 else "")
            md_lines.append(f"| {r.turn_index} | `{cmd_str}` | {r.exit_code} | **{mark}** | {r.duration_ms:.1f} |")

        if receipts and not receipts[-1].passed:
            last = receipts[-1]
            md_lines.extend([
                "",
                "## Last Failure Evidence",
                "```",
                (last.stderr_snippet or last.stdout_snippet or "No output")[:1000],
                "```"
            ])

        progress_md.write_text("\n".join(md_lines), encoding="utf-8")
        return state_file

    def execute_hard_gate(
        self,
        command: List[str],
        cwd: Path,
        turn_index: int,
        timeout: float = 30.0,
    ) -> EvidenceReceipt:
        """
        Executes the objective hard gate command directly as a subprocess.
        'Done 是声明，不是证明' — exit code 0 is required.
        """
        start = time.perf_counter()
        cmd_str = " ".join(command)
        receipt_id = hashlib.sha256(f"{turn_index}:{cmd_str}:{time.time()}".encode()).hexdigest()[:12]

        try:
            proc = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            duration_ms = (time.perf_counter() - start) * 1000.0
            files_changed = self._get_git_changed_files(cwd)
            passed = proc.returncode == 0

            return EvidenceReceipt(
                receipt_id=receipt_id,
                turn_index=turn_index,
                command=cmd_str,
                exit_code=proc.returncode,
                stdout_snippet=proc.stdout[-2000:] if proc.stdout else "",
                stderr_snippet=proc.stderr[-2000:] if proc.stderr else "",
                duration_ms=duration_ms,
                files_changed=files_changed,
                passed=passed,
            )
        except subprocess.TimeoutExpired as te:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return EvidenceReceipt(
                receipt_id=receipt_id,
                turn_index=turn_index,
                command=cmd_str,
                exit_code=124,
                stderr_snippet=f"Gate execution timed out after {timeout} seconds",
                duration_ms=duration_ms,
                passed=False,
            )
        except Exception as ex:
            duration_ms = (time.perf_counter() - start) * 1000.0
            return EvidenceReceipt(
                receipt_id=receipt_id,
                turn_index=turn_index,
                command=cmd_str,
                exit_code=1,
                stderr_snippet=f"Execution error: {str(ex)}",
                duration_ms=duration_ms,
                passed=False,
            )

    async def run_loop(
        self,
        spec: LoopTaskSpec,
        agent_step: Callable[[int, Optional[EvidenceReceipt]], Awaitable[str]],
    ) -> LoopExecutionReport:
        """
        Runs the unattended autonomous loop until objective hard gate passes or budget halts.
        """
        start_time = time.time()
        cwd = Path(spec.workspace_dir) if spec.workspace_dir else project_root()
        receipts: List[EvidenceReceipt] = []

        logger.info("Starting autonomous loop for task '%s': %s", spec.task_id, spec.goal_title)

        # Run pre-script if defined
        if spec.pre_script:
            try:
                subprocess.run(spec.pre_script, cwd=str(cwd), capture_output=True, timeout=30.0)
            except Exception as e:
                logger.warning("Pre-script failed for task %s: %s", spec.task_id, e)

        # Initial baseline gate verification (non-blocking in threadpool)
        initial_receipt = await asyncio.to_thread(self.execute_hard_gate, spec.verification_command, cwd, 0)
        receipts.append(initial_receipt)
        await asyncio.to_thread(self._write_ledger_disk, spec, receipts, "IN_PROGRESS")

        if initial_receipt.passed:
            logger.info("Task '%s' already satisfies hard gate at turn 0", spec.task_id)
            state_file = await asyncio.to_thread(self._write_ledger_disk, spec, receipts, "COMPLETED")
            return LoopExecutionReport(
                task_id=spec.task_id,
                status="COMPLETED",
                total_turns=0,
                receipts=receipts,
                summary=f"Goal '{spec.goal_title}' was already satisfied on baseline verification.",
                state_file_path=str(state_file),
                duration_seconds=time.time() - start_time,
            )

        # Loop iterations
        last_failure_receipt: Optional[EvidenceReceipt] = initial_receipt
        consecutive_same_errors = 0
        last_error_signature = ""

        status = "FAILED"
        for turn in range(1, spec.max_turns + 1):
            logger.info("Executing Loop Task '%s' — Turn %d/%d", spec.task_id, turn, spec.max_turns)

            # 1. Agent execution step (receives last failure evidence to repair)
            try:
                agent_summary = await agent_step(turn, last_failure_receipt)
            except Exception as ex:
                logger.error("Agent step failed on turn %d: %s", turn, ex)
                agent_summary = f"Agent execution raised error: {ex}"

            # 2. Objective Hard Gate verification (non-blocking in threadpool)
            receipt = await asyncio.to_thread(
                self.execute_hard_gate,
                spec.verification_command,
                cwd,
                turn,
                spec.timeout_per_turn_seconds,
            )
            receipts.append(receipt)

            # Check if passed
            if receipt.passed:
                status = "COMPLETED"
                logger.info("Objective hard gate PASSED at turn %d for task '%s'", turn, spec.task_id)

                # Run post-script if provided (e.g. git commit)
                if spec.post_script:
                    try:
                        subprocess.run(spec.post_script, cwd=str(cwd), capture_output=True, timeout=30.0)
                    except Exception as e:
                        logger.warning("Post-script failed: %s", e)

                state_file = await asyncio.to_thread(self._write_ledger_disk, spec, receipts, status)
                return LoopExecutionReport(
                    task_id=spec.task_id,
                    status=status,
                    total_turns=turn,
                    receipts=receipts,
                    summary=f"Successfully completed '{spec.goal_title}' at turn {turn} with verifiable exit code 0.",
                    state_file_path=str(state_file),
                    duration_seconds=time.time() - start_time,
                )

            # Consecutive failure detector (sorrycc rule: 连续同一错误即停)
            error_sig = (receipt.stderr_snippet or receipt.stdout_snippet or "")[:200]
            if error_sig and error_sig == last_error_signature:
                consecutive_same_errors += 1
            else:
                consecutive_same_errors = 1
                last_error_signature = error_sig

            if consecutive_same_errors >= spec.consecutive_failure_limit:
                status = "STOPPED_CONSECUTIVE_FAILURES"
                logger.warning(
                    "Halting loop task '%s': encountered identical failure %d consecutive times.",
                    spec.task_id,
                    consecutive_same_errors,
                )
                break

            last_failure_receipt = receipt
            await asyncio.to_thread(self._write_ledger_disk, spec, receipts, "IN_PROGRESS")

        if status != "COMPLETED" and status != "STOPPED_CONSECUTIVE_FAILURES":
            status = "STOPPED_MAX_TURNS"

        state_file = await asyncio.to_thread(self._write_ledger_disk, spec, receipts, status)
        return LoopExecutionReport(
            task_id=spec.task_id,
            status=status,
            total_turns=len(receipts) - 1,
            receipts=receipts,
            summary=f"Loop halted with status '{status}' after {len(receipts) - 1} turns.",
            state_file_path=str(state_file),
            duration_seconds=time.time() - start_time,
        )
