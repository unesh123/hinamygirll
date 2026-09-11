from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
import re
from typing import TYPE_CHECKING, Any

from .contracts import (
    AgentPlan,
    AgentRun,
    IntentResult,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
    VerificationResult,
    validate_run_transition,
    validate_step_transition,
)
from .context import ContextBuilder
from .events import EventLog
from .intent import IntentInterpreter
from .validation import PlanValidator
from .retry import is_retryable, FailureCategory
from .scheduler import StepScheduler
from .verifier import AgentVerifier

if TYPE_CHECKING:
    from .persistence import AgentPersistenceService


def _sanitize_value(val: Any, key: str | None = None) -> Any:
    if isinstance(val, str):
        if key and re.search(r"(?i)\b(api[_-]?key|access[_-]?token|secret|password)\b", key):
            return "[REDACTED]"
        if key and re.search(r"(?i)\b(auth|authorization)\b", key):
            if re.match(r"(?i)^\s*bearer\s+", val):
                return "Bearer [REDACTED]"
            return "[REDACTED]"
        v = re.sub(r"(?i)(api[_-]?key|access[_-]?token|authorization|secret|password)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", val)
        v = re.sub(r"(?i)\bBearer\s+[A-Za-z0-9._~+/-]+=*", "Bearer [REDACTED]", v)
        v = re.sub(r"(?i)\b(?:sk|key|token|bearer|secret)[-_][A-Za-z0-9._-]{6,}", "[REDACTED]", v)
        return v
    elif isinstance(val, dict):
        return {k: _sanitize_value(v, k) for k, v in val.items()}
    elif isinstance(val, list):
        return [_sanitize_value(item) for item in val]
    return val


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {k: _sanitize_value(v, k) for k, v in payload.items()}


class AgentRuntime:
    """Single bounded runtime boundary; tool execution remains external."""

    def __init__(
        self,
        *,
        executor: Callable[[PlanStep], Awaitable[Any]] | None = None,
        max_steps: int = 12,
        max_replans: int = 2,
        step_attempts: int = 2,
        run_timeout: float = 300,
        enabled: bool = True,
        allowed_tools: set[str] | None = None,
        persistence: AgentPersistenceService | None = None,
    ):
        self.enabled = enabled
        self.max_steps = max_steps
        self.max_replans = max_replans
        self.step_attempts = step_attempts
        self.run_timeout = run_timeout
        self.executor = executor
        self.persistence = persistence
        self.context_builder = ContextBuilder()
        self.interpreter = IntentInterpreter()
        self.validator = PlanValidator(max_steps, allowed_tools=allowed_tools)
        self.scheduler = StepScheduler()
        self.verifier = AgentVerifier()
        self.runs: dict[str, AgentRun] = {}
        self.plans: dict[str, AgentPlan] = {}
        self.events: dict[str, EventLog] = {}

    def create_run(
        self,
        goal: str,
        user_id: str,
        conversation_id: str | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
    ) -> AgentRun:
        run_data = {"run_id": run_id} if run_id else {}
        run = AgentRun(
            **run_data,
            user_id=user_id,
            goal=goal,
            conversation_id=conversation_id,
            project_id=project_id,
            maximum_steps=self.max_steps,
            maximum_replans=self.max_replans,
        )
        self.runs[run.run_id] = run
        self.events[run.run_id] = EventLog(run.run_id, conversation_id)
        if self.persistence:
            self.persistence.save_run(run)
        self._emit(run.run_id, "agent.run.created", payload={"goal": goal[:500]})
        return run

    def _emit(self, run_id: str, event_type: str, step_id: str | None = None, payload: dict | None = None) -> Any:
        if run_id not in self.events:
            self.events[run_id] = EventLog(run_id)
            if self.persistence:
                db_events = self.persistence.get_events(run_id)
                for de in db_events:
                    self.events[run_id]._events.append(de)
        safe = _sanitize_payload(payload or {})
        event = self.events[run_id].emit(event_type, step_id=step_id, payload=safe)
        if self.persistence:
            self.persistence.save_event(
                run_id,
                sequence=event.sequence,
                event_type=event_type,
                step_id=step_id,
                payload=safe,
            )
        return event

    def begin_stream_turn(self, run: AgentRun) -> tuple[AgentPlan, PlanStep, list[Any]]:
        """Start a chat/voice turn through the durable runtime lifecycle."""
        events: list[Any] = []
        if run.status == RunStatus.QUEUED:
            validate_run_transition(run.status, RunStatus.UNDERSTANDING)
            run.status = RunStatus.UNDERSTANDING
            run.started_at = datetime.now(timezone.utc)
            run.updated_at = datetime.now(timezone.utc)
            if self.persistence:
                self.persistence.save_run(run)
            events.append(self._emit(run.run_id, "agent.run.started", payload={"goal": run.goal[:500]}))

        validate_run_transition(run.status, RunStatus.PLANNING)
        run.status = RunStatus.PLANNING
        run.updated_at = datetime.now(timezone.utc)
        if self.persistence:
            self.persistence.save_run(run)
        events.append(self._emit(run.run_id, "agent.planning.started"))

        step = PlanStep(
            plan_id="pending",
            sequence=0,
            title="Generate assistant response",
            description="Stream the assistant response through the selected provider.",
            operation_type=OperationType.RESPOND,
            maximum_attempts=self.step_attempts,
        )
        plan = AgentPlan(run_id=run.run_id, goal=run.goal, steps=[step])
        step.plan_id = plan.plan_id
        self.validator.validate(plan)
        self.plans[plan.plan_id] = plan
        run.total_steps = len(plan.steps)
        if self.persistence:
            self.persistence.save_plan(plan)
            self.persistence.save_run(run)
        events.append(
            self._emit(
                run.run_id,
                "agent.plan.ready",
                payload={"planId": plan.plan_id, "stepCount": len(plan.steps)},
            )
        )

        validate_run_transition(run.status, RunStatus.EXECUTING)
        run.status = RunStatus.EXECUTING
        validate_step_transition(step.status, StepState.READY)
        step.status = StepState.READY
        validate_step_transition(step.status, StepState.RUNNING)
        step.status = StepState.RUNNING
        step.started_at = datetime.now(timezone.utc)
        step.attempt_count = 1
        run.current_step_id = step.step_id
        run.updated_at = datetime.now(timezone.utc)
        if self.persistence:
            self.persistence.save_step(step)
            self.persistence.save_run(run)
        events.append(
            self._emit(
                run.run_id,
                "agent.step.started",
                step_id=step.step_id,
                payload={"title": step.title, "sequence": step.sequence, "totalSteps": run.total_steps},
            )
        )
        return plan, step, events

    def complete_stream_turn(
        self,
        run: AgentRun,
        plan: AgentPlan,
        step: PlanStep,
        *,
        result: Any = None,
    ) -> list[Any]:
        events: list[Any] = []
        if step.status == StepState.RUNNING:
            validate_step_transition(step.status, StepState.COMPLETED)
            step.status = StepState.COMPLETED
            step.completed_at = datetime.now(timezone.utc)
            step.result = result
            run.completed_steps = max(run.completed_steps, 1)
            if self.persistence:
                self.persistence.save_step(step)
                self.persistence.save_run(run)
            events.append(
                self._emit(
                    run.run_id,
                    "agent.step.completed",
                    step_id=step.step_id,
                    payload={"title": step.title, "sequence": step.sequence, "totalSteps": run.total_steps},
                )
            )

        if run.status == RunStatus.EXECUTING:
            validate_run_transition(run.status, RunStatus.VERIFYING)
            run.status = RunStatus.VERIFYING
            run.updated_at = datetime.now(timezone.utc)
            if self.persistence:
                self.persistence.save_run(run)
            events.append(self._emit(run.run_id, "agent.verification.started"))
            verification = self.verifier.verify_run(run, plan)
            events.append(
                self._emit(
                    run.run_id,
                    "agent.verification.completed",
                    payload=verification.model_dump(),
                )
            )
            final_status = RunStatus.COMPLETED if verification.valid else RunStatus.FAILED
            validate_run_transition(run.status, final_status)
            run.status = final_status
            if not verification.valid:
                run.failure_code = verification.failure_code or "verification_failed"
                run.failure_message = "; ".join(verification.issues)

        run.completed_at = (
            datetime.now(timezone.utc)
            if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
            else None
        )
        run.updated_at = datetime.now(timezone.utc)
        if self.persistence:
            self.persistence.save_run(run)
        terminal_type = "agent.run.completed" if run.status == RunStatus.COMPLETED else "agent.run.failed"
        events.append(
            self._emit(
                run.run_id,
                terminal_type,
                payload={"status": run.status.value, "failureCode": run.failure_code},
            )
        )
        return events

    def fail_stream_turn(
        self,
        run: AgentRun,
        *,
        step: PlanStep | None = None,
        code: str = "STREAM_ERROR",
        message: str = "Agent stream failed.",
    ) -> list[Any]:
        events: list[Any] = []
        if step is not None and step.status == StepState.RUNNING:
            validate_step_transition(step.status, StepState.FAILED)
            step.status = StepState.FAILED
            step.error_code = code
            step.error_message = message[:500]
            if self.persistence:
                self.persistence.save_step(step)
            events.append(
                self._emit(
                    run.run_id,
                    "agent.step.failed",
                    step_id=step.step_id,
                    payload={"code": code, "message": step.error_message},
                )
            )
        if run.status not in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            validate_run_transition(run.status, RunStatus.FAILED)
            run.status = RunStatus.FAILED
        run.failure_code = code
        run.failure_message = message[:500]
        run.completed_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)
        if self.persistence:
            self.persistence.save_run(run)
        events.append(
            self._emit(
                run.run_id,
                "agent.run.failed",
                payload={"code": code, "message": run.failure_message},
            )
        )
        return events

    def _check_user(self, run: AgentRun | None, user_id: str | set[str] | list[str]) -> bool:
        if run is None:
            return False
        allowed = {user_id} if isinstance(user_id, str) else set(user_id)
        return run.user_id in allowed

    def get_run(self, run_id: str, user_id: str | set[str] | list[str]) -> AgentRun | None:
        if run_id not in self.runs and self.persistence:
            persisted = self.persistence.get_run(run_id)
            if persisted:
                self.runs[run_id] = persisted
        run = self.runs.get(run_id)
        if not self._check_user(run, user_id):
            return None
        return run

    def get_plan(self, run_id: str) -> AgentPlan | None:
        plan = next((p for p in self.plans.values() if p.run_id == run_id), None)
        if plan is None and self.persistence:
            plan = self.persistence.get_plan_by_run(run_id)
            if plan:
                self.plans[plan.plan_id] = plan
        return plan

    def get_steps(self, run_id: str, user_id: str | set[str] | list[str]) -> list[PlanStep] | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        plan = self.get_plan(run_id)
        return list(plan.steps) if plan else []

    def get_events(self, run_id: str, user_id: str | set[str] | list[str]) -> list[Any] | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        if run_id not in self.events and self.persistence:
            db_events = self.persistence.get_events(run_id)
            if db_events:
                log = EventLog(run_id, run.conversation_id)
                log._events = list(db_events)
                self.events[run_id] = log
                return db_events
        log = self.events.get(run_id)
        return list(log.events) if log else []

    def cancel(self, run_id: str, user_id: str | set[str] | list[str]) -> AgentRun | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        if run.status not in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            run.cancellation_requested = True
            validate_run_transition(run.status, RunStatus.CANCELLED)
            run.status = RunStatus.CANCELLED
            run.updated_at = datetime.now(timezone.utc)
            self._emit(run_id, "agent.run.cancelled", payload={"reason": "user"})
            self._emit(run_id, "turn.cancelled", payload={"reason": "user"})
            if self.persistence:
                self.persistence.save_run(run)
        return run

    def resume(self, run_id: str, user_id: str | set[str] | list[str]) -> AgentRun | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        if run.status == RunStatus.INTERRUPTED:
            plan = self.get_plan(run_id)
            if plan:
                for step in plan.steps:
                    if step.status == StepState.INTERRUPTED:
                        if step.operation_type == OperationType.TOOL and step.tool_parameters.get("idempotent") is False:
                            validate_step_transition(step.status, StepState.AWAITING_CONFIRMATION)
                            step.status = StepState.AWAITING_CONFIRMATION
                        else:
                            validate_step_transition(step.status, StepState.READY)
                            step.status = StepState.READY
                        if self.persistence:
                            self.persistence.save_step(step)
            validate_run_transition(run.status, RunStatus.EXECUTING)
            run.status = RunStatus.EXECUTING
            run.updated_at = datetime.now(timezone.utc)
            self._emit(run_id, "agent.step.progress", payload={"action": "resumed"})
            self._emit(run_id, "step.progress", payload={"action": "resumed"})
            if self.persistence:
                self.persistence.save_run(run)
        return run

    def confirm(self, run_id: str, step_id: str, user_id: str | set[str] | list[str], approved: bool) -> AgentRun | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        plan = self.get_plan(run_id)
        if plan is None:
            return None
        step = next((s for s in plan.steps if s.step_id == step_id), None)
        if step is None:
            return None
        if not approved:
            step.status = StepState.CANCELLED
            run.status = RunStatus.CANCELLED
            self._emit(run_id, "agent.run.cancelled", step_id=step_id, payload={"reason": "rejected"})
            self._emit(run_id, "turn.cancelled", step_id=step_id, payload={"reason": "rejected"})
            if self.persistence:
                self.persistence.save_step(step)
                self.persistence.save_run(run)
            return run
        if step.status == StepState.AWAITING_CONFIRMATION:
            step.status = StepState.READY
            run.status = RunStatus.EXECUTING
            self._emit(run_id, "agent.step.progress", step_id=step_id, payload={"action": "confirmed"})
            self._emit(run_id, "step.progress", step_id=step_id, payload={"action": "confirmed"})
            if self.persistence:
                self.persistence.save_step(step)
                self.persistence.save_run(run)
        return run

    def recover(self, run_id: str, user_id: str | set[str] | list[str]) -> AgentRun | None:
        run = self.get_run(run_id, user_id)
        if run is None:
            return None
        plan = self.get_plan(run_id)
        from .recovery import recover_run
        recover_run(run, plan)
        if self.persistence:
            self.persistence.save_run(run)
            if plan:
                for step in plan.steps:
                    self.persistence.save_step(step)
        self._emit(run_id, "agent.run.recovered", payload={"status": run.status.value})
        return run

    async def execute(
        self,
        run: AgentRun,
        *,
        plan: AgentPlan | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
        attachments: list[str] | None = None,
    ) -> AgentRun:
        if not self.enabled:
            return run

        async def _run() -> None:
            if run.cancellation_requested or run.status == RunStatus.CANCELLED:
                run.status = RunStatus.CANCELLED
                if self.persistence:
                    self.persistence.save_run(run)
                return

            if run.status == RunStatus.QUEUED:
                validate_run_transition(run.status, RunStatus.UNDERSTANDING)
                run.status = RunStatus.UNDERSTANDING
                run.started_at = datetime.now(timezone.utc)
                if self.persistence:
                    self.persistence.save_run(run)
                context = self.context_builder.build(
                    run.goal, recent_messages=recent_messages, attachments=attachments, user_id=run.user_id
                )
                self._emit(run.run_id, "agent.context.ready", payload={"tokenEstimate": context.token_estimate})
                self._emit(run.run_id, "context.ready", payload={"tokenEstimate": context.token_estimate})
                intent: IntentResult = self.interpreter.interpret(run.goal, context)
                self._emit(run.run_id, "agent.intent.ready", payload=intent.model_dump())
                self._emit(run.run_id, "intent.ready", payload=intent.model_dump())

                if run.cancellation_requested or run.status == RunStatus.CANCELLED:
                    validate_run_transition(run.status, RunStatus.CANCELLED)
                    run.status = RunStatus.CANCELLED
                    if self.persistence:
                        self.persistence.save_run(run)
                    return

                validate_run_transition(run.status, RunStatus.PLANNING)
                run.status = RunStatus.PLANNING
                if self.persistence:
                    self.persistence.save_run(run)
                exec_plan = plan or self._plan_from_intent(run, intent)
                self.validator.validate(exec_plan)
                self.plans[exec_plan.plan_id] = exec_plan
                run.total_steps = len(exec_plan.steps)
                if self.persistence:
                    self.persistence.save_plan(exec_plan)
                    self.persistence.save_run(run)
                self._emit(
                    run.run_id,
                    "agent.plan.ready",
                    payload={"planId": exec_plan.plan_id, "stepCount": len(exec_plan.steps)},
                )
                self._emit(
                    run.run_id,
                    "plan.ready",
                    payload={"planId": exec_plan.plan_id, "stepCount": len(exec_plan.steps)},
                )

                if run.cancellation_requested or run.status == RunStatus.CANCELLED:
                    validate_run_transition(run.status, RunStatus.CANCELLED)
                    run.status = RunStatus.CANCELLED
                    if self.persistence:
                        self.persistence.save_run(run)
                    return

                validate_run_transition(run.status, RunStatus.EXECUTING)
                run.status = RunStatus.EXECUTING
                if self.persistence:
                    self.persistence.save_run(run)
            else:
                exec_plan = plan or self.get_plan(run.run_id)
                if exec_plan is None:
                    raise ValueError(f"No plan found for resumed run {run.run_id}")

            while True:
                if run.cancellation_requested:
                    validate_run_transition(run.status, RunStatus.CANCELLED)
                    run.status = RunStatus.CANCELLED
                    if self.persistence:
                        self.persistence.save_run(run)
                    break

                step = self.scheduler.next_ready(run, exec_plan)
                if step is None:
                    if any(s.status == StepState.AWAITING_CONFIRMATION for s in exec_plan.steps):
                        validate_run_transition(run.status, RunStatus.AWAITING_CONFIRMATION)
                        run.status = RunStatus.AWAITING_CONFIRMATION
                        if self.persistence:
                            self.persistence.save_run(run)
                        break
                    if any(s.status == StepState.BLOCKED for s in exec_plan.steps):
                        validate_run_transition(run.status, RunStatus.FAILED)
                        run.status = RunStatus.FAILED
                        run.failure_code = "step_blocked"
                        run.failure_message = "Step execution blocked due to dependency failure"
                        if self.persistence:
                            self.persistence.save_run(run)
                        break
                    break

                validate_step_transition(step.status, StepState.RUNNING)
                step.status = StepState.RUNNING
                step.attempt_count += 1
                run.current_step_id = step.step_id
                if self.persistence:
                    self.persistence.save_step(step)
                    self.persistence.save_run(run)
                self._emit(run.run_id, "agent.step.started", step_id=step.step_id, payload={"title": step.title})
                self._emit(run.run_id, "step.started", step_id=step.step_id, payload={"title": step.title})

                while True:
                    if step.status != StepState.RUNNING:
                        validate_step_transition(step.status, StepState.RUNNING)
                        step.status = StepState.RUNNING
                        if self.persistence:
                            self.persistence.save_step(step)
                    try:
                        if self.executor is None:
                            raise RuntimeError("No runtime executor configured")
                        step.result = await asyncio.wait_for(
                            self.executor(step), timeout=step.timeout_seconds
                        )
                        validate_step_transition(step.status, StepState.COMPLETED)
                        step.status = StepState.COMPLETED
                        step.completed_at = datetime.now(timezone.utc)
                        run.completed_steps += 1
                        if self.persistence:
                            self.persistence.save_step(step)
                            self.persistence.save_run(run)
                        self._emit(
                            run.run_id,
                            "agent.step.completed",
                            step_id=step.step_id,
                            payload={"result": step.result if isinstance(step.result, (dict, list, str, int, float, bool)) else None},
                        )
                        self._emit(
                            run.run_id,
                            "step.completed",
                            step_id=step.step_id,
                            payload={"result": step.result if isinstance(step.result, (dict, list, str, int, float, bool)) else None},
                        )
                        break
                    except asyncio.CancelledError:
                        validate_step_transition(step.status, StepState.CANCELLED)
                        step.status = StepState.CANCELLED
                        validate_run_transition(run.status, RunStatus.CANCELLED)
                        run.status = RunStatus.CANCELLED
                        if self.persistence:
                            self.persistence.save_step(step)
                            self.persistence.save_run(run)
                        raise
                    except Exception as error:
                        err_str = str(error)
                        transient = is_retryable(error) or "transient" in err_str.lower() or "timeout" in err_str.lower()
                        if transient and step.attempt_count < step.maximum_attempts:
                            step.attempt_count += 1
                            validate_step_transition(step.status, StepState.FAILED)
                            step.status = StepState.FAILED
                            validate_step_transition(step.status, StepState.READY)
                            step.status = StepState.READY
                            if self.persistence:
                                self.persistence.save_step(step)
                            self._emit(run.run_id, "agent.step.retrying", step_id=step.step_id, payload={"attempt": step.attempt_count})
                            self._emit(run.run_id, "step.retrying", step_id=step.step_id, payload={"attempt": step.attempt_count})
                            continue
                        validate_step_transition(step.status, StepState.FAILED)
                        step.status = StepState.FAILED
                        step.error_message = err_str[:500]
                        if hasattr(error, "code"):
                            step.error_code = str(error.code)
                        if self.persistence:
                            self.persistence.save_step(step)
                        self._emit(
                            run.run_id,
                            "agent.step.failed",
                            step_id=step.step_id,
                            payload={"error": step.error_message, "code": step.error_code},
                        )
                        self._emit(
                            run.run_id,
                            "step.failed",
                            step_id=step.step_id,
                            payload={"error": step.error_message, "code": step.error_code},
                        )
                        validate_run_transition(run.status, RunStatus.FAILED)
                        run.status = RunStatus.FAILED
                        run.failure_code = getattr(error, "code", None) or "step_failed"
                        run.failure_message = step.error_message
                        if self.persistence:
                            self.persistence.save_run(run)
                        break

                if run.status in {RunStatus.FAILED, RunStatus.CANCELLED}:
                    break

            if run.status == RunStatus.EXECUTING:
                validate_run_transition(run.status, RunStatus.VERIFYING)
                run.status = RunStatus.VERIFYING
                if self.persistence:
                    self.persistence.save_run(run)
                self._emit(run.run_id, "agent.verification.started")
                self._emit(run.run_id, "verification.started")
                verification = self.verifier.verify_run(run, exec_plan)
                self._emit(run.run_id, "agent.verification.completed", payload=verification.model_dump())
                self._emit(run.run_id, "verification.completed", payload=verification.model_dump())
                final_status = RunStatus.COMPLETED if verification.valid else RunStatus.FAILED
                validate_run_transition(run.status, final_status)
                run.status = final_status
                if not verification.valid:
                    run.failure_code = verification.failure_code or "verification_failed"
                    run.failure_message = "; ".join(verification.issues)
                if self.persistence:
                    self.persistence.save_run(run)

            run.completed_at = (
                datetime.now(timezone.utc)
                if run.status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}
                else None
            )
            run.updated_at = datetime.now(timezone.utc)
            if self.persistence:
                self.persistence.save_run(run)
            if run.status == RunStatus.COMPLETED:
                self._emit(run.run_id, "agent.run.completed", payload={"status": run.status.value})
            elif run.status == RunStatus.FAILED:
                self._emit(
                    run.run_id,
                    "agent.run.failed",
                    payload={"code": run.failure_code, "message": run.failure_message},
                )
            elif run.status == RunStatus.CANCELLED:
                self._emit(run.run_id, "agent.run.cancelled", payload={"reason": "cancelled"})

        try:
            await asyncio.wait_for(_run(), timeout=self.run_timeout)
        except asyncio.TimeoutError:
            run.status = RunStatus.FAILED
            run.failure_code = "run_timeout"
            run.failure_message = "Agent run timed out."
            if self.persistence:
                self.persistence.save_run(run)
            self._emit(run.run_id, "agent.run.failed", payload={"code": run.failure_code})
            self._emit(run.run_id, "turn.failed", payload={"code": run.failure_code})

        return run

    def _plan_from_intent(self, run: AgentRun, intent: IntentResult) -> AgentPlan:
        operation = (
            OperationType.RESPOND if intent.primary_intent == "conversation" else OperationType.SUMMARIZE
        )
        step = PlanStep(
            plan_id="pending",
            sequence=0,
            title="Respond to user",
            description=intent.requested_outcome,
            operation_type=operation,
            maximum_attempts=self.step_attempts,
        )
        plan = AgentPlan(run_id=run.run_id, goal=run.goal, steps=[step])
        step.plan_id = plan.plan_id
        return plan
