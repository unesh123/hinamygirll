"""Unified Browser Automation and Web Operations Service.

Orchestrates runtime, session isolation, policy gates, planning, action execution,
SSE streaming, and integrations with Agency Engine, CRAG, and Tool Registry.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .action_schema import (
    BrowserActionRequest,
    BrowserActionResult,
    BrowserActionType,
    BrowserTaskApprovalRequest,
    BrowserTaskEvent,
    BrowserTaskSpec,
    BrowserTaskState,
    PermissionTier,
)
from .evidence import EvidenceCollector
from .executor import ActionExecutor
from .extraction import PageExtractor
from .file_transfer import FileTransferManager
from .navigation import NavigationHandler
from .planner import BrowserTaskPlanner
from .policy import BrowserSecurityPolicy
from .runtime import BrowserRuntimeManager
from .session_manager import BrowserSession, BrowserSessionManager

logger = logging.getLogger("hinaa.browser.service")


class BrowserAutomationService:
    """Enterprise-grade service managing browser tasks, permissions, and tool execution."""

    def __init__(
        self,
        runtime: Optional[BrowserRuntimeManager] = None,
        policy: Optional[BrowserSecurityPolicy] = None,
        artifacts_dir: Optional[Path] = None,
        downloads_dir: Optional[Path] = None,
    ) -> None:
        self.runtime = runtime or BrowserRuntimeManager()
        self.policy = policy or BrowserSecurityPolicy()
        self.session_manager = BrowserSessionManager(self.runtime)
        self.evidence = EvidenceCollector(artifacts_dir=artifacts_dir)
        self.files = FileTransferManager(downloads_dir=downloads_dir)
        self.navigation = NavigationHandler(self.policy)
        self.executor = ActionExecutor(
            self.policy,
            evidence_collector=self.evidence,
            file_transfer_manager=self.files,
        )
        self.planner = BrowserTaskPlanner()
        self._task_results: Dict[str, List[BrowserActionResult]] = {}

    async def create_task(self, spec: BrowserTaskSpec) -> BrowserSession:
        """Creates a new isolated browser task and session."""
        session = await self.session_manager.create_session(spec)
        self._task_results[spec.task_id] = []
        return session

    def get_task(self, task_id: str) -> Optional[BrowserSession]:
        return self.session_manager.get_session(task_id)

    async def execute_action(
        self, task_id: str, request: BrowserActionRequest
    ) -> BrowserActionResult:
        """Executes a single action in the context of an active session."""
        session = self.get_task(task_id)
        if not session:
            raise ValueError(f"Task '{task_id}' not found or session closed")

        if request.action_type == BrowserActionType.OPEN and request.url:
            res = await self.navigation.navigate(session, request.url, timeout_ms=request.timeout_ms)
        else:
            res = await self.executor.execute(session, request)

        if task_id in self._task_results:
            self._task_results[task_id].append(res)

        return res

    async def run_task_plan(
        self, task_id: str, plan: List[BrowserActionRequest]
    ) -> List[BrowserActionResult]:
        """Runs a sequential plan, stopping immediately on failure or approval requirement."""
        session = self.get_task(task_id)
        if not session:
            raise ValueError(f"Task '{task_id}' not found or session closed")

        results: List[BrowserActionResult] = []
        session.emit_event(f"Beginning execution of {len(plan)}-step plan", state=BrowserTaskState.RUNNING)

        for step_idx, action_req in enumerate(plan):
            if session.is_cancelled:
                session.emit_event("Task cancelled before step execution", state=BrowserTaskState.CANCELLED)
                break

            session.emit_event(
                f"Executing step {step_idx + 1}/{len(plan)}: {action_req.action_type.value}",
                observed_url=session.current_page.url if session.pages else None,
            )

            res = await self.execute_action(task_id, action_req)
            results.append(res)

            # If Tier C approval is demanded, pause and surface request
            if res.status == "APPROVAL_REQUIRED":
                current_url = session.current_page.url
                approval_id = f"appr-{uuid4().hex[:8]}"
                token = self.policy.generate_approval_token(task_id, action_req, current_url)
                
                approval_req = BrowserTaskApprovalRequest(
                    approval_id=approval_id,
                    task_id=task_id,
                    action_type=action_req.action_type,
                    target_origin=current_url.split("/")[2] if "://" in current_url else current_url,
                    destination_url=current_url,
                    summary=f"Approval needed for {action_req.action_type.value} on {current_url}",
                    proposed_payload={"action_id": action_req.action_id, "token": token},
                )
                session.pending_approval = approval_req
                session.emit_event(
                    f"Task paused: {approval_req.summary}",
                    state=BrowserTaskState.WAITING_FOR_USER,
                )
                break

            if res.status != "SUCCESS":
                session.emit_event(
                    f"Step {step_idx + 1} failed: {res.failure_message or res.failure_code}",
                    state=BrowserTaskState.FAILED,
                )
                break

        # Check final task state
        if all(r.status == "SUCCESS" for r in results) and len(results) == len(plan):
            session.emit_event("All planned steps executed successfully", state=BrowserTaskState.COMPLETED)

        return results

    async def approve_and_resume(
        self,
        task_id: str,
        approval_id: str,
        token: str,
        action_request: BrowserActionRequest,
    ) -> BrowserActionResult:
        """Processes human approval for a paused Tier C action and resumes execution."""
        session = self.get_task(task_id)
        if not session:
            raise ValueError(f"Task '{task_id}' not found")

        if not session.pending_approval or session.pending_approval.approval_id != approval_id:
            raise ValueError("No matching pending approval found for this task")

        action_request.user_approved = True
        action_request.approval_token = token
        session.pending_approval = None
        session.emit_event("Human approval verified; resuming execution", state=BrowserTaskState.RUNNING)

        res = await self.execute_action(task_id, action_request)
        if res.status == "SUCCESS":
            session.emit_event("Approved action completed successfully", state=BrowserTaskState.COMPLETED)
        else:
            session.emit_event(f"Approved action failed: {res.failure_message}", state=BrowserTaskState.FAILED)
        return res

    async def cancel_task(self, task_id: str) -> bool:
        """Signals cancellation to an active session."""
        session = self.get_task(task_id)
        if session:
            session.request_cancellation()
            await self.session_manager.close_session(task_id)
            return True
        return False

    def get_task_artifacts(self, task_id: str) -> List[Dict[str, Any]]:
        """Returns collected artifacts (screenshots, downloads) for a given task."""
        artifacts: List[Dict[str, Any]] = []

        # Check screenshots
        shot_dir = self.evidence.artifacts_dir / task_id
        if shot_dir.exists():
            for p in shot_dir.glob("*.png"):
                artifacts.append({
                    "kind": "screenshot",
                    "filename": p.name,
                    "filepath": str(p.resolve()),
                    "size_bytes": p.stat().st_size,
                })

        # Check downloads
        down_dir = self.files.downloads_dir / task_id
        if down_dir.exists():
            for p in down_dir.glob("*"):
                if p.is_file():
                    artifacts.append({
                        "kind": "download",
                        "filename": p.name,
                        "filepath": str(p.resolve()),
                        "size_bytes": p.stat().st_size,
                    })

        return artifacts

    async def shutdown(self) -> None:
        """Shuts down all active sessions and browser runtime processes."""
        await self.session_manager.close_all()
        await self.runtime.shutdown()
