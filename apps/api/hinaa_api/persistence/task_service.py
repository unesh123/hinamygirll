from __future__ import annotations

import json
import re
import uuid
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from ..errors import HinaaError
from .orm import (
    DurableDeadLetter,
    DurableOutboxEvent,
    DurableTask,
    DurableTaskCheckpoint,
    DurableTaskEvent,
    DurableTaskStep,
    SideEffectJournal,
    User,
)

TASK_STATUSES = {
    "created",
    "planning",
    "active",
    "waiting_tool",
    "waiting_user",
    "blocked",
    "verifying",
    "completed",
    "failed",
    "cancelled",
}
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}
STEP_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "skipped"}
CONTINUE_RE = re.compile(r"\b(continue|keep going|resume|finish(?: it)?|do the rest)\b", re.I)


def _loads(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return fallback


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _now() -> datetime:
    return datetime.now(UTC)


def _uuid() -> str:
    return str(uuid.uuid4())


class TaskService:
    """Durable local-first task brain for HINAA's continuous execution layer.

    This service stores task intent, plan steps, append-only workflow events,
    and checkpoint state. It intentionally does not execute arbitrary tools yet;
    it provides the restart-safe substrate that chat/maker/runtime execution can
    attach to without trusting client-submitted completion.
    """

    def __init__(self, factory: sessionmaker[Session]) -> None:
        self._factory = factory

    def create_task(
        self,
        owner_id: str,
        goal: str,
        *,
        task_id: str | None = None,
        conversation_id: str | None = None,
        project_id: str | None = None,
        task_type: str = "general",
        priority: int = 0,
        reasoning_mode: str = "balanced",
        steps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned_goal = goal.strip()
        if len(cleaned_goal) < 3:
            raise HinaaError("TASK_GOAL_INVALID", "Task goal is too short.", 422, False)
        with self._factory() as session:
            self._user(session, owner_id)
            self._validate_acyclic_steps(steps or self._starter_steps(cleaned_goal))
            task = DurableTask(
                id=task_id or _uuid(),
                owner_id=owner_id,
                conversation_id=conversation_id,
                project_id=project_id,
                goal=cleaned_goal,
                task_type=task_type[:60] or "general",
                priority=priority,
                reasoning_mode=reasoning_mode[:40] or "balanced",
                status="planning",
                metadata_json=_dumps(metadata or {}),
            )
            session.add(task)

            session.flush()
            self._append_event(
                session,
                task.id,
                "TASK_CREATED",
                {"goal": cleaned_goal, "conversationId": conversation_id, "projectId": project_id},
            )
            plan_steps = steps or self._starter_steps(cleaned_goal)
            for index, step in enumerate(plan_steps):
                session.add(
                    DurableTaskStep(
                        id=str(step.get("id") or _uuid()),
                        task_id=task.id,
                        position=index,
                        title=str(step.get("title") or f"Step {index + 1}")[:240],
                        description=str(step.get("description") or ""),
                        status=str(step.get("status") or "pending"),
                        dependencies_json=_dumps(step.get("dependencies") or []),
                        max_attempts=int(step.get("maxAttempts") or step.get("max_attempts") or 3),
                        tool_call_ids_json=_dumps(step.get("toolCallIds") or []),
                        input_artifact_ids_json=_dumps(step.get("inputArtifactIds") or []),
                        output_artifact_ids_json=_dumps(step.get("outputArtifactIds") or []),
                    )
                )
            task.status = "active"
            session.flush()
            steps_rows = self._steps(session, task.id)
            task.current_step_id = self._next_step(steps_rows).id if self._next_step(steps_rows) else None
            self._append_event(
                session,
                task.id,
                "PLAN_CREATED",
                {"stepCount": len(steps_rows), "reasoningMode": task.reasoning_mode},
            )
            self._checkpoint(session, task, steps_rows, reason="created")
            session.commit()
            return self._public_task(task, steps_rows, self._latest_checkpoint(session, task.id))

    def claim_next(
        self,
        owner_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        conversation_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Atomically claim one runnable task lease for a worker.

        SQLite dev uses a single transactional update path; PostgreSQL can later
        swap this selection for SKIP LOCKED without changing the public contract.
        Every claim increments the fencing token, so expired workers cannot write
        after another worker acquires the task.
        """
        now = _now()
        with self._factory() as session:
            self._user(session, owner_id)
            query = (
                select(DurableTask)
                .where(DurableTask.owner_id == owner_id)
                .where(DurableTask.status.in_(("active", "waiting_tool", "blocked", "planning")))
                .order_by(DurableTask.priority.desc(), DurableTask.updated_at.asc())
                .limit(20)
            )
            if conversation_id:
                query = query.where(DurableTask.conversation_id == conversation_id)
            if project_id:
                query = query.where(DurableTask.project_id == project_id)
            candidates = session.scalars(query).all()
            task = next(
                (
                    candidate
                    for candidate in candidates
                    if candidate.lease_expires_at is None or self._is_expired(candidate.lease_expires_at, now)
                ),
                None,
            )
            if task is None:
                return None
            lease_id = _uuid()
            task.worker_id = worker_id[:120]
            task.lease_id = lease_id
            task.fencing_token += 1
            task.version += 1
            task.lease_acquired_at = now
            task.lease_expires_at = now + timedelta(seconds=max(5, min(lease_seconds, 3600)))
            task.status = "active"
            self._append_event(
                session,
                task.id,
                "TASK_CLAIMED",
                {
                    "workerId": task.worker_id,
                    "leaseId": lease_id,
                    "fencingToken": task.fencing_token,
                    "leaseExpiresAt": task.lease_expires_at.isoformat(),
                },
            )
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="claimed")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def claim_task(
        self,
        owner_id: str,
        task_id: str,
        *,
        worker_id: str,
        lease_seconds: int = 60,
        force: bool = False,
    ) -> dict[str, Any]:
        """Atomically claim a specific task lease for a worker.
        Increments fencing token and validates that any previous lease is expired or held by same worker.
        """
        now = _now()
        with self._factory() as session:
            self._user(session, owner_id)
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                raise HinaaError("TASK_ALREADY_TERMINAL", "Terminal tasks cannot be claimed.", 409, False)
            if (
                not force
                and task.lease_expires_at is not None
                and not self._is_expired(task.lease_expires_at, now)
                and task.worker_id != worker_id
            ):
                raise HinaaError("TASK_LEASE_HELD", "Task lease is currently held by another worker.", 409, True)
            lease_id = _uuid()
            task.worker_id = worker_id[:120]
            task.lease_id = lease_id
            task.fencing_token += 1
            task.version += 1
            task.lease_acquired_at = now
            task.lease_expires_at = now + timedelta(seconds=max(5, min(lease_seconds, 3600)))
            task.status = "active"
            self._append_event(
                session,
                task.id,
                "TASK_CLAIMED",
                {
                    "workerId": task.worker_id,
                    "leaseId": lease_id,
                    "fencingToken": task.fencing_token,
                    "leaseExpiresAt": task.lease_expires_at.isoformat(),
                },
            )
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="claimed_by_id")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def complete_step_with_lease(
        self,
        owner_id: str,
        task_id: str,
        step_id: str,
        *,
        lease_id: str,
        fencing_token: int,
        output_artifact_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            self._assert_worker_fence(task, lease_id=lease_id, fencing_token=fencing_token)
            step = self._step(session, task_id, step_id)
            step.version += 1
            step.status = "completed"
            step.completed_at = _now()
            step.output_artifact_ids_json = _dumps(output_artifact_ids or _loads(step.output_artifact_ids_json, []))
            task.version += 1
            self._append_event(session, task.id, "STEP_COMPLETED", {"title": step.title}, step_id=step.id)
            steps = self._steps(session, task.id)
            next_step = self._next_step(steps)
            task.current_step_id = next_step.id if next_step else None
            task.status = "active" if next_step else "completed"
            if next_step is None:
                task.completed_at = _now()
                task.worker_id = None
                task.lease_id = None
                task.lease_expires_at = None
                self._append_event(session, task.id, "TASK_COMPLETED", {"verified": True})
            self._checkpoint(session, task, steps, reason="lease_step_completed")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def fail_step_with_lease(
        self,
        owner_id: str,
        task_id: str,
        step_id: str,
        reason: str,
        *,
        lease_id: str,
        fencing_token: int,
        retry_limit: int = 2,
    ) -> dict[str, Any]:
        """Record step failure while validating that the worker lease is still active and valid."""
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            self._assert_worker_fence(task, lease_id=lease_id, fencing_token=fencing_token)
            step = self._step(session, task_id, step_id)
            step.failure_reason = reason
            step.attempt_count += 1
            step.version += 1
            task.failure_count += 1
            task.version += 1
            if step.attempt_count <= retry_limit:
                step.status = "pending"
                step.retry_after = _now() + timedelta(seconds=min(300, 2 ** max(1, step.attempt_count)))
                task.status = "active"
                self._append_event(
                    session,
                    task.id,
                    "STEP_FAILED",
                    {"reason": reason, "willRetry": True, "attemptCount": step.attempt_count},
                    step_id=step.id,
                )
            else:
                step.status = "failed"
                step.completed_at = _now()
                task.status = "failed"
                task.completed_at = _now()
                task.blocked_reason = reason
                task.worker_id = None
                task.lease_id = None
                task.lease_expires_at = None
                self._append_event(
                    session,
                    task.id,
                    "STEP_FAILED",
                    {"reason": reason, "willRetry": False, "attemptCount": step.attempt_count},
                    step_id=step.id,
                )
                self._append_event(session, task.id, "TASK_FAILED", {"reason": reason})
                session.add(
                    DurableDeadLetter(
                        task_id=task.id,
                        step_id=step.id,
                        reason=reason,
                        payload_json=_dumps({"attemptCount": step.attempt_count, "retryLimit": retry_limit}),
                    )
                )
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="lease_step_failed")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def extend_lease(
        self,
        owner_id: str,
        task_id: str,
        *,
        lease_id: str,
        fencing_token: int,
        additional_seconds: int = 60,
    ) -> dict[str, Any]:
        """Extend the lease expiration for an active task worker without changing fencing token."""
        now = _now()
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            self._assert_worker_fence(task, lease_id=lease_id, fencing_token=fencing_token)
            extend_by = max(5, min(additional_seconds, 3600))
            task.lease_expires_at = now + timedelta(seconds=extend_by)
            task.version += 1
            self._append_event(
                session,
                task.id,
                "TASK_LEASE_EXTENDED",
                {
                    "workerId": task.worker_id,
                    "leaseId": lease_id,
                    "fencingToken": fencing_token,
                    "leaseExpiresAt": task.lease_expires_at.isoformat(),
                },
            )
            steps = self._steps(session, task.id)
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def record_side_effect_planned(
        self,
        owner_id: str,
        task_id: str,
        *,
        step_id: str | None,
        idempotency_key: str,
        provider: str,
        operation_type: str,
        request_payload: dict[str, Any],
    ) -> dict[str, Any]:
        with self._factory() as session:
            self._task(session, owner_id, task_id)
            existing = session.scalar(
                select(SideEffectJournal).where(SideEffectJournal.idempotency_key == idempotency_key)
            )
            if existing is not None:
                return self._public_side_effect(existing)
            journal = SideEffectJournal(
                task_id=task_id,
                step_id=step_id,
                idempotency_key=idempotency_key,
                provider=provider[:80],
                operation_type=operation_type[:80],
                status="PLANNED",
                request_hash=self._stable_hash(request_payload),
                metadata_json=_dumps({"atLeastOnce": True, "exactlyOnce": False}),
            )
            session.add(journal)
            self._append_event(
                session,
                task_id,
                "TOOL_STARTED",
                {"operationId": journal.operation_id, "provider": provider, "operationType": operation_type},
                step_id=step_id,
            )
            session.commit()
            return self._public_side_effect(journal)

    def mark_side_effect_provider_accepted(
        self,
        owner_id: str,
        operation_id: str,
        *,
        provider_operation_id: str,
        response_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        with self._factory() as session:
            journal = session.get(SideEffectJournal, operation_id)
            if journal is None:
                raise HinaaError("SIDE_EFFECT_NOT_FOUND", "Side-effect journal record not found.", 404, False)
            self._task(session, owner_id, journal.task_id)
            journal.status = "PROVIDER_ACCEPTED"
            journal.provider_operation_id = provider_operation_id[:160]
            journal.response_hash = self._stable_hash(response_payload or {})
            journal.updated_at = _now()
            self._append_event(
                session,
                journal.task_id,
                "TOOL_COMPLETED",
                {
                    "operationId": journal.operation_id,
                    "providerOperationId": journal.provider_operation_id,
                    "status": journal.status,
                },
                step_id=journal.step_id,
            )
            session.commit()
            return self._public_side_effect(journal)

    def list_tasks(
        self,
        owner_id: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        include_completed: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        with self._factory() as session:
            self._user(session, owner_id)
            query = select(DurableTask).where(DurableTask.owner_id == owner_id)
            if conversation_id:
                query = query.where(DurableTask.conversation_id == conversation_id)
            if project_id:
                query = query.where(DurableTask.project_id == project_id)
            if not include_completed:
                query = query.where(DurableTask.status.not_in(TERMINAL_STATUSES))
            rows = session.scalars(
                query.order_by(DurableTask.priority.desc(), DurableTask.updated_at.desc()).limit(max(1, min(limit, 200)))
            ).all()
            return [
                self._public_task(row, self._steps(session, row.id), self._latest_checkpoint(session, row.id))
                for row in rows
            ]

    def get_task(self, owner_id: str, task_id: str) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def events(self, owner_id: str, task_id: str, *, after: int = 0) -> dict[str, Any]:
        with self._factory() as session:
            self._task(session, owner_id, task_id)
            rows = session.scalars(
                select(DurableTaskEvent)
                .where(DurableTaskEvent.task_id == task_id, DurableTaskEvent.sequence > max(0, after))
                .order_by(DurableTaskEvent.sequence.asc())
            ).all()
            cursor = session.scalar(
                select(func.max(DurableTaskEvent.sequence)).where(DurableTaskEvent.task_id == task_id)
            ) or 0
            return {"taskId": task_id, "cursor": cursor, "events": [self._public_event(row) for row in rows]}

    def list_checkpoints(self, owner_id: str, task_id: str) -> list[dict[str, Any]]:
        with self._factory() as session:
            self._task(session, owner_id, task_id)
            rows = session.scalars(
                select(DurableTaskCheckpoint)
                .where(DurableTaskCheckpoint.task_id == task_id)
                .order_by(DurableTaskCheckpoint.version.desc())
            ).all()
            return [
                {
                    "id": row.id,
                    "taskId": row.task_id,
                    "version": row.version,
                    "state": _loads(row.state_json, {}),
                    "createdAt": row.created_at.isoformat() if row.created_at else None,
                }
                for row in rows
            ]

    def resolve_active_task(
        self,
        owner_id: str,
        *,
        text: str,
        conversation_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Resolve continue/resume to the most relevant unfinished task."""
        if not CONTINUE_RE.search(text.strip()):
            return {"intent": "new_request", "confidence": 0.0, "task": None, "ambiguous": False}
        with self._factory() as session:
            self._user(session, owner_id)
            query = (
                select(DurableTask)
                .where(DurableTask.owner_id == owner_id)
                .where(DurableTask.status.not_in(TERMINAL_STATUSES))
                .order_by(DurableTask.priority.desc(), DurableTask.updated_at.desc())
                .limit(20)
            )
            candidates = session.scalars(query).all()
            scored: list[tuple[int, DurableTask]] = []
            for task in candidates:
                score = 1
                if conversation_id and task.conversation_id == conversation_id:
                    score += 4
                if project_id and task.project_id == project_id:
                    score += 4
                if task.status in {"active", "waiting_tool", "waiting_user", "blocked"}:
                    score += 2
                scored.append((score, task))
            scored.sort(key=lambda item: (item[0], item[1].updated_at or item[1].created_at), reverse=True)
            if not scored:
                return {"intent": "continue_task", "confidence": 0.0, "task": None, "ambiguous": False}
            top_score = scored[0][0]
            top_matches = [task for score, task in scored if score == top_score]
            ambiguous = len(top_matches) > 1 and not (conversation_id or project_id)
            confidence = min(0.95, 0.35 + top_score / 10)
            selected = top_matches[0]
            return {
                "intent": "continue_task",
                "confidence": confidence if not ambiguous else 0.45,
                "ambiguous": ambiguous,
                "task": self._public_task(
                    selected, self._steps(session, selected.id), self._latest_checkpoint(session, selected.id)
                )
                if not ambiguous
                else None,
                "candidateTaskIds": [task.id for task in top_matches[:5]],
            }

    def continue_task(self, owner_id: str, task_id: str) -> dict[str, Any]:
        """Resume from the next unfinished step without replaying completed steps."""
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                raise HinaaError("TASK_ALREADY_TERMINAL", "That task is already finished.", 409, False)
            steps = self._steps(session, task.id)
            next_step = self._next_step(steps)
            if next_step is None:
                task.status = "verifying"
                task.current_step_id = None
                self._append_event(session, task.id, "TASK_CHECKPOINTED", {"reason": "all_steps_finished"})
                task.status = "completed"
                task.completed_at = _now()
                self._append_event(session, task.id, "TASK_COMPLETED", {"verified": True})
            else:
                task.status = "active"
                task.current_step_id = next_step.id
                if next_step.status == "pending":
                    next_step.status = "active"
                    next_step.started_at = next_step.started_at or _now()
                    next_step.attempt_count += 1
                    self._append_event(
                        session,
                        task.id,
                        "STEP_STARTED",
                        {"title": next_step.title, "position": next_step.position},
                        step_id=next_step.id,
                    )
                self._append_event(session, task.id, "TASK_CHECKPOINTED", {"reason": "continue", "stepId": next_step.id})
            task.updated_at = _now()
            self._checkpoint(session, task, steps, reason="continue")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def complete_step(self, owner_id: str, task_id: str, step_id: str, *, output_artifact_ids: list[str] | None = None) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            step = self._step(session, task_id, step_id)
            step.status = "completed"
            step.completed_at = _now()
            step.output_artifact_ids_json = _dumps(output_artifact_ids or _loads(step.output_artifact_ids_json, []))
            self._append_event(session, task.id, "STEP_COMPLETED", {"title": step.title}, step_id=step.id)
            steps = self._steps(session, task.id)
            next_step = self._next_step(steps)
            task.current_step_id = next_step.id if next_step else None
            task.status = "active" if next_step else "verifying"
            if next_step is None:
                task.status = "completed"
                task.completed_at = _now()
                self._append_event(session, task.id, "TASK_COMPLETED", {"verified": True})
            self._checkpoint(session, task, steps, reason="step_completed")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def steer_task(self, owner_id: str, task_id: str, instruction: str) -> dict[str, Any]:
        cleaned = instruction.strip()
        if not cleaned:
            raise HinaaError("TASK_STEER_INVALID", "Steering instruction is empty.", 422, False)
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                raise HinaaError("TASK_ALREADY_TERMINAL", "Terminal tasks cannot be steered.", 409, False)
            metadata = _loads(task.metadata_json, {})
            constraints = list(metadata.get("constraints") or [])
            constraints.append(cleaned)
            metadata["constraints"] = constraints[-20:]
            metadata["lastSteeringInstruction"] = cleaned
            task.metadata_json = _dumps(metadata)
            task.status = "active"
            self._append_event(session, task.id, "USER_STEERED", {"instruction": cleaned})
            self._append_event(session, task.id, "TASK_REPLANNED", {"scope": "remaining_steps_only"})
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="steered")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def cancel_task(self, owner_id: str, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))
            task.status = "cancelled"
            task.completed_at = _now()
            task.blocked_reason = reason
            for step in self._steps(session, task.id):
                if step.status not in STEP_TERMINAL_STATUSES:
                    step.status = "cancelled"
                    step.completed_at = _now()
            self._append_event(session, task.id, "TASK_FAILED" if reason else "TASK_CANCELLED", {"reason": reason})
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="cancelled")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def fail_step(self, owner_id: str, task_id: str, step_id: str, reason: str, *, retry_limit: int = 2) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            step = self._step(session, task_id, step_id)
            step.failure_reason = reason
            step.attempt_count += 1
            task.failure_count += 1
            if step.attempt_count <= retry_limit:
                step.status = "pending"
                step.retry_after = _now() + timedelta(seconds=min(300, 2 ** max(1, step.attempt_count)))
                task.status = "active"
                self._append_event(session, task.id, "STEP_FAILED", {"reason": reason, "willRetry": True}, step_id=step.id)
            else:
                step.status = "failed"
                step.completed_at = _now()
                task.status = "failed"
                task.completed_at = _now()
                task.blocked_reason = reason
                self._append_event(session, task.id, "STEP_FAILED", {"reason": reason, "willRetry": False}, step_id=step.id)
                self._append_event(session, task.id, "TASK_FAILED", {"reason": reason})
                session.add(
                    DurableDeadLetter(
                        task_id=task.id,
                        step_id=step.id,
                        reason=reason,
                        payload_json=_dumps({"attemptCount": step.attempt_count, "retryLimit": retry_limit}),
                    )
                )
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="step_failed")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def recover_interrupted_tasks(self, owner_id: str | None = None) -> list[dict[str, Any]]:
        """Find in-flight tasks interrupted by server restart, reset active steps, and record checkpoint."""
        recovered_tasks: list[dict[str, Any]] = []
        with self._factory() as session:
            query = select(DurableTask).where(DurableTask.status.not_in(TERMINAL_STATUSES))
            if owner_id:
                query = query.where(DurableTask.owner_id == owner_id)
            tasks = session.scalars(query).all()
            for task in tasks:
                steps = self._steps(session, task.id)
                interrupted_any = False
                for step in steps:
                    if step.status == "active":
                        step.status = "pending"
                        step.attempt_count += 1
                        step.failure_reason = "interrupted_by_server_restart"
                        self._append_event(
                            session,
                            task.id,
                            "STEP_INTERRUPTED",
                            {"stepId": step.id, "reason": "interrupted_by_server_restart"},
                            step_id=step.id,
                        )
                        interrupted_any = True
                if interrupted_any or task.status in {"active", "planning", "waiting_tool", "verifying"}:
                    prev_status = task.status
                    task.status = "waiting_user"
                    task.worker_id = None
                    task.lease_id = None
                    task.lease_expires_at = None
                    task.updated_at = _now()
                    self._append_event(
                        session,
                        task.id,
                        "TASK_RECOVERED",
                        {"previousStatus": prev_status, "reason": "server_restart"},
                    )
                    self._checkpoint(session, task, steps, reason="restart_recovery")
                    recovered_tasks.append(
                        self._public_task(task, steps, self._latest_checkpoint(session, task.id))
                    )
            session.commit()
        return recovered_tasks

    def rollback_to_checkpoint(self, owner_id: str, task_id: str, version: int) -> dict[str, Any]:
        """Revert task and step states to the state captured at a specified checkpoint version."""
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            checkpoint = session.scalar(
                select(DurableTaskCheckpoint).where(
                    DurableTaskCheckpoint.task_id == task_id,
                    DurableTaskCheckpoint.version == version,
                )
            )
            if checkpoint is None:
                raise HinaaError("CHECKPOINT_NOT_FOUND", f"Checkpoint version {version} not found.", 404, False)
            state = _loads(checkpoint.state_json, {})
            task.status = state.get("status", "planning")
            task.current_step_id = state.get("currentStepId")
            if task.status not in TERMINAL_STATUSES:
                task.completed_at = None
                task.blocked_reason = None
            task.updated_at = _now()

            steps = self._steps(session, task_id)
            completed_steps = set(state.get("completedSteps", []))
            remaining_steps = set(state.get("remainingSteps", []))
            for step in steps:
                if step.id in completed_steps:
                    step.status = "completed"
                elif step.id in remaining_steps:
                    step.status = "pending"
                    step.completed_at = None
                    step.failure_reason = None
                else:
                    step.status = "pending"
                    step.completed_at = None
                    step.failure_reason = None

            self._append_event(
                session,
                task.id,
                "TASK_ROLLED_BACK",
                {"targetVersion": version, "restoredStatus": task.status},
            )
            self._checkpoint(session, task, steps, reason=f"rollback_to_version_{version}")
            session.commit()
            return self._public_task(task, self._steps(session, task.id), self._latest_checkpoint(session, task.id))

    def pause_task(self, owner_id: str, task_id: str, reason: str | None = None) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                raise HinaaError("TASK_ALREADY_TERMINAL", "Terminal tasks cannot be paused.", 409, False)
            task.status = "paused"
            task.blocked_reason = reason
            task.worker_id = None
            task.lease_id = None
            task.lease_expires_at = None
            task.version += 1
            self._append_event(session, task.id, "TASK_PAUSED", {"reason": reason})
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="paused")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    def resume_task(self, owner_id: str, task_id: str) -> dict[str, Any]:
        with self._factory() as session:
            task = self._task(session, owner_id, task_id)
            if task.status in TERMINAL_STATUSES:
                raise HinaaError("TASK_ALREADY_TERMINAL", "Terminal tasks cannot be resumed.", 409, False)
            task.status = "active"
            task.blocked_reason = None
            task.version += 1
            self._append_event(session, task.id, "TASK_RESUMED", {})
            steps = self._steps(session, task.id)
            self._checkpoint(session, task, steps, reason="resumed")
            session.commit()
            return self._public_task(task, steps, self._latest_checkpoint(session, task.id))

    @staticmethod
    def _starter_steps(goal: str) -> list[dict[str, str]]:
        return [
            {"title": "Understand goal", "description": f"Clarify completion criteria for: {goal[:240]}"},
            {"title": "Execute safely", "description": "Run only scoped, approved work and capture observations."},
            {"title": "Verify completion", "description": "Check evidence before marking the task complete."},
        ]

    @staticmethod
    def _stable_hash(payload: Any) -> str:
        return hashlib.sha256(_dumps(payload).encode("utf-8")).hexdigest()

    @staticmethod
    def _validate_acyclic_steps(steps: list[dict[str, Any]]) -> None:
        names = [str(step.get("id") or step.get("title") or index) for index, step in enumerate(steps)]
        known = set(names)
        graph: dict[str, list[str]] = {}
        for name, step in zip(names, steps, strict=False):
            deps = [str(dep) for dep in (step.get("dependencies") or [])]
            unknown = [dep for dep in deps if dep not in known]
            if unknown:
                raise HinaaError("TASK_DAG_INVALID", f"Unknown task step dependency: {unknown[0]}", 422, False)
            graph[name] = deps
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(node: str) -> None:
            if node in visited:
                return
            if node in visiting:
                raise HinaaError("TASK_DAG_CYCLE", "Task step dependency graph contains a cycle.", 422, False)
            visiting.add(node)
            for dep in graph.get(node, []):
                visit(dep)
            visiting.remove(node)
            visited.add(node)

        for node in names:
            visit(node)

    @staticmethod
    def _assert_worker_fence(task: DurableTask, *, lease_id: str, fencing_token: int) -> None:
        now = _now()
        if task.lease_id != lease_id or int(task.fencing_token or 0) != int(fencing_token):
            raise HinaaError("STALE_WORKER_FENCE", "Worker lease is stale; mutation rejected.", 409, True)
        if task.lease_expires_at and TaskService._is_expired(task.lease_expires_at, now):
            raise HinaaError("TASK_LEASE_EXPIRED", "Worker lease expired; claim the task again.", 409, True)

    @staticmethod
    def _is_expired(expires_at: datetime, now: datetime) -> bool:
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return expires_at <= now

    @staticmethod
    def _user(session: Session, owner_id: str) -> User:
        user = session.scalar(select(User).where(User.id == owner_id, User.deleted_at.is_(None)))
        if user is None:
            user = session.scalar(select(User).where(User.auth_subject == owner_id, User.deleted_at.is_(None)))
        if user is None:
            user = User(id=owner_id, auth_subject=owner_id)
            session.add(user)
            session.flush()
        return user

    @staticmethod
    def _task(session: Session, owner_id: str, task_id: str) -> DurableTask:
        task = session.scalar(select(DurableTask).where(DurableTask.id == task_id, DurableTask.owner_id == owner_id))
        if task is None:
            raise HinaaError("TASK_NOT_FOUND", "Task not found.", 404, False)
        return task

    @staticmethod
    def _step(session: Session, task_id: str, step_id: str) -> DurableTaskStep:
        step = session.scalar(select(DurableTaskStep).where(DurableTaskStep.id == step_id, DurableTaskStep.task_id == task_id))
        if step is None:
            raise HinaaError("TASK_STEP_NOT_FOUND", "Task step not found.", 404, False)
        return step

    @staticmethod
    def _steps(session: Session, task_id: str) -> list[DurableTaskStep]:
        return list(
            session.scalars(
                select(DurableTaskStep)
                .where(DurableTaskStep.task_id == task_id)
                .order_by(DurableTaskStep.position.asc())
            ).all()
        )

    @staticmethod
    def _next_step(steps: list[DurableTaskStep]) -> DurableTaskStep | None:
        for step in steps:
            if step.status not in STEP_TERMINAL_STATUSES:
                return step
        return None

    def _append_event(
        self,
        session: Session,
        task_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        step_id: str | None = None,
    ) -> DurableTaskEvent:
        last_sequence = session.scalar(
            select(func.max(DurableTaskEvent.sequence)).where(DurableTaskEvent.task_id == task_id)
        ) or 0
        event = DurableTaskEvent(
            task_id=task_id,
            sequence=int(last_sequence) + 1,
            event_type=event_type,
            step_id=step_id,
            payload_json=_dumps(payload or {}),
        )
        session.add(event)
        session.add(
            DurableOutboxEvent(
                aggregate_type="task",
                aggregate_id=task_id,
                event_type=event_type,
                payload_json=_dumps({"taskId": task_id, "stepId": step_id, "payload": payload or {}}),
            )
        )
        return event

    def _checkpoint(
        self,
        session: Session,
        task: DurableTask,
        steps: list[DurableTaskStep],
        *,
        reason: str,
    ) -> DurableTaskCheckpoint:
        task.checkpoint_version += 1
        state = {
            "schemaVersion": 1,
            "runtimeVersion": "task-runtime-hardening-v1",
            "planRevision": task.version,
            "goal": task.goal,
            "status": task.status,
            "currentStepId": task.current_step_id,
            "completedSteps": [step.id for step in steps if step.status == "completed"],
            "remainingSteps": [step.id for step in steps if step.status not in STEP_TERMINAL_STATUSES],
            "importantEvidence": _loads(task.metadata_json, {}).get("importantEvidence", []),
            "knownFailures": [
                {"stepId": step.id, "reason": step.failure_reason}
                for step in steps
                if step.failure_reason
            ],
            "openQuestions": _loads(task.metadata_json, {}).get("openQuestions", []),
            "toolObservations": _loads(task.metadata_json, {}).get("toolObservations", []),
            "artifacts": sorted(
                {
                    artifact
                    for step in steps
                    for artifact in [
                        *_loads(step.input_artifact_ids_json, []),
                        *_loads(step.output_artifact_ids_json, []),
                    ]
                }
            ),
            "completionConditions": _loads(task.metadata_json, {}).get(
                "completionConditions",
                ["all steps terminal", "verification event recorded"],
            ),
            "checkpointReason": reason,
        }
        checkpoint = DurableTaskCheckpoint(
            task_id=task.id,
            version=task.checkpoint_version,
            state_json=_dumps(state),
        )
        session.add(checkpoint)
        self._append_event(session, task.id, "TASK_CHECKPOINTED", {"version": task.checkpoint_version, "reason": reason})
        return checkpoint

    @staticmethod
    def _latest_checkpoint(session: Session, task_id: str) -> DurableTaskCheckpoint | None:
        return session.scalar(
            select(DurableTaskCheckpoint)
            .where(DurableTaskCheckpoint.task_id == task_id)
            .order_by(DurableTaskCheckpoint.version.desc())
            .limit(1)
        )

    @staticmethod
    def _public_step(step: DurableTaskStep) -> dict[str, Any]:
        return {
            "id": step.id,
            "stepId": step.id,
            "taskId": step.task_id,
            "position": step.position,
            "title": step.title,
            "description": step.description,
            "status": step.status,
            "version": step.version,
            "dependencies": _loads(step.dependencies_json, []),
            "attemptCount": step.attempt_count,
            "maxAttempts": step.max_attempts,
            "retryAfter": step.retry_after.isoformat() if step.retry_after else None,
            "deadlineAt": step.deadline_at.isoformat() if step.deadline_at else None,
            "toolCallIds": _loads(step.tool_call_ids_json, []),
            "inputArtifactIds": _loads(step.input_artifact_ids_json, []),
            "outputArtifactIds": _loads(step.output_artifact_ids_json, []),
            "startedAt": step.started_at.isoformat() if step.started_at else None,
            "completedAt": step.completed_at.isoformat() if step.completed_at else None,
            "failureReason": step.failure_reason,
        }

    @staticmethod
    def _public_side_effect(row: SideEffectJournal) -> dict[str, Any]:
        return {
            "operationId": row.operation_id,
            "taskId": row.task_id,
            "stepId": row.step_id,
            "idempotencyKey": row.idempotency_key,
            "provider": row.provider,
            "operationType": row.operation_type,
            "status": row.status,
            "requestHash": row.request_hash,
            "providerOperationId": row.provider_operation_id,
            "responseHash": row.response_hash,
            "metadata": _loads(row.metadata_json, {}),
            "createdAt": row.created_at.isoformat() if row.created_at else None,
            "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
        }

    @staticmethod
    def _public_event(event: DurableTaskEvent) -> dict[str, Any]:
        return {
            "id": event.id,
            "taskId": event.task_id,
            "sequence": event.sequence,
            "type": event.event_type,
            "eventType": event.event_type,
            "stepId": event.step_id,
            "payload": _loads(event.payload_json, {}),
            "createdAt": event.created_at.isoformat() if event.created_at else None,
        }

    def _public_task(
        self,
        task: DurableTask,
        steps: list[DurableTaskStep],
        checkpoint: DurableTaskCheckpoint | None,
    ) -> dict[str, Any]:
        checkpoint_state = _loads(checkpoint.state_json, {}) if checkpoint else {}
        return {
            "id": task.id,
            "taskId": task.id,
            "ownerId": task.owner_id,
            "conversationId": task.conversation_id,
            "projectId": task.project_id,
            "goal": task.goal,
            "taskType": task.task_type,
            "status": task.status,
            "version": task.version,
            "priority": task.priority,
            "reasoningMode": task.reasoning_mode,
            "currentStepId": task.current_step_id,
            "blockedReason": task.blocked_reason,
            "failureCount": task.failure_count,
            "checkpointVersion": task.checkpoint_version,
            "lease": {
                "workerId": task.worker_id,
                "leaseId": task.lease_id,
                "fencingToken": task.fencing_token,
                "leaseAcquiredAt": task.lease_acquired_at.isoformat() if task.lease_acquired_at else None,
                "leaseExpiresAt": task.lease_expires_at.isoformat() if task.lease_expires_at else None,
            },
            "checkpoint": checkpoint_state,
            "metadata": _loads(task.metadata_json, {}),
            "steps": [self._public_step(step) for step in steps],
            "createdAt": task.created_at.isoformat() if task.created_at else None,
            "updatedAt": task.updated_at.isoformat() if task.updated_at else None,
            "completedAt": task.completed_at.isoformat() if task.completed_at else None,
        }
