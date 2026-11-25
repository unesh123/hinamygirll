"""Coding Service: Durable task orchestration, event streaming, and sandbox management."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from hinaa_api.coding.loop import AutonomousCodingLoop
from hinaa_api.coding.models import (
    CodingActionRequest,
    CodingTaskEvent,
    CodingTaskSpec,
    CodingTaskState,
    CodingTaskStatus,
)
from hinaa_api.coding.policy import CodingSecurityPolicy
from hinaa_api.runtime_paths import project_root
from hinaa_api.sandbox.isolation_base import IsolationBackendType, SandboxAdapter
from hinaa_api.sandbox.process_adapter import RestrictedProcessAdapter
from hinaa_api.sandbox.runtime_discovery import IsolationHealthReport, RuntimeDiscovery

logger = logging.getLogger("hinaa.coding.service")


class CodingService:
    """Central orchestration service for autonomous coding tasks and sandboxes."""

    def __init__(
        self,
        policy: Optional[CodingSecurityPolicy] = None,
        storage_dir: Optional[str | Path] = None,
    ) -> None:
        self.policy = policy or CodingSecurityPolicy()
        self._active_loops: Dict[str, AutonomousCodingLoop] = {}
        self._event_subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._event_history: Dict[str, List[CodingTaskEvent]] = {}
        self._artifacts_registry: Dict[str, Dict[str, Any]] = {}

        if storage_dir is not None:
            self._storage_dir = Path(storage_dir)
        else:
            env_dir = os.environ.get("HINAA_CODING_TASKS_DIR")
            self._storage_dir = Path(env_dir) if env_dir else (project_root() / ".hina" / "coding_tasks")
        self._storage_dir.mkdir(parents=True, exist_ok=True)

    def _task_file(self, task_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)[:96]
        return self._storage_dir / f"{safe}.json"

    def _events_file(self, task_id: str) -> Path:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", task_id)[:96]
        return self._storage_dir / f"{safe}.events.jsonl"

    def _persist_task_record(self, task_id: str, spec: Optional[CodingTaskSpec], status: CodingTaskStatus) -> None:
        try:
            payload = {
                "spec": spec.model_dump(mode="json") if spec else None,
                "status": status.model_dump(mode="json"),
                "artifacts": list(self._artifacts_registry.get(task_id, {}).values()),
            }
            p = self._task_file(task_id)
            tmp = p.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
            os.replace(tmp, p)
        except Exception:
            logger.debug("Failed persisting coding task %s", task_id, exc_info=True)

    def _append_persisted_event(self, evt: CodingTaskEvent) -> None:
        try:
            ef = self._events_file(evt.run_id)
            with ef.open("a", encoding="utf-8") as fh:
                fh.write(evt.model_dump_json() + "\n")
        except Exception:
            logger.debug("Failed appending event for task %s", evt.run_id, exc_info=True)

    def _load_persisted_record(self, task_id: str) -> Optional[Dict[str, Any]]:
        p = self._task_file(task_id)
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _load_persisted_events(self, task_id: str) -> List[CodingTaskEvent]:
        ef = self._events_file(task_id)
        if not ef.exists():
            return []
        events: List[CodingTaskEvent] = []
        for raw_line in ef.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                events.append(CodingTaskEvent.model_validate_json(line))
            except Exception:
                continue
        return events

    def get_sandbox_status(self) -> IsolationHealthReport:
        """Returns the current host isolation health report."""
        return RuntimeDiscovery.get_health_report()

    def _build_sandbox(self, workspace: Path, report: IsolationHealthReport) -> SandboxAdapter:
        # Keep RestrictedProcessAdapter as default on host/Windows; use Docker only when explicitly healthy
        return RestrictedProcessAdapter(workspace_root=workspace)

    def _wire_loop(self, spec: CodingTaskSpec, sandbox: SandboxAdapter, initial_status: Optional[CodingTaskStatus] = None) -> AutonomousCodingLoop:
        def event_dispatcher(evt: CodingTaskEvent) -> None:
            if evt.run_id not in self._event_history:
                self._event_history[evt.run_id] = self._load_persisted_events(evt.run_id)
            self._event_history[evt.run_id].append(evt)
            self._append_persisted_event(evt)

            active = self._active_loops.get(evt.run_id)
            if active is not None:
                self._persist_task_record(evt.run_id, active.spec, active.status)

            subs = self._event_subscribers.get(evt.run_id, set())
            for q in list(subs):
                try:
                    q.put_nowait(evt)
                except Exception:
                    pass

        loop = AutonomousCodingLoop(spec=spec, sandbox=sandbox, event_callback=event_dispatcher)
        if initial_status is not None:
            loop.status = initial_status
        self._active_loops[spec.task_id] = loop
        return loop

    def create_task(self, spec: CodingTaskSpec) -> AutonomousCodingLoop:
        """Initializes a new durable coding task with appropriate sandbox adapter."""
        workspace = Path(spec.workspace_path).resolve()
        report = self.get_sandbox_status()

        if spec.require_high_security and report.primary_backend not in {
            IsolationBackendType.DOCKER_CONTAINER,
            IsolationBackendType.WSL2_MICROVM,
        }:
            raise PermissionError(
                "High-security container isolation requested, but host currently only supports RESTRICTED_HOST_PROCESS."
            )

        sandbox = self._build_sandbox(workspace, report)
        loop = self._wire_loop(spec, sandbox)
        loop.status.backend_type = report.primary_backend
        self._persist_task_record(spec.task_id, spec, loop.status)
        return loop

    def get_task(self, task_id: str) -> Optional[CodingTaskStatus]:
        loop = self._active_loops.get(task_id)
        if loop:
            return loop.status
        rec = self._load_persisted_record(task_id)
        if not rec or not rec.get("status"):
            return None
        try:
            return CodingTaskStatus.model_validate(rec["status"])
        except Exception:
            return None

    def get_spec(self, task_id: str) -> Optional[CodingTaskSpec]:
        loop = self._active_loops.get(task_id)
        if loop:
            return loop.spec
        rec = self._load_persisted_record(task_id)
        if rec and rec.get("spec"):
            try:
                return CodingTaskSpec.model_validate(rec["spec"])
            except Exception:
                return None
        return None

    def list_tasks(self, limit: int = 50) -> List[CodingTaskStatus]:
        by_id: Dict[str, CodingTaskStatus] = {tid: lp.status for tid, lp in self._active_loops.items()}
        for fp in sorted(self._storage_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                st = CodingTaskStatus.model_validate(data["status"])
                by_id.setdefault(st.task_id, st)
            except Exception:
                continue
        return list(by_id.values())[:limit]

    def get_events(self, task_id: str) -> List[CodingTaskEvent]:
        if task_id in self._event_history:
            return list(self._event_history[task_id])
        loaded = self._load_persisted_events(task_id)
        if loaded:
            self._event_history[task_id] = loaded
        return loaded

    def subscribe_events(self, task_id: str) -> asyncio.Queue:
        if task_id not in self._event_subscribers:
            self._event_subscribers[task_id] = set()

        q: asyncio.Queue = asyncio.Queue()
        self._event_subscribers[task_id].add(q)

        for evt in self.get_events(task_id):
            q.put_nowait(evt)

        return q

    def unsubscribe_events(self, task_id: str, q: asyncio.Queue) -> None:
        subs = self._event_subscribers.get(task_id)
        if subs and q in subs:
            subs.remove(q)

    def cancel_task(self, task_id: str) -> bool:
        loop = self._active_loops.get(task_id)
        if loop:
            loop.request_cancellation()
            try:
                running_loop = asyncio.get_running_loop()
                running_loop.create_task(loop.sandbox.terminate())
            except RuntimeError:
                pass
            self._persist_task_record(task_id, loop.spec, loop.status)
            return True

        rec = self._load_persisted_record(task_id)
        if not rec or not rec.get("status"):
            return False
        try:
            st = CodingTaskStatus.model_validate(rec["status"])
            st.state = CodingTaskState.CANCELLED
            st.error = "Cancelled by user."
            spec = CodingTaskSpec.model_validate(rec["spec"]) if rec.get("spec") else None
            self._persist_task_record(task_id, spec, st)
            return True
        except Exception:
            return False

    def resume_task(self, task_id: str) -> Optional[AutonomousCodingLoop]:
        """Rehydrates a persisted task from disk after restart so remaining work can resume."""
        existing = self._active_loops.get(task_id)
        if existing is not None:
            return existing
        rec = self._load_persisted_record(task_id)
        if not rec or not rec.get("spec") or not rec.get("status"):
            return None
        spec = CodingTaskSpec.model_validate(rec["spec"])
        status = CodingTaskStatus.model_validate(rec["status"])
        if status.state in {CodingTaskState.COMPLETED, CodingTaskState.CANCELLED}:
            return None
        workspace = Path(spec.workspace_path).resolve()
        if not workspace.exists():
            return None
        report = self.get_sandbox_status()
        sandbox = self._build_sandbox(workspace, report)
        loop = self._wire_loop(spec, sandbox, initial_status=status)
        if isinstance(rec.get("artifacts"), list):
            for art in rec["artifacts"]:
                self.register_artifact(task_id, art)
        loop.emit("run.resumed", "Task state rehydrated from durable checkpoint", {"state": status.state.value})
        return loop

    def approve_action(
        self,
        task_id: str,
        action: CodingActionRequest,
        token: str,
    ) -> bool:
        loop = self._active_loops.get(task_id)
        workspace = str(loop.workspace_root) if loop else None
        if workspace is None:
            st = self.get_task(task_id)
            workspace = st.workspace_path if st else None
        if workspace is None:
            return False
        return self.policy.verify_approval_token(
            token=token,
            task_id=task_id,
            action=action,
            workspace_path=workspace,
        )

    def rollback_task(self, task_id: str) -> List[str]:
        loop = self._active_loops.get(task_id)
        if not loop:
            loop = self.resume_task(task_id)
        if not loop:
            return []
        reverted = loop.manager.rollback(task_id)
        loop.status.state = CodingTaskState.COMPLETED
        loop.emit("run.completed", f"Rollback executed: {', '.join(reverted)}", {"reverted_files": reverted})
        self._persist_task_record(task_id, loop.spec, loop.status)
        return reverted

    def register_artifact(self, task_id: str, artifact_meta: Dict[str, Any]) -> None:
        if task_id not in self._artifacts_registry:
            self._artifacts_registry[task_id] = {}
        art_id = artifact_meta.get("artifactId") or f"art-{len(self._artifacts_registry[task_id])+1}"
        self._artifacts_registry[task_id][art_id] = artifact_meta
        loop = self._active_loops.get(task_id)
        if loop:
            self._persist_task_record(task_id, loop.spec, loop.status)

    def list_artifacts(self, task_id: str) -> List[Dict[str, Any]]:
        if task_id in self._artifacts_registry:
            return list(self._artifacts_registry[task_id].values())
        rec = self._load_persisted_record(task_id)
        if rec and isinstance(rec.get("artifacts"), list):
            return list(rec["artifacts"])
        return []
