"""
HINAA OS — Phase 12 Hierarchical Team Planner
Decomposes complex objectives into nested, cross-team delegation workstreams.
Generates acyclic Directed Acyclic Graphs (DAGs) across canonical team templates:
Engineering, Research, Creative, and Operations.
Enforces hard ceilings: max depth <= 2 below global supervisor, max nodes <= 50,
and validates strict capability bounds for all team roles.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    AgentRole,
    BudgetLedger,
    DelegationRequest,
    ExecutionMode,
    PermissionTier,
    TaskNode,
    TaskSpec,
    TaskStatus,
    TeamType,
)
from .planner import DAGCycleError
from .registry import SpecialistRegistry

logger = logging.getLogger("hinaa.agents.hierarchy_planner")

MAX_HIERARCHY_DEPTH = 2
MAX_GRAPH_NODES = 50


class HierarchicalPlanner:
    """Plans multi-team hierarchical task workflows with bounded depth and acyclic dependencies."""

    def __init__(self, registry: Optional[SpecialistRegistry] = None) -> None:
        self.registry = registry or SpecialistRegistry()

    def detect_cycles(self, nodes: List[TaskNode]) -> bool:
        """Check for cycles using standard DFS."""
        node_map: Dict[str, TaskNode] = {n.node_id: n for n in nodes}
        adj: Dict[str, List[str]] = {n.node_id: [] for n in nodes}

        for n in nodes:
            for dep in n.dependencies:
                if dep in adj:
                    adj[dep].append(n.node_id)
                elif dep in node_map:
                    adj[dep] = [n.node_id]

        visited: Dict[str, int] = {n.node_id: 0 for n in nodes}

        def dfs(node_id: str) -> bool:
            visited[node_id] = 1
            for neighbor in adj.get(node_id, []):
                if neighbor not in visited:
                    continue
                if visited[neighbor] == 1:
                    return True
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

    def validate_hierarchical_graph(
        self,
        nodes: List[TaskNode],
        delegations: Optional[List[DelegationRequest]] = None,
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate acyclicity, depth limits (<= 2), node count ceiling (<= 50),
        and role capability grants.
        """
        if len(nodes) > MAX_GRAPH_NODES:
            return False, f"Total nodes ({len(nodes)}) exceeds hard ceiling ({MAX_GRAPH_NODES})"

        if self.detect_cycles(nodes):
            return False, "DAG cycle detected in hierarchical task graph"

        node_ids = {n.node_id for n in nodes}
        for n in nodes:
            if n.depth > MAX_HIERARCHY_DEPTH:
                return False, f"Node '{n.node_id}' depth ({n.depth}) exceeds maximum hierarchy depth ({MAX_HIERARCHY_DEPTH})"

            for dep in n.dependencies:
                if dep not in node_ids:
                    return False, f"Missing dependency '{dep}' for node '{n.node_id}'"

            grant = self.registry.get_capability_grant(n.specialist_role)
            if not grant:
                return False, f"Unknown specialist role '{n.specialist_role}'"

            for tool in n.allowed_tools:
                if not self.registry.is_tool_allowed(n.specialist_role, tool):
                    return False, f"Tool '{tool}' not granted to role '{n.specialist_role}'"

        return True, None

    def plan_hierarchical_mission(
        self,
        task_id: str,
        goal: str,
        tenant_id: str = "default",
        user_id: str = "user-default",
        language: str = "en",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[DelegationRequest], List[TaskNode]]:
        """
        Decomposes complex mission into canonical team workstreams and bounded internal subgraphs.
        """
        lower = goal.lower()
        context = context or {}
        delegations: List[DelegationRequest] = []
        all_nodes: List[TaskNode] = []

        # Determine which teams are involved
        is_w1 = any(w in lower for w in ["bilingual website build", "w1", "full-stack", "website build"])
        is_w2 = any(w in lower for w in ["w2", "research to code", "legal code", "tax calculator", "sourced code"])
        is_w3 = any(w in lower for w in ["w3", "conflict", "qa override", "failing test"])
        is_w4 = any(w in lower for w in ["w4", "recovery", "worker crash", "lease recovery"])
        is_w5 = any(w in lower for w in ["w5", "commerce", "esewa", "khalti", "payment"])
        is_w6 = any(w in lower for w in ["w6", "neural video", "text-to-video", "creative limitation"])

        teams_to_plan: List[TeamType] = []

        if is_w1:
            teams_to_plan = [TeamType.RESEARCH, TeamType.ENGINEERING]
        elif is_w2:
            teams_to_plan = [TeamType.RESEARCH, TeamType.ENGINEERING]
        elif is_w3:
            teams_to_plan = [TeamType.ENGINEERING]
        elif is_w4:
            teams_to_plan = [TeamType.ENGINEERING]
        elif is_w5:
            teams_to_plan = [TeamType.OPERATIONS, TeamType.ENGINEERING]
        elif is_w6:
            teams_to_plan = [TeamType.CREATIVE]
        else:
            # Dynamic team selection based on semantic triggers
            if any(w in lower for w in ["research", "investigate", "source", "law", "nepali", "bilingual"]):
                teams_to_plan.append(TeamType.RESEARCH)
            if any(w in lower for w in ["build", "code", "implement", "app", "fix", "test"]):
                teams_to_plan.append(TeamType.ENGINEERING)
            if any(w in lower for w in ["video", "image", "creative", "media"]):
                teams_to_plan.append(TeamType.CREATIVE)
            if any(w in lower for w in ["commerce", "payment", "paisa", "deploy", "operation"]):
                teams_to_plan.append(TeamType.OPERATIONS)

            if not teams_to_plan:
                teams_to_plan = [TeamType.ENGINEERING]

        prior_team_nodes: List[str] = []

        for team_type in teams_to_plan:
            team_spec = self.registry.get_team_spec(team_type)
            if not team_spec:
                continue

            team_run_id = f"team-run-{team_type.value.lower()}-{uuid.uuid4().hex[:6]}"
            ancestry = [task_id, team_spec.team_id]

            # Create DelegationRequest
            del_req = DelegationRequest(
                parent_task_id=task_id,
                team_run_id=team_run_id,
                principal_id=user_id,
                tenant_id=tenant_id,
                team_type=team_type,
                lead_role=team_spec.lead_role,
                objective=f"{team_spec.team_name} execution for: {goal}",
                acceptance_criteria=[
                    f"{team_spec.team_name} outputs verified",
                    "All node receipts signed and postconditions met",
                ],
                budget_slice=BudgetLedger(
                    allocated_tokens=team_spec.budget_slice.allocated_tokens,
                    allocated_tool_calls=team_spec.budget_slice.allocated_tool_calls,
                    allocated_cost_paisa=team_spec.budget_slice.allocated_cost_paisa,
                    allocated_seconds=120.0,
                    max_recursion_depth=MAX_HIERARCHY_DEPTH,
                    current_depth=1,
                ),
                depth=1,
                ancestry=ancestry,
            )
            delegations.append(del_req)

            # Generate internal team nodes (depth = 1 or 2)
            team_nodes = self._generate_team_subgraph(
                task_id=task_id,
                team_run_id=team_run_id,
                team_spec=team_spec,
                goal=goal,
                ancestry=ancestry,
                prior_team_exit_nodes=prior_team_nodes,
                is_w1=is_w1,
                is_w2=is_w2,
                is_w3=is_w3,
                is_w4=is_w4,
                is_w5=is_w5,
                is_w6=is_w6,
            )
            all_nodes.extend(team_nodes)
            prior_team_nodes = [team_nodes[-1].node_id] if team_nodes else []

        # Validate planned graph
        valid, err = self.validate_hierarchical_graph(all_nodes, delegations)
        if not valid:
            raise DAGCycleError(f"Hierarchical graph validation failed: {err}")

        return delegations, all_nodes

    def _generate_team_subgraph(
        self,
        task_id: str,
        team_run_id: str,
        team_spec: Any,
        goal: str,
        ancestry: List[str],
        prior_team_exit_nodes: List[str],
        is_w1: bool,
        is_w2: bool,
        is_w3: bool,
        is_w4: bool,
        is_w5: bool,
        is_w6: bool,
    ) -> List[TaskNode]:
        """Generate bounded DAG nodes for a specific team run."""
        nodes: List[TaskNode] = []
        team_id = team_spec.team_id
        team_type = team_spec.team_type

        if team_type == TeamType.RESEARCH:
            # 1. Lead planning
            lead_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=lead_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Research Team: Scope & Source Investigation",
                    specialist_role=AgentRole.RESEARCHER,
                    dependencies=list(prior_team_exit_nodes),
                    allowed_tools=["crag_search", "fetch_url_content", "extract_citations"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"query": goal, "team_run_id": team_run_id},
                    expected_postcondition="Grounded research evidence and verified sources extracted",
                    depth=1,
                    ancestry=ancestry + [lead_id],
                )
            )

            # 2. Localization / Curator
            loc_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=loc_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Research Team: Nepali Bilingual Adaptation & Fact Verification",
                    specialist_role=AgentRole.LOCALIZATION_SPECIALIST,
                    dependencies=[lead_id],
                    allowed_tools=["translate_text", "validate_devanagari_encoding", "cultural_glossary_lookup"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={"source_node": lead_id, "goal": goal},
                    expected_postcondition="Devanagari verified and cultural accuracy asserted",
                    depth=2,
                    ancestry=ancestry + [loc_id],
                )
            )

        elif team_type == TeamType.ENGINEERING:
            # 1. Lead Developer implementation
            eng_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=eng_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Engineering Team: Workspace Implementation & Code Delivery",
                    specialist_role=AgentRole.ENGINEER,
                    dependencies=list(prior_team_exit_nodes),
                    allowed_tools=["sandbox_write", "sandbox_read", "sandbox_execute", "git_commit_scoped"],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    input_data={
                        "instruction": goal,
                        "team_run_id": team_run_id,
                        "path": "workspace/bilingual_app.html",
                        "content": "<!DOCTYPE html><html><body><h1>नमस्ते / Welcome to HINAA</h1></body></html>",
                        "mock_exit_code": 1 if is_w3 else 0,  # Intentional bug in W3
                    },
                    expected_postcondition="Code implementation written and tested in scoped sandbox",
                    depth=1,
                    ancestry=ancestry + [eng_id],
                )
            )

            # 2. Independent QA Node
            qa_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=qa_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Engineering Team: Independent QA Verification & Exit Code Check",
                    specialist_role=AgentRole.QA,
                    dependencies=[eng_id],
                    allowed_tools=["run_test_suite", "verify_file_hash", "check_exit_code"],
                    permission_tier=PermissionTier.TIER_A_READ_ONLY,
                    input_data={
                        "target_node": eng_id,
                        "mock_exit_code": 1 if is_w3 else 0,  # QA strictly fails on W3
                    },
                    expected_postcondition="Test suite passed with exit_code 0 and verified artifact checksums",
                    depth=2,
                    ancestry=ancestry + [qa_id],
                )
            )

            # 3. Browser verification if W1
            if is_w1:
                browser_id = f"node-{uuid.uuid4().hex[:8]}"
                nodes.append(
                    TaskNode(
                        node_id=browser_id,
                        task_id=task_id,
                        team_id=team_id,
                        team_type=team_type,
                        title="Engineering Team: Browser Rendering & Accessibility Audit",
                        specialist_role=AgentRole.BROWSER_OPERATOR,
                        dependencies=[qa_id],
                        allowed_tools=["browser_navigate", "inspect_accessibility_tree", "verify_page_content"],
                        permission_tier=PermissionTier.TIER_A_READ_ONLY,
                        input_data={"target_url": "http://localhost:3000"},
                        expected_postcondition="DOM elements and bilingual text rendered without clipping",
                        depth=2,
                        ancestry=ancestry + [browser_id],
                    )
                )

        elif team_type == TeamType.OPERATIONS:
            # Operations / Commerce node
            ops_id = f"node-{uuid.uuid4().hex[:8]}"
            tier = PermissionTier.TIER_C_EXPLICIT_APPROVAL if is_w5 else PermissionTier.TIER_B_SCOPED_DEV
            nodes.append(
                TaskNode(
                    node_id=ops_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Operations Team: Commerce Transaction & Policy Governance",
                    specialist_role=AgentRole.PLANNER,
                    dependencies=list(prior_team_exit_nodes),
                    allowed_tools=["simulate_nepali_payment", "verify_paisa_amount"],
                    permission_tier=tier,
                    input_data={
                        "amount_npr": 250,
                        "amount_paisa": 25000,
                        "gateway": "eSewa",
                        "sandbox_only": True,
                    },
                    expected_postcondition="Signed approval verified and simulated transaction logged",
                    depth=1,
                    ancestry=ancestry + [ops_id],
                )
            )

        elif team_type == TeamType.CREATIVE:
            # Creative Operator
            creative_id = f"node-{uuid.uuid4().hex[:8]}"
            nodes.append(
                TaskNode(
                    node_id=creative_id,
                    task_id=task_id,
                    team_id=team_id,
                    team_type=team_type,
                    title="Creative Team: Media Generation & Pipeline Export",
                    specialist_role=AgentRole.CREATIVE_OPERATOR,
                    dependencies=list(prior_team_exit_nodes),
                    allowed_tools=["generate_video_prompt", "export_timeline_video"],
                    permission_tier=PermissionTier.TIER_B_SCOPED_DEV,
                    input_data={
                        "request_type": "text-to-video" if is_w6 else "timeline-export",
                        "prompt": goal,
                    },
                    expected_postcondition="Media generated or honest technical limitation declared",
                    depth=1,
                    ancestry=ancestry + [creative_id],
                )
            )

        return nodes

    def replan_subgraph(
        self,
        task: TaskSpec,
        failed_node: TaskNode,
        remediation_role: AgentRole,
        instruction: str,
    ) -> TaskNode:
        """
        Safely insert remediation node without introducing DAG cycles or widening permissions.
        """
        remed_id = f"remed-{uuid.uuid4().hex[:8]}"
        grant = self.registry.get_capability_grant(remediation_role)
        allowed_tools = grant.allowed_tools[:2] if grant else ["synthesize_response"]

        remed_node = TaskNode(
            node_id=remed_id,
            task_id=task.task_id,
            team_id=failed_node.team_id,
            team_type=failed_node.team_type,
            title=f"Remediation: Fix failure in {failed_node.title}",
            specialist_role=remediation_role,
            dependencies=[failed_node.node_id],
            allowed_tools=allowed_tools,
            permission_tier=failed_node.permission_tier,
            input_data={"instruction": instruction, "original_error": failed_node.error},
            expected_postcondition="Defect corrected and state verified",
            depth=min(MAX_HIERARCHY_DEPTH, failed_node.depth + 1),
            ancestry=failed_node.ancestry + [remed_id],
        )

        task.nodes.append(remed_node)
        valid, err = self.validate_hierarchical_graph(task.nodes)
        if not valid:
            task.nodes.pop()
            raise DAGCycleError(f"Cannot replan: DAG validation failed: {err}")

        return remed_node
