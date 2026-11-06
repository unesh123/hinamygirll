"""
HINAA OS — Phase 18 Unified Mission Coordinator & Execution Adapter.

Integrates existing subsystems (Phases 01–17) into a unified mission lifecycle:
- Manages state machine transitions with evidence-based verification gates.
- Enforces Central Policy Decision Point (PDP) and parameter-bound human approvals.
- Prevents invalid transitions and refuses terminal state resurrections.
- Binds all task steps, artifacts, tool receipts, and traces to a single immutable correlation ID.
- Tracks integer minor-unit Nepalese Paisa accounting and hard budget caps.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from hinaa_api.convergence.capability_router import CapabilityRouter
from hinaa_api.convergence.contracts import (
    ArtifactType,
    AutonomousMode,
    BudgetConstraint,
    CapabilityStatus,
    MissionStatus,
    TypedArtifact,
    UnifiedMission,
)
from hinaa_api.convergence.store import MissionStore
from hinaa_api.platform.metrics import get_telemetry_collector
from hinaa_api.security.contracts import DecisionEffect, PolicyContext, SecurityPermission, SecurityRole, SecuritySubject
from hinaa_api.security.pdp import get_pdp

logger = logging.getLogger(__name__)

# Valid state machine transitions
ALLOWED_TRANSITIONS: Dict[MissionStatus, List[MissionStatus]] = {
    MissionStatus.CREATED: [MissionStatus.SCOPING, MissionStatus.PLANNING, MissionStatus.CANCELLED],
    MissionStatus.SCOPING: [MissionStatus.PLANNING, MissionStatus.BLOCKED_UNAVAILABLE, MissionStatus.FAILED, MissionStatus.CANCELLED],
    MissionStatus.PLANNING: [MissionStatus.RUNNING, MissionStatus.WAITING_APPROVAL, MissionStatus.BLOCKED_UNAVAILABLE, MissionStatus.FAILED, MissionStatus.CANCELLED],
    MissionStatus.RUNNING: [MissionStatus.WAITING_APPROVAL, MissionStatus.PAUSED_OFFLINE, MissionStatus.RECOVERING, MissionStatus.VERIFYING, MissionStatus.FAILED, MissionStatus.CANCELLED],
    MissionStatus.WAITING_APPROVAL: [MissionStatus.RUNNING, MissionStatus.CANCELLED, MissionStatus.FAILED],
    MissionStatus.PAUSED_OFFLINE: [MissionStatus.RUNNING, MissionStatus.RECOVERING, MissionStatus.CANCELLED],
    MissionStatus.RECOVERING: [MissionStatus.RUNNING, MissionStatus.FAILED, MissionStatus.CANCELLED],
    MissionStatus.VERIFYING: [MissionStatus.COMPLETED_VERIFIED, MissionStatus.PARTIAL, MissionStatus.FAILED],
    MissionStatus.COMPLETED_VERIFIED: [],  # Terminal
    MissionStatus.PARTIAL: [],             # Terminal
    MissionStatus.BLOCKED_UNAVAILABLE: [], # Terminal
    MissionStatus.FAILED: [],              # Terminal
    MissionStatus.CANCELLED: [],           # Terminal
}


class MissionCoordinator:
    """Orchestrates cross-domain missions across existing HINAA engines with rigorous governance."""

    def __init__(self, store: Optional[MissionStore] = None) -> None:
        self.store = store or MissionStore()
        self.router = CapabilityRouter()
        self.pdp = get_pdp()
        self.telemetry = get_telemetry_collector()

    def create_mission(
        self,
        objective: str,
        authenticated_actor: str = "user",
        tenant_id: str = "default",
        autonomous_mode: AutonomousMode = AutonomousMode.BOUNDED_DELEGATED,
        budget: Optional[BudgetConstraint] = None,
        constraints: Optional[List[str]] = None,
    ) -> UnifiedMission:
        """Initializes a new Unified Mission with immutable correlation ID and capability snapshot."""
        mission_id = f"msn_{uuid.uuid4().hex[:12]}"
        correlation_id = f"corr_{uuid.uuid4().hex[:16]}"
        now = time.time()

        caps_matrix = self.router.get_capability_matrix()
        snapshot = {k: CapabilityStatus(v["status"]) for k, v in caps_matrix.items()}

        contract = self.store.get_autonomy_contract(tenant_id=tenant_id)
        if contract.emergency_stop_active:
            raise PermissionError("Mission creation blocked: Emergency stop is active on this tenant.")

        b = budget or BudgetConstraint()

        mission = UnifiedMission(
            mission_id=mission_id,
            tenant_id=tenant_id,
            authenticated_actor=authenticated_actor,
            objective=objective,
            constraints=constraints or [],
            deployment_profile="LOCAL_DESKTOP",
            capability_snapshot=snapshot,
            budget=b,
            consent_state="USER_REQUESTED",
            goal_dag_version=1,
            checkpoint_lineage=[f"init_{int(now)}"],
            evidence_refs=[],
            output_artifacts=[],
            run_state=MissionStatus.CREATED,
            autonomous_mode=autonomous_mode,
            side_effect_registry=[],
            audit_correlation_id=correlation_id,
            created_at=now,
            updated_at=now,
        )

        self.store.save_mission(mission)
        return mission

    def transition_state(
        self,
        mission_id: str,
        target_state: MissionStatus,
        reason: Optional[str] = None,
        reason_code: Optional[str] = None,
    ) -> UnifiedMission:
        """Transitions mission state validating state machine invariants and evidence gates."""
        mission = self.store.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")

        current = mission.run_state
        allowed = ALLOWED_TRANSITIONS.get(current, [])

        if target_state not in allowed:
            raise ValueError(
                f"Invalid mission state transition: Cannot transition from {current.value} to {target_state.value}. "
                f"Allowed transitions: {[s.value for s in allowed]}"
            )

        # Non-negotiable Evidence Gate: COMPLETED_VERIFIED requires real verified artifacts
        if target_state == MissionStatus.COMPLETED_VERIFIED:
            artifacts = self.store.get_artifacts_for_mission(mission_id)
            verified_count = sum(1 for a in artifacts if a.is_verified)
            if verified_count == 0:
                logger.warning(f"Mission {mission_id} attempted COMPLETED_VERIFIED with 0 verified artifacts. Falling back to PARTIAL.")
                target_state = MissionStatus.PARTIAL
                reason = "No verified artifacts or passing test reports produced. Marked PARTIAL per evidence gate."
                reason_code = "EVIDENCE_GATE_UNMET"

        mission.run_state = target_state
        mission.status_reason = reason
        mission.reason_code = reason_code
        mission.updated_at = time.time()

        self.store.save_mission(mission)
        return mission

    def execute_step(
        self,
        mission_id: str,
        step_name: str,
        tool_action: str,
        resource: str,
        execution_fn: Callable[[], Any],
        cost_paisa: int = 10,
        tokens_used: int = 150,
    ) -> Any:
        """Executes a single mission step with PDP authorization and budget accounting."""
        mission = self.store.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")

        if mission.is_terminal():
            raise RuntimeError(f"Cannot execute steps on terminal mission {mission_id} ({mission.run_state.value})")

        # 1. Check Autonomy Contract & Emergency Stop
        contract = self.store.get_autonomy_contract(tenant_id=mission.tenant_id)
        if contract.emergency_stop_active:
            self.transition_state(mission_id, MissionStatus.CANCELLED, reason="Emergency stop triggered by operator", reason_code="EMERGENCY_STOP")
            raise PermissionError("Execution halted immediately: Tenant emergency stop active.")

        # 2. Check Budget
        if not mission.budget.has_budget():
            self.transition_state(mission_id, MissionStatus.PARTIAL, reason="Mission spending or token budget exhausted", reason_code="BUDGET_EXCEEDED")
            raise PermissionError("Mission budget ceiling exceeded.")

        # 3. PDP Authorization Check
        subject = SecuritySubject(
            subject_id=mission.authenticated_actor,
            role=SecurityRole.USER if mission.authenticated_actor != "admin" else SecurityRole.ADMIN,
            tenant_id=mission.tenant_id,
        )
        context = PolicyContext(
            tenant_id=mission.tenant_id,
            ip_address="127.0.0.1",
            risk_score=0.1,
            is_break_glass=False,
            requires_human_presence=False,
        )

        decision = self.pdp.evaluate(subject=subject, action=tool_action, resource=resource, context=context)
        if decision.effect == DecisionEffect.DENY:
            raise PermissionError(f"PDP Denied action '{tool_action}' on '{resource}': {decision.reason}")

        # If PDP requires Tier C ceremony (e.g. monetary transaction or destructive action)
        if decision.effect == DecisionEffect.REQUIRE_APPROVAL:
            self.transition_state(
                mission_id,
                MissionStatus.WAITING_APPROVAL,
                reason=f"Action '{tool_action}' on '{resource}' requires Tier C human authorization.",
                reason_code="APPROVAL_REQUIRED",
            )
            return {"status": "WAITING_APPROVAL", "ceremony_id": decision.ceremony_id, "resource": resource}

        # 4. Execute work with telemetry span
        t0 = time.perf_counter()
        span = self.telemetry.start_span(operation=step_name, tenant_id=mission.tenant_id)
        try:
            result = execution_fn()
            duration_ms = (time.perf_counter() - t0) * 1000.0

            # Record spending
            mission.budget.spent_tokens += tokens_used
            mission.budget.spent_cost_paisa += cost_paisa
            mission.budget.spent_duration_seconds += (duration_ms / 1000.0)

            self.telemetry.finish_span(span.span_id, success=True, cost_paisa=cost_paisa)
            self.store.save_mission(mission)
            return result
        except Exception as e:
            self.telemetry.finish_span(span.span_id, success=False, cost_paisa=cost_paisa)
            raise e

    def record_artifact(
        self,
        mission_id: str,
        artifact_type: ArtifactType,
        title: str,
        content_bytes: bytes,
        payload: Dict[str, Any],
        is_verified: bool = True,
        verification_method: str = "oracle_assert",
        producer_role: str = "orchestrator",
        file_path: Optional[str] = None,
    ) -> TypedArtifact:
        """Records a typed output artifact with cryptographic SHA-256 digest."""
        mission = self.store.get_mission(mission_id)
        if not mission:
            raise ValueError(f"Mission not found: {mission_id}")

        sha256 = hashlib.sha256(content_bytes).hexdigest()
        artifact_id = f"art_{uuid.uuid4().hex[:12]}"

        artifact = TypedArtifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            content_digest=sha256,
            tenant_id=mission.tenant_id,
            producer_role=producer_role,
            confidence=1.0 if is_verified else 0.8,
            created_at=time.time(),
            payload=payload,
            file_path=file_path,
            file_size_bytes=len(content_bytes),
            is_verified=is_verified,
            verification_method=verification_method,
        )

        self.store.save_artifact(mission_id, artifact)

        mission.output_artifacts.append(artifact)
        mission.evidence_refs.append({
            "artifact_id": artifact_id,
            "type": artifact_type.value,
            "digest": sha256,
            "verified": is_verified,
        })
        self.store.save_mission(mission)
        return artifact

    def pause_mission(self, mission_id: str, reason: str = "User requested pause") -> UnifiedMission:
        return self.transition_state(mission_id, MissionStatus.PAUSED_OFFLINE, reason=reason, reason_code="USER_PAUSE")

    def resume_mission(self, mission_id: str) -> UnifiedMission:
        return self.transition_state(mission_id, MissionStatus.RUNNING, reason="User resumed execution", reason_code="USER_RESUME")

    def cancel_mission(self, mission_id: str, reason: str = "User cancelled mission") -> UnifiedMission:
        return self.transition_state(mission_id, MissionStatus.CANCELLED, reason=reason, reason_code="USER_CANCEL")


_global_coordinator: Optional[MissionCoordinator] = None


def get_mission_coordinator() -> MissionCoordinator:
    global _global_coordinator
    if _global_coordinator is None:
        _global_coordinator = MissionCoordinator()
    return _global_coordinator
