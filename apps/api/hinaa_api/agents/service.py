"""
HINAA OS — Phase 11 Unified Agent Orchestration Service Facade
Top-level gateway for managing tasks, DAG lifecycle, approvals, event streams,
specialist registries, and crash recovery.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .budget import BudgetController
from .contracts import (
    AgentRole,
    AgentSpec,
    ApprovalRecord,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
)
from .dispatcher import TaskDispatcher
from .event_log import EventLogStore
from .handoff import ContextHandoffManager
from .planner import TaskPlanner
from .policy_bridge import PolicyBridge
from .reflection import AgentReflector
from .registry import SpecialistRegistry
from .resume import TaskStore
from .supervisor import SupervisorAgent
from .verifier import IndependentVerifier

logger = logging.getLogger("hinaa.agents.service")


class AgentOrchestrationService:
    """Unified service facade for Phase 11 multi-agent swarms and tooling."""

    def __init__(
        self,
        db_path_events: Optional[str | Path] = None,
        db_path_tasks: Optional[str | Path] = None,
    ) -> None:
        self.registry = SpecialistRegistry()
        self.task_store = TaskStore(db_path=db_path_tasks)
        self.event_log = EventLogStore(db_path=db_path_events)
        self.policy_bridge = PolicyBridge()
        self.budget_controller = BudgetController()
        self.planner = TaskPlanner(self.registry)
        self.verifier = IndependentVerifier()
        self.handoff_manager = ContextHandoffManager()
        self.dispatcher = TaskDispatcher(self.registry, self.task_store, self.budget_controller)
        self.reflector = AgentReflector()

        self.supervisor = SupervisorAgent(
            registry=self.registry,
            task_store=self.task_store,
            event_log=self.event_log,
            policy_bridge=self.policy_bridge,
            budget_controller=self.budget_controller,
            planner=self.planner,
            verifier=self.verifier,
            handoff_manager=self.handoff_manager,
        )

    # -------------------------------------------------------------------------
    # Task Operations
    # -------------------------------------------------------------------------

    def create_task(
        self,
        goal: str,
        tenant_id: str = "default",
        user_id: str = "user-default",
        language: str = "en",
    ) -> TaskSpec:
        """Create and plan a new task with DAG."""
        return self.supervisor.create_task(
            goal=goal,
            tenant_id=tenant_id,
            user_id=user_id,
            language=language,
        )

    def get_task(self, task_id: str) -> Optional[TaskSpec]:
        """Fetch task specification and node states."""
        return self.task_store.get_task(task_id)

    def run_task(self, task_id: str) -> Optional[TaskResult]:
        """Execute task to completion or next approval checkpoint."""
        task = self.task_store.get_task(task_id)
        if not task:
            return None
        res = self.supervisor.run_task_to_completion(task)
        # Stage reflections if completed
        if res.status == TaskStatus.COMPLETED:
            self.reflector.stage_task_reflections(task, res)
        return res

    def get_task_events(self, task_id: str, since_sequence: int = 0, limit: int = 100) -> List[TaskEvent]:
        """Retrieve ordered task events since sequence cursor."""
        return self.event_log.get_events(task_id, since_sequence=since_sequence, limit=limit)

    def approve_action(
        self,
        task_id: str,
        approval_id: str,
        signature: str,
        tenant_id: str = "default",
    ) -> Tuple[bool, Optional[str]]:
        """Approve pending Tier C action with cryptographic signature and resume execution."""
        task = self.task_store.get_task(task_id)
        if not task:
            return False, "Task not found"

        # Check pending approval record
        appr = self.policy_bridge.get_approval(approval_id)
        if not appr:
            return False, "Approval record not found"

        if appr.task_id != task_id:
            return False, "Approval record task_id mismatch"

        appr.approved = True
        appr.signature = signature

        # Find waiting node
        waiting_nodes = [n for n in task.nodes if n.status == TaskStatus.WAITING_APPROVAL]
        if not waiting_nodes:
            return False, "No nodes waiting for approval in this task"

        target_node = waiting_nodes[0]
        self.supervisor.execute_node(task, target_node, approval_id=approval_id)

        # Continue task run
        self.supervisor.run_task_to_completion(task)
        return True, "Approval granted and node executed"

    def cancel_task(self, task_id: str, reason: str = "User requested cancellation") -> bool:
        """Cancel a running or queued task."""
        task = self.task_store.get_task(task_id)
        if not task:
            return False

        task.status = TaskStatus.CANCELLED
        for n in task.nodes:
            if n.status in (TaskStatus.READY, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL, TaskStatus.RETRYING):
                n.status = TaskStatus.CANCELLED
                n.error = reason
                if n.lease_owner:
                    self.task_store.release_node_lease(n.node_id, n.lease_owner, TaskStatus.CANCELLED)

        self.task_store.save_task(task)
        self.supervisor.emit_event(
            task_id=task_id,
            actor_role=AgentRole.SUPERVISOR,
            event_type="task.cancelled",
            payload={"reason": reason},
            state_before=TaskStatus.RUNNING,
            state_after=TaskStatus.CANCELLED,
        )
        return True

    def resume_interrupted_tasks(self) -> List[str]:
        """Crash recovery: reset expired leases and resume uncompleted tasks."""
        reset_count = self.task_store.reset_expired_leases()
        logger.info(f"Crash recovery reset {reset_count} expired worker leases.")
        recoverable = self.task_store.find_recoverable_tasks()
        resumed: List[str] = []
        for tid in recoverable:
            t = self.task_store.get_task(tid)
            if t and t.status in (TaskStatus.RUNNING, TaskStatus.RETRYING, TaskStatus.RECOVERING):
                self.supervisor.run_task_to_completion(t)
                resumed.append(tid)
        return resumed

    def get_artifacts(self, task_id: str) -> List[Dict[str, Any]]:
        """Fetch verified artifacts generated during task execution."""
        task = self.task_store.get_task(task_id)
        return task.artifacts if task else []

    # -------------------------------------------------------------------------
    # Registry & System Health
    # -------------------------------------------------------------------------

    def list_specialists(self) -> List[AgentSpec]:
        """List all 10 registered specialist agent specs and capability grants."""
        return self.registry.list_all_agents()

    def get_health(self) -> Dict[str, Any]:
        """Return orchestration health status, concurrency meters, and emergency stop flag."""
        return {
            "status": "HEALTHY",
            "emergency_stop": self.policy_bridge.is_stopped(),
            "active_concurrency": self.budget_controller.active_concurrency,
            "max_concurrency": self.budget_controller.max_concurrency,
            "specialist_count": len(self.registry.list_all_agents()),
            "budget": self.budget_controller.ledger.model_dump(),
        }


# Global singleton instance
agent_service = AgentOrchestrationService()
