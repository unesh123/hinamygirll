"""
HINAA OS — Phase 11 Acyclic Dependency Task Planner
Generates verified Directed Acyclic Graphs (DAGs) for specialist multi-agent swarms,
validates dependency graphs, detects cycles, and ensures least-privilege role assignments.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    AgentRole,
    PermissionTier,
    TaskNode,
    TaskStatus,
)
from .registry import SpecialistRegistry

logger = logging.getLogger("hinaa.agents.planner")


class DAGCycleError(ValueError):
    """Raised when a task graph contains cyclic dependencies."""
    pass


class TaskPlanner:
    """Decomposes user objectives into structured, acyclic specialist execution DAGs."""

    def __init__(self, registry: Optional[SpecialistRegistry] = None) -> None:
        self.registry = registry or SpecialistRegistry()

    def detect_cycles(self, nodes: List[TaskNode]) -> bool:
        """
        Check for cycles using standard DFS / Kahn's algorithm.
        Returns True if a cycle exists, False if acyclic.
        """
        node_map: Dict[str, TaskNode] = {n.node_id: n for n in nodes}
        adj: Dict[str, List[str]] = {n.node_id: [] for n in nodes}

        # Build adjacency: dependency -> dependent node
        for n in nodes:
            for dep in n.dependencies:
                if dep in adj:
                    adj[dep].append(n.node_id)
                elif dep in node_map:
                    adj[dep] = [n.node_id]

        visited: Dict[str, int] = {n.node_id: 0 for n in nodes}  # 0: unvisited, 1: visiting, 2: visited

        def dfs(node_id: str) -> bool:
            visited[node_id] = 1
            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    continue
                if visited[neighbor] == 1:
                    return True  # Cycle detected
                if visited[neighbor] == 0:
                    if dfs(neighbor):
                        return True
            visited[node_id] = 2
            return False

        for n in nodes:
            if visited[n.node_id] == 0:
                if dfs(n.node_id):
                    return True
        return False

    def topological_sort(self, nodes: List[TaskNode]) -> List[TaskNode]:
        """
        Return nodes in topological order (dependencies first).
        Raises DAGCycleError if cyclic.
        """
        if self.detect_cycles(nodes):
            raise DAGCycleError("DAG cycle detected in task graph dependencies")

        node_map = {n.node_id: n for n in nodes}
        in_degree: Dict[str, int] = {n.node_id: 0 for n in nodes}
        adj: Dict[str, List[str]] = {n.node_id: [] for n in nodes}

        for n in nodes:
            for dep in n.dependencies:
                if dep in node_map:
                    adj[dep].append(n.node_id)
                    in_degree[n.node_id] += 1

        queue: List[str] = [n_id for n_id, deg in in_degree.items() if deg == 0]
        sorted_nodes: List[TaskNode] = []

        while queue:
            curr_id = queue.pop(0)
            sorted_nodes.append(node_map[curr_id])
            for neighbor in adj.get(curr_id, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(sorted_nodes) != len(nodes):
            raise DAGCycleError("DAG cycle detected: unresolved dependencies remain")

        return sorted_nodes

    def validate_dag(self, nodes: List[TaskNode]) -> Tuple[bool, Optional[str]]:
        """Validate DAG acyclicity and specialist capability grants."""
        try:
            self.topological_sort(nodes)
        except DAGCycleError as e:
            return False, str(e)

        node_ids = {n.node_id for n in nodes}
        for n in nodes:
            for dep in n.dependencies:
                if dep not in node_ids:
                    return False, f"Missing dependency '{dep}' for node '{n.node_id}'"

            # Verify specialist role exists and tools match capability grant
            grant = self.registry.get_capability_grant(n.specialist_role)
            if not grant:
                return False, f"Unknown specialist role '{n.specialist_role}'"

            for tool in n.allowed_tools:
                if not self.registry.is_tool_allowed(n.specialist_role, tool):
                    return False, f"Tool '{tool}' not granted to role '{n.specialist_role}'"

        return True, None

    def plan_task(self, task_id: str, goal: str, context: Optional[Dict[str, Any]] = None) -> List[TaskNode]:
        """
        Generate an execution DAG based on the goal description.
        Distinguishes simple single-agent queries from complex multi-step workflows.
        """
        lower_goal = goal.lower()
        context = context or {}

        # 1. Simple queries / fast-path single agent
        is_simple = any(w in lower_goal for w in ["hi", "hello", "who are you", "what time", "namaste"]) and len(lower_goal.split()) < 10
        if is_simple and not any(w in lower_goal for w in ["build", "write", "search", "create", "test", "buy"]):
            return [
                TaskNode(
                    node_id=f"node-{uuid.uuid4().hex[:8]}",
                    task_id=task_id,
                    title="Direct Conversation",
                    specialist_role=AgentRole.SUPERVISOR,
                    dependencies=[],
                    allowed_tools=["synthesize_response"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"goal": goal, "fast_path": True},
                    expected_postcondition="Natural conversational response provided",
                )
            ]

        # 2. Multi-agent workflows
        nodes: List[TaskNode] = []

        # Step A: Research / Exploration (if knowledge, search, docs, or analysis needed)
        needs_research = any(w in lower_goal for w in ["search", "find", "research", "investigate", "docs", "learn", "nepal", "law", "news", "price"])
        research_node_id = None
        if needs_research or "build" in lower_goal or "create" in lower_goal:
            research_node_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=research_node_id,
                    task_id=task_id,
                    title="Gather Background & Technical Evidence",
                    specialist_role=AgentRole.RESEARCHER,
                    dependencies=[],
                    allowed_tools=["crag_search", "fetch_url_content", "extract_citations"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"query": goal, "context": context},
                    expected_postcondition="Verified sources and grounded factual claims extracted",
                )
            )

        # Step B: Engineering / Coding (if code, build, fix, refactor, implement requested)
        needs_code = any(w in lower_goal for w in ["build", "code", "implement", "create app", "write file", "fix", "script", "refactor", "api", "test"])
        eng_node_id = None
        if needs_code:
            eng_node_id = f"node-{uuid.uuid4().hex[:8]}"
            deps = [research_node_id] if research_node_id else []
            nodes.append(
                TaskNode(
                    node_id=eng_node_id,
                    task_id=task_id,
                    title="Implement Solution & Workspace Changes",
                    specialist_role=AgentRole.ENGINEER,
                    dependencies=deps,
                    allowed_tools=["sandbox_read", "sandbox_write", "sandbox_execute", "git_commit_scoped"],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    input_data={"instruction": goal, "upstream_research": research_node_id},
                    expected_postcondition="Files written and tested within isolated workspace sandbox",
                )
            )

        # Step C: Independent QA / Verification (always accompanies engineering)
        qa_node_id = None
        if eng_node_id:
            qa_node_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=qa_node_id,
                    task_id=task_id,
                    title="Independent QA Verification & Exit Code Auditing",
                    specialist_role=AgentRole.QA,
                    dependencies=[eng_node_id],
                    allowed_tools=["run_test_suite", "verify_file_hash", "check_exit_code"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"target_node": eng_node_id},
                    expected_postcondition="Test suite passed with exit_code 0 and verified artifact checksums",
                )
            )

        # Step D: Localization / Bilingual adaptation (if Nepali/Bilingual requested)
        needs_loc = any(w in lower_goal for w in ["nepali", "bilingual", "नेपाली", "nepal", "romanized", "translate"])
        loc_node_id = None
        if needs_loc:
            loc_node_id = f"node-{uuid.uuid4().hex[:8]}"
            loc_deps = [qa_node_id] if qa_node_id else ([eng_node_id] if eng_node_id else ([research_node_id] if research_node_id else []))
            nodes.append(
                TaskNode(
                    node_id=loc_node_id,
                    task_id=task_id,
                    title="Nepali / English Localization & Cultural Adaptation",
                    specialist_role=AgentRole.LOCALIZATION_SPECIALIST,
                    dependencies=loc_deps,
                    allowed_tools=["translate_text", "validate_devanagari_encoding", "cultural_glossary_lookup"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"goal": goal},
                    expected_postcondition="Devanagari and romanized Nepali verified without corruption",
                )
            )

        # Step E: Supervisor Final Synthesis
        all_prior = [n.node_id for n in nodes]
        final_node_id = f"node-{uuid.uuid4().hex[:8]}"
        nodes.append(
            TaskNode(
                node_id=final_node_id,
                task_id=task_id,
                title="Authoritative Mission Synthesis & Evidence Review",
                specialist_role=AgentRole.SUPERVISOR,
                dependencies=all_prior,
                allowed_tools=["plan_decomposition", "check_policy", "synthesize_response"],
                permission_tier=PermissionTier.TIER_A_READ_ONLY,
                input_data={"goal": goal},
                expected_postcondition="Final verifiable summary synthesized with receipts and artifact links",
            )
        )

        return nodes
