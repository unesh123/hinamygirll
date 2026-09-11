from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session, sessionmaker

from .contracts import (
    AgentEvent,
    AgentPlan,
    AgentRun,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
)
from ..persistence.orm import (
    AgentRunRecord,
    AgentPlanRecord,
    AgentStepRecord,
    AgentEventRecord,
)


class AgentPersistenceService:
    """Durable relational persistence backing store for the Agent Runtime.
    
    Ensures that runs, plans, steps, and event histories survive server/process restarts.
    """

    def __init__(self, session_factory: sessionmaker[Session]):
        self._factory = session_factory

    def save_run(self, run: AgentRun) -> None:
        with self._factory() as session:
            rec = session.query(AgentRunRecord).filter_by(run_id=run.run_id).first()
            if rec is None:
                rec = AgentRunRecord(
                    run_id=run.run_id,
                    user_id=run.user_id,
                    conversation_id=run.conversation_id,
                    project_id=run.project_id,
                    goal=run.goal,
                    status=run.status.value,
                    failure_code=run.failure_code,
                    failure_reason=run.failure_message,
                    maximum_steps=run.maximum_steps,
                    maximum_replans=run.maximum_replans,
                    replan_count=run.replan_count,
                    created_at=run.created_at,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                    cancelled_at=datetime.now(timezone.utc) if run.cancellation_requested else None,
                    metadata_json=json.dumps({"cancellation_requested": run.cancellation_requested}),
                )
                session.add(rec)
            else:
                rec.status = run.status.value
                rec.failure_code = run.failure_code
                rec.failure_reason = run.failure_message
                rec.replan_count = run.replan_count
                rec.started_at = run.started_at
                rec.completed_at = run.completed_at
                if run.cancellation_requested and not rec.cancelled_at:
                    rec.cancelled_at = datetime.now(timezone.utc)
                rec.metadata_json = json.dumps({"cancellation_requested": run.cancellation_requested})
            session.commit()

    def get_run(self, run_id: str) -> AgentRun | None:
        with self._factory() as session:
            rec = session.query(AgentRunRecord).filter_by(run_id=run_id).first()
            if not rec:
                return None
            return AgentRun(
                run_id=rec.run_id,
                user_id=rec.user_id,
                conversation_id=rec.conversation_id,
                project_id=rec.project_id,
                goal=rec.goal,
                status=RunStatus(rec.status),
                failure_code=rec.failure_code,
                failure_message=rec.failure_reason,
                maximum_steps=rec.maximum_steps,
                maximum_replans=rec.maximum_replans,
                replan_count=rec.replan_count,
                created_at=rec.created_at,
                started_at=rec.started_at,
                completed_at=rec.completed_at,
                cancellation_requested=(RunStatus(rec.status) == RunStatus.CANCELLED or rec.cancelled_at is not None),
            )

    def save_plan(self, plan: AgentPlan) -> None:
        with self._factory() as session:
            rec = session.query(AgentPlanRecord).filter_by(plan_id=plan.plan_id).first()
            if rec is None:
                rec = AgentPlanRecord(
                    plan_id=plan.plan_id,
                    run_id=plan.run_id,
                    goal=plan.goal,
                    version=plan.version,
                    created_at=plan.created_at,
                )
                session.add(rec)
            else:
                rec.goal = plan.goal
                rec.version = plan.version
            session.commit()
            
        for step in plan.steps:
            self.save_step(step)

    def get_plan(self, plan_id: str) -> AgentPlan | None:
        with self._factory() as session:
            rec = session.query(AgentPlanRecord).filter_by(plan_id=plan_id).first()
            if not rec:
                return None
            steps = self.get_steps_for_plan(plan_id)
            return AgentPlan(
                plan_id=rec.plan_id,
                run_id=rec.run_id,
                goal=rec.goal,
                version=rec.version,
                created_at=rec.created_at,
                steps=steps,
            )

    def get_plan_by_run(self, run_id: str) -> AgentPlan | None:
        with self._factory() as session:
            rec = session.query(AgentPlanRecord).filter_by(run_id=run_id).order_by(AgentPlanRecord.version.desc()).first()
            if not rec:
                return None
            steps = self.get_steps_for_plan(rec.plan_id)
            return AgentPlan(
                plan_id=rec.plan_id,
                run_id=rec.run_id,
                goal=rec.goal,
                version=rec.version,
                created_at=rec.created_at,
                steps=steps,
            )

    def save_step(self, step: PlanStep) -> None:
        with self._factory() as session:
            rec = session.query(AgentStepRecord).filter_by(step_id=step.step_id).first()
            if rec is None:
                rec = AgentStepRecord(
                    step_id=step.step_id,
                    plan_id=step.plan_id,
                    sequence=step.sequence,
                    title=step.title,
                    operation_type=step.operation_type.value if hasattr(step.operation_type, "value") else str(step.operation_type),
                    tool_name=step.tool_name,
                    parameters_json=json.dumps(step.tool_parameters or {}),
                    state=step.status.value if hasattr(step.status, "value") else str(step.status),
                    requires_confirmation=step.requires_confirmation,
                    confirmed_by_user=False,
                    attempt_count=step.attempt_count,
                    max_attempts=step.maximum_attempts,
                    error_message=step.error_message,
                    dependencies_json=json.dumps(step.dependencies or []),
                    created_at=datetime.now(timezone.utc),
                    completed_at=step.completed_at,
                )
                session.add(rec)
            else:
                rec.state = step.status.value if hasattr(step.status, "value") else str(step.status)
                rec.attempt_count = step.attempt_count
                rec.error_message = step.error_message
                rec.completed_at = step.completed_at
                rec.parameters_json = json.dumps(step.tool_parameters or {})
            session.commit()

    def get_steps_for_plan(self, plan_id: str) -> list[PlanStep]:
        with self._factory() as session:
            recs = (
                session.query(AgentStepRecord)
                .filter_by(plan_id=plan_id)
                .order_by(AgentStepRecord.sequence.asc())
                .all()
            )
            steps = []
            for r in recs:
                params = {}
                deps = []
                try:
                    params = json.loads(r.parameters_json or "{}")
                except Exception:
                    pass
                try:
                    deps = json.loads(r.dependencies_json or "[]")
                except Exception:
                    pass
                steps.append(
                    PlanStep(
                        step_id=r.step_id,
                        plan_id=r.plan_id,
                        sequence=r.sequence,
                        title=r.title,
                        description="",
                        operation_type=OperationType(r.operation_type),
                        tool_name=r.tool_name,
                        tool_parameters=params,
                        status=StepState(r.state),
                        requires_confirmation=r.requires_confirmation,
                        attempt_count=r.attempt_count,
                        maximum_attempts=r.max_attempts,
                        error_message=r.error_message,
                        dependencies=deps,
                        completed_at=r.completed_at,
                    )
                )
            return steps

    def save_event(self, run_id: str, sequence: int, event_type: str, step_id: str | None = None, payload: dict | None = None) -> None:
        with self._factory() as session:
            rec = AgentEventRecord(
                run_id=run_id,
                sequence=sequence,
                event_type=event_type,
                step_id=step_id,
                payload_json=json.dumps(payload or {}),
                timestamp=datetime.now(timezone.utc),
            )
            session.add(rec)
            session.commit()

    def get_events(self, run_id: str) -> list[AgentEvent]:
        with self._factory() as session:
            recs = (
                session.query(AgentEventRecord)
                .filter_by(run_id=run_id)
                .order_by(AgentEventRecord.sequence.asc())
                .all()
            )
            events = []
            for r in recs:
                payload = {}
                try:
                    payload = json.loads(r.payload_json or "{}")
                except Exception:
                    pass
                events.append(
                    AgentEvent(
                        event_id=r.id,
                        run_id=r.run_id,
                        sequence=r.sequence,
                        event_type=r.event_type,
                        step_id=r.step_id,
                        payload=payload,
                        timestamp=r.timestamp or datetime.now(timezone.utc),
                    )
                )
            return events

    def list_active_runs(self) -> list[AgentRun]:
        with self._factory() as session:
            active_statuses = [
                RunStatus.QUEUED.value,
                RunStatus.UNDERSTANDING.value,
                RunStatus.PLANNING.value,
                RunStatus.EXECUTING.value,
                RunStatus.VERIFYING.value,
            ]
            recs = (
                session.query(AgentRunRecord)
                .filter(AgentRunRecord.status.in_(active_statuses))
                .all()
            )
            runs = []
            for rec in recs:
                runs.append(
                    AgentRun(
                        run_id=rec.run_id,
                        user_id=rec.user_id,
                        conversation_id=rec.conversation_id,
                        project_id=rec.project_id,
                        goal=rec.goal,
                        status=RunStatus(rec.status),
                        failure_code=rec.failure_code,
                        failure_message=rec.failure_reason,
                        maximum_steps=rec.maximum_steps,
                        maximum_replans=rec.maximum_replans,
                        replan_count=rec.replan_count,
                        created_at=rec.created_at,
                        started_at=rec.started_at,
                        completed_at=rec.completed_at,
                        cancellation_requested=(RunStatus(rec.status) == RunStatus.CANCELLED or rec.cancelled_at is not None),
                    )
                )
            return runs
