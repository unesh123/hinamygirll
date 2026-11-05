"""
HINAA OS — Phase 11 & Phase 12 Task Dispatcher & Decision Gate
Evaluates 3-way adaptive execution mode (single-agent fast path, flat multi-agent swarm,
or hierarchical team orchestration), and dispatches ready DAG nodes under bounded concurrency.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .budget import BudgetController
from .contracts import (
    AgentRole,
    ExecutionMode,
    PermissionTier,
    TaskNode,
    TaskSpec,
    TaskStatus,
)
from .registry import SpecialistRegistry
from .resume import TaskStore

logger = logging.getLogger("hinaa.agents.dispatcher")


class TaskDispatcher:
    """Manages the 3-way decision gate and execution scheduling for tasks."""

    def __init__(
        self,
        registry: Optional[SpecialistRegistry] = None,
        task_store: Optional[TaskStore] = None,
        budget_controller: Optional[BudgetController] = None,
    ) -> None:
        self.registry = registry or SpecialistRegistry()
        self.task_store = task_store or TaskStore()
        self.budget_controller = budget_controller or BudgetController()

    def evaluate_execution_mode(self, goal: str) -> ExecutionMode:
        """
        Evaluate 3-way adaptive execution mode:
        1. SINGLE_AGENT_FAST_PATH: Direct specialist / simple queries.
        2. FLAT_MULTI_AGENT: Moderate single-workstream multi-step tasks.
        3. HIERARCHICAL_TEAM: Complex multi-team, cross-domain, long-horizon workflows.
        """
        lower = goal.lower()
        words = lower.split()

        # Simple conversational queries
        is_simple = any(w in lower for w in ["hi", "hello", "who are you", "what time", "namaste"]) and len(words) < 10
        if is_simple and not any(w in lower for w in ["build", "write", "search", "create", "test", "buy", "team"]):
            return ExecutionMode.SINGLE_AGENT_FAST_PATH

        # Explicit hierarchical triggers
        hierarchical_triggers = [
            "hierarchical", "nested", "cross-team", "team orchestration",
            "bilingual website build", "workflow w1", "workflow w2", "workflow w3",
            "workflow w4", "workflow w5", "workflow w6", "w1", "w2", "w3", "w4", "w5", "w6",
            "engineering team", "research team", "creative team", "operations team",
            "full-stack app", "multi-team", "nested team"
        ]
        if any(trig in lower for trig in hierarchical_triggers):
            return ExecutionMode.HIERARCHICAL_TEAM

        # Multi-domain cross-cutting triggers (>= 3 distinct domains)
        domains = 0
        if any(w in lower for w in ["build", "code", "implement", "app", "api", "backend", "frontend"]):
            domains += 1
        if any(w in lower for w in ["research", "investigate", "sources", "citations", "crag", "law"]):
            domains += 1
        if any(w in lower for w in ["nepali", "bilingual", "translate", "localization", "devanagari"]):
            domains += 1
        if any(w in lower for w in ["video", "image", "creative", "media", "timeline"]):
            domains += 1
        if any(w in lower for w in ["esewa", "khalti", "payment", "paisa", "commerce"]):
            domains += 1

        if domains >= 3:
            return ExecutionMode.HIERARCHICAL_TEAM

        # Multi-agent triggers
        multi_agent_triggers = [
            "build", "implement", "create app", "code", "refactor", "test suite",
            "research", "investigate", "multi-hop", "browse", "scrape",
            "video", "audio", "timeline", "localize", "nepali translation",
            "verify exit code", "docker", "sandbox", "git commit"
        ]
        if any(trig in lower for trig in multi_agent_triggers) or len(words) > 25:
            return ExecutionMode.FLAT_MULTI_AGENT

        return ExecutionMode.SINGLE_AGENT_FAST_PATH

    def evaluate_routing_gate(self, goal: str) -> Tuple[str, str]:
        """
        Decision Gate: Evaluates whether to route to single-agent fast path, flat multi-agent, or hierarchical teams.
        Returns: (routing_mode, rationale)
        routing_mode: 'SINGLE_AGENT_FAST_PATH' | 'MULTI_AGENT_SWARM' | 'HIERARCHICAL_TEAM'
        """
        mode = self.evaluate_execution_mode(goal)
        if mode == ExecutionMode.SINGLE_AGENT_FAST_PATH:
            return "SINGLE_AGENT_FAST_PATH", "Direct single-agent query; bypassing swarm overhead"
        elif mode == ExecutionMode.HIERARCHICAL_TEAM:
            return "HIERARCHICAL_TEAM", "Complex cross-team mission requires hierarchical team orchestration"
        else:
            return "MULTI_AGENT_SWARM", "Complex goal requires multi-agent specialization"

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
