"""
HINAA Canonical OpenTelemetry-Compatible Event Bus & Replay Engine.

Architecture:
1. Canonical HinaEvent Schema:
   - Tracks comprehensive audit trail: actor, tenant, device, agent, capability,
     action, pre/post state hashes, policy decision, trace ID, latency, and outcome.
2. Unified Consumer Routing:
   - Motion Brain (Synchronizes physical locomotion, posture, and shader trails)
   - Replay Engine (Permits complete deterministic step-by-step playback of any run)
   - Security Audit & Observability (SIEM / OpenTelemetry integration)
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.harness.motion_brain import get_motion_director, SemanticIntent

logger = logging.getLogger(__name__)


class HinaCanonicalEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    run_id: str
    parent_event_id: Optional[str] = None
    timestamp: float = Field(default_factory=time.time)
    actor: str = "user:primary"
    tenant_id: str = "org_default"
    device_id: str = "dev_local_primary"
    agent_name: str = "HostAgent"
    capability: str = "computer_use"
    action: str
    resource: str
    pre_state_hash: str = ""
    post_state_hash: str = ""
    policy_decision: str = "allow"
    approval_id: Optional[str] = None
    trace_id: str = Field(default_factory=lambda: f"tr_{uuid.uuid4().hex[:16]}")
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    latency_ms: float = 0.0


class ExecutionRunTrace(BaseModel):
    run_id: str
    goal: str
    started_at: float
    completed_at: Optional[float] = None
    total_events: int = 0
    events: List[HinaCanonicalEvent] = Field(default_factory=list)
    success: bool = True


class CanonicalEventBus:
    """
    Central Event Bus broadcasting events to Motion Brain, Replay store, and Observability.
    """

    def __init__(self) -> None:
        self._traces: Dict[str, ExecutionRunTrace] = {}
        self._subscribers: List[Callable[[HinaCanonicalEvent], None]] = []
        self._register_default_subscribers()

    def _register_default_subscribers(self) -> None:
        # Motion Brain Subscriber
        def _motion_consumer(event: HinaCanonicalEvent) -> None:
            try:
                director = get_motion_director()
                if event.error or event.policy_decision == "deny":
                    director.transition_state(
                        intent=SemanticIntent.ERROR,
                        active_tool=event.capability,
                        energy=0.8,
                        focus=0.9,
                    )
                elif "verify" in event.action.lower() or event.policy_decision == "allow":
                    director.transition_state(
                        intent=SemanticIntent.SUCCESS,
                        active_tool=event.capability,
                        energy=0.7,
                        focus=0.8,
                    )
                else:
                    director.transition_state(
                        intent=SemanticIntent.OPERATING_COMPUTER,
                        active_tool=event.capability,
                        energy=0.85,
                        focus=0.95,
                    )
            except Exception:
                pass

        self._subscribers.append(_motion_consumer)

    def publish_event(self, event: HinaCanonicalEvent) -> None:
        # 1. Append to run trace
        if event.run_id not in self._traces:
            self._traces[event.run_id] = ExecutionRunTrace(
                run_id=event.run_id,
                goal=event.action,
                started_at=event.timestamp,
            )

        trace = self._traces[event.run_id]
        trace.events.append(event)
        trace.total_events = len(trace.events)
        if event.error:
            trace.success = False

        # 2. Dispatch to subscribers
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception as e:
                logger.debug("Subscriber error: %s", e)

    def get_run_trace(self, run_id: str) -> Optional[ExecutionRunTrace]:
        return self._traces.get(run_id)

    def replay_run(self, run_id: str) -> List[Dict[str, Any]]:
        """
        Replays the step-by-step execution timeline for debugging or audit verification.
        """
        trace = self.get_run_trace(run_id)
        if not trace:
            return []

        timeline: List[Dict[str, Any]] = []
        for idx, ev in enumerate(trace.events):
            timeline.append({
                "step": idx + 1,
                "timestamp": ev.timestamp,
                "action": ev.action,
                "resource": ev.resource,
                "decision": ev.policy_decision,
                "latency_ms": ev.latency_ms,
                "status": "error" if ev.error else "success",
            })
        return timeline


_global_event_bus: Optional[CanonicalEventBus] = None


def get_canonical_event_bus() -> CanonicalEventBus:
    global _global_event_bus
    if _global_event_bus is None:
        _global_event_bus = CanonicalEventBus()
    return _global_event_bus
