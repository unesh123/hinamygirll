"""
HINAA Enterprise Durable Runtime & Event Sourcing (Temporal Paradigm).

Architecture:
1. Workflow Identity & State:
   - DurableWorkflow: workflow_id, run_id, idempotency_key, status.
   - Status: INITIALIZED, RUNNING, CHECKPOINTED, COMPLETED, FAILED, COMPENSATING.

2. Event Sourcing Log (Append-Only Immutable Stream):
   - Sequence of events with cryptographic hash chains (SHA-256):
     hash_n = SHA256(hash_{n-1} + event_type + payload + timestamp)
   - Every side effect (e.g. computer action, external API, approval) is recorded.

3. Checkpoint Engine:
   - Checkpoints state snapshot to durable storage (.hina/checkpoints/).
   - Stores: completed step index, variable bindings, last event hash, idempotency tokens.

4. Crash & Resume (Fault Tolerance):
   - If execution fails or machine restarts halfway through:
     resume_workflow(workflow_id) rehydrates state from the latest valid checkpoint,
     skips already-completed activities using idempotency keys, and completes remaining work.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class WorkflowStatus(str, Enum):
    INITIALIZED = "initialized"
    RUNNING = "running"
    CHECKPOINTED = "checkpointed"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATING = "compensating"


class DurableEvent(BaseModel):
    event_id: str
    run_id: str
    sequence: int
    event_type: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    pre_state_hash: str = ""
    post_state_hash: str = ""
    timestamp: float = Field(default_factory=time.time)


class WorkflowCheckpoint(BaseModel):
    checkpoint_id: str
    workflow_id: str
    run_id: str
    completed_step_index: int
    state_variables: Dict[str, Any] = Field(default_factory=dict)
    last_event_hash: str = ""
    idempotency_keys: List[str] = Field(default_factory=list)
    timestamp: float = Field(default_factory=time.time)


class WorkflowStep(BaseModel):
    step_id: str
    name: str
    idempotency_key: str
    handler_name: str
    params: Dict[str, Any] = Field(default_factory=dict)


class DurableRuntime:
    """
    Enterprise Durable Execution Engine with event sourcing and checkpoint recovery.
    """

    def __init__(self, checkpoint_dir: Optional[str] = None) -> None:
        if checkpoint_dir:
            self.storage_dir = Path(checkpoint_dir)
        else:
            self.storage_dir = Path(".hina/checkpoints")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.events_dir = self.storage_dir / "events"
        self.events_dir.mkdir(parents=True, exist_ok=True)

        self._handlers: Dict[str, Callable[[Dict[str, Any], Dict[str, Any]], Any]] = {}

    def register_step_handler(
        self,
        name: str,
        handler: Callable[[Dict[str, Any], Dict[str, Any]], Any],
    ) -> None:
        self._handlers[name] = handler

    def _hash_event(self, prev_hash: str, event_type: str, payload: dict, ts: float) -> str:
        raw = f"{prev_hash}:{event_type}:{json.dumps(payload, sort_keys=True)}:{ts}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def record_event(
        self,
        run_id: str,
        sequence: int,
        event_type: str,
        payload: dict,
        prev_hash: str,
    ) -> DurableEvent:
        ts = time.time()
        post_hash = self._hash_event(prev_hash, event_type, payload, ts)
        event = DurableEvent(
            event_id=f"ev_{uuid.uuid4().hex[:12]}",
            run_id=run_id,
            sequence=sequence,
            event_type=event_type,
            payload=payload,
            pre_state_hash=prev_hash,
            post_state_hash=post_hash,
            timestamp=ts,
        )

        event_path = self.events_dir / f"{run_id}_{sequence:05d}.json"
        event_path.write_text(event.model_dump_json(indent=2), encoding="utf-8")
        return event

    def save_checkpoint(self, checkpoint: WorkflowCheckpoint) -> None:
        file_path = self.storage_dir / f"chk_{checkpoint.workflow_id}.json"
        file_path.write_text(checkpoint.model_dump_json(indent=2), encoding="utf-8")

    def load_latest_checkpoint(self, workflow_id: str) -> Optional[WorkflowCheckpoint]:
        file_path = self.storage_dir / f"chk_{workflow_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            return WorkflowCheckpoint(**data)
        except Exception as e:
            logger.warning("Failed to load checkpoint for %s: %s", workflow_id, e)
            return None

    async def execute_workflow(
        self,
        workflow_id: str,
        steps: List[WorkflowStep],
        initial_state: Optional[Dict[str, Any]] = None,
        simulate_crash_at_step: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes or resumes a durable workflow.
        If a checkpoint exists, it starts from step `checkpoint.completed_step_index + 1`.
        """
        run_id = f"run_{uuid.uuid4().hex[:12]}"
        state = dict(initial_state or {})
        last_hash = "GENESIS"
        sequence = 0
        idempotency_keys: List[str] = []

        # 1. Check for existing checkpoint to resume
        checkpoint = self.load_latest_checkpoint(workflow_id)
        start_step_index = 0
        if checkpoint:
            start_step_index = checkpoint.completed_step_index + 1
            state.update(checkpoint.state_variables)
            last_hash = checkpoint.last_event_hash
            idempotency_keys = list(checkpoint.idempotency_keys)
            logger.info("Resuming workflow %s from checkpoint at step %d", workflow_id, start_step_index)

        # Record workflow start event
        ev = self.record_event(run_id, sequence, "workflow_started", {"workflow_id": workflow_id, "resumed_from": start_step_index}, last_hash)
        last_hash = ev.post_state_hash
        sequence += 1

        # 2. Step execution loop with checkpointing
        for idx in range(start_step_index, len(steps)):
            step = steps[idx]

            # Simulate infrastructure/process crash if requested
            if simulate_crash_at_step is not None and idx == simulate_crash_at_step:
                raise RuntimeError(f"Simulated Process Crash at step {idx} ({step.name})")

            # Check idempotency
            if step.idempotency_key in idempotency_keys:
                logger.info("Step %s already executed (idempotency key %s). Skipping side-effect.", step.name, step.idempotency_key)
                continue

            # Record step start
            ev = self.record_event(run_id, sequence, "step_started", {"step_id": step.step_id, "name": step.name}, last_hash)
            last_hash = ev.post_state_hash
            sequence += 1

            # Dispatch step handler
            handler = self._handlers.get(step.handler_name)
            if not handler:
                raise ValueError(f"No handler registered for '{step.handler_name}'")

            result = handler(step.params, state)
            state[f"result_{step.step_id}"] = result
            idempotency_keys.append(step.idempotency_key)

            # Record step completion
            ev = self.record_event(run_id, sequence, "step_completed", {"step_id": step.step_id, "result": str(result)}, last_hash)
            last_hash = ev.post_state_hash
            sequence += 1

            # Checkpoint progress
            chk = WorkflowCheckpoint(
                checkpoint_id=f"chk_{uuid.uuid4().hex[:8]}",
                workflow_id=workflow_id,
                run_id=run_id,
                completed_step_index=idx,
                state_variables=state,
                last_event_hash=last_hash,
                idempotency_keys=idempotency_keys,
            )
            self.save_checkpoint(chk)

        # Record workflow completed
        ev = self.record_event(run_id, sequence, "workflow_completed", {"workflow_id": workflow_id}, last_hash)

        return {
            "status": WorkflowStatus.COMPLETED,
            "workflow_id": workflow_id,
            "run_id": run_id,
            "final_state": state,
            "total_events": sequence + 1,
            "final_hash": ev.post_state_hash,
        }
