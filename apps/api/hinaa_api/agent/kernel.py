from __future__ import annotations

import asyncio
import inspect
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from .state import (
    AgentGoal,
    AgentResult,
    PlanStep,
    StepResult,
    StepStatus,
    VerificationReport,
)
from .planner import AgentPlanner
from .verifier import AgentVerifier

logger = logging.getLogger("hinaa.agent.kernel")


def _compiled_visual_query(parameters: dict[str, Any]) -> dict[str, Any]:
    """Compile the image step's query through the shared media compiler.

    Planners fill this step differently, and one measured run handed the vendor
    "i want pics of tokyo ghoul" verbatim. If the compile raises, the step keeps
    the planner's own value rather than losing the request.
    """
    try:
        from ..media.search_intelligence import compiled_image_query_parameters

        return compiled_image_query_parameters(parameters)
    except Exception:
        logger.warning("image_search query compilation failed; using planner value", exc_info=True)
        return parameters


def _compiled_web_query(parameters: dict[str, Any]) -> dict[str, Any]:
    """Compile the web step's query through the shared intent normalizer.

    Same reason as the visual step: a plan written by a model echoes the whole
    utterance — addressee, command verb, pleasantry and all — into `query`.
    """
    try:
        from ..media.search_intelligence import compiled_web_query_parameters

        return compiled_web_query_parameters(parameters)
    except Exception:
        logger.warning("web_search query compilation failed; using planner value", exc_info=True)
        return parameters


def _safe_error_text(value: object) -> str:
    """Keep provider/transport errors useful without echoing credentials."""
    text = str(value)
    text = re.sub(r"(?i)(api[_ -]?key|access[_ -]?token|authorization|secret)\s*[:=]\s*[^\s,;]+", r"\1=[REDACTED]", text)
    text = re.sub(r"(?i)\b(?:sk|key|token|bearer)[-_][A-Za-z0-9._-]{8,}", "[REDACTED]", text)
    return text[:500]


class HinaaAgent:
    """The central HINAA v2 Sakura Agent OS runtime.

    Orchestrates the cognitive loop:
    Goal -> Retrieve -> Plan -> Execute Steps -> Observe -> Verify -> (Replan) -> Finalize
    """

    def __init__(
        self,
        planner: AgentPlanner | None = None,
        verifier: AgentVerifier | None = None,
        executor_func: Callable[[str, dict[str, Any]], Awaitable[Any]] | None = None,
        *,
        max_iterations: int = 8,
        step_timeout_s: float = 120.0,
        max_cost_units: int = 32,
        allowed_skill_ids: set[str] | None = None,
        audit_sink: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        if step_timeout_s <= 0:
            raise ValueError("step_timeout_s must be greater than zero")
        if max_cost_units < 1:
            raise ValueError("max_cost_units must be at least 1")
        self.planner = planner or AgentPlanner()
        self.verifier = verifier or AgentVerifier()
        self.executor_func = executor_func
        self.max_iterations = max_iterations
        self.step_timeout_s = step_timeout_s
        self.max_cost_units = max_cost_units
        self.allowed_skill_ids = allowed_skill_ids
        self.audit_sink = audit_sink

    async def run(
        self,
        text: str,
        user_id: str,
        conversation_id: str | None = None,
        session_id: str | None = None,
        context: dict[str, Any] | None = None,
        constraints: list[str] | None = None,
    ) -> AgentResult:
        """Executes the full agent loop for a user request."""
        start_time = time.time()
        ctx = context or {}
        audit_events: list[dict[str, Any]] = []
        cost_units = 0
        attempts = 0
        provider_cost: float | None = None

        def audit(event: str, **fields: Any) -> None:
            record = {
                "event": event,
                "timestamp": time.time(),
                "goal_text": text[:200],
                **fields,
            }
            audit_events.append(record)
            if self.audit_sink is not None:
                try:
                    self.audit_sink(record)
                except Exception:  # pragma: no cover - telemetry must not break a run
                    logger.warning("Agent audit sink failed", exc_info=True)

        # 1. UNDERSTAND: Formulate Goal
        goal = AgentGoal(
            user_id=user_id,
            conversation_id=conversation_id,
            session_id=session_id,
            text=text,
            constraints=constraints or [],
        )

        # 2. PLAN: Formulate initial step DAG
        steps = self.planner.create_plan(goal, ctx)
        audit("run_started", goal_id=goal.id, step_count=len(steps))
        executed_steps: list[PlanStep] = []
        replans_count = 0
        iteration = 0

        # 3. EXECUTION & VERIFICATION LOOP
        while iteration < self.max_iterations:
            iteration += 1
            # Find next pending step whose dependencies are completed
            ready_step = None
            for s in steps:
                if s.status == StepStatus.PENDING:
                    deps_met = all(
                        any(prev.step_id == dep_id and prev.status == StepStatus.COMPLETED for prev in executed_steps)
                        for dep_id in s.depends_on
                    )
                    if deps_met:
                        ready_step = s
                        break

            if not ready_step:
                # No more executable pending steps
                break

            if self.allowed_skill_ids is not None and ready_step.skill_id not in self.allowed_skill_ids:
                ready_step.status = StepStatus.FAILED
                ready_step.error = f"Skill '{ready_step.skill_id}' is not allowed for this run."
                executed_steps.append(ready_step)
                audit("step_rejected", step_id=ready_step.step_id, skill_id=ready_step.skill_id, reason="skill_not_allowed")
                break

            if cost_units >= self.max_cost_units:
                ready_step.status = StepStatus.FAILED
                ready_step.error = f"Run budget exhausted at {self.max_cost_units} cost units."
                executed_steps.append(ready_step)
                audit("run_budget_exhausted", step_id=ready_step.step_id, cost_units=cost_units)
                break

            ready_step.status = StepStatus.RUNNING
            step_start = time.time()
            step_result = StepResult(step_id=ready_step.step_id)
            cost_units += 1
            attempts += 1
            audit("step_started", step_id=ready_step.step_id, skill_id=ready_step.skill_id, iteration=iteration)

            try:
                # 4. EXECUTE STEP
                if self.executor_func:
                    if ready_step.skill_id == "image_search":
                        ready_step.parameters = _compiled_visual_query(dict(ready_step.parameters))
                    elif ready_step.skill_id == "web_search":
                        ready_step.parameters = _compiled_web_query(dict(ready_step.parameters))
                    # Pass dependency results explicitly as untrusted context so
                    # later steps (for example PDF compilation) can consume
                    # verified upstream material without hidden global state.
                    step_parameters = dict(ready_step.parameters)
                    dependency_outputs = {
                        previous.step_id: previous.result.output
                        for previous in executed_steps
                        if previous.step_id in ready_step.depends_on
                        and previous.status == StepStatus.COMPLETED
                        and previous.result is not None
                    }
                    if dependency_outputs:
                        step_parameters["_dependency_outputs"] = dependency_outputs
                    if inspect.iscoroutinefunction(self.executor_func):
                        invocation = self.executor_func(ready_step.skill_id, step_parameters)
                        output = await asyncio.wait_for(invocation, timeout=self.step_timeout_s)
                    else:
                        # Keep legacy synchronous adapters from blocking the
                        # event loop. Their work runs in a worker thread and is
                        # still bounded by the per-step timeout.
                        output = await asyncio.wait_for(
                            asyncio.to_thread(self.executor_func, ready_step.skill_id, step_parameters),
                            timeout=self.step_timeout_s,
                        )
                        if inspect.isawaitable(output):
                            output = await asyncio.wait_for(output, timeout=self.step_timeout_s)
                    step_result.output = output
                    step_result.observations = f"Tool {ready_step.skill_id} completed successfully."
                else:
                    # Every skill, including conversational synthesis, must
                    # have a real executor. Never fabricate a successful
                    # response when the model/tool backend is unavailable.
                    raise RuntimeError(f"No executor configured for skill '{ready_step.skill_id}'.")

                if isinstance(step_result.output, dict):
                    reported_cost = step_result.output.get("provider_cost") or step_result.output.get("cost")
                    if isinstance(reported_cost, (int, float)) and reported_cost >= 0:
                        provider_cost = float(reported_cost) if provider_cost is None else provider_cost + float(reported_cost)

                step_result.latency_ms = int((time.time() - step_start) * 1000)
                ready_step.result = step_result

                # 5. VERIFY STEP
                verification = self.verifier.check_step(goal, ready_step, step_result)
                audit(
                    "step_verified",
                    step_id=ready_step.step_id,
                    skill_id=ready_step.skill_id,
                    passed=verification.passed,
                    confidence=verification.confidence,
                )

                if verification.needs_replan and ready_step.retry_count < ready_step.max_retries:
                    ready_step.status = StepStatus.FAILED
                    ready_step.error = _safe_error_text("; ".join(verification.unresolved_issues))
                    executed_steps.append(ready_step.model_copy(deep=True))
                    replans_count += 1
                    # Replan
                    steps = self.planner.replan(goal, ready_step, verification, steps)
                    continue
                elif not verification.passed:
                    # Exhausted verification retries are a terminal failure;
                    # accepting the last bad output would create false success.
                    ready_step.status = StepStatus.FAILED
                    ready_step.error = _safe_error_text(
                        "; ".join(verification.unresolved_issues) or "Step verification failed."
                    )
                    executed_steps.append(ready_step)
                    audit("step_failed", step_id=ready_step.step_id, skill_id=ready_step.skill_id, error=ready_step.error)
                else:
                    ready_step.status = StepStatus.COMPLETED
                    executed_steps.append(ready_step)
                    audit("step_completed", step_id=ready_step.step_id, skill_id=ready_step.skill_id)

            except Exception as exc:
                logger.error(
                    "Step execution error in %s: %s",
                    ready_step.skill_id,
                    _safe_error_text(exc),
                    exc_info=True,
                )
                ready_step.status = StepStatus.FAILED
                ready_step.error = _safe_error_text(exc)
                if isinstance(exc, TimeoutError):
                    ready_step.error = f"Step timed out after {self.step_timeout_s:.1f}s."
                verification = VerificationReport(
                    passed=False,
                    confidence=0.0,
                    unresolved_issues=[_safe_error_text(exc)],
                    needs_replan=True,
                )
                if ready_step.retry_count < ready_step.max_retries:
                    replans_count += 1
                    executed_steps.append(ready_step.model_copy(deep=True))
                    steps = self.planner.replan(goal, ready_step, verification, steps)
                else:
                    executed_steps.append(ready_step)
                audit("step_failed", step_id=ready_step.step_id, skill_id=ready_step.skill_id, error=ready_step.error)

        # A bounded loop is not permission to report success. Mark work that
        # could not run (dependency failure, cycle, or iteration exhaustion)
        # explicitly so callers can distinguish incomplete from completed.
        pending_steps = [s for s in steps if s.status in (StepStatus.PENDING, StepStatus.RUNNING)]
        for pending in pending_steps:
            pending.status = StepStatus.SKIPPED
            pending.error = "Step could not execute before the run limit or because a dependency failed."
            executed_steps.append(pending.model_copy(deep=True))
            audit("step_skipped", step_id=pending.step_id, skill_id=pending.skill_id, reason=pending.error)

        # 6. FINALIZE & OVERALL AUDIT
        final_answer = self._synthesize_final_answer(goal, executed_steps)
        overall_verification = self.verifier.check_overall(goal, executed_steps, final_answer)
        # ``executed_steps`` contains attempt history. Aggregate status must
        # use the latest attempt for each step id, otherwise a recovered
        # failure can incorrectly poison (or falsely complete) the run.
        terminal_steps: dict[str, PlanStep] = {}
        for step in executed_steps:
            terminal_steps[step.step_id] = step
        terminal = list(terminal_steps.values())
        has_failures = any(step.status in (StepStatus.FAILED, StepStatus.SKIPPED) for step in terminal)
        has_completed = any(step.status == StepStatus.COMPLETED for step in terminal)
        all_steps_completed = bool(terminal) and all(step.status == StepStatus.COMPLETED for step in terminal)
        if overall_verification.passed and all_steps_completed and not has_failures:
            overall_verification.confidence = max(overall_verification.confidence, 0.92)
        if all_steps_completed and overall_verification.passed:
            status = "completed"
        elif has_completed:
            status = "partial"
        else:
            status = "failed"
        artifacts = self._collect_artifacts(terminal)
        audit(
            "run_completed",
            goal_id=goal.id,
            status=status,
            confidence=overall_verification.confidence,
            cost_units=cost_units,
            attempts=attempts,
            artifact_count=len(artifacts),
        )

        total_latency = int((time.time() - start_time) * 1000)

        return AgentResult(
            goal_id=goal.id,
            final_answer=final_answer,
            spoken_text=final_answer[:140] if final_answer else None,
            confidence=overall_verification.confidence,
            evidence=overall_verification.evidence,
            steps_executed=executed_steps,
            replans_count=replans_count,
            total_latency_ms=total_latency,
            audit_events=audit_events,
            cost_units=cost_units,
            provider_cost=provider_cost,
            attempts=attempts,
            status=status,
            artifacts=artifacts,
        )

    @staticmethod
    def _collect_artifacts(steps: list[PlanStep]) -> list[dict[str, Any]]:
        """Expose only explicit artifact metadata from terminal step outputs."""
        artifacts: list[dict[str, Any]] = []
        for step in steps:
            if step.status != StepStatus.COMPLETED or step.result is None:
                continue
            output = step.result.output
            if not isinstance(output, dict):
                continue
            for key in ("downloadUrl", "download_url", "imageUrl", "image_url", "url", "filename", "docId", "job_id", "jobId"):
                value = output.get(key)
                if value:
                    artifacts.append({"stepId": step.step_id, "skillId": step.skill_id, "kind": key, "value": value})
        return artifacts

    def _synthesize_final_answer(self, goal: AgentGoal, steps: list[PlanStep]) -> str:
        """Synthesizes the final answer from completed steps."""
        if not steps:
            return "I couldn't find a way to complete this request."

        # Extract primary completed outputs
        completed = [s for s in steps if s.status == StepStatus.COMPLETED]
        if not completed:
            failed = [s for s in steps if s.status == StepStatus.FAILED]
            err_msg = failed[0].error if failed else "Execution could not proceed."
            return f"I encountered an issue completing your goal: {err_msg}"

        # If image search or generate completed
        for s in completed:
            if s.skill_id == "image_search":
                return f"Here are some visual results I found for **{goal.text}**! ✨"
            elif s.skill_id == "image_generate":
                output = s.result.output if s.result else None
                if isinstance(output, dict) and output.get("status") in {"queued", "processing"}:
                    return f"Your image request is queued for **{goal.text}**; I’ll show it when the renderer finishes. ✨"
                return f"I generated a custom creative image for **{goal.text}**! ✨"
            elif s.skill_id == "pdf_generate":
                return f"I compiled your assignment and documentation into a structured PDF for **{goal.text}**! 📄"

        # If web research / synthesis completed
        synthesis_step = next((s for s in completed if s.skill_id in ("web_answer", "conversational_synthesis")), completed[-1])
        if synthesis_step.result and isinstance(synthesis_step.result.output, str):
            return synthesis_step.result.output
        elif synthesis_step.result and isinstance(synthesis_step.result.output, dict):
            text = synthesis_step.result.output.get("text") or synthesis_step.result.output.get("summary")
            if text:
                return str(text)
            return f"The run completed, but the tool returned structured data without a readable summary for **{goal.text}**."

        return f"Completed analysis on {goal.text} across {len(completed)} verified steps."
