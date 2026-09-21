from __future__ import annotations

import asyncio
import pytest

from hinaa_api.agent import (
    AgentRuntime,
    ContextBuilder,
    PlanValidator,
    PlanValidationError,
    IntentInterpreter,
    StepScheduler,
    AgentVerifier,
)
from hinaa_api.agent.contracts import (
    AgentPlan,
    AgentRun,
    IntentResult,
    OperationType,
    PlanStep,
    RunStatus,
    StepState,
    validate_run_transition,
    validate_step_transition,
)
from hinaa_api.agent.cancellation import request_cancellation
from hinaa_api.agent.recovery import recover_run
from hinaa_api.agent.retry import FailureCategory, is_retryable
from hinaa_api.errors import HinaaError


# ==============================================================================
# 1. CONTEXT
# ==============================================================================

def test_context_builder_retains_current_message_and_bounds_history():
    cb = ContextBuilder(max_tokens=64)
    ctx = cb.build(
        "current user request",
        recent_messages=[{"id": str(i), "content": "long message content " * 10} for i in range(10)],
    )
    assert ctx.current_message == "current user request"
    assert ctx.token_estimate <= 64
    assert ctx.items[0].source_type == "current_message"
    assert ctx.items[0].priority == 100


def test_context_builder_excludes_unrelated_user_data_and_preserves_attachments():
    cb = ContextBuilder(max_tokens=500)
    ctx = cb.build(
        "hello",
        recent_messages=[
            {"id": "1", "content": "user1 message", "user_id": "u1"},
            {"id": "2", "content": "user2 private message", "user_id": "u2"},
        ],
        memories=[
            {"id": "m1", "content": "u1 preference", "userId": "u1"},
            {"id": "m2", "content": "u2 secret", "userId": "u2"},
        ],
        tool_results=[
            {"id": "t1", "content": "u1 verified result", "user_id": "u1"},
            {"id": "t2", "content": "u2 private tool result", "user_id": "u2"},
        ],
        attachments=["asset-photo-1", "asset-photo-2"],
        user_id="u1",
    )
    contents = [item.content for item in ctx.items]
    assert "user1 message" in contents
    assert "user2 private message" not in contents
    assert "u1 preference" in contents
    assert "u2 secret" not in contents
    assert "u1 verified result" in contents
    assert "u2 private tool result" not in contents
    assert ctx.attachments == ["asset-photo-1", "asset-photo-2"]


def test_context_builder_accounts_for_and_bounds_oversized_current_message():
    cb = ContextBuilder(max_tokens=64)
    current_message = "begin " + ("important context " * 100) + "final requirement"

    ctx = cb.build(current_message)

    assert ctx.current_message == current_message
    assert ctx.items[0].token_size > 0
    assert ctx.token_estimate <= 64
    assert "...[truncated]..." in ctx.items[0].content
    assert ctx.items[0].content.startswith("begin ")
    assert ctx.items[0].content.endswith("final requirement")


# ==============================================================================
# 2. INTENT
# ==============================================================================

def test_intent_boundary_parses_valid_payload():
    interpreter = IntentInterpreter()
    payload = {
        "primary_intent": "generation",
        "goal": "generate financial report",
        "requested_outcome": "PDF document",
        "candidate_tools": ["pdf_generate"],
        "confidence": 0.95,
    }
    result = interpreter.interpret(payload)
    assert result.primary_intent == "generation"
    assert result.goal == "generate financial report"
    assert result.candidate_tools == ["pdf_generate"]
    assert result.requires_planning is True
    assert result.confidence == 0.95


def test_intent_boundary_handles_malformed_payload_with_deterministic_fallback():
    interpreter = IntentInterpreter()
    result = interpreter.interpret("{malformed json: broken syntax, missing quotes")
    assert result.primary_intent == "conversation"
    assert "malformed" in result.goal
    assert result.confidence == 0.5


def test_intent_boundary_detects_cancellation_and_retry():
    interpreter = IntentInterpreter()
    assert interpreter.interpret("please stop this task immediately").primary_intent == "cancellation"
    assert interpreter.interpret("cancel the current operation").primary_intent == "cancellation"
    assert interpreter.interpret("please try again with different keywords").primary_intent == "retry"
    assert interpreter.interpret("retry the previous search").primary_intent == "retry"


# ==============================================================================
# 3. PLANNER & VALIDATOR
# ==============================================================================

def test_planner_and_validator_accept_valid_single_step_plan():
    plan = AgentPlan(run_id="run-1", goal="say hello")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="respond",
        operation_type=OperationType.RESPOND,
    )
    plan.steps = [step]
    validated = PlanValidator(max_steps=5).validate(plan)
    assert len(validated.steps) == 1
    assert validated.steps[0].operation_type == OperationType.RESPOND


def test_planner_and_validator_accept_multi_step_dag():
    plan = AgentPlan(run_id="run-1", goal="research topic")
    s0 = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="search",
        operation_type=OperationType.TOOL,
        tool_name="web_search",
    )
    s1 = PlanStep(
        plan_id=plan.plan_id,
        sequence=1,
        title="summarize",
        operation_type=OperationType.SUMMARIZE,
        dependencies=[s0.step_id],
    )
    plan.steps = [s0, s1]
    validated = PlanValidator(max_steps=5, allowed_tools={"web_search"}).validate(plan)
    assert len(validated.steps) == 2


def test_validator_rejects_unknown_tools():
    plan = AgentPlan(run_id="run-1", goal="exploit")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="hack",
        operation_type=OperationType.TOOL,
        tool_name="unregistered_dangerous_tool",
    )
    plan.steps = [step]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator(allowed_tools={"web_search", "pdf_generate"}).validate(plan)
    assert any("unknown tool" in issue for issue in exc.value.issues)


def test_validator_rejects_excessive_steps():
    plan = AgentPlan(run_id="run-1", goal="too many")
    plan.steps = [
        PlanStep(plan_id=plan.plan_id, sequence=i, title=f"s{i}", operation_type=OperationType.RESPOND)
        for i in range(15)
    ]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator(max_steps=10).validate(plan)
    assert any("maximum step count" in issue for issue in exc.value.issues)


def test_validator_rejects_duplicate_step_ids():
    plan = AgentPlan(run_id="run-1", goal="duplicate ids")
    s1 = PlanStep(plan_id=plan.plan_id, sequence=0, title="s1", operation_type=OperationType.RESPOND)
    s2 = PlanStep(step_id=s1.step_id, plan_id=plan.plan_id, sequence=1, title="s2", operation_type=OperationType.RESPOND)
    plan.steps = [s1, s2]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator().validate(plan)
    assert any("duplicate step id" in issue for issue in exc.value.issues)


def test_validator_rejects_missing_dependency():
    plan = AgentPlan(run_id="run-1", goal="missing dep")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="step",
        operation_type=OperationType.RESPOND,
        dependencies=["ghost_step_id"],
    )
    plan.steps = [step]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator().validate(plan)
    assert any("missing dependency" in issue for issue in exc.value.issues)


def test_validator_rejects_dependency_cycle():
    plan = AgentPlan(run_id="run-1", goal="cycle")
    s1 = PlanStep(plan_id=plan.plan_id, sequence=0, title="s1", operation_type=OperationType.RESPOND)
    s2 = PlanStep(plan_id=plan.plan_id, sequence=1, title="s2", operation_type=OperationType.RESPOND, dependencies=[s1.step_id])
    s1.dependencies = [s2.step_id]
    plan.steps = [s1, s2]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator().validate(plan)
    assert any("cycle" in issue for issue in exc.value.issues)


def test_validator_rejects_forbidden_video_operations():
    plan = AgentPlan(run_id="run-1", goal="make video")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="video",
        operation_type=OperationType.TOOL,
        tool_name="video_generate",
    )
    plan.steps = [step]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator().validate(plan)
    assert any("video generation is forbidden" in issue for issue in exc.value.issues)


def test_validator_rejects_identity_or_limit_overrides():
    plan = AgentPlan(run_id="run-1", goal="override")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="override",
        operation_type=OperationType.RESPOND,
        tool_parameters={"user_id": "attacker", "max_steps": 100},
    )
    plan.steps = [step]
    with pytest.raises(PlanValidationError) as exc:
        PlanValidator().validate(plan)
    assert any("identity override" in issue for issue in exc.value.issues)
    assert any("runtime limit override" in issue for issue in exc.value.issues)


# ==============================================================================
# 4. SCHEDULER
# ==============================================================================

def test_scheduler_dependency_resolution_and_blocking():
    scheduler = StepScheduler()
    run = AgentRun(user_id="u1", goal="scheduler test")
    plan = AgentPlan(run_id=run.run_id, goal="scheduler test")
    s0 = PlanStep(plan_id=plan.plan_id, sequence=0, title="s0", operation_type=OperationType.RESPOND)
    s1 = PlanStep(plan_id=plan.plan_id, sequence=1, title="s1", operation_type=OperationType.RESPOND, dependencies=[s0.step_id])
    plan.steps = [s0, s1]

    # Initially, s0 is ready
    ready = scheduler.next_ready(run, plan)
    assert ready is not None
    assert ready.step_id == s0.step_id

    # If s0 fails permanently, s1 is blocked
    s0.status = StepState.FAILED
    s0.attempt_count = s0.maximum_attempts
    ready2 = scheduler.next_ready(run, plan)
    assert ready2 is None
    assert s1.status == StepState.BLOCKED


def test_scheduler_cancelled_or_confirmation_blocked():
    scheduler = StepScheduler()
    run = AgentRun(user_id="u1", goal="cancel test", cancellation_requested=True)
    plan = AgentPlan(run_id=run.run_id, goal="cancel test")
    s0 = PlanStep(plan_id=plan.plan_id, sequence=0, title="s0", operation_type=OperationType.RESPOND)
    plan.steps = [s0]
    assert scheduler.next_ready(run, plan) is None

    # Step awaiting confirmation blocks execution
    run.cancellation_requested = False
    s0.requires_confirmation = True
    assert scheduler.next_ready(run, plan) is None
    assert s0.status == StepState.AWAITING_CONFIRMATION


# ==============================================================================
# 5. EXECUTOR
# ==============================================================================

@pytest.mark.asyncio
async def test_executor_executes_simple_response_plan():
    async def echo_executor(step):
        return {"response": f"Processed {step.title}"}

    runtime = AgentRuntime(executor=echo_executor)
    run = runtime.create_run("greeting", "u1")
    result = await runtime.execute(run)
    assert result.status == RunStatus.COMPLETED
    assert result.completed_steps == 1


@pytest.mark.asyncio
async def test_executor_emits_canonical_agent_lifecycle_events_with_legacy_aliases():
    async def echo_executor(step):
        return {"response": f"Processed {step.title}"}

    runtime = AgentRuntime(executor=echo_executor)
    run = runtime.create_run("greeting", "u1")
    result = await runtime.execute(run)

    assert result.status == RunStatus.COMPLETED
    events = runtime.get_events(run.run_id, "u1") or []
    event_types = [event.event_type for event in events]
    assert "agent.run.created" in event_types
    assert "agent.context.ready" in event_types
    assert "agent.intent.ready" in event_types
    assert "agent.plan.ready" in event_types
    assert "agent.step.started" in event_types
    assert "agent.step.completed" in event_types
    assert "agent.verification.started" in event_types
    assert "agent.verification.completed" in event_types
    assert "agent.run.completed" in event_types
    assert "plan.ready" in event_types
    assert "step.started" in event_types
    assert "step.completed" in event_types


@pytest.mark.asyncio
async def test_executor_ordered_multi_step_and_persists_results():
    execution_order = []
    async def step_executor(step):
        execution_order.append(step.title)
        return {"step": step.title, "status": "ok"}

    runtime = AgentRuntime(executor=step_executor)
    run = runtime.create_run("pipeline", "u1")
    plan = AgentPlan(run_id=run.run_id, goal="pipeline")
    s0 = PlanStep(plan_id=plan.plan_id, sequence=0, title="first", operation_type=OperationType.RESPOND)
    s1 = PlanStep(plan_id=plan.plan_id, sequence=1, title="second", operation_type=OperationType.RESPOND, dependencies=[s0.step_id])
    plan.steps = [s0, s1]

    result = await runtime.execute(run, plan=plan)
    assert result.status == RunStatus.COMPLETED
    assert execution_order == ["first", "second"]
    assert s0.result == {"step": "first", "status": "ok"}
    assert s1.result == {"step": "second", "status": "ok"}


@pytest.mark.asyncio
async def test_executor_stops_on_non_retryable_failure():
    async def failing_executor(step):
        raise ValueError("FATAL_ERROR: Unrecoverable validation error")

    runtime = AgentRuntime(executor=failing_executor)
    run = runtime.create_run("fatal", "u1")
    result = await runtime.execute(run)
    assert result.status == RunStatus.FAILED
    assert result.failure_code == "step_failed"
    assert "FATAL_ERROR" in (result.failure_message or "")


@pytest.mark.asyncio
async def test_executor_retries_transient_failure_up_to_limit():
    attempts = 0
    async def flaky_executor(step):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            raise RuntimeError("transient network timeout")
        return {"recovered": True}

    runtime = AgentRuntime(executor=flaky_executor, step_attempts=3)
    run = runtime.create_run("retry test", "u1")
    result = await runtime.execute(run)
    assert result.status == RunStatus.COMPLETED
    assert attempts == 2


def test_executor_enforces_maximum_steps_and_replans():
    runtime = AgentRuntime(max_steps=5, max_replans=2)
    run = runtime.create_run("limits", "u1")
    assert run.maximum_steps == 5
    assert run.maximum_replans == 2


# ==============================================================================
# 6. CANCELLATION
# ==============================================================================

@pytest.mark.asyncio
async def test_cancellation_manager_queued_and_planning():
    runtime = AgentRuntime()
    run = runtime.create_run("cancel queued", "u1")
    cancelled = runtime.cancel(run.run_id, "u1")
    assert cancelled is not None
    assert cancelled.status == RunStatus.CANCELLED
    res = await runtime.execute(run)
    assert res.status == RunStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancellation_manager_executing_and_idempotent():
    runtime = AgentRuntime()
    run = runtime.create_run("idempotent cancel", "u1")
    c1 = runtime.cancel(run.run_id, "u1")
    c2 = runtime.cancel(run.run_id, "u1")
    assert c1.status == RunStatus.CANCELLED
    assert c2.status == RunStatus.CANCELLED

    # Completed run cannot be transitioned to cancelled
    completed_run = AgentRun(user_id="u1", goal="done", status=RunStatus.COMPLETED)
    assert request_cancellation(completed_run, "u1").status == RunStatus.COMPLETED


def test_cancellation_manager_ownership_enforcement():
    runtime = AgentRuntime()
    run = runtime.create_run("ownership cancel", "owner-user")
    assert runtime.cancel(run.run_id, "attacker-user") is None
    assert run.status == RunStatus.QUEUED
    assert request_cancellation(run, "attacker-user") is None


@pytest.mark.asyncio
async def test_cancellation_stops_registered_active_task_and_marks_steps():
    runtime = AgentRuntime()
    run = runtime.create_run("cancel active stream", "u1")
    plan, step, _ = runtime.begin_stream_turn(run)
    started = asyncio.Event()

    async def active_stream():
        task = runtime.register_active_task(run.run_id)
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            runtime.unregister_active_task(run.run_id, task)

    task = asyncio.create_task(active_stream())
    await asyncio.wait_for(started.wait(), timeout=1)

    cancelled = runtime.cancel(run.run_id, "u1")
    with pytest.raises(asyncio.CancelledError):
        await task

    assert cancelled is run
    assert run.status == RunStatus.CANCELLED
    assert run.completed_at is not None
    assert step.status == StepState.CANCELLED
    assert runtime.complete_stream_turn(run, plan, step, result={"late": True}) == []
    event_types = [event.event_type for event in runtime.get_events(run.run_id, "u1") or []]
    assert event_types.count("agent.run.cancelled") == 1
    assert "agent.run.completed" not in event_types
    assert "agent.run.failed" not in event_types


@pytest.mark.asyncio
async def test_run_timeout_is_failed_not_misreported_as_cancelled():
    async def slow_executor(_step):
        await asyncio.sleep(1)
        return {"late": True}

    runtime = AgentRuntime(executor=slow_executor, run_timeout=0.01, step_attempts=1)
    run = runtime.create_run("bounded run", "u1")

    result = await runtime.execute(run)

    assert result.status == RunStatus.FAILED
    assert result.failure_code == "run_timeout"
    assert result.completed_at is not None
    steps = runtime.get_steps(run.run_id, "u1") or []
    assert steps[0].status == StepState.INTERRUPTED
    event_types = [event.event_type for event in runtime.get_events(run.run_id, "u1") or []]
    assert "agent.run.failed" in event_types
    assert "agent.run.cancelled" not in event_types


def test_stream_failure_redacts_secrets_and_terminalizes_once():
    runtime = AgentRuntime()
    run = runtime.create_run("secret failure", "u1")
    _, step, _ = runtime.begin_stream_turn(run)
    credential_value = "sk-live-1234567890abcdef"

    events = runtime.fail_stream_turn(
        run,
        step=step,
        code="PROVIDER_ERROR",
        message=f"provider api_key={credential_value}",
    )
    event_count = len(runtime.get_events(run.run_id, "u1") or [])

    assert run.status == RunStatus.FAILED
    assert run.completed_at is not None
    assert credential_value not in (run.failure_message or "")
    assert "[REDACTED]" in (run.failure_message or "")
    assert credential_value not in (step.error_message or "")
    assert credential_value not in str([event.payload for event in events])
    assert runtime.fail_stream_turn(run, step=step, message=credential_value) == []
    assert len(runtime.get_events(run.run_id, "u1") or []) == event_count


# ==============================================================================
# 7. CONFIRMATION
# ==============================================================================

@pytest.mark.asyncio
async def test_confirmation_pauses_execution_and_resumes_once():
    call_counts = 0
    async def guarded_executor(step):
        nonlocal call_counts
        call_counts += 1
        return {"executed": True}

    runtime = AgentRuntime(executor=guarded_executor)
    run = runtime.create_run("dangerous action", "u1")
    plan = AgentPlan(run_id=run.run_id, goal="dangerous action")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="delete_table",
        operation_type=OperationType.TOOL,
        tool_name="delete_table",
        requires_confirmation=True,
    )
    plan.steps = [step]

    # Initial execution must pause at AWAITING_CONFIRMATION
    res1 = await runtime.execute(run, plan=plan)
    assert res1.status == RunStatus.AWAITING_CONFIRMATION
    assert call_counts == 0

    # Confirm and resume
    res_confirm = runtime.confirm(run.run_id, step.step_id, "u1", approved=True)
    assert res_confirm is not None
    assert step.status == StepState.READY

    res2 = await runtime.execute(run, plan=plan)
    assert res2.status == RunStatus.COMPLETED
    assert call_counts == 1

    # Duplicate confirmation does not re-execute
    runtime.confirm(run.run_id, step.step_id, "u1", approved=True)
    assert call_counts == 1


def test_confirmation_manager_rejects_cross_user():
    runtime = AgentRuntime()
    run = runtime.create_run("confirm auth", "user-alice")
    plan = AgentPlan(run_id=run.run_id, goal="confirm auth")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="action",
        operation_type=OperationType.RESPOND,
        requires_confirmation=True,
        status=StepState.AWAITING_CONFIRMATION,
    )
    plan.steps = [step]
    runtime.plans[plan.plan_id] = plan

    assert runtime.confirm(run.run_id, step.step_id, "user-mallory", approved=True) is None

    # Rejection by owner cancels run cleanly
    rejected = runtime.confirm(run.run_id, step.step_id, "user-alice", approved=False)
    assert rejected is not None
    assert rejected.status == RunStatus.CANCELLED
    assert step.status == StepState.CANCELLED


# ==============================================================================
# 8. PERSISTENCE
# ==============================================================================

@pytest.mark.asyncio
async def test_persistence_manager_records_plan_steps_and_events():
    async def dummy_executor(step):
        return {"data": "persisted"}

    runtime = AgentRuntime(executor=dummy_executor)
    run = runtime.create_run("persistence check", "u1")
    await runtime.execute(run)

    assert runtime.get_run(run.run_id, "u1") is not None
    steps = runtime.get_steps(run.run_id, "u1")
    assert steps is not None and len(steps) >= 1
    events = runtime.get_events(run.run_id, "u1")
    assert events is not None and len(events) >= 1
    sequences = [e.sequence for e in events]
    assert sequences == list(range(1, len(events) + 1))


# ==============================================================================
# 9. STATE MACHINE
# ==============================================================================

def test_state_machine_validates_legal_transitions_and_rejects_illegal():
    assert validate_run_transition(RunStatus.QUEUED, RunStatus.UNDERSTANDING) is True
    assert validate_run_transition(RunStatus.UNDERSTANDING, RunStatus.PLANNING) is True
    assert validate_run_transition(RunStatus.PLANNING, RunStatus.EXECUTING) is True
    with pytest.raises(ValueError) as exc:
        validate_run_transition(RunStatus.COMPLETED, RunStatus.EXECUTING)
    assert "Illegal run transition" in str(exc.value)

    assert validate_step_transition(StepState.PENDING, StepState.READY) is True
    assert validate_step_transition(StepState.READY, StepState.RUNNING) is True
    assert validate_step_transition(StepState.RUNNING, StepState.COMPLETED) is True
    with pytest.raises(ValueError) as exc2:
        validate_step_transition(StepState.COMPLETED, StepState.READY)
    assert "Illegal step transition" in str(exc2.value)


# ==============================================================================
# 10. RECOVERY
# ==============================================================================

def test_interrupted_run_recovery_detects_and_marks_interrupted():
    run = AgentRun(user_id="u1", goal="stale active run", status=RunStatus.EXECUTING)
    plan = AgentPlan(run_id=run.run_id, goal="stale active run")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="inflight",
        operation_type=OperationType.TOOL,
        tool_name="web_search",
        status=StepState.RUNNING,
    )
    plan.steps = [step]

    recovered = recover_run(run, plan)
    assert recovered.status == RunStatus.INTERRUPTED
    assert step.status == StepState.INTERRUPTED


def test_recovery_does_not_rerun_completed_or_uncertain_non_idempotent_steps():
    runtime = AgentRuntime()
    run = runtime.create_run("recovery safety", "u1")
    run.status = RunStatus.INTERRUPTED
    plan = AgentPlan(run_id=run.run_id, goal="recovery safety")
    s0 = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="step0",
        operation_type=OperationType.RESPOND,
        status=StepState.COMPLETED,
    )
    s1 = PlanStep(
        plan_id=plan.plan_id,
        sequence=1,
        title="non_idempotent_tool",
        operation_type=OperationType.TOOL,
        tool_name="stripe_charge",
        tool_parameters={"idempotent": False},
        status=StepState.INTERRUPTED,
    )
    plan.steps = [s0, s1]
    runtime.plans[plan.plan_id] = plan

    runtime.resume(run.run_id, "u1")
    assert s0.status == StepState.COMPLETED  # Completed step never reruns
    assert s1.status == StepState.AWAITING_CONFIRMATION  # Uncertain non-idempotent requires approval


# ==============================================================================
# 11. VERIFIER
# ==============================================================================

def test_verifier_detects_anomalies_and_corrects_once():
    verifier = AgentVerifier()
    run = AgentRun(user_id="u1", goal="verify", maximum_replans=1, replan_count=0)
    plan = AgentPlan(run_id=run.run_id, goal="verify")
    step = PlanStep(
        plan_id=plan.plan_id,
        sequence=0,
        title="search",
        operation_type=OperationType.TOOL,
        tool_name="web_search",
        status=StepState.FAILED,
        error_message="Connection timed out",
    )
    plan.steps = [step]

    # First pass detects anomaly and offers one correction pass
    res1 = verifier.verify_run(run, plan)
    assert res1.valid is False
    assert run.replan_count == 1
    assert res1.corrected_response is not None

    # Second pass: replan limit reached, recursion prevented
    res2 = verifier.verify_run(run, plan)
    assert res2.valid is False
    assert run.replan_count == 1
    assert res2.corrected_response is None


# ==============================================================================
# 12. STREAM & EVENT INTEGRITY
# ==============================================================================

def test_stream_events_are_ordered_and_do_not_leak_secrets_or_reasoning():
    runtime = AgentRuntime()
    run = runtime.create_run("audit events", "u1")
    runtime._emit(
        run.run_id,
        "step.progress",
        payload={
            "token": "sk-proj-supersecretkey12345678",
            "api_key": "Bearer token-value-1234567890",
            "safe_data": "visible output",
        },
    )
    events = runtime.get_events(run.run_id, "u1")
    assert events is not None and len(events) >= 2
    latest = events[-1]
    assert "[REDACTED]" in latest.payload["token"]
    assert "[REDACTED]" in latest.payload["api_key"]
    assert latest.payload["safe_data"] == "visible output"
    assert "thinking" not in latest.payload


# ==============================================================================
# 13. FEATURE FLAG FALLBACK
# ==============================================================================

@pytest.mark.asyncio
async def test_runtime_feature_flag_fallback():
    runtime = AgentRuntime(enabled=False)
    run = runtime.create_run("disabled flag", "u1")
    result = await runtime.execute(run)
    assert result.status == RunStatus.QUEUED
    assert len(runtime.plans) == 0


# ==============================================================================
# 14. API ENDPOINT INTEGRATION TESTS
# ==============================================================================

def test_api_agent_runs_crud_and_isolation(client):
    runtime: AgentRuntime = client.app.state.agent_runtime
    run = runtime.create_run("test run via api", "local-dev-user")

    # 1. GET /v1/agent/runs/{run_id}
    res = client.get(f"/v1/agent/runs/{run.run_id}")
    assert res.status_code == 200
    data = res.json()
    assert data["run_id"] == run.run_id
    assert data["user_id"] == "local-dev-user"

    # 2. GET /v1/agent/runs/{run_id}/steps
    res_steps = client.get(f"/v1/agent/runs/{run.run_id}/steps")
    assert res_steps.status_code == 200
    assert "steps" in res_steps.json()

    # 3. GET /v1/agent/runs/{run_id}/events
    res_events = client.get(f"/v1/agent/runs/{run.run_id}/events")
    assert res_events.status_code == 200
    assert len(res_events.json()["events"]) >= 1

    # 4. Cross-user 404 isolation
    res_alien = client.get(
        f"/v1/agent/runs/{run.run_id}",
        headers={"X-HINAA-Dev-User": "another-user"},
    )
    assert res_alien.status_code == 404

    # 5. POST /v1/agent/runs/{run_id}/cancel
    res_cancel = client.post(f"/v1/agent/runs/{run.run_id}/cancel")
    assert res_cancel.status_code == 200
    assert res_cancel.json()["status"] == "cancelled"
    assert res_cancel.json()["idempotent"] is True

    # 6. POST /v1/agent/runs/{run_id}/resume
    run.status = RunStatus.INTERRUPTED
    res_resume = client.post(f"/v1/agent/runs/{run.run_id}/resume")
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] == "executing"

    # 7. POST /v1/agent/runs/{run_id}/recover
    recovery_run = runtime.create_run("recoverable run via api", "local-dev-user")
    recovery_run.status = RunStatus.EXECUTING
    res_recover = client.post(f"/v1/agent/runs/{recovery_run.run_id}/recover")
    assert res_recover.status_code == 200
    assert res_recover.json()["status"] == "interrupted"


# ==============================================================================
# 15. FAILURE CLASSIFICATION
# ==============================================================================

def test_mapped_provider_connection_error_is_classified_retryable():
    """Measured before the fix: HinaaError is a dataclass Exception, so its args
    stay empty and str(err) == "". The runtime's transient branch scraped str()
    for keywords, which matched nothing — so a gateway connection reset failed
    the step on the first attempt and the turn ended with no text at all.
    """
    reset = HinaaError(
        code="PROVIDER_UNREACHABLE",
        status_code=500,
        message="Connection Error",
        developer_message="APIConnectionError: [Errno 64] Connection reset by peer",
    )
    assert str(reset) == ""
    assert is_retryable(reset) is True


@pytest.mark.parametrize(
    "code,message",
    [
        ("SAFETY_REFUSAL", "Refusal due to safety policy"),
        ("AUTH_REQUIRED", "Authentication required for task management"),
        ("PROVIDER_AUTH_FAILED", "Authentication Failed"),
        ("VALIDATION_ERROR", "Invalid sessionId"),
    ],
)
def test_permanent_failures_are_not_retried(code: str, message: str) -> None:
    assert is_retryable(HinaaError(code=code, status_code=400, message=message)) is False


@pytest.mark.asyncio
async def test_runtime_retries_a_step_that_hits_a_transient_provider_error():
    """The classifier is only half the guarantee: the runtime has to actually
    re-run the step, otherwise one gateway reset still ends the turn silent.
    """
    calls = 0

    async def flaky_executor(step):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HinaaError(
                code="PROVIDER_UNREACHABLE",
                status_code=500,
                message="Connection Error",
            )
        return {"data": "answered on the second attempt"}

    runtime = AgentRuntime(executor=flaky_executor)
    run = runtime.create_run("transient provider reset", "u1")
    result = await runtime.execute(run)

    assert result.status == RunStatus.COMPLETED
    assert calls == 2
    event_types = [e.event_type for e in runtime.get_events(run.run_id, "u1")]
    assert "agent.step.retrying" in event_types
