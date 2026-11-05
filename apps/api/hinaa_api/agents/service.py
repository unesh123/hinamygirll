"""
HINAA OS — Phase 11 & Phase 12 Unified Agent Orchestration Service Facade
Top-level gateway for managing tasks, 3-way adaptive execution (fast path, flat swarm,
and hierarchical teams), DAG lifecycle, approvals, event streams, specialist registries,
and crash recovery.
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
    ExecutionMode,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    TeamSpec,
    TeamType,
)
from .dispatcher import TaskDispatcher
from .event_log import EventLogStore
from .handoff import ContextHandoffManager
from .hierarchy_planner import HierarchicalPlanner
from .hierarchy_supervisor import HierarchicalSupervisor
from .planner import TaskPlanner
from .policy_bridge import PolicyBridge
from .reflection import AgentReflector
from .registry import SpecialistRegistry
from .resume import TaskStore
from .supervisor import SupervisorAgent
from .verifier import IndependentVerifier

logger = logging.getLogger("hinaa.agents.service")


class AgentOrchestrationService:
    """Unified service facade for Phase 11 multi-agent swarms and Phase 12 hierarchical teams."""

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
        self.hierarchy_planner = HierarchicalPlanner(self.registry)
        self.verifier = IndependentVerifier()
        self.handoff_manager = ContextHandoffManager()
        self.dispatcher = TaskDispatcher(self.registry, self.task_store, self.budget_controller)
        self.reflector = AgentReflector()

        # Flat Multi-Agent Supervisor
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

        # Hierarchical Team Supervisor
        self.hierarchical_supervisor = HierarchicalSupervisor(
            registry=self.registry,
            task_store=self.task_store,
            event_log=self.event_log,
            policy_bridge=self.policy_bridge,
            budget_controller=self.budget_controller,
            planner=self.hierarchy_planner,
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
        execution_mode: Optional[ExecutionMode] = None,
    ) -> TaskSpec:
        """Create and plan a new task with DAG (auto-routing or explicit mode)."""
        mode = execution_mode or self.dispatcher.evaluate_execution_mode(goal)
        if mode == ExecutionMode.HIERARCHICAL_TEAM:
            return self.hierarchical_supervisor.create_hierarchical_task(
                goal=goal,
                tenant_id=tenant_id,
                user_id=user_id,
                language=language,
            )
        else:
            task = self.supervisor.create_task(
                goal=goal,
                tenant_id=tenant_id,
                user_id=user_id,
                language=language,
            )
            task.execution_mode = mode
            self.task_store.save_task(task)
            return task

    def create_hierarchical_task(
        self,
        goal: str,
        tenant_id: str = "default",
        user_id: str = "user-default",
        language: str = "en",
    ) -> TaskSpec:
        """Explicitly create and plan a nested hierarchical team mission."""
        return self.hierarchical_supervisor.create_hierarchical_task(
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

        if task.execution_mode == ExecutionMode.HIERARCHICAL_TEAM:
            res = self.hierarchical_supervisor.run_task_to_completion(task)
        else:
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

        appr = self.policy_bridge.get_approval(approval_id)
        if not appr:
            return False, "Approval record not found"

        if appr.task_id != task_id:
            return False, "Approval record task_id mismatch"

        appr.approved = True
        appr.signature = signature

        waiting_nodes = [n for n in task.nodes if n.status == TaskStatus.WAITING_APPROVAL]
        if not waiting_nodes:
            return False, "No nodes waiting for approval in this task"

        target_node = waiting_nodes[0]
        if task.execution_mode == ExecutionMode.HIERARCHICAL_TEAM:
            self.hierarchical_supervisor.execute_node(task, target_node, approval_id=approval_id)
            self.hierarchical_supervisor.run_task_to_completion(task)
        else:
            self.supervisor.execute_node(task, target_node, approval_id=approval_id)
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
                if t.execution_mode == ExecutionMode.HIERARCHICAL_TEAM:
                    self.hierarchical_supervisor.run_task_to_completion(t)
                else:
                    self.supervisor.run_task_to_completion(t)
                resumed.append(tid)
        return resumed

    def get_artifacts(self, task_id: str) -> List[Dict[str, Any]]:
        """Fetch verified artifacts generated during task execution."""
        task = self.task_store.get_task(task_id)
        return task.artifacts if task else []

    # -------------------------------------------------------------------------
    # Teams & Registry
    # -------------------------------------------------------------------------

    def list_teams(self) -> List[TeamSpec]:
        """List all 4 canonical team templates (Engineering, Research, Creative, Operations)."""
        return self.registry.list_teams()

    def get_team_spec(self, team_type: TeamType) -> Optional[TeamSpec]:
        """Fetch specification for a canonical team template."""
        return self.registry.get_team_spec(team_type)

    def get_task_teams(self, task_id: str) -> Dict[str, Any]:
        """Fetch team delegation runs and outcomes for a hierarchical task."""
        task = self.task_store.get_task(task_id)
        if not task:
            return {"task_id": task_id, "team_runs": [], "team_results": []}
        return {
            "task_id": task_id,
            "execution_mode": task.execution_mode.value,
            "team_runs": [r.model_dump() for r in task.team_runs],
            "team_results": [r.model_dump() for r in task.team_results],
        }

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
            "team_count": len(self.registry.list_teams()),
            "budget": self.budget_controller.ledger.model_dump(),
        }


# Global singleton instance
agent_service = AgentOrchestrationService()
