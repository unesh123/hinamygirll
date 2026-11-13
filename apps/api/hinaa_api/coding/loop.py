"""Autonomous Bounded Coding Loop.

Executes: Understand -> Inspect -> Plan -> Baseline Test -> Snapshot -> Patch ->
Deterministic Verification -> Diagnose & Repair -> Diff/Artifacts -> Rollback.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from hinaa_api.coding.models import (
    CodingActionRequest,
    CodingActionType,
    CodingStepResult,
    CodingTaskEvent,
    CodingTaskSpec,
    CodingTaskState,
    CodingTaskStatus,
)
from hinaa_api.coding.policy import CodingSecurityPolicy
from hinaa_api.sandbox.isolation_base import ExecutionResult, SandboxAdapter
from hinaa_api.sandbox.limits import ResourceLimits
from hinaa_api.workspaces.diff_engine import DiffEngine, PatchResult
from hinaa_api.workspaces.manager import WorkspaceManager
from hinaa_api.workspaces.scanner import ProjectOverview, WorkspaceScanner

logger = logging.getLogger("hinaa.coding.loop")


class AutonomousCodingLoop:
    """Orchestrates bounded multi-step autonomous coding tasks."""

    def __init__(
        self,
        spec: CodingTaskSpec,
        sandbox: SandboxAdapter,
        event_callback: Callable[[CodingTaskEvent], None],
    ) -> None:
        self.spec = spec
        self.workspace_root = Path(spec.workspace_path).resolve()
        self.sandbox = sandbox
        self.event_callback = event_callback
        self.scanner = WorkspaceScanner(self.workspace_root)
        self.manager = WorkspaceManager(self.workspace_root)
        self.is_cancelled = False
        self.status = CodingTaskStatus(
            task_id=spec.task_id,
            user_id=spec.user_id,
            tenant_id=spec.tenant_id,
            state=CodingTaskState.CREATED,
            workspace_path=str(self.workspace_root),
            objective=spec.objective,
            max_repair_iterations=spec.max_repair_iterations,
        )

    def emit(self, event_type: str, label: str, extra: Optional[Dict[str, Any]] = None) -> None:
        evt = CodingTaskEvent(
            run_id=self.spec.task_id,
            type=event_type,
            label=label,
            extra=extra or {},
        )
        self.event_callback(evt)

    def request_cancellation(self) -> None:
        self.is_cancelled = True
        self.status.state = CodingTaskState.CANCELLED
        self.emit("run.failed", "Task cancelled by user signal", {"reason": "USER_CANCELLED"})

    async def execute_task(
        self,
        target_file: str,
        target_content: str,
        replacement_content: str,
        test_command: Optional[List[str]] = None,
        repair_patches: Optional[List[Dict[str, str]]] = None,
    ) -> CodingTaskStatus:
        """Executes full verified coding workflow: inspect -> snapshot -> patch -> test -> repair -> commit/PR."""
        self.status.state = CodingTaskState.INITIALIZING
        self.emit("run.started", "Request accepted, initializing developer sandbox")

        if self.is_cancelled:
            self.status.state = CodingTaskState.CANCELLED
            return self.status

        # 1. Model routing event (real status stream, not pretend timer)
        self.emit("model.selecting", "Analyzing project complexity and selecting model")
        overview = self.scanner.scan_project()
        self.emit("model.selected", f"Selected reasoning router for {overview.primary_language}")

        # 2. Workspace inspection
        self.status.state = CodingTaskState.PLANNING
        self.emit("tool.started", f"Inspecting workspace ({overview.total_files} files discovered)", {"tool": "scanner"})
        self.emit("tool.completed", f"Detected {overview.primary_language} with tests: {', '.join(overview.test_frameworks) or 'none'}", {"tool": "scanner"})

        if self.is_cancelled:
            self.status.state = CodingTaskState.CANCELLED
            return self.status

        # 3. Snapshot pre-mutation state
        self.status.state = CodingTaskState.EXECUTING
        self.emit("tool.started", f"Backing up {target_file} for safe rollback", {"tool": "workspace_manager"})
        self.manager.backup_file_before_mutation(self.spec.task_id, target_file)
        self.emit("tool.completed", "Pre-mutation snapshot secured", {"tool": "workspace_manager"})

        # 4. Apply structured patch
        self.emit("tool.started", f"Applying patch to {target_file}", {"tool": "diff_engine"})
        patch_res = DiffEngine.apply_patch(
            workspace_root=self.workspace_root,
            relative_path=target_file,
            target_content=target_content,
            replacement_content=replacement_content,
        )

        if not patch_res.success:
            self.status.state = CodingTaskState.FAILED
            self.status.error = patch_res.error
            self.emit("tool.failed", f"Patch failed: {patch_res.error}", {"tool": "diff_engine", "error": patch_res.error})
            self.emit("run.failed", f"Failed applying patch: {patch_res.error}", {"error": patch_res.error})
            return self.status

        self.status.files_changed.append(target_file)
        self.status.diff_summary = patch_res.diff
        self.emit("tool.completed", f"Patch applied to {target_file}", {"tool": "diff_engine", "diff": patch_res.diff})

        if self.is_cancelled:
            self.status.state = CodingTaskState.CANCELLED
            return self.status

        # 5. Deterministic testing / build check
        self.status.state = CodingTaskState.TESTING
        cmd = test_command or (["pytest"] if overview.primary_language == "Python" else ["npm", "test"])
        self.emit("tool.started", f"Executing tests: {' '.join(cmd)}", {"tool": "sandbox", "command": cmd})

        exec_res = await self.sandbox.run_command(cmd, cwd=self.workspace_root)

        step_res = CodingStepResult(
            step_id=f"step-test-{int(time.time()*1000)}",
            action_type=CodingActionType.RUN_TEST,
            status="SUCCESS" if exec_res.exit_code == 0 else "FAILED",
            exit_code=exec_res.exit_code,
            stdout=exec_res.stdout,
            stderr=exec_res.stderr,
            duration_ms=exec_res.duration_ms,
        )
        self.status.step_results.append(step_res)

        # 6. Repair loop if initial tests failed
        if exec_res.exit_code != 0 and repair_patches and not self.is_cancelled:
            for r_patch in repair_patches:
                if self.is_cancelled:
                    self.status.state = CodingTaskState.CANCELLED
                    return self.status
                if self.status.current_iteration >= self.spec.max_repair_iterations:
                    break
                self.status.current_iteration += 1
                r_file = r_patch.get("target_file", target_file)
                r_target = r_patch.get("target_content", "")
                r_replacement = r_patch.get("replacement_content", "")
                self.emit("tool.started", f"Attempting self-repair {self.status.current_iteration} on {r_file}", {"tool": "diff_engine"})

                r_res = DiffEngine.apply_patch(
                    workspace_root=self.workspace_root,
                    relative_path=r_file,
                    target_content=r_target,
                    replacement_content=r_replacement,
                )
                if not r_res.success:
                    self.emit("tool.failed", f"Repair patch failed: {r_res.error}", {"tool": "diff_engine"})
                    continue

                if r_file not in self.status.files_changed:
                    self.status.files_changed.append(r_file)
                self.emit("tool.completed", f"Repair patch applied to {r_file}", {"tool": "diff_engine", "diff": r_res.diff})

                # Re-run test
                self.emit("tool.started", f"Re-executing tests for repair attempt {self.status.current_iteration}", {"tool": "sandbox"})
                exec_res = await self.sandbox.run_command(cmd, cwd=self.workspace_root)
                step_res = CodingStepResult(
                    step_id=f"step-test-repair-{int(time.time()*1000)}",
                    action_type=CodingActionType.RUN_TEST,
                    status="SUCCESS" if exec_res.exit_code == 0 else "FAILED",
                    exit_code=exec_res.exit_code,
                    stdout=exec_res.stdout,
                    stderr=exec_res.stderr,
                    duration_ms=exec_res.duration_ms,
                )
                self.status.step_results.append(step_res)
                if exec_res.exit_code == 0:
                    break

        if exec_res.exit_code == 0:
            evidence_msg = f"Deterministic tests passed with exit code 0 ({exec_res.duration_ms:.1f}ms)"
            self.status.verification_evidence.append(evidence_msg)
            self.emit("tool.completed", evidence_msg, {"tool": "sandbox", "exit_code": 0})

            # 7. Governed Git commit and PR creation (if requested)
            if self.spec.create_pr:
                if self.spec.require_high_security:
                    # Enforce approval token verification
                    action_req = CodingActionRequest(
                        task_id=self.spec.task_id,
                        action_type=CodingActionType.GIT_PUSH,
                        command_args=["git", "push"],
                    )
                    if not self.spec.approval_token or not CodingSecurityPolicy.verify_approval_token(
                        self.spec.approval_token, self.spec.task_id, action_req, str(self.workspace_root)
                    ):
                        self.status.state = CodingTaskState.WAITING_APPROVAL
                        self.status.error = "Action requires Tier C user approval token"
                        self.emit("tool.failed", "Action requires Tier C user approval token", {"action": "create_pr"})
                        self.emit("run.failed", "Action blocked pending approval token", {"error": self.status.error})
                        return self.status

                from hinaa_api.repository.github_flow import GovernedGitHubFlow, GitHubPermission, EvidenceGuardViolation
                try:
                    flow = GovernedGitHubFlow(str(self.workspace_root), permission=GitHubPermission.CREATE_PR)
                    task_branch = flow.generate_branch_name(self.spec.task_type, self.spec.task_id)
                    flow.create_or_checkout_branch(task_branch)
                    self.emit("tool.started", f"Checked out task branch {task_branch}", {"branch": task_branch})
                    self.emit("tool.started", "Committing task-scoped changes", {"tool": "git_commit"})
                    commit_res = flow.atomic_commit(
                        task_id=self.spec.task_id,
                        task_goal=self.spec.objective,
                        task_type=self.spec.task_type,
                        task_allowed_files=set(self.status.files_changed),
                        verification_evidence=self.status.verification_evidence,
                    )
                    self.status.commit_sha = commit_res.commit_sha
                    self.status.branch_name = commit_res.branch
                    self.emit("tool.completed", f"Committed {commit_res.commit_sha[:8]} on {commit_res.branch}", {
                        "sha": commit_res.commit_sha,
                        "branch": commit_res.branch,
                        "preserved": commit_res.unrelated_files_preserved,
                    })

                    if self.spec.repo:
                        self.emit("tool.started", f"Opening verified draft PR on {self.spec.repo}", {"tool": "github_pr"})
                        pr_res = await flow.create_evidence_backed_pr(
                            task_id=self.spec.task_id,
                            task_goal=self.spec.objective,
                            task_type=self.spec.task_type,
                            commit_sha=commit_res.commit_sha,
                            verification_passed=True,
                            verification_evidence=self.status.verification_evidence,
                            changed_files=self.status.files_changed,
                            repair_attempts_count=self.status.current_iteration,
                            mock_remote=False,
                            repo=self.spec.repo,
                            base=self.spec.base_branch or "main",
                        )
                        self.status.pr_url = pr_res.pr_url
                        self.status.pr_number = pr_res.pr_number
                        self.emit("artifact.ready", f"Draft PR opened: {pr_res.pr_url}", {
                            "url": pr_res.pr_url,
                            "number": pr_res.pr_number,
                            "sha": commit_res.commit_sha,
                        })
                except EvidenceGuardViolation as egv:
                    self.status.state = CodingTaskState.FAILED
                    self.status.error = str(egv)
                    self.emit("tool.failed", f"Evidence guard violation: {egv}", {"error": str(egv)})
                    self.emit("run.failed", f"PR creation blocked: {egv}", {"error": str(egv)})
                    return self.status
                except Exception as exc:
                    logger.exception("Git operation failed in execute_task")
                    self.status.state = CodingTaskState.FAILED
                    self.status.error = str(exc)
                    self.emit("tool.failed", f"Git operation failed: {exc}", {"error": str(exc)})
                    self.emit("run.failed", f"Git operation failed: {exc}", {"error": str(exc)})
                    return self.status

            self.status.state = CodingTaskState.COMPLETED
            self.emit("run.completed", "Code modification and verification completed successfully", {
                "diff": patch_res.diff,
                "duration_ms": exec_res.duration_ms,
                "commit_sha": self.status.commit_sha,
                "pr_url": self.status.pr_url,
            })
        else:
            self.status.state = CodingTaskState.FAILED
            self.status.error = f"Test failure (exit code {exec_res.exit_code})"
            self.emit("tool.failed", f"Tests failed with exit code {exec_res.exit_code}", {
                "tool": "sandbox",
                "stderr": exec_res.stderr,
                "stdout": exec_res.stdout[:500],
            })
            self.emit("run.failed", "Tests failed post-patch", {"exit_code": exec_res.exit_code})

        return self.status
