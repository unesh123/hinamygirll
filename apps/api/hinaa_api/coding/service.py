"""Coding Service: Task orchestration, event streaming, and sandbox management."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hinaa_api.coding.loop import AutonomousCodingLoop
from hinaa_api.coding.models import (
    CodingActionRequest,
    CodingActionType,
    CodingPermissionTier,
    CodingTaskEvent,
    CodingTaskSpec,
    CodingTaskState,
    CodingTaskStatus,
)
from hinaa_api.coding.policy import CodingSecurityPolicy
from hinaa_api.sandbox.isolation_base import IsolationBackendType, SandboxAdapter
from hinaa_api.sandbox.process_adapter import RestrictedProcessAdapter
from hinaa_api.sandbox.runtime_discovery import IsolationHealthReport, RuntimeDiscovery

logger = logging.getLogger("hinaa.coding.service")


class CodingService:
    """Central orchestration service for autonomous coding tasks and sandboxes."""

    def __init__(self, policy: Optional[CodingSecurityPolicy] = None) -> None:
        self.policy = policy or CodingSecurityPolicy()
        self._active_loops: Dict[str, AutonomousCodingLoop] = {}
        self._event_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._event_history: Dict[str, List[CodingTaskEvent]] = {}
        self._artifacts_registry: Dict[str, Dict[str, Any]] = {}

    def get_sandbox_status(self) -> IsolationHealthReport:
        """Returns the current host isolation health report."""
        return RuntimeDiscovery.get_health_report()

    def create_task(self, spec: CodingTaskSpec) -> AutonomousCodingLoop:
        """Initializes a new coding task with appropriate sandbox adapter."""
        workspace = Path(spec.workspace_path).resolve()
        report = self.get_sandbox_status()

        if spec.require_high_security and report.primary_backend not in {
            IsolationBackendType.DOCKER_CONTAINER,
            IsolationBackendType.WSL2_MICROVM,
        }:
            raise PermissionError(
                "High-security container isolation requested, but host currently only supports RESTRICTED_HOST_PROCESS."
            )

        # Initialize adapter
        sandbox = RestrictedProcessAdapter(workspace_root=workspace)

        def event_dispatcher(evt: CodingTaskEvent) -> None:
            if evt.run_id not in self._event_history:
                self._event_history[evt.run_id] = []
            self._event_history[evt.run_id].append(evt)

            subs = self._event_subscribers.get(evt.run_id, set())
            for q in list(subs):
                try:
                    q.put_nowait(evt)
                except Exception:
                    pass

        loop = AutonomousCodingLoop(spec=spec, sandbox=sandbox, event_callback=event_dispatcher)
        self._active_loops[spec.task_id] = loop
        return loop

    def get_task(self, task_id: str) -> Optional[CodingTaskStatus]:
        loop = self._active_loops.get(task_id)
        return loop.status if loop else None

    def subscribe_events(self, task_id: str) -> asyncio.Queue:
        if task_id not in self._event_subscribers:
            self._event_subscribers[task_id] = set()

        q: asyncio.Queue = asyncio.Queue()
        self._event_subscribers[task_id].add(q)

        # Replay past events to subscriber
        past_events = self._event_history.get(task_id, [])
        for evt in past_events:
            q.put_nowait(evt)

        return q

    def unsubscribe_events(self, task_id: str, q: asyncio.Queue) -> None:
        subs = self._event_subscribers.get(task_id)
        if subs and q in subs:
            subs.remove(q)

    def cancel_task(self, task_id: str) -> bool:
        loop = self._active_loops.get(task_id)
        if not loop:
            return False
        loop.request_cancellation()
        return True

    def approve_action(
        self,
        task_id: str,
        action: CodingActionRequest,
        token: str,
    ) -> bool:
        loop = self._active_loops.get(task_id)
        if not loop:
            return False
        return self.policy.verify_approval_token(
            token=token,
            task_id=task_id,
            action=action,
            workspace_path=str(loop.workspace_root),
        )

    def rollback_task(self, task_id: str) -> List[str]:
        loop = self._active_loops.get(task_id)
        if not loop:
            return []
        reverted = loop.manager.rollback(task_id)
        loop.status.state = CodingTaskState.COMPLETED
        loop.emit("run.completed", f"Rollback executed: {', '.join(reverted)}", {"reverted_files": reverted})
        return reverted

    def register_artifact(self, task_id: str, artifact_meta: Dict[str, Any]) -> None:
        if task_id not in self._artifacts_registry:
            self._artifacts_registry[task_id] = {}
        art_id = artifact_meta.get("artifactId") or f"art-{len(self._artifacts_registry[task_id])+1}"
        self._artifacts_registry[task_id][art_id] = artifact_meta

    def list_artifacts(self, task_id: str) -> List[Dict[str, Any]]:
        return list(self._artifacts_registry.get(task_id, {}).values())
