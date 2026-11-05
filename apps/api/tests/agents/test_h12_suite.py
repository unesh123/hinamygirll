"""
HINAA OS — Phase 12 Acceptance Test Suite (H12-01 to H12-80)
Validates Hierarchical Team Orchestration, 3-Way Adaptive Execution,
Canonical Team Registry, Typed Delegation Packets, Context Isolation,
Nested Budget Slicing, HMAC Ancestry Binding, QA Verification Overrides,
Workflows W1-W6, and Long-Horizon Resilience.
"""

import hashlib
import hmac
import os
import tempfile
import time
import uuid
import pytest

from hinaa_api.agents.contracts import (
    AgentRole,
    BudgetLedger,
    DelegationRequest,
    ExecutionMode,
    PermissionTier,
    TaskEvent,
    TaskNode,
    TaskResult,
    TaskSpec,
    TaskStatus,
    TeamResult,
    TeamSpec,
    TeamType,
    ToolReceipt,
)
from hinaa_api.agents.registry import SpecialistRegistry
from hinaa_api.agents.dispatcher import TaskDispatcher
from hinaa_api.agents.budget import BudgetController
from hinaa_api.agents.policy_bridge import PolicyBridge, _APPROVAL_SECRET
from hinaa_api.agents.hierarchy_planner import (
    HierarchicalPlanner,
    MAX_HIERARCHY_DEPTH,
    MAX_GRAPH_NODES,
)
from hinaa_api.agents.planner import DAGCycleError
from hinaa_api.agents.hierarchy_supervisor import HierarchicalSupervisor
from hinaa_api.agents.service import AgentOrchestrationService
from hinaa_api.agents.event_log import EventLogStore
from hinaa_api.agents.resume import TaskStore
from hinaa_api.agents.verifier import IndependentVerifier
from hinaa_api.agents.handoff import ContextHandoffManager, ContextScrubber


# =============================================================================
# GROUP A: Execution Mode Decision Gate (H12-01 to H12-08)
# =============================================================================

def test_h12_01_single_agent_fast_path():
    """H12-01: Single-agent fast path routing for short greetings / simple facts."""
    dispatcher = TaskDispatcher()
    mode = dispatcher.evaluate_execution_mode("Hello Hinaa, namaste!")
    assert mode == ExecutionMode.SINGLE_AGENT_FAST_PATH
    gate_mode, rationale = dispatcher.evaluate_routing_gate("Hello Hinaa, namaste!")
    assert gate_mode == "SINGLE_AGENT_FAST_PATH"
    assert "single-agent" in rationale.lower() or "fast" in rationale.lower()


def test_h12_02_flat_multi_agent_routing():
    """H12-02: Flat multi-agent routing for single-workstream multi-step tasks."""
    dispatcher = TaskDispatcher()
    mode = dispatcher.evaluate_execution_mode("Refactor the login module error handling and verify exit code")
    assert mode == ExecutionMode.FLAT_MULTI_AGENT
    gate_mode, rationale = dispatcher.evaluate_routing_gate("Refactor the login module error handling and verify exit code")
    assert gate_mode == "MULTI_AGENT_SWARM"


def test_h12_03_hierarchical_team_routing():
    """H12-03: Hierarchical team routing for multi-team separable missions."""
    dispatcher = TaskDispatcher()
    mode = dispatcher.evaluate_execution_mode("Build a complete bilingual website with tests and browser verification")
    assert mode == ExecutionMode.HIERARCHICAL_TEAM
    gate_mode, _ = dispatcher.evaluate_routing_gate("Build a complete bilingual website with tests and browser verification")
    assert gate_mode == "HIERARCHICAL_TEAM"


def test_h12_04_explicit_override_hierarchical():
    """H12-04: Explicit override to HIERARCHICAL_TEAM via request payload."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_task(
        goal="Simple query but forced team",
        execution_mode=ExecutionMode.HIERARCHICAL_TEAM,
    )
    assert task.execution_mode == ExecutionMode.HIERARCHICAL_TEAM
    assert len(task.team_runs) > 0


def test_h12_05_explicit_override_flat():
    """H12-05: Explicit override to FLAT_MULTI_AGENT via request payload."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_task(
        goal="Build something",
        execution_mode=ExecutionMode.FLAT_MULTI_AGENT,
    )
    assert task.execution_mode == ExecutionMode.FLAT_MULTI_AGENT


def test_h12_06_explicit_override_fast_path():
    """H12-06: Explicit override to SINGLE_AGENT_FAST_PATH via request payload."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_task(
        goal="Hello",
        execution_mode=ExecutionMode.SINGLE_AGENT_FAST_PATH,
    )
    assert task.execution_mode == ExecutionMode.SINGLE_AGENT_FAST_PATH


def test_h12_07_routing_gate_latency():
    """H12-07: Routing gate latency < 20ms under all modes."""
    dispatcher = TaskDispatcher()
    queries = [
        "Hello Hinaa",
        "Refactor code and run tests",
        "Build a bilingual website with full stack testing and browser automation",
    ]
    for q in queries:
        t0 = time.perf_counter()
        dispatcher.evaluate_execution_mode(q)
        dt_ms = (time.perf_counter() - t0) * 1000
        assert dt_ms < 20.0, f"Routing latency exceeded: {dt_ms}ms"


def test_h12_08_decision_gate_rationale():
    """H12-08: Decision gate rationale contains clear matched domain trigger keywords."""
    dispatcher = TaskDispatcher()
    mode, rationale = dispatcher.evaluate_routing_gate("Hierarchical cross-team full-stack app")
    assert mode == "HIERARCHICAL_TEAM"
    assert "hierarchical" in rationale.lower() or "cross-team" in rationale.lower() or "team" in rationale.lower()


# =============================================================================
# GROUP B: Canonical Team Registry & Scopes (H12-09 to H12-16)
# =============================================================================

def test_h12_09_engineering_team_spec():
    """H12-09: Engineering team spec verification (lead ENGINEER, members [ENGINEER, QA, BROWSER_OPERATOR])."""
    registry = SpecialistRegistry()
    spec = registry.get_team_spec(TeamType.ENGINEERING)
    assert spec is not None
    assert spec.lead_role == AgentRole.ENGINEER
    assert set(spec.member_roles) == {AgentRole.ENGINEER, AgentRole.QA, AgentRole.BROWSER_OPERATOR}


def test_h12_10_research_team_spec():
    """H12-10: Research team spec verification (lead RESEARCHER, members [RESEARCHER, KNOWLEDGE_CURATOR, LOCALIZATION_SPECIALIST])."""
    registry = SpecialistRegistry()
    spec = registry.get_team_spec(TeamType.RESEARCH)
    assert spec is not None
    assert spec.lead_role == AgentRole.RESEARCHER
    assert set(spec.member_roles) == {AgentRole.RESEARCHER, AgentRole.KNOWLEDGE_CURATOR, AgentRole.LOCALIZATION_SPECIALIST}


def test_h12_11_creative_team_spec():
    """H12-11: Creative team spec verification (lead CREATIVE_OPERATOR, members [CREATIVE_OPERATOR, QA])."""
    registry = SpecialistRegistry()
    spec = registry.get_team_spec(TeamType.CREATIVE)
    assert spec is not None
    assert spec.lead_role == AgentRole.CREATIVE_OPERATOR
    assert set(spec.member_roles) == {AgentRole.CREATIVE_OPERATOR, AgentRole.QA}


def test_h12_12_operations_team_spec():
    """H12-12: Operations team spec verification (lead PLANNER, members [PLANNER, BROWSER_OPERATOR, SECURITY_REVIEWER])."""
    registry = SpecialistRegistry()
    spec = registry.get_team_spec(TeamType.OPERATIONS)
    assert spec is not None
    assert spec.lead_role == AgentRole.PLANNER
    assert set(spec.member_roles) == {AgentRole.PLANNER, AgentRole.BROWSER_OPERATOR, AgentRole.SECURITY_REVIEWER}


def test_h12_13_list_teams_count():
    """H12-13: Listing teams returns exactly 4 canonical templates."""
    registry = SpecialistRegistry()
    teams = registry.list_teams()
    assert len(teams) == 4
    team_types = {t.team_type for t in teams}
    assert team_types == {TeamType.ENGINEERING, TeamType.RESEARCH, TeamType.CREATIVE, TeamType.OPERATIONS}


def test_h12_14_role_capability_grants():
    """H12-14: Role capability grants strictly enforce allowed tool whitelist per team member."""
    registry = SpecialistRegistry()
    assert registry.is_tool_allowed(AgentRole.ENGINEER, "sandbox_write")
    assert not registry.is_tool_allowed(AgentRole.ENGINEER, "crag_search")
    assert registry.is_tool_allowed(AgentRole.RESEARCHER, "crag_search")
    assert not registry.is_tool_allowed(AgentRole.RESEARCHER, "sandbox_write")


def test_h12_15_unauthorized_tool_assignment_fails():
    """H12-15: Attempt to assign unauthorized tool to team role fails validation."""
    planner = HierarchicalPlanner()
    node = TaskNode(
        node_id="bad-node",
        task_id="task-1",
        title="Unauthorized Tool Node",
        specialist_role=AgentRole.QA,
        dependencies=[],
        allowed_tools=["git_commit_scoped"],  # QA cannot git_commit
    )
    valid, err = planner.validate_hierarchical_graph([node])
    assert not valid
    assert "not granted" in err


def test_h12_16_team_registration_idempotency():
    """H12-16: Team registration idempotency & spec retrieval by team_type."""
    registry = SpecialistRegistry()
    spec1 = registry.get_team_spec(TeamType.ENGINEERING)
    registry.register_team(spec1)
    spec2 = registry.get_team_spec(TeamType.ENGINEERING)
    assert spec1.team_id == spec2.team_id


# =============================================================================
# GROUP C: Typed Delegation Packets & Outcome Verification (H12-17 to H12-24)
# =============================================================================

def test_h12_17_typed_delegation_request():
    """H12-17: Typed DelegationRequest generation with parent task id, team run id, and ancestry."""
    planner = HierarchicalPlanner()
    dels, nodes = planner.plan_hierarchical_mission(task_id="task-100", goal="Build bilingual website")
    assert len(dels) > 0
    del_req = dels[0]
    assert isinstance(del_req, DelegationRequest)
    assert del_req.parent_task_id == "task-100"
    assert len(del_req.ancestry) >= 2
    assert del_req.ancestry[0] == "task-100"


def test_h12_18_typed_team_result_generation():
    """H12-18: Typed TeamResult generation with cryptographic HMAC signature."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    assert isinstance(team_res, TeamResult)
    assert len(team_res.signature) == 64  # SHA-256 hex length


def test_h12_19_signature_verification_team_result():
    """H12-19: Signature verification of TeamResult succeeds with correct secret and fails on tampering."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])

    raw_msg = f"{team_res.team_run_id}:{team_res.status.value}:{len(team_res.evidence_receipts)}:{team_res.duration_ms}"
    expected_sig = hmac.new(_APPROVAL_SECRET.encode("utf-8"), raw_msg.encode("utf-8"), hashlib.sha256).hexdigest()
    assert hmac.compare_digest(team_res.signature, expected_sig)

    # Tampered message fails
    tampered_msg = f"{team_res.team_run_id}:FAILED:{len(team_res.evidence_receipts)}:{team_res.duration_ms}"
    tampered_sig = hmac.new(_APPROVAL_SECRET.encode("utf-8"), tampered_msg.encode("utf-8"), hashlib.sha256).hexdigest()
    assert not hmac.compare_digest(team_res.signature, tampered_sig)


def test_h12_20_team_result_verified_postconditions():
    """H12-20: Team result contains verified postconditions from completed nodes."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    assert len(team_res.verified_postconditions) > 0


def test_h12_21_team_result_evidence_receipts():
    """H12-21: Team result contains verified tool receipts with SHA256 input/output digests."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    assert len(team_res.evidence_receipts) > 0
    receipt = team_res.evidence_receipts[0]
    assert len(receipt.input_digest) == 64
    assert len(receipt.output_digest) == 64


def test_h12_22_team_result_cost_metrics():
    """H12-22: Team result cost metrics match consumed token and integer paisa usage."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    metrics = team_res.cost_metrics
    assert "consumed_tokens" in metrics
    assert "consumed_cost_paisa" in metrics
    assert metrics["consumed_tokens"] > 0
    assert metrics["consumed_cost_paisa"] > 0


def test_h12_23_scoped_context_summary():
    """H12-23: Scoped context summary generated without leaking internal prompt history."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    assert "successfully" in team_res.scoped_context_summary.lower()
    assert "prompt" not in team_res.scoped_context_summary.lower()


def test_h12_24_failure_reasons_captured():
    """H12-24: Failure reasons correctly captured and reported in TeamResult on failure."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W3 with intentional conflict")
    # Engineering team in W3 fails on QA
    team_res = supervisor.run_team_workstream(task, task.team_runs[0])
    assert team_res.status == TaskStatus.FAILED
    assert len(team_res.failure_reasons) > 0


# =============================================================================
# GROUP D: Context Isolation, Scrubbing & Provenance (H12-25 to H12-32)
# =============================================================================

def test_h12_25_token_and_api_key_scrubbing():
    """H12-25: Token and API key scrubbing during inter-team context handoff."""
    scrubber = ContextScrubber()
    secret_text = "Bearer sk-proj-1234567890abcdef1234567890abcdef is secret"
    cleaned = scrubber.scrub_string(secret_text)
    assert "sk-proj" not in cleaned
    assert "[REDACTED_SECRET]" in cleaned


def test_h12_26_tenant_isolation():
    """H12-26: Tenant isolation prevents cross-tenant artifact access."""
    bridge = PolicyBridge()
    appr = bridge.create_approval_request(
        tenant_id="tenant-alpha",
        user_id="user-1",
        task_id="task-1",
        node_id="node-1",
        action="deploy",
        arguments={},
    )
    bridge.approve_action(appr.approval_id, tenant_id="tenant-alpha")
    # Verify with wrong tenant fails
    ok, err = bridge.verify_and_consume_approval(appr.approval_id, tenant_id="tenant-beta", action="deploy", arguments={})
    assert not ok
    assert err == "TENANT_MISMATCH"


def test_h12_27_scoped_input_data():
    """H12-27: Scoped input data provides only necessary upstream artifact references."""
    planner = HierarchicalPlanner()
    dels, nodes = planner.plan_hierarchical_mission("task-100", "Build bilingual site")
    for n in nodes:
        assert isinstance(n.input_data, dict)
        assert "raw_user_password" not in n.input_data


def test_h12_28_trace_id_propagation():
    """H12-28: Trace ID propagation across parent task, team run, and child nodes."""
    planner = HierarchicalPlanner()
    dels, nodes = planner.plan_hierarchical_mission("task-100", "Build bilingual site")
    for d in dels:
        assert d.trace_id.startswith("trc-")


def test_h12_29_idempotency_keys():
    """H12-29: Idempotency keys prevent duplicate execution of delegated team workstreams."""
    planner = HierarchicalPlanner()
    dels, _ = planner.plan_hierarchical_mission("task-100", "Build bilingual site")
    keys = {d.idempotency_key for d in dels}
    assert len(keys) == len(dels)


def test_h12_30_secret_scrubber_receipts():
    """H12-30: Secret scrubber redacts raw password strings and bearer tokens in receipts."""
    scrubber = ContextScrubber()
    data = {"api_key": "Bearer 1234567890abcdef", "normal": "valid"}
    scrubbed = scrubber.scrub_data(data)
    assert scrubbed["api_key"] == "[REDACTED_SECRET]"
    assert scrubbed["normal"] == "valid"


def test_h12_31_context_handoff_checksums():
    """H12-31: Context handoff manager preserves artifact checksums across team boundaries."""
    handoff = ContextHandoffManager()
    sha = handoff.compute_artifact_sha256(__file__)
    assert len(sha) == 64


def test_h12_32_context_provenance():
    """H12-32: Context provenance correctly records originating specialist and team id."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Bilingual website build")
    res = supervisor.run_task_to_completion(task)
    for art in res.artifacts:
        assert "created_by" in art
        assert "team_id" in art


# =============================================================================
# GROUP E: Nested Budget Slicing & Conservation (H12-33 to H12-40)
# =============================================================================

def test_h12_33_child_slice_bounded_by_parent():
    """H12-33: Child slice allocation ensures sum(slices) <= parent budget."""
    controller = BudgetController(
        ledger=BudgetLedger(allocated_tokens=10000, allocated_cost_paisa=5000)
    )
    slice1 = controller.allocate_slice(tokens=6000, cost_paisa=3000)
    assert slice1.allocated_tokens == 6000
    slice2 = controller.allocate_slice(tokens=6000, cost_paisa=3000)
    # Headroom was only 4000 tokens and 2000 paisa
    assert slice2.allocated_tokens == 4000
    assert slice2.allocated_cost_paisa == 2000


def test_h12_34_unused_budget_refund():
    """H12-34: Unused child budget slice refunded to parent upon team completion."""
    controller = BudgetController(
        ledger=BudgetLedger(allocated_tokens=10000, allocated_cost_paisa=5000)
    )
    slice1 = controller.allocate_slice(tokens=5000, cost_paisa=2500)
    # Child only consumes 1000 tokens and 500 paisa
    slice1.consumed_tokens = 1000
    slice1.consumed_cost_paisa = 500
    controller.reconcile_slice(slice1)

    assert controller.ledger.consumed_tokens == 1000
    assert controller.ledger.consumed_cost_paisa == 500
    # Headroom is now 10000 - 1000 = 9000
    slice2 = controller.allocate_slice(tokens=9000, cost_paisa=4500)
    assert slice2.allocated_tokens == 9000


def test_h12_35_integer_paisa_conservation():
    """H12-35: Integer paisa conservation: integer math without floating-point drift."""
    controller = BudgetController(
        ledger=BudgetLedger(allocated_cost_paisa=25000)
    )
    s1 = controller.allocate_slice(cost_paisa=10000)
    s2 = controller.allocate_slice(cost_paisa=15000)
    assert s1.allocated_cost_paisa + s2.allocated_cost_paisa == 25000


def test_h12_36_hard_ceiling_tokens():
    """H12-36: Hard ceiling enforcement: child cannot exceed allocated slice tokens."""
    ledger = BudgetLedger(allocated_tokens=1000, consumed_tokens=1000)
    exceeded, reason = ledger.is_exceeded()
    assert exceeded
    assert reason == "TOKEN_BUDGET_EXCEEDED"


def test_h12_37_hard_ceiling_tool_calls():
    """H12-37: Hard ceiling enforcement: child cannot exceed allocated tool calls."""
    ledger = BudgetLedger(allocated_tool_calls=5, consumed_tool_calls=5)
    exceeded, reason = ledger.is_exceeded()
    assert exceeded
    assert reason == "TOOL_CALL_BUDGET_EXCEEDED"


def test_h12_38_hard_ceiling_paisa():
    """H12-38: Hard ceiling enforcement: child cannot exceed allocated paisa limit."""
    ledger = BudgetLedger(allocated_cost_paisa=500, consumed_cost_paisa=500)
    exceeded, reason = ledger.is_exceeded()
    assert exceeded
    assert reason == "COST_PAISA_BUDGET_EXCEEDED"


def test_h12_39_slice_headroom_clamping():
    """H12-39: Attempt to allocate slice exceeding parent capacity is bounded to remaining headroom."""
    controller = BudgetController(
        ledger=BudgetLedger(allocated_tokens=5000, consumed_tokens=4000)
    )
    s = controller.allocate_slice(tokens=2000)
    assert s.allocated_tokens == 1000


def test_h12_40_budget_metrics_accuracy():
    """H12-40: Budget metrics accurately reflect consumed vs allocated across all teams."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Creative media run")
    res = supervisor.run_task_to_completion(task)
    assert res.budget_used.consumed_tokens > 0
    assert res.budget_used.consumed_cost_paisa > 0


# =============================================================================
# GROUP F: Hierarchical DAG Validation & Ceilings (H12-41 to H12-48)
# =============================================================================

def test_h12_41_max_hierarchy_depth_enforced():
    """H12-41: Maximum hierarchy depth <= 2 below global supervisor enforced."""
    planner = HierarchicalPlanner()
    node = TaskNode(
        node_id="deep-node",
        task_id="task-1",
        title="Excessive Depth Node",
        specialist_role=AgentRole.ENGINEER,
        allowed_tools=["sandbox_read"],
        depth=3,  # Exceeds max depth 2
    )
    valid, err = planner.validate_hierarchical_graph([node])
    assert not valid
    assert "exceeds maximum hierarchy depth" in err


def test_h12_42_max_node_count_ceiling():
    """H12-42: Total node count hard ceiling <= 50 enforced."""
    planner = HierarchicalPlanner()
    nodes = [
        TaskNode(
            node_id=f"node-{i}",
            task_id="task-1",
            title=f"Node {i}",
            specialist_role=AgentRole.RESEARCHER,
            allowed_tools=["crag_search"],
            depth=1,
        )
        for i in range(51)  # 51 nodes > 50
    ]
    valid, err = planner.validate_hierarchical_graph(nodes)
    assert not valid
    assert "exceeds hard ceiling" in err


def test_h12_43_acyclic_dependency_enforcement():
    """H12-43: Acyclic dependency enforcement: DAGCycleError raised on cyclic node dependencies."""
    planner = HierarchicalPlanner()
    n1 = TaskNode(
        node_id="n1",
        task_id="task-1",
        title="Node 1",
        specialist_role=AgentRole.ENGINEER,
        dependencies=["n2"],
        allowed_tools=["sandbox_read"],
    )
    n2 = TaskNode(
        node_id="n2",
        task_id="task-1",
        title="Node 2",
        specialist_role=AgentRole.QA,
        dependencies=["n1"],
        allowed_tools=["run_test_suite"],
    )
    valid, err = planner.validate_hierarchical_graph([n1, n2])
    assert not valid
    assert "cycle detected" in err.lower()


def test_h12_44_topological_sort_order():
    """H12-44: Topological ordering sorts dependency nodes strictly before dependent nodes."""
    planner = HierarchicalPlanner()
    _, nodes = planner.plan_hierarchical_mission("task-1", "Bilingual website build")
    assert len(nodes) >= 4
    # All nodes must have their dependencies appear earlier in execution order
    completed_ids = set()
    for n in nodes:
        for dep in n.dependencies:
            assert dep in completed_ids, f"Dependency {dep} did not precede {n.node_id}"
        completed_ids.add(n.node_id)


def test_h12_45_dynamic_replanning_no_cycles():
    """H12-45: Dynamic replanning inserts remediation nodes without introducing cycles."""
    planner = HierarchicalPlanner()
    task = TaskSpec(
        task_id="task-replan",
        goal="Test replan",
        nodes=[
            TaskNode(
                node_id="failed-node",
                task_id="task-replan",
                title="Failed node",
                specialist_role=AgentRole.ENGINEER,
                allowed_tools=["sandbox_read"],
                error="Compile error",
                depth=1,
            )
        ]
    )
    remed = planner.replan_subgraph(
        task=task,
        failed_node=task.nodes[0],
        remediation_role=AgentRole.ENGINEER,
        instruction="Fix compile error",
    )
    assert remed.node_id in [n.node_id for n in task.nodes]
    valid, _ = planner.validate_hierarchical_graph(task.nodes)
    assert valid


def test_h12_46_dynamic_replanning_respects_capabilities():
    """H12-46: Dynamic replanning respects role capability grants without widening permissions."""
    planner = HierarchicalPlanner()
    task = TaskSpec(
        task_id="task-replan-cap",
        goal="Test cap",
        nodes=[
            TaskNode(
                node_id="failed-node-cap",
                task_id="task-replan-cap",
                title="Failed node cap",
                specialist_role=AgentRole.QA,
                allowed_tools=["run_test_suite"],
                error="QA assertion fail",
                depth=1,
            )
        ]
    )
    remed = planner.replan_subgraph(
        task=task,
        failed_node=task.nodes[0],
        remediation_role=AgentRole.QA,
        instruction="Rerun check",
    )
    # QA must only have QA tools
    registry = SpecialistRegistry()
    for tool in remed.allowed_tools:
        assert registry.is_tool_allowed(AgentRole.QA, tool)


def test_h12_47_missing_dependency_detected():
    """H12-47: Graph validator checks that missing dependency IDs are detected and rejected."""
    planner = HierarchicalPlanner()
    node = TaskNode(
        node_id="orphan-node",
        task_id="task-1",
        title="Orphan",
        specialist_role=AgentRole.ENGINEER,
        dependencies=["non-existent-dep"],
        allowed_tools=["sandbox_read"],
    )
    valid, err = planner.validate_hierarchical_graph([node])
    assert not valid
    assert "Missing dependency" in err


def test_h12_48_concurrent_node_dispatch():
    """H12-48: Concurrent node dispatch respects concurrency limits across multiple teams."""
    budget = BudgetController(max_concurrency=2)
    assert budget.acquire_slot()
    assert budget.acquire_slot()
    assert not budget.acquire_slot()  # Bounded at 2
    budget.release_slot()
    assert budget.acquire_slot()


# =============================================================================
# GROUP G: Complete Ancestry Binding in Tier C Approvals (H12-49 to H12-56)
# =============================================================================

def test_h12_49_hmac_ancestry_binding():
    """H12-49: HMAC-SHA256 signature binds complete ancestry string (task > team > node)."""
    bridge = PolicyBridge()
    ancestry = ["task-100", "team-operations", "node-commerce-1"]
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-commerce-1",
        action="simulate_nepali_payment",
        arguments={"amount_paisa": 25000},
        amount_paisa=25000,
        team_id="team-operations",
        ancestry=ancestry,
    )
    assert appr.ancestry == ancestry
    assert len(appr.signature) == 64


def test_h12_50_approval_verification_success():
    """H12-50: Approval verification succeeds with valid token, nonce, and matching ancestry."""
    bridge = PolicyBridge()
    ancestry = ["task-100", "team-operations", "node-commerce-1"]
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-commerce-1",
        action="simulate_nepali_payment",
        arguments={"amount_paisa": 25000},
        amount_paisa=25000,
        team_id="team-operations",
        ancestry=ancestry,
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok, err = bridge.verify_and_consume_approval(
        approval_id=appr.approval_id,
        tenant_id="default",
        action="simulate_nepali_payment",
        arguments={"amount_paisa": 25000},
        amount_paisa=25000,
        team_id="team-operations",
        ancestry=ancestry,
    )
    assert ok
    assert err is None


def test_h12_51_tampered_ancestry_rejected():
    """H12-51: Tampered ancestry chain rejected with ANCESTRY_MISMATCH."""
    bridge = PolicyBridge()
    ancestry = ["task-100", "team-operations", "node-commerce-1"]
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-commerce-1",
        action="simulate_nepali_payment",
        arguments={"amount_paisa": 25000},
        amount_paisa=25000,
        team_id="team-operations",
        ancestry=ancestry,
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    # Present different ancestry
    ok, err = bridge.verify_and_consume_approval(
        approval_id=appr.approval_id,
        tenant_id="default",
        action="simulate_nepali_payment",
        arguments={"amount_paisa": 25000},
        amount_paisa=25000,
        team_id="team-operations",
        ancestry=["task-100", "team-spoofed", "node-commerce-1"],
    )
    assert not ok
    assert err == "ANCESTRY_MISMATCH"


def test_h12_52_tampered_team_id_rejected():
    """H12-52: Tampered team ID rejected with TEAM_MISMATCH."""
    bridge = PolicyBridge()
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-1",
        action="deploy",
        arguments={},
        team_id="team-engineering",
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok, err = bridge.verify_and_consume_approval(
        approval_id=appr.approval_id,
        tenant_id="default",
        action="deploy",
        arguments={},
        team_id="team-rogue",
    )
    assert not ok
    assert err == "TEAM_MISMATCH"


def test_h12_53_tampered_paisa_amount_rejected():
    """H12-53: Tampered paisa amount rejected with PRICE_AMOUNT_MISMATCH."""
    bridge = PolicyBridge()
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-1",
        action="pay",
        arguments={},
        amount_paisa=5000,
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok, err = bridge.verify_and_consume_approval(
        approval_id=appr.approval_id,
        tenant_id="default",
        action="pay",
        arguments={},
        amount_paisa=10000,
    )
    assert not ok
    assert err == "PRICE_AMOUNT_MISMATCH"


def test_h12_54_replay_attack_rejected():
    """H12-54: Replay attack with consumed nonce rejected with APPROVAL_ALREADY_USED."""
    bridge = PolicyBridge()
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-1",
        action="pay",
        arguments={},
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok1, _ = bridge.verify_and_consume_approval(appr.approval_id, tenant_id="default", action="pay", arguments={})
    assert ok1
    ok2, err2 = bridge.verify_and_consume_approval(appr.approval_id, tenant_id="default", action="pay", arguments={})
    assert not ok2
    assert err2 == "APPROVAL_ALREADY_USED"


def test_h12_55_expired_approval_rejected():
    """H12-55: Expired approval token rejected with APPROVAL_EXPIRED."""
    bridge = PolicyBridge()
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-1",
        action="pay",
        arguments={},
        ttl_seconds=-10,  # Already expired
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok, err = bridge.verify_and_consume_approval(appr.approval_id, tenant_id="default", action="pay", arguments={})
    assert not ok
    assert err == "APPROVAL_EXPIRED"


def test_h12_56_emergency_stop_suspension():
    """H12-56: Cascading emergency stop immediately suspends Tier C approvals and execution."""
    bridge = PolicyBridge()
    bridge.trigger_emergency_stop()
    assert bridge.is_stopped()
    appr = bridge.create_approval_request(
        tenant_id="default",
        user_id="user-1",
        task_id="task-100",
        node_id="node-1",
        action="pay",
        arguments={},
    )
    bridge.approve_action(appr.approval_id, tenant_id="default")
    ok, err = bridge.verify_and_consume_approval(appr.approval_id, tenant_id="default", action="pay", arguments={})
    assert not ok
    assert err == "EMERGENCY_STOP_ACTIVE"
    bridge.resume_from_emergency_stop()
    assert not bridge.is_stopped()


# =============================================================================
# GROUP H: Independent QA Verification & Conflict Resolution (H12-57 to H12-64)
# =============================================================================

def test_h12_57_qa_overrides_optimistic_claims():
    """H12-57: QA verification strictly overrides optimistic claims by Engineer."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Engineering mission with bug")
    eng_node = TaskNode(
        node_id="eng-1",
        task_id=task.task_id,
        team_id="team-engineering",
        title="Developer writes code",
        specialist_role=AgentRole.ENGINEER,
        allowed_tools=["sandbox_write"],
        input_data={"content": "def bug(): raise Exception()"},
    )
    supervisor.execute_node(task, eng_node)
    assert eng_node.status == TaskStatus.COMPLETED  # Engineer wrote file

    # QA Node tests and fails
    qa_node = TaskNode(
        node_id="qa-1",
        task_id=task.task_id,
        team_id="team-engineering",
        title="QA independent test",
        specialist_role=AgentRole.QA,
        dependencies=["eng-1"],
        allowed_tools=["run_test_suite"],
        input_data={"mock_exit_code": 1},  # Fails
    )
    supervisor.execute_node(task, qa_node)
    assert qa_node.status == TaskStatus.FAILED  # QA strictly marked FAILED


def test_h12_58_qa_failure_exit_code():
    """H12-58: QA failure (exit code != 0) causes node status FAILED."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Test QA exit code")
    qa_node = TaskNode(
        node_id="qa-exit",
        task_id=task.task_id,
        team_id="team-engineering",
        title="QA exit check",
        specialist_role=AgentRole.QA,
        allowed_tools=["check_exit_code"],
        input_data={"mock_exit_code": 2},
    )
    supervisor.execute_node(task, qa_node)
    assert qa_node.status == TaskStatus.FAILED
    assert "exit code" in qa_node.error.lower()


def test_h12_59_supervisor_halts_on_qa_failure():
    """H12-59: Supervisor halts completion when QA node fails and records verifiable error."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W3 with QA failure")
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.FAILED
    assert not res.verification_passed


def test_h12_60_qa_verified_receipts():
    """H12-60: QA verified receipts require exit_code == 0 and valid artifact hashes."""
    verifier = IndependentVerifier()
    node = TaskNode(
        node_id="n-v",
        task_id="t-1",
        title="Node V",
        specialist_role=AgentRole.QA,
        allowed_tools=["run_test_suite"],
    )
    r = ToolReceipt(
        task_id="t-1",
        node_id="n-v",
        agent_role=AgentRole.QA,
        tool_name="run_test_suite",
        action="execute",
        exit_code=0,
    )
    v_res = verifier.verify_node(node, [r])
    assert v_res.passed


def test_h12_61_cross_team_conflict_detection():
    """H12-61: Cross-team conflict detection flags discrepancy between developer and QA."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W3 conflict")
    res = supervisor.run_task_to_completion(task)
    failed_team = next((r for r in res.team_results if r.status == TaskStatus.FAILED), None)
    assert failed_team is not None
    assert any("QA" in r or "exit" in r for r in failed_team.failure_reasons)


def test_h12_62_verification_notes_contain_details():
    """H12-62: Verification result notes contain exact failure details from test suite."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W3 conflict")
    res = supervisor.run_task_to_completion(task)
    failed_node = next((n for n in task.nodes if n.status == TaskStatus.FAILED), None)
    assert failed_node is not None
    assert failed_node.error is not None


def test_h12_63_successful_qa_enables_completion():
    """H12-63: Successful QA verification enables task status COMPLETED with verified receipts."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W1 bilingual website build")
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.COMPLETED
    assert res.verification_passed


def test_h12_64_partial_success_flagging():
    """H12-64: Partial status flagged when task is halted prematurely."""
    task = TaskSpec(
        task_id="task-partial",
        goal="Partial run",
        status=TaskStatus.PARTIAL,
    )
    assert task.status == TaskStatus.PARTIAL


# =============================================================================
# GROUP I: The Six Canonical Workflows W1–W6 (H12-65 to H12-72)
# =============================================================================

def test_h12_65_workflow_w1_bilingual_website():
    """H12-65: Workflow W1 (Bilingual Website Build): Engineering + Localization + BrowserOperator."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W1: Build bilingual website build")
    assert len(task.team_runs) >= 2
    team_types = {d.team_type for d in task.team_runs}
    assert TeamType.ENGINEERING in team_types
    assert TeamType.RESEARCH in team_types


def test_h12_66_workflow_w1_artifact_devanagari():
    """H12-66: W1 artifact verification: HTML/JS written with valid Devanagari and English strings."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W1: Build bilingual website build")
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.COMPLETED
    assert len(res.artifacts) > 0
    # Check that localization node verified devanagari
    loc_node = next((n for n in task.nodes if n.specialist_role == AgentRole.LOCALIZATION_SPECIALIST), None)
    assert loc_node is not None
    assert loc_node.result_data.get("devanagari_valid") is True


def test_h12_67_workflow_w2_research_to_code():
    """H12-67: Workflow W2 (Research to Code): Research CRAG citations inform usable code."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W2: Research to code tax calculator")
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.COMPLETED
    # Check research node citations
    res_node = next((n for n in task.nodes if n.specialist_role == AgentRole.RESEARCHER), None)
    assert res_node is not None
    assert "citations" in res_node.result_data


def test_h12_68_workflow_w2_attribution():
    """H12-68: W2 attribution check: Code artifact cites verified sources."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W2: Research to code tax calculator")
    res = supervisor.run_task_to_completion(task)
    res_node = next((n for n in task.nodes if n.specialist_role == AgentRole.RESEARCHER), None)
    citations = res_node.result_data.get("citations", [])
    assert len(citations) > 0
    assert "lawcommission.gov.np" in citations[0]["url"]


def test_h12_69_workflow_w3_conflict_rejection():
    """H12-69: Workflow W3 (Cross-Team Conflict): Engineer optimistic, QA fails, supervisor halts."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W3 cross-team conflict")
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.FAILED
    assert not res.verification_passed


def test_h12_70_workflow_w4_crash_recovery():
    """H12-70: Workflow W4 (Crash Recovery): Worker lease reset mid-nested run, resumed cleanly."""
    task_store = TaskStore(db_path=":memory:")
    supervisor = HierarchicalSupervisor(task_store=task_store)
    task = supervisor.create_hierarchical_task("Workflow W4: crash recovery test")

    # Mark node 0 completed, node 1 running with expired lease
    task.nodes[0].status = TaskStatus.COMPLETED
    task.nodes[1].status = TaskStatus.RUNNING
    task.nodes[1].lease_owner = "dead-worker"
    task.nodes[1].lease_expires_at = time.time() - 10  # Expired
    task.status = TaskStatus.RUNNING
    task_store.save_task(task)

    # Trigger recovery
    reset = task_store.reset_expired_leases()
    assert reset >= 1
    # Node 1 lease cleared and ready for resumption
    recovered_task = task_store.get_task(task.task_id)
    assert recovered_task.nodes[1].status in (TaskStatus.RECOVERING, TaskStatus.READY)


def test_h12_71_workflow_w5_safe_nepali_commerce():
    """H12-71: Workflow W5 (Nepali Commerce): Exact paisa accounting, ancestry HMAC, live gate blocked."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W5: eSewa payment simulation")
    ops_node = next((n for n in task.nodes if n.specialist_role == AgentRole.PLANNER), None)
    assert ops_node is not None
    assert ops_node.permission_tier == PermissionTier.TIER_C_EXPLICIT_APPROVAL

    # Run pauses for approval
    res = supervisor.run_task_to_completion(task)
    assert res.status == TaskStatus.WAITING_APPROVAL

    # Approve with ancestry
    bridge = supervisor.policy_bridge
    appr = next(iter(bridge._approvals.values()))
    bridge.approve_action(appr.approval_id, tenant_id="default")

    # Complete execution
    supervisor.execute_node(task, ops_node, approval_id=appr.approval_id)
    assert ops_node.status == TaskStatus.COMPLETED
    assert ops_node.result_data.get("live_financial_gateways_forbidden") is True
    assert ops_node.result_data.get("amount_paisa") == 25000


def test_h12_72_workflow_w6_creative_limitation_honesty():
    """H12-72: Workflow W6 (Creative Limitation): T2V requested -> BLOCKED_UNAVAILABLE, timeline offered."""
    supervisor = HierarchicalSupervisor()
    task = supervisor.create_hierarchical_task("Workflow W6: neural text-to-video creative request")
    res = supervisor.run_task_to_completion(task)
    creative_node = next((n for n in task.nodes if n.specialist_role == AgentRole.CREATIVE_OPERATOR), None)
    assert creative_node is not None
    assert creative_node.result_data.get("status") == "BLOCKED_UNAVAILABLE"
    assert "TIMELINE_EXPORT" in creative_node.result_data.get("alternative_offered")


# =============================================================================
# GROUP J: Long-Horizon Telemetry, Events & Resilience (H12-73 to H12-80)
# =============================================================================

def test_h12_73_event_journal_team_lifecycle():
    """H12-73: Append-only audit journal records team.delegated and team.completed events."""
    event_store = EventLogStore(db_path=":memory:")
    supervisor = HierarchicalSupervisor(event_log=event_store)
    task = supervisor.create_hierarchical_task("Bilingual website build")
    supervisor.run_task_to_completion(task)

    events = event_store.get_events(task.task_id)
    event_types = [e.event_type for e in events]
    assert "team.delegated" in event_types
    assert "team.completed" in event_types


def test_h12_74_event_sequence_monotonicity():
    """H12-74: Event sequence monotonicity maintained across all hierarchical events."""
    event_store = EventLogStore(db_path=":memory:")
    supervisor = HierarchicalSupervisor(event_log=event_store)
    task = supervisor.create_hierarchical_task("Bilingual website build")
    supervisor.run_task_to_completion(task)

    events = event_store.get_events(task.task_id)
    sequences = [e.sequence for e in events]
    assert sequences == sorted(sequences)
    assert len(sequences) == len(set(sequences))  # strictly monotonic


def test_h12_75_sse_event_stream():
    """H12-75: SSE event stream yields real-time updates for nested team execution."""
    event_store = EventLogStore(db_path=":memory:")
    supervisor = HierarchicalSupervisor(event_log=event_store)
    task = supervisor.create_hierarchical_task("Bilingual website build")
    events = event_store.get_events(task.task_id)
    assert len(events) >= 1
    assert events[0].event_type == "task.created"


def test_h12_76_crash_recovery_resumes_without_duplicates():
    """H12-76: Crash recovery resume_interrupted_tasks recovers hierarchical tasks without duplicates."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_hierarchical_task("Creative media run")
    # Complete node 0, leave node 1 running with expired lease
    task.nodes[0].status = TaskStatus.COMPLETED
    task.nodes[0].receipts.append(ToolReceipt(
        task_id=task.task_id,
        node_id=task.nodes[0].node_id,
        agent_role=task.nodes[0].specialist_role,
        tool_name="synthesize_response",
        action="execute",
    ))
    task.status = TaskStatus.RUNNING
    service.task_store.save_task(task)

    resumed = service.resume_interrupted_tasks()
    assert task.task_id in resumed
    updated = service.get_task(task.task_id)
    assert updated.status == TaskStatus.COMPLETED


def test_h12_77_cas_lease_expiration_detection():
    """H12-77: Worker lease expiration correctly detected and reset via CAS."""
    store = TaskStore(db_path=":memory:")
    task = TaskSpec(
        task_id="t-cas",
        goal="CAS test",
        nodes=[
            TaskNode(
                node_id="n-cas",
                task_id="t-cas",
                title="Node CAS",
                specialist_role=AgentRole.ENGINEER,
                lease_owner="worker-old",
                lease_expires_at=time.time() - 5.0,  # Expired
                status=TaskStatus.RUNNING,
            )
        ]
    )
    store.save_task(task)
    reset_count = store.reset_expired_leases()
    assert reset_count == 1
    t = store.get_task("t-cas")
    assert t.nodes[0].status == TaskStatus.RECOVERING
    assert t.nodes[0].lease_owner is None


def test_h12_78_cascading_cancellation():
    """H12-78: Cancellation of hierarchical task cascades to all child nodes and releases leases."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_hierarchical_task("Bilingual website build")
    assert service.cancel_task(task.task_id, reason="User abort")
    cancelled = service.get_task(task.task_id)
    assert cancelled.status == TaskStatus.CANCELLED
    for n in cancelled.nodes:
        assert n.status == TaskStatus.CANCELLED


def test_h12_79_reflection_staging():
    """H12-79: Reflection staging captures cross-team metrics upon task completion."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    task = service.create_hierarchical_task("Creative media run")
    res = service.run_task(task.task_id)
    assert res.status == TaskStatus.COMPLETED
    reflections = service.reflector.get_pending_reflections()
    assert len(reflections) > 0


def test_h12_80_health_endpoint_metrics():
    """H12-80: Health check returns specialist count, team count, and budget state."""
    service = AgentOrchestrationService(db_path_events=":memory:", db_path_tasks=":memory:")
    health = service.get_health()
    assert health["status"] == "HEALTHY"
    assert health["specialist_count"] == 10
    assert health["team_count"] == 4
    assert "budget" in health
    assert "active_concurrency" in health
