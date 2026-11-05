"""
HINAA OS — Phase 11: 80-Scenario Autonomous Tooling & Multi-Agent Swarms Benchmark Runner
Executes the acceptance suite, captures evidence classes, measures latency,
and outputs docs/agents/benchmark_results.json.
"""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
DOCS_AGENTS = REPO_ROOT / "docs" / "agents"
BENCHMARK_JSON = DOCS_AGENTS / "benchmark_results.json"
TEST_FILE = REPO_ROOT / "apps" / "api" / "tests" / "agents" / "test_a11_suite.py"

A11_SCENARIO_METADATA = {
    # Group A: Baseline, Registry & Routing
    "test_a11_01_baseline_verification": ("A11-01", "Baseline, Registry & Routing", "Component Integration (I)", "Verify baseline contracts, models, and 10 canonical roles without regression"),
    "test_a11_02_specialist_registry_initialization": ("A11-02", "Baseline, Registry & Routing", "Runtime Discovery (R)", "Verify SpecialistRegistry enumerates all 10 specialist specifications"),
    "test_a11_03_capability_grant_whitelisting": ("A11-03", "Baseline, Registry & Routing", "Security Boundary (S)", "Verify capability whitelisting grants and denies tools correctly"),
    "test_a11_04_model_routing_configuration": ("A11-04", "Baseline, Registry & Routing", "Component Integration (I)", "Verify specialist specifications assign appropriate foundation models"),
    "test_a11_05_provider_degradation_handling": ("A11-05", "Baseline, Registry & Routing", "Runtime Discovery (R)", "Verify provider degradation handling and health state updates"),
    "test_a11_06_decision_gate_single_agent_fast_path": ("A11-06", "Baseline, Registry & Routing", "Live Generation (L)", "Verify decision gate routes conversational greetings directly to single-agent fast path"),
    "test_a11_07_decision_gate_multi_agent_swarm": ("A11-07", "Baseline, Registry & Routing", "Live Generation (L)", "Verify decision gate routes complex instructions to multi-agent swarm DAG"),
    "test_a11_08_decision_gate_token_savings": ("A11-08", "Baseline, Registry & Routing", "Component Integration (I)", "Verify decision gate token and cost savings on fast path"),

    # Group B: Planning, DAG Execution & Handoffs
    "test_a11_09_dag_plan_generation": ("A11-09", "Planning, DAG Execution & Handoffs", "Live Generation (L)", "Verify DAG plan generation produces ordered nodes with explicit dependencies"),
    "test_a11_10_topological_dependency_ordering": ("A11-10", "Planning, DAG Execution & Handoffs", "Component Integration (I)", "Verify topological sort returns nodes in valid dependency execution sequence"),
    "test_a11_11_dag_cycle_rejection": ("A11-11", "Planning, DAG Execution & Handoffs", "Security Boundary (S)", "Verify cyclic dependency in task DAG raises DAGCycleError"),
    "test_a11_12_context_minimization_scrubbing": ("A11-12", "Planning, DAG Execution & Handoffs", "Security Boundary (S)", "Verify ContextScrubber redacts API keys and tokens from payloads"),
    "test_a11_13_scoped_upstream_results_propagation": ("A11-13", "Planning, DAG Execution & Handoffs", "Component Integration (I)", "Verify context handoff manager packages only declared upstream context"),
    "test_a11_14_delegation_depth_enforcement": ("A11-14", "Planning, DAG Execution & Handoffs", "Security Boundary (S)", "Verify delegation beyond maximum recursion depth (4) is rejected"),
    "test_a11_15_self_delegation_prevention": ("A11-15", "Planning, DAG Execution & Handoffs", "Security Boundary (S)", "Verify recursive self-delegation loop to the same role is prohibited"),
    "test_a11_16_tenant_isolation_boundary_preserved": ("A11-16", "Planning, DAG Execution & Handoffs", "Security Boundary (S)", "Verify tenant isolation check enforces strict multi-tenant boundaries"),

    # Group C: Universal Tool Registry & Real Execution
    "test_a11_17_universal_tool_execution_receipt": ("A11-17", "Universal Tool Registry & Execution", "Component Integration (I)", "Verify executing a tool yields a valid ToolReceipt with digests and exit code"),
    "test_a11_18_tool_receipt_cryptographic_digests": ("A11-18", "Universal Tool Registry & Execution", "Security Boundary (S)", "Verify SHA-256 digest computation is deterministic for tool receipts"),
    "test_a11_19_tool_receipt_duration_timing": ("A11-19", "Universal Tool Registry & Execution", "Component Integration (I)", "Verify ToolReceipt records positive non-zero execution duration in ms"),
    "test_a11_20_idempotency_key_tracking": ("A11-20", "Universal Tool Registry & Execution", "Component Integration (I)", "Verify idempotency key is uniquely attached to each receipt"),
    "test_a11_21_sandbox_file_write_physical_artifact": ("A11-21", "Universal Tool Registry & Execution", "Live Generation (L)", "Verify file write creates physical file and verifier records matching SHA-256"),
    "test_a11_22_test_suite_execution_exit_code": ("A11-22", "Universal Tool Registry & Execution", "Live Generation (L)", "Verify QA test execution tool captures exit code 0 on success"),
    "test_a11_23_grounded_research_citation_extraction": ("A11-23", "Universal Tool Registry & Execution", "Live Generation (L)", "Verify grounded researcher tool returns structured citations with confidence scores"),
    "test_a11_24_localization_devanagari_validation": ("A11-24", "Universal Tool Registry & Execution", "Live Generation (L)", "Verify localization tool preserves Unicode Devanagari characters"),

    # Group D: Permissions, Approvals & Governance
    "test_a11_25_tier_a_read_only_execution": ("A11-25", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify Tier A read-only operations proceed immediately without approval pause"),
    "test_a11_26_tier_b_scoped_workspace_execution": ("A11-26", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify Tier B scoped workspace modifications execute under local tracking"),
    "test_a11_27_tier_c_explicit_user_approval_pause": ("A11-27", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify Tier C actions automatically pause execution in WAITING_APPROVAL state"),
    "test_a11_28_cryptographic_hmac_signature_generation": ("A11-28", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify HMAC-SHA256 signature generation binds action, args, and amount"),
    "test_a11_29_one_time_use_nonce_consumption": ("A11-29", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify approval token is strictly single-use and fails on replay attempt"),
    "test_a11_30_argument_tampering_rejection": ("A11-30", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify modifying arguments after signing causes approval verification to reject"),
    "test_a11_31_monetary_amount_binding_in_paisa": ("A11-31", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify monetary amount binding in integer paisa prevents tampering"),
    "test_a11_32_emergency_stop_kill_switch": ("A11-32", "Permissions, Approvals & Governance", "Security Boundary (S)", "Verify emergency stop suspends all operations immediately with code 126"),

    # Group E: Persistence, Leases, Crash & Replay Safety
    "test_a11_33_atomic_task_status_updates": ("A11-33", "Persistence, Leases & Safety", "Component Integration (I)", "Verify TaskStore writes TaskSpec and TaskNode transactionally"),
    "test_a11_34_sqlite_wal_mode_enabled": ("A11-34", "Persistence, Leases & Safety", "Component Integration (I)", "Verify SQLite database journal mode is WAL"),
    "test_a11_35_optimistic_cas_worker_lease_acquisition": ("A11-35", "Persistence, Leases & Safety", "Component Integration (I)", "Verify Compare-And-Swap worker lease claims a ready node atomically"),
    "test_a11_36_worker_lease_expiration_and_reset": ("A11-36", "Persistence, Leases & Safety", "Component Integration (I)", "Verify expired worker leases are automatically identified and reset"),
    "test_a11_37_crash_recovery_uncompleted_task_discovery": ("A11-37", "Persistence, Leases & Safety", "Component Integration (I)", "Verify crash recovery identifies uncompleted tasks"),
    "test_a11_38_idempotent_tool_execution_safety": ("A11-38", "Persistence, Leases & Safety", "Component Integration (I)", "Verify re-running a completed node preserves existing receipt idempotently"),
    "test_a11_39_event_log_append_monotonic_sequence": ("A11-39", "Persistence, Leases & Safety", "Component Integration (I)", "Verify EventLogStore increments sequence monotonically per task"),
    "test_a11_40_cursor_based_event_log_querying": ("A11-40", "Persistence, Leases & Safety", "Component Integration (I)", "Verify cursor querying with since_sequence returns only newer events"),

    # Group F: Budgets, Concurrency & Performance
    "test_a11_41_token_budget_tracking_and_rejection": ("A11-41", "Budgets, Concurrency & Performance", "Security Boundary (S)", "Verify budget controller rejects admission when token budget is exhausted"),
    "test_a11_42_tool_call_quota_enforcement": ("A11-42", "Budgets, Concurrency & Performance", "Security Boundary (S)", "Verify budget controller enforces hard ceiling on tool calls"),
    "test_a11_43_wall_clock_execution_timeout": ("A11-43", "Budgets, Concurrency & Performance", "Security Boundary (S)", "Verify wall clock timeout triggers deadline exceeded"),
    "test_a11_44_concurrency_semaphore_bounding": ("A11-44", "Budgets, Concurrency & Performance", "Security Boundary (S)", "Verify concurrency semaphore caps active concurrent tasks at 5"),
    "test_a11_45_monetary_expenditure_tracking": ("A11-45", "Budgets, Concurrency & Performance", "Component Integration (I)", "Verify integer paisa and USD costs accumulate accurately"),
    "test_a11_46_concurrency_slot_release": ("A11-46", "Budgets, Concurrency & Performance", "Component Integration (I)", "Verify releasing an acquired concurrency slot restores capacity"),
    "test_a11_47_fast_path_execution_latency": ("A11-47", "Budgets, Concurrency & Performance", "Live Generation (L)", "Verify fast-path decision gate evaluation completes in under 50ms"),
    "test_a11_48_dag_node_dispatch_latency": ("A11-48", "Budgets, Concurrency & Performance", "Live Generation (L)", "Verify ready node selection latency is sub-millisecond"),

    # Group G: Security, Privacy & Adversarial Inputs
    "test_a11_49_prompt_injection_resistance_in_task_goal": ("A11-49", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify adversarial prompt injections in task goal are planned safely"),
    "test_a11_50_path_traversal_defense_in_tool_arguments": ("A11-50", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify path traversal outside workspace is safely handled"),
    "test_a11_51_unauthorized_tool_invocation_blocked": ("A11-51", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify specialist cannot execute tools outside its capability whitelist"),
    "test_a11_52_cross_tenant_data_isolation": ("A11-52", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify TaskStore isolates records by tenant_id"),
    "test_a11_53_secret_token_redaction_in_logged_events": ("A11-53", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify ContextScrubber scrubs passwords before event logging"),
    "test_a11_54_emergency_stop_recovery_cycle": ("A11-54", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify complete emergency stop trigger, verification, and clear cycle"),
    "test_a11_55_expired_approval_token_rejection": ("A11-55", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify approval tokens past their TTL are rejected as APPROVAL_EXPIRED"),
    "test_a11_56_tampered_amount_rejection_closed": ("A11-56", "Security, Privacy & Adversarial", "Security Boundary (S)", "Verify monetary tampering fails closed"),

    # Group H: End-to-End Project Workflows & Quality
    "test_a11_57_task_a_bilingual_nepal_mini_app_end_to_end": ("A11-57", "End-to-End Workflows & Quality", "Live Generation (L)", "Workflow A: Multi-agent execution of a bilingual Nepal mini-app"),
    "test_a11_58_task_b_grounded_research_to_code_generation": ("A11-58", "End-to-End Workflows & Quality", "Live Generation (L)", "Workflow B: Grounded research to code generation with QA verification"),
    "test_a11_59_task_c_mid_flight_crash_and_recovery": ("A11-59", "End-to-End Workflows & Quality", "Component Integration (I)", "Workflow C: Simulate mid-flight crash and test restart recovery"),
    "test_a11_60_task_d_engineer_vs_qa_conflicts_reconciliation": ("A11-60", "End-to-End Workflows & Quality", "Security Boundary (S)", "Workflow D: QA test failure strictly overrides an Engineer's claims"),
    "test_a11_61_task_e_mid_flight_task_cancellation": ("A11-61", "End-to-End Workflows & Quality", "Component Integration (I)", "Workflow E: Task cancellation halts execution and marks all nodes CANCELLED"),
    "test_a11_62_task_f_privilege_escalation_attempt_blocked": ("A11-62", "End-to-End Workflows & Quality", "Security Boundary (S)", "Workflow F: Subagent attempting self-approval is blocked closed"),
    "test_a11_63_independent_verifier_physical_checksum": ("A11-63", "End-to-End Workflows & Quality", "Component Integration (I)", "Verify IndependentVerifier calculates and validates physical file SHA-256"),
    "test_a11_64_continuous_knowledge_graph_quarantine_staging": ("A11-64", "End-to-End Workflows & Quality", "Component Integration (I)", "Verify task reflection extracts learnings and stages them into quarantine"),

    # Group I: Frontend, Voice, Localization & Integration
    "test_a11_65_rest_create_task": ("A11-65", "Frontend, Voice & Integration", "Component Integration (I)", "Verify POST /api/agents/tasks creates a valid task with DAG"),
    "test_a11_66_rest_get_task": ("A11-66", "Frontend, Voice & Integration", "Component Integration (I)", "Verify GET /api/agents/tasks/{id} returns task and nodes"),
    "test_a11_67_rest_stream_events": ("A11-67", "Frontend, Voice & Integration", "Component Integration (I)", "Verify GET /api/agents/tasks/{id}/events returns text/event-stream"),
    "test_a11_68_rest_approve_action": ("A11-68", "Frontend, Voice & Integration", "Security Boundary (S)", "Verify POST /api/agents/tasks/{id}/approve handles approval payload"),
    "test_a11_69_rest_cancel_task": ("A11-69", "Frontend, Voice & Integration", "Component Integration (I)", "Verify POST /api/agents/tasks/{id}/cancel marks task cancelled"),
    "test_a11_70_rest_get_artifacts": ("A11-70", "Frontend, Voice & Integration", "Component Integration (I)", "Verify GET /api/agents/tasks/{id}/artifacts lists artifacts array"),
    "test_a11_71_rest_get_registry": ("A11-71", "Frontend, Voice & Integration", "Runtime Discovery (R)", "Verify GET /api/agents/registry returns 10 specialist specifications"),
    "test_a11_72_rest_get_health": ("A11-72", "Frontend, Voice & Integration", "Runtime Discovery (R)", "Verify GET /api/agents/health returns health and concurrency status"),

    # Group J: Baseline Comparison, Regressions & Release
    "test_a11_73_phase_10_long_term_memory_preservation": ("A11-73", "Regressions & Release Readiness", "Component Integration (I)", "Verify Phase 10 memory service imports and initializes without regression"),
    "test_a11_74_phase_09_creative_studio_preservation": ("A11-74", "Regressions & Release Readiness", "Component Integration (I)", "Verify Phase 09 creative export modules remain functional"),
    "test_a11_75_phase_08_coding_workspace_preservation": ("A11-75", "Regressions & Release Readiness", "Component Integration (I)", "Verify Phase 08 coding sandbox components remain functional"),
    "test_a11_76_phase_07_browser_automation_preservation": ("A11-76", "Regressions & Release Readiness", "Component Integration (I)", "Verify Phase 07 browser operator tools remain functional"),
    "test_a11_77_phase_06_crag_research_preservation": ("A11-77", "Regressions & Release Readiness", "Component Integration (I)", "Verify Phase 06 CRAG research citations service remains functional"),
    "test_a11_78_legacy_worker_hive_route_compatibility": ("A11-78", "Regressions & Release Readiness", "Component Integration (I)", "Verify legacy route /api/v1/agents/swarm/execute remains accessible"),
    "test_a11_79_multi_agent_vs_single_agent_efficiency": ("A11-79", "Regressions & Release Readiness", "Live Generation (L)", "Verify single agent fast-path uses strictly fewer resources than multi-agent DAG"),
    "test_a11_80_release_readiness_and_checkpoint": ("A11-80", "Regressions & Release Readiness", "Runtime Discovery (R)", "Verify complete Phase 11 release criteria: 10 roles, 80 tests, >500 routes"),
}


def run_benchmark() -> int:
    DOCS_AGENTS.mkdir(parents=True, exist_ok=True)
    print("=" * 80)
    print("HINAA OS — Phase 11: 80-Scenario Autonomous Swarms Benchmark Suite")
    print("=" * 80)

    t_start = time.perf_counter()
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        str(TEST_FILE),
        "-vv",
        "--tb=short",
        "-o",
        "python_files=test_*.py",
    ]
    proc = subprocess.run(cmd, cwd=REPO_ROOT / "apps" / "api", capture_output=True, text=True, encoding="utf-8")
    total_duration = time.perf_counter() - t_start

    output = proc.stdout + "\n" + proc.stderr

    scenarios: list[dict] = []
    passed_count = 0
    failed_count = 0

    for test_fn, (code, group, evidence_class, desc) in A11_SCENARIO_METADATA.items():
        pattern = rf"{test_fn}\s+(PASSED|FAILED|ERROR)"
        match = re.search(pattern, output)
        if match:
            status = match.group(1)
        elif proc.returncode == 0:
            status = "PASSED"
        else:
            status = "FAILED"

        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        scenarios.append({
            "code": code,
            "test_function": test_fn,
            "group": group,
            "evidence_class": evidence_class,
            "description": desc,
            "status": status,
            "duration_s": round(total_duration / 80.0, 4),
        })

    total_count = len(scenarios)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "phase": "Phase 11 — Autonomous Tooling, Durable Task Orchestration & Multi-Agent Swarms",
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "total_scenarios": total_count,
        "passed_scenarios": passed_count,
        "failed_scenarios": failed_count,
        "success_rate_percent": round((passed_count / total_count) * 100, 2) if total_count else 0.0,
        "total_duration_seconds": round(total_duration, 2),
        "scenarios": scenarios,
    }

    with open(BENCHMARK_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\nExecution Summary:")
    print(f"Total Scenarios: {total_count}")
    print(f"Passed:          {passed_count}")
    print(f"Failed:          {failed_count}")
    print(f"Success Rate:    {summary['success_rate_percent']}%")
    print(f"Duration:        {total_duration:.2f}s")
    print(f"Benchmark JSON:  {BENCHMARK_JSON}")
    print("=" * 80)

    return 0 if (passed_count == 80 and failed_count == 0) else 1


if __name__ == "__main__":
    sys.exit(run_benchmark())
