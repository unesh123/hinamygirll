"""
Test Suite for Enterprise Durable Runtime & Event Sourcing (Temporal Paradigm).
"""

import pytest
import tempfile
from hinaa_api.durable.runtime import (
    DurableRuntime,
    WorkflowStep,
    WorkflowStatus,
)


@pytest.mark.asyncio
async def test_durable_workflow_execution_and_event_hashing():
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime = DurableRuntime(checkpoint_dir=tmp_dir)

        # Register handlers
        executed_steps = []

        def step_handler(params, state):
            name = params.get("name")
            executed_steps.append(name)
            return f"output_{name}"

        runtime.register_step_handler("generic_step", step_handler)

        steps = [
            WorkflowStep(step_id="s1", name="Fetch Logs", idempotency_key="idemp_1", handler_name="generic_step", params={"name": "step_1"}),
            WorkflowStep(step_id="s2", name="Analyze Metrics", idempotency_key="idemp_2", handler_name="generic_step", params={"name": "step_2"}),
            WorkflowStep(step_id="s3", name="Deploy Canary", idempotency_key="idemp_3", handler_name="generic_step", params={"name": "step_3"}),
        ]

        result = await runtime.execute_workflow(
            workflow_id="wf_canary_01",
            steps=steps,
            initial_state={"env": "production"},
        )

        assert result["status"] == WorkflowStatus.COMPLETED
        assert result["total_events"] > len(steps)
        assert result["final_hash"] is not None
        assert executed_steps == ["step_1", "step_2", "step_3"]


@pytest.mark.asyncio
async def test_durable_workflow_crash_and_recovery():
    """Simulates a process crash halfway through execution and verifies resumption from checkpoint."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        runtime = DurableRuntime(checkpoint_dir=tmp_dir)

        executed_steps = []

        def counting_handler(params, state):
            name = params.get("name")
            executed_steps.append(name)
            return len(executed_steps)

        runtime.register_step_handler("counting", counting_handler)

        steps = [
            WorkflowStep(step_id="s1", name="Step 1", idempotency_key="id_1", handler_name="counting", params={"name": "step_1"}),
            WorkflowStep(step_id="s2", name="Step 2", idempotency_key="id_2", handler_name="counting", params={"name": "step_2"}),
            WorkflowStep(step_id="s3", name="Step 3", idempotency_key="id_3", handler_name="counting", params={"name": "step_3"}),
            WorkflowStep(step_id="s4", name="Step 4", idempotency_key="id_4", handler_name="counting", params={"name": "step_4"}),
        ]

        # 1. Run until simulated crash at step 2
        with pytest.raises(RuntimeError, match="Simulated Process Crash"):
            await runtime.execute_workflow(
                workflow_id="wf_crash_test",
                steps=steps,
                simulate_crash_at_step=2,
            )

        assert executed_steps == ["step_1", "step_2"]

        # Checkpoint must exist at step index 1 (Step 2 completed)
        chk = runtime.load_latest_checkpoint("wf_crash_test")
        assert chk is not None
        assert chk.completed_step_index == 1
        assert "id_1" in chk.idempotency_keys
        assert "id_2" in chk.idempotency_keys

        # 2. Re-instantiate runtime and resume workflow
        new_runtime = DurableRuntime(checkpoint_dir=tmp_dir)
        new_runtime.register_step_handler("counting", counting_handler)

        resumed_result = await new_runtime.execute_workflow(
            workflow_id="wf_crash_test",
            steps=steps,
        )

        assert resumed_result["status"] == WorkflowStatus.COMPLETED
        # Step 1 and 2 must NOT have re-executed! Only 3 and 4!
        assert executed_steps == ["step_1", "step_2", "step_3", "step_4"]
        assert "result_s4" in resumed_result["final_state"]
