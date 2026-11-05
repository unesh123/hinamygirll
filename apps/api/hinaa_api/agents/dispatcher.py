"""
HINAA OS — Phase 11 Task Dispatcher & Decision Gate
Evaluates whether a task requires multi-agent orchestration or single-agent fast path,
and dispatches ready DAG nodes under bounded concurrency.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .budget import BudgetController
from .contracts import (
    AgentRole,
    PermissionTier,
    TaskNode,
    TaskSpec,
    TaskStatus,
)
from .registry import SpecialistRegistry
from .resume import TaskStore

logger = logging.getLogger("hinaa.agents.dispatcher")


class TaskDispatcher:
    """Manages the decision gate and execution scheduling for tasks."""

    def __init__(
        self,
        registry: Optional[SpecialistRegistry] = None,
        task_store: Optional[TaskStore] = None,
        budget_controller: Optional[BudgetController] = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.task_store = task_store or TaskStore()
        self.budget_controller = budget_controller or BudgetController()

    def evaluate_routing_gate(self, goal: str) -> Tuple[str, str]:
        """
        Decision Gate: Evaluates whether to route to single-agent fast path or multi-agent swarm.
        Returns: (routing_mode, rationale)
        routing_mode: 'SINGLE_AGENT_FAST_PATH' | 'MULTI_AGENT_SWARM'
        """
        lower = goal.lower()
        words = lower.split()

        # Keywords demanding multi-agent specialist coordination
        multi_agent_triggers = [
            "build", "implement", "create app", "code", "refactor", "test suite",
            "research", "investigate", "multi-hop", "browse", "scrape",
            "video", "audio", "timeline", "localize", "nepali translation",
            "verify exit code", "docker", "sandbox", "git commit"
        ]

        if any(trig in lower for trig in multi_agent_triggers) or len(words) > 25:
            matched = [t for t in multi_agent_triggers if t in lower]
            return "MULTI_AGENT_SWARM", f"Complex goal requires multi-agent specialization (triggers: {matched})"

        # Simple conversational queries
        return "SINGLE_AGENT_FAST_PATH", "Direct single-agent query; bypassing swarm overhead"

    def get_ready_nodes(self, task: TaskSpec) -> List[TaskNode]:
        """
        Identify nodes whose dependencies are strictly COMPLETED and are READY.
        """
        completed_node_ids = {n.node_id for n in task.nodes if n.status == TaskStatus.COMPLETED}
        ready: List[TaskNode] = []

        for node in task.nodes:
            if node.status in (TaskStatus.READY, TaskStatus.RETRYING, TaskStatus.RECOVERING):
                all_deps_met = all(dep in completed_node_ids for dep in node.dependencies)
                if all_deps_met:
                    ready.append(node)

        return ready

    def dispatch_next_node(
        self,
        task: TaskSpec,
        worker_id: Optional[str] = None,
    ) -> Optional[TaskNode]:
        """
        Acquire lease on the next available ready node under concurrency limits.
        """
        worker_id = worker_id or f"worker-{uuid.uuid4().hex[:6]}"
        admitted, reason = self.budget_controller.check_admission()
        if not admitted:
            logger.warning(f"Admission denied for task {task.task_id}: {reason}")
            return None

        ready_nodes = self.get_ready_nodes(task)
        if not ready_nodes:
            return None

        for candidate in ready_nodes:
            if self.task_store.claim_node_lease(candidate.node_id, worker_id):
                candidate.lease_owner = worker_id
                candidate.status = TaskStatus.RUNNING
                task.active_node_id = candidate.node_id
                self.task_store.save_task(task)
                return candidate

        return None
