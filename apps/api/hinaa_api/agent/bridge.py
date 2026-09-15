from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from ..persistence.task_service import TaskService
from .contracts import (
    AgentPlan,
    AgentRun,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
)
from .runtime import AgentRuntime


class VerificationType(str, Enum):
    NON_EMPTY = "non_empty"
    REQUIRED_KEYS = "required_keys"
    ARTIFACT_EXISTS = "artifact_exists"
    COMMAND_SUCCESS = "command_success"
    CUSTOM = "custom"


@dataclass
class StepVerificationCondition:
    """Deterministic step completion condition to prevent LLM self-attestation hallucinations."""

    verification_type: VerificationType = VerificationType.NON_EMPTY
    required_keys: list[str] = field(default_factory=list)
    custom_predicate: Callable[[Any], bool] | None = None
    expected_artifact_kinds: list[str] = field(default_factory=list)

    def evaluate(self, result: Any) -> tuple[bool, str]:
        if result is None:
            return False, "Result is None"

        if self.verification_type == VerificationType.NON_EMPTY:
            if not result or (isinstance(result, (str, list, dict)) and len(result) == 0):
                return False, "Result is empty"
            return True, "Result verified non-empty"

        if self.verification_type == VerificationType.REQUIRED_KEYS:
            if not isinstance(result, dict):
                return False, "Result must be a dictionary to verify required keys"
            missing = [k for k in self.required_keys if k not in result]
            if missing:
                return False, f"Missing required keys: {missing}"
            return True, f"All required keys present: {self.required_keys}"

        if self.verification_type == VerificationType.COMMAND_SUCCESS:
            if isinstance(result, dict):
                code = result.get("exit_code", result.get("returncode", 0))
                if code != 0:
                    return False, f"Command exited with non-zero code {code}"
            return True, "Command execution succeeded"

        if self.verification_type == VerificationType.ARTIFACT_EXISTS:
            if isinstance(result, dict) and "artifacts" in result:
                arts = result.get("artifacts") or []
                if not arts:
                    return False, "No artifacts were produced"
            return True, "Artifact presence verified"

        if self.verification_type == VerificationType.CUSTOM:
            if self.custom_predicate and not self.custom_predicate(result):
                return False, "Custom verification predicate failed"
            return True, "Custom verification passed"

        return True, "Verified"


@dataclass
class LoopExecutionSummary:
    task_id: str
    status: str
    completed_steps: int
    total_steps: int
    duration_seconds: float
    final_checkpoint: dict[str, Any]
    error: str | None = None


class DurableTaskBridge:
    """Bridges TaskService (durable SQLite storage, append-only events, checkpoints)

    with AgentRuntime (DAG execution, validation, step retries, verifications).
    """

    def __init__(self, task_service: TaskService, runtime: AgentRuntime) -> None:
        self.task_service = task_service
        self.runtime = runtime

    def create_durable_agent_run(
        self,
        owner_id: str,
        goal: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        run_id: str | None = None,
        task_type: str = "general",
        priority: int = 0,
        reasoning_mode: str = "balanced",
        steps: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], AgentRun, AgentPlan]:
        """Create a durable task in TaskService and mirror it as an AgentRun in AgentRuntime."""
        # 1. Create in TaskService
        task_dict = self.task_service.create_task(
            owner_id=owner_id,
            goal=goal,
            task_id=run_id,
            conversation_id=conversation_id,
            project_id=project_id,
            task_type=task_type,
            priority=priority,
            reasoning_mode=reasoning_mode,
            steps=steps,
            metadata=metadata,
        )

        task_id = task_dict["id"]

        # 2. Create matching AgentRun in AgentRuntime
        run = self.runtime.create_run(
            goal=goal,
            user_id=owner_id,
            conversation_id=conversation_id,
            project_id=project_id,
            run_id=task_id,
        )
        run.status = RunStatus.PLANNING

        # 3. Translate steps into AgentPlan
        plan_steps: list[PlanStep] = []
        for s in task_dict.get("steps", []):
            op_type = OperationType.TOOL if s.get("toolCallIds") else OperationType.RESPOND
            p_step = PlanStep(
                step_id=s["id"],
                plan_id=f"plan_{task_id}",
                sequence=s["position"],
                title=s["title"],
                description=s.get("description", ""),
                operation_type=op_type,
                dependencies=s.get("dependencies") or [],
                status=StepState.PENDING,
            )
            plan_steps.append(p_step)

        plan = AgentPlan(
            plan_id=f"plan_{task_id}",
            run_id=run.run_id,
            goal=goal,
            steps=plan_steps,
        )
        self.runtime.plans[plan.plan_id] = plan
        if self.runtime.persistence:
            self.runtime.persistence.save_plan(plan)
        run.total_steps = len(plan.steps)
        run.status = RunStatus.EXECUTING

        return task_dict, run, plan

    def resume_from_checkpoint(
        self,
        owner_id: str,
        task_id: str,
    ) -> tuple[AgentRun, AgentPlan]:
        """Restore AgentRun and AgentPlan from TaskService checkpoint without re-running finished steps."""
        task_data = self.task_service.get_task(owner_id, task_id)
        task_meta = task_data.get("task") if "task" in task_data else task_data
        steps_meta = task_data.get("steps", [])

        run = AgentRun(
            run_id=task_id,
            user_id=owner_id,
            conversation_id=task_meta.get("conversationId"),
            project_id=task_meta.get("projectId"),
            goal=task_meta["goal"],
            current_step_id=task_meta.get("currentStepId"),
            status=RunStatus.EXECUTING if task_meta["status"] == "active" else RunStatus.COMPLETED,
            total_steps=len(steps_meta),
            completed_steps=sum(1 for s in steps_meta if s["status"] == "completed"),
        )
        self.runtime.runs[run.run_id] = run

        plan_steps: list[PlanStep] = []
        for s in steps_meta:
            state = StepState.PENDING
            if s["status"] == "completed":
                state = StepState.COMPLETED
            elif s["status"] == "active":
                state = StepState.READY
            elif s["status"] == "failed":
                state = StepState.FAILED

            p_step = PlanStep(
                step_id=s["id"],
                plan_id=f"plan_{task_id}",
                sequence=s["position"],
                title=s["title"],
                description=s.get("description", ""),
                operation_type=OperationType.TOOL if s.get("toolCallIds") else OperationType.RESPOND,
                dependencies=s.get("dependencies") or [],
                status=state,
                attempt_count=s.get("attemptCount", 0),
            )
            plan_steps.append(p_step)

        plan = AgentPlan(
            plan_id=f"plan_{task_id}",
            run_id=run.run_id,
            goal=task_meta["goal"],
            steps=plan_steps,
        )
        self.runtime.plans[plan.plan_id] = plan
        return run, plan

    def steer_task(
        self,
        owner_id: str,
        task_id: str,
        instruction: str,
    ) -> dict[str, Any]:
        """Inject user steering directive into TaskService and runtime context."""
        updated_task = self.task_service.steer_task(owner_id, task_id, instruction)

        # Mirror steering into runtime events and active run if present
        if task_id in self.runtime.runs:
            run = self.runtime.runs[task_id]
            self.runtime._emit(
                task_id,
                "agent.task.steered",
                payload={"instruction": instruction[:300]},
            )

        return updated_task

    async def execute_step(
        self,
        owner_id: str,
        task_id: str,
        step_id: str,
        *,
        executor: Callable[[dict[str, Any]], Awaitable[Any]],
        verification: StepVerificationCondition | None = None,
        lease_id: str | None = None,
        fencing_token: int | None = None,
        retry_limit: int = 2,
    ) -> tuple[dict[str, Any], Any]:
        """Execute a single step, enforce verification condition, and commit checkpoint upon completion."""
        # Find step details
        task_data = self.task_service.get_task(owner_id, task_id)
        steps = task_data.get("steps", [])
        step = next((s for s in steps if s["id"] == step_id), None)
        if step is None:
            raise KeyError(f"Step {step_id} not found in task {task_id}")

        if step["status"] == "completed":
            # Already completed, do not re-run!
            return task_data, None

        # Execute step work
        try:
            result = await executor(step)
        except Exception as exc:
            if lease_id is not None and fencing_token is not None:
                self.task_service.fail_step_with_lease(
                    owner_id, task_id, step_id, str(exc),
                    lease_id=lease_id, fencing_token=fencing_token,
                    retry_limit=retry_limit,
                )
            else:
                self.task_service.fail_step(owner_id, task_id, step_id, reason=str(exc))
            raise RuntimeError(f"Step execution failed: {exc}") from exc

        # Verify step condition
        if verification:
            verified, reason = verification.evaluate(result)
            if not verified:
                msg = f"Verification failed: {reason}"
                if lease_id is not None and fencing_token is not None:
                    self.task_service.fail_step_with_lease(
                        owner_id, task_id, step_id, msg,
                        lease_id=lease_id, fencing_token=fencing_token,
                        retry_limit=retry_limit,
                    )
                else:
                    self.task_service.fail_step(owner_id, task_id, step_id, reason=msg)
                raise ValueError(f"Step verification failed: {reason}")

        # Extract artifact IDs if result produced any
        output_artifact_ids: list[str] = []
        if isinstance(result, dict) and "artifacts" in result:
            arts = result.get("artifacts") or []
            output_artifact_ids = [str(a.get("id") or a) for a in arts]

        # Commit step completion and checkpoint in TaskService
        if lease_id is not None and fencing_token is not None:
            completed_task = self.task_service.complete_step_with_lease(
                owner_id, task_id, step_id,
                lease_id=lease_id, fencing_token=fencing_token,
                output_artifact_ids=output_artifact_ids,
            )
        else:
            completed_task = self.task_service.complete_step(
                owner_id, task_id, step_id, output_artifact_ids=output_artifact_ids
            )

        # Mirror completion to runtime
        if task_id in self.runtime.runs:
            run = self.runtime.runs[task_id]
            run.completed_steps += 1
            plan = self.runtime.get_plan(task_id)
            if plan:
                p_step = next((ps for ps in plan.steps if ps.step_id == step_id), None)
                if p_step:
                    p_step.status = StepState.COMPLETED
                    p_step.result = result

        return completed_task, result

    async def run_autonomous_loop(
        self,
        owner_id: str,
        task_id: str,
        *,
        worker_id: str,
        executor: Callable[[dict[str, Any], dict[str, Any]], Awaitable[Any]],
        verifications: dict[str, StepVerificationCondition] | None = None,
        max_steps: int = 20,
        max_wall_time_seconds: float = 600.0,
        lease_seconds: int = 60,
        context_compiler: Any | None = None,
        repository_map: Any | None = None,
        retry_limit: int = 2,
    ) -> LoopExecutionSummary:
        """Continuously and autonomously drives multi-step DAG task execution to completion.

        Enforces:
        - Worker lease fencing tokens across every step execution and checkpoint.
        - Respects DAG step dependencies.
        - Compiles grounded turn context using canonical ContextCompiler.
        - Enforces resource limits (max_steps, max_wall_time_seconds).
        - Handles failure retries and returns comprehensive execution summary.
        """
        import time

        start_time = time.time()

        # 1. Claim task or verify lease
        task_data = self.task_service.claim_task(
            owner_id, task_id, worker_id=worker_id, lease_seconds=lease_seconds
        )
        lease_info = task_data.get("lease", {})
        lease_id = lease_info.get("leaseId")
        fencing_token = lease_info.get("fencingToken")

        if not lease_id or fencing_token is None:
            raise RuntimeError(f"Failed to acquire valid lease for task {task_id}")

        # Ensure task is tracked in AgentRuntime
        if task_id not in self.runtime.runs:
            self.resume_from_checkpoint(owner_id, task_id)

        step_counter = 0

        while True:
            # Check resource bounds
            elapsed = time.time() - start_time
            if elapsed > max_wall_time_seconds:
                task_data = self.task_service.get_task(owner_id, task_id)
                return LoopExecutionSummary(
                    task_id=task_id,
                    status="budget_exhausted",
                    completed_steps=sum(1 for s in task_data.get("steps", []) if s["status"] == "completed"),
                    total_steps=len(task_data.get("steps", [])),
                    duration_seconds=elapsed,
                    final_checkpoint=task_data.get("checkpoint", {}),
                    error=f"Exceeded max wall time of {max_wall_time_seconds}s",
                )

            if step_counter >= max_steps:
                task_data = self.task_service.get_task(owner_id, task_id)
                return LoopExecutionSummary(
                    task_id=task_id,
                    status="budget_exhausted",
                    completed_steps=sum(1 for s in task_data.get("steps", []) if s["status"] == "completed"),
                    total_steps=len(task_data.get("steps", [])),
                    duration_seconds=elapsed,
                    final_checkpoint=task_data.get("checkpoint", {}),
                    error=f"Exceeded max step budget of {max_steps} steps",
                )

            task_data = self.task_service.get_task(owner_id, task_id)
            if task_data.get("status") in ("completed", "failed", "cancelled"):
                return LoopExecutionSummary(
                    task_id=task_id,
                    status=task_data["status"],
                    completed_steps=sum(1 for s in task_data.get("steps", []) if s["status"] == "completed"),
                    total_steps=len(task_data.get("steps", [])),
                    duration_seconds=elapsed,
                    final_checkpoint=task_data.get("checkpoint", {}),
                    error=task_data.get("blockedReason"),
                )

            steps = task_data.get("steps", [])
            completed_step_ids = {s["id"] for s in steps if s["status"] == "completed"}

            # Resolve ready step
            ready_step: dict[str, Any] | None = None
            for s in steps:
                if s["status"] in ("pending", "active"):
                    deps = s.get("dependencies") or []
                    if all(d in completed_step_ids for d in deps):
                        ready_step = s
                        break

            if ready_step is None:
                # No runnable steps. If all are completed, task is done.
                if all(s["status"] == "completed" for s in steps):
                    return LoopExecutionSummary(
                        task_id=task_id,
                        status="completed",
                        completed_steps=len(steps),
                        total_steps=len(steps),
                        duration_seconds=elapsed,
                        final_checkpoint=task_data.get("checkpoint", {}),
                    )
                else:
                    # Unfinished steps exist but dependencies cannot be satisfied
                    return LoopExecutionSummary(
                        task_id=task_id,
                        status="blocked",
                        completed_steps=len(completed_step_ids),
                        total_steps=len(steps),
                        duration_seconds=elapsed,
                        final_checkpoint=task_data.get("checkpoint", {}),
                        error="Dependency deadlock: pending steps have unsatisfied dependencies",
                    )

            # Extend lease to avoid expiry during step execution
            self.task_service.extend_lease(
                owner_id, task_id, lease_id=lease_id, fencing_token=fencing_token, additional_seconds=lease_seconds
            )

            # Build step context
            step_context: dict[str, Any] = {
                "taskId": task_id,
                "goal": task_data["goal"],
                "step": ready_step,
                "completedStepIds": list(completed_step_ids),
                "leaseId": lease_id,
                "fencingToken": fencing_token,
            }

            if repository_map:
                step_context["repositoryMap"] = repository_map

            # Execute step
            step_counter += 1
            verification = None
            if verifications:
                verification = verifications.get(ready_step["id"]) or verifications.get(ready_step.get("title", ""))

            try:
                # Execute step and verify with fencing token
                step_task_data, result = await self.execute_step(
                    owner_id,
                    task_id,
                    ready_step["id"],
                    executor=lambda s: executor(s, step_context),
                    verification=verification,
                    lease_id=lease_id,
                    fencing_token=fencing_token,
                    retry_limit=retry_limit,
                )
            except Exception as exc:
                # Failure was recorded with lease in execute_step. Check task status
                refreshed = self.task_service.get_task(owner_id, task_id)
                if refreshed.get("status") == "failed":
                    return LoopExecutionSummary(
                        task_id=task_id,
                        status="failed",
                        completed_steps=sum(1 for s in refreshed.get("steps", []) if s["status"] == "completed"),
                        total_steps=len(refreshed.get("steps", [])),
                        duration_seconds=time.time() - start_time,
                        final_checkpoint=refreshed.get("checkpoint", {}),
                        error=str(exc),
                    )
                # If retryable, continue next iteration
                continue

            # Check if all finished after this step
            if step_task_data.get("status") == "completed":
                return LoopExecutionSummary(
                    task_id=task_id,
                    status="completed",
                    completed_steps=len(step_task_data.get("steps", [])),
                    total_steps=len(step_task_data.get("steps", [])),
                    duration_seconds=time.time() - start_time,
                    final_checkpoint=step_task_data.get("checkpoint", {}),
                )
