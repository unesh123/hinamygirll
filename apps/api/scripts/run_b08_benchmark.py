"""Benchmark runner for HINAA OS Phase 08 Code Execution & Developer Sandbox.

Executes all 48 B08 scenarios, measures per-test duration, verifies assertions,
and serializes results to docs/coding/benchmark_results.json.
"""

from __future__ import annotations

import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest

SCENARIO_METADATA = {
    "test_b08_01_runtime_discovery": {
        "scenario_id": "B08-01",
        "name": "Host OS/runtime discovery accurately distinguishes available backends; fail closed",
        "evidence_class": "Component Integration (I)",
        "description": "Probes Docker, WSL2, and Windows Job Objects; verifies honest security classification.",
    },
    "test_b08_02_launch_isolated_environment": {
        "scenario_id": "B08-02",
        "name": "Launch real disposable isolated environment; verify identity and cleanup",
        "evidence_class": "Sandbox Security (S)",
        "description": "Spawns isolated worker under boundary constraints and verifies process termination.",
    },
    "test_b08_03_attempt_read_outside_workspace": {
        "scenario_id": "B08-03",
        "name": "Attempt read outside authorized project root; blocked by real runtime",
        "evidence_class": "Sandbox Security (S)",
        "description": "Enforces canonical workspace root verification and blocks directory traversal escape.",
    },
    "test_b08_04_cross_tenant_project_isolation": {
        "scenario_id": "B08-04",
        "name": "Attempt cross-tenant project/file access; boundaries prevent leakage",
        "evidence_class": "Sandbox Security (S)",
        "description": "Confirms Tenant B cannot execute commands or read files in Tenant A workspace.",
    },
    "test_b08_05_outbound_network_default_off": {
        "scenario_id": "B08-05",
        "name": "Attempt outbound network in default-off runtime",
        "evidence_class": "Sandbox Security (S)",
        "description": "ResourceLimits enforces allow_network=False boundary by default.",
    },
    "test_b08_06_scrubbed_process_environment": {
        "scenario_id": "B08-06",
        "name": "Attempt access to secrets; no credential exposed in env",
        "evidence_class": "Sandbox Security (S)",
        "description": "Strips all API keys, merchant secrets, and tokens from child process environment.",
    },
    "test_b08_07_reject_privileged_escalation": {
        "scenario_id": "B08-07",
        "name": "Reject privileged container, host-mounted root, Docker socket",
        "evidence_class": "Sandbox Security (S)",
        "description": "Blocks --privileged, /var/run/docker.sock, and root filesystem mount arguments.",
    },
    "test_b08_08_timeout_and_resource_limit": {
        "scenario_id": "B08-08",
        "name": "Enforce CPU and memory limits on aggressive fixture",
        "evidence_class": "Sandbox Security (S)",
        "description": "Terminates infinite loops and long-running fixtures upon timeout ceiling.",
    },
    "test_b08_09_output_buffer_truncation": {
        "scenario_id": "B08-09",
        "name": "Enforce PID/process count and output buffer quotas (1MB)",
        "evidence_class": "Sandbox Security (S)",
        "description": "Gracefully truncates oversized stdout/stderr buffers exceeding quota.",
    },
    "test_b08_10_cancel_process_tree": {
        "scenario_id": "B08-10",
        "name": "Cancel a spawned process tree; all descendants gone and resources cleaned",
        "evidence_class": "Sandbox Security (S)",
        "description": "Kills entire process tree via Windows Job Object / taskkill with zero zombie PIDs.",
    },
    "test_b08_11_workspace_snapshot_preservation": {
        "scenario_id": "B08-11",
        "name": "Create workspace snapshot; preserve existing user files",
        "evidence_class": "Component Integration (I)",
        "description": "Pre-mutation backup stores file state before applying patches for safe reversal.",
    },
    "test_b08_12_block_traversal_paths": {
        "scenario_id": "B08-12",
        "name": "Block ../, absolute paths, symlink/junction escape",
        "evidence_class": "Sandbox Security (S)",
        "description": "DiffEngine rejects patches targeting paths outside the workspace boundary.",
    },
    "test_b08_13_project_language_and_tool_detection": {
        "scenario_id": "B08-13",
        "name": "Detect project languages, lockfiles, tests, build scripts",
        "evidence_class": "Component Integration (I)",
        "description": "Accurately indexes Python (pytest) and Node/TypeScript (npm test, build) setups.",
    },
    "test_b08_14_bounded_symbol_search": {
        "scenario_id": "B08-14",
        "name": "Perform bounded repository search and symbol retrieval",
        "evidence_class": "Component Integration (I)",
        "description": "Retrieves class and function definitions without whole-repository context flooding.",
    },
    "test_b08_15_apply_structured_patch": {
        "scenario_id": "B08-15",
        "name": "Apply structured patch; generated diff matches disk result",
        "evidence_class": "Component Integration (I)",
        "description": "Replaces exact target characters and generates standard unified diff.",
    },
    "test_b08_16_reject_conflicting_patch": {
        "scenario_id": "B08-16",
        "name": "Reject patch outside scope, invalid base hash and conflicting modifications",
        "evidence_class": "Component Integration (I)",
        "description": "Detects missing target text or concurrent base hash drift and aborts cleanly.",
    },
    "test_b08_17_task_scoped_rollback": {
        "scenario_id": "B08-17",
        "name": "Roll back only task-owned modifications; detect conflicts",
        "evidence_class": "Component Integration (I)",
        "description": "Reverts only changes made by specific task ID, preserving user modifications.",
    },
    "test_b08_18_preserve_nepali_unicode": {
        "scenario_id": "B08-18",
        "name": "Preserve UTF-8 Nepali/Devanagari source, filenames and mixed-language strings",
        "evidence_class": "Component Integration (I)",
        "description": "Ensures Devanagari Unicode scripts and vowel matras are preserved without corruption.",
    },
    "test_b08_19_python_script_execution": {
        "scenario_id": "B08-19",
        "name": "Python script executes with real bounded stdout/stderr/exit status",
        "evidence_class": "Sandbox Security (S)",
        "description": "Executes real Python interpreter and captures separate stdout and stderr streams.",
    },
    "test_b08_20_node_test_execution": {
        "scenario_id": "B08-20",
        "name": "Node/TypeScript test runs with accurate tool version and isolated evidence",
        "evidence_class": "Sandbox Security (S)",
        "description": "Executes Node.js test script inside sandbox and asserts genuine test output.",
    },
    "test_b08_21_failing_test_reported_accurately": {
        "scenario_id": "B08-21",
        "name": "A failed lint/test reports precise failure and remains failed until fixed",
        "evidence_class": "Component Integration (I)",
        "description": "Captures ZeroDivisionError traceback and non-zero exit code faithfully.",
    },
    "test_b08_22_package_install_policy": {
        "scenario_id": "B08-22",
        "name": "Package install offline denies unseen dependency downloads",
        "evidence_class": "Component Integration (I)",
        "description": "Classifies package install actions under mutation tiers with audit checks.",
    },
    "test_b08_23_reject_shell_injection_commands": {
        "scenario_id": "B08-23",
        "name": "Reject shell-injection arguments; never concatenate untrusted strings",
        "evidence_class": "Component Integration (I)",
        "description": "Identifies dangerous system commands (rm -rf /, curl | sh) as Tier C.",
    },
    "test_b08_24_explicit_build_execution": {
        "scenario_id": "B08-24",
        "name": "Run build with explicit command, exit code and hashes",
        "evidence_class": "Component Integration (I)",
        "description": "Executes build script and asserts bundle file generation on disk.",
    },
    "test_b08_25_python_e2e_fix_workflow": {
        "scenario_id": "B08-25",
        "name": "Python feature task: inspect -> baseline fail -> patch -> tests pass -> verified diff",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Autonomous repair of Python calculator bug; runs pytest and verifies green status.",
    },
    "test_b08_26_node_e2e_fix_workflow": {
        "scenario_id": "B08-26",
        "name": "TypeScript bug fix: reproduce issue, patch, build and verify",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Autonomous update of Node.js function with test pass and build confirmation.",
    },
    "test_b08_27_decline_false_success_on_regression": {
        "scenario_id": "B08-27",
        "name": "Introduce intentional regression fixture; coding loop declines false success",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Agent declines false success when tests fail; transitions to FAILED state.",
    },
    "test_b08_28_prevent_unrelated_file_mutations": {
        "scenario_id": "B08-28",
        "name": "Ambiguous user task produces explicit assumptions; no unrelated mutations",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Guarantees out-of-scope files like README are completely untouched by task.",
    },
    "test_b08_29_repair_loop_budget_ceiling": {
        "scenario_id": "B08-29",
        "name": "Repair loop executes within configured iteration budget",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Task spec enforces hard ceiling of 3 repair iterations to avoid runaway loops.",
    },
    "test_b08_30_reproducible_test_run": {
        "scenario_id": "B08-30",
        "name": "Fresh checkout reruns instructions and reproduces build/test result",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Deterministic rerun of pytest suite produces identical passing result.",
    },
    "test_b08_31_git_branch_safety": {
        "scenario_id": "B08-31",
        "name": "Git branch creation leaves main unchanged",
        "evidence_class": "Component Integration (I)",
        "description": "Ensures feature branching operates safely under Tier B mutation tier.",
    },
    "test_b08_32_reject_git_push_without_approval": {
        "scenario_id": "B08-32",
        "name": "Reject git push, force push, remote change without Tier C approval",
        "evidence_class": "Component Integration (I)",
        "description": "Remote git operations strictly classified as Tier C Specific Approval.",
    },
    "test_b08_33_artifact_provenance_manifest": {
        "scenario_id": "B08-33",
        "name": "Artifact manifest includes task, command, time, checksum, dependency digest",
        "evidence_class": "Component Integration (I)",
        "description": "Verifies artifact inventory records 64-char SHA-256 and task provenance.",
    },
    "test_b08_34_trace_tenant_id_propagation": {
        "scenario_id": "B08-34",
        "name": "Trace/tenant/task IDs link backend action history",
        "evidence_class": "Component Integration (I)",
        "description": "Guarantees tenant_id and user_id propagate through coding task status.",
    },
    "test_b08_35_event_schema_contract": {
        "scenario_id": "B08-35",
        "name": "Developer panel event schema verification",
        "evidence_class": "UI Observation (UI)",
        "description": "Verifies activity status stream schema (runId, type, label, timestamp).",
    },
    "test_b08_36_streaming_large_log_virtualization": {
        "scenario_id": "B08-36",
        "name": "Streaming output handles large outputs via truncation",
        "evidence_class": "UI Observation (UI)",
        "description": "Truncates large terminal streams gracefully without freezing client DOM.",
    },
    "test_b08_37_cancellation_confirmation": {
        "scenario_id": "B08-37",
        "name": "User cancellation immediately stops active task and backend processes",
        "evidence_class": "UI Observation (UI)",
        "description": "Cancellation signal instantly transitions task to CANCELLED state.",
    },
    "test_b08_38_sse_event_history_replay": {
        "scenario_id": "B08-38",
        "name": "Reconnected SSE resumes event stream from buffer",
        "evidence_class": "UI Observation (UI)",
        "description": "Reconnected clients receive all past events in sequence before live stream.",
    },
    "test_b08_39_frontend_component_export": {
        "scenario_id": "B08-39",
        "name": "UI component export verification",
        "evidence_class": "UI Observation (UI)",
        "description": "Verifies CodingTaskPanel.tsx exists, compiles, and connects to EventSource.",
    },
    "test_b08_40_approval_token_tamper_defense": {
        "scenario_id": "B08-40",
        "name": "Approval token bound to user, tenant, task, command; tampering invalidates it",
        "evidence_class": "Component Integration (I)",
        "description": "HMAC-SHA256 parameter binding rejects altered command or task targets.",
    },
    "test_b08_41_prompt_injection_sanitization": {
        "scenario_id": "B08-41",
        "name": "Malicious README/log prompt-injection defanged; no privileges granted",
        "evidence_class": "Sandbox Security (S)",
        "description": "Defangs override instructions and encapsulates in untrusted tags.",
    },
    "test_b08_42_untrusted_script_secret_isolation": {
        "scenario_id": "B08-42",
        "name": "Untrusted script inside sandbox cannot access secrets",
        "evidence_class": "Sandbox Security (S)",
        "description": "Child process inspection reveals scrubbed environment variables.",
    },
    "test_b08_43_durable_terminal_state": {
        "scenario_id": "B08-43",
        "name": "Task cancellation leaves durable terminal state",
        "evidence_class": "Component Integration (I)",
        "description": "Cancelled tasks persist CANCELLED status in service registry.",
    },
    "test_b08_44_parallel_tasks_isolation": {
        "scenario_id": "B08-44",
        "name": "Two parallel tasks enforce quotas and isolated workspaces",
        "evidence_class": "Component Integration (I)",
        "description": "Concurrent workers run independently without cross-workspace interference.",
    },
    "test_b08_45_repeated_workflow_stability": {
        "scenario_id": "B08-45",
        "name": "Repeated 5-step coding workflow completes reliably over 5 runs",
        "evidence_class": "End-to-End Workflow (E2E)",
        "description": "Five consecutive command executions exhibit 100% stability and consistent latency.",
    },
    "test_b08_46_actionable_error_classification": {
        "scenario_id": "B08-46",
        "name": "Distinct actionable error classification for dependency failure and timeouts",
        "evidence_class": "Component Integration (I)",
        "description": "Distinguishes ModuleNotFoundError and TimeoutError with explicit diagnostic signals.",
    },
    "test_b08_47_no_browser_to_shell_escalation": {
        "scenario_id": "B08-47",
        "name": "Phase 06 CRAG and Phase 07 browser integration preserve permissions",
        "evidence_class": "Component Integration (I)",
        "description": "Prevents shell command execution under read-only browser or search permissions.",
    },
    "test_b08_48_regression_contracts": {
        "scenario_id": "B08-48",
        "name": "Regression check across Phase 06 CRAG, Phase 05 Voice, and Agency",
        "evidence_class": "Component Integration (I)",
        "description": "Verifies core contract enum imports for Research, Voice, and Browser engines.",
    },
}


class BenchmarkCollector:
    def __init__(self):
        self.reports = {}

    def pytest_runtest_logreport(self, report):
        if report.when == "call":
            test_name = report.location[2]
            self.reports[test_name] = {
                "outcome": report.outcome,
                "duration": report.duration,
            }


def main():
    print("=" * 70)
    print("HINAA OS Phase 08 — 48-Scenario Acceptance & Benchmark Execution")
    print("=" * 70)

    collector = BenchmarkCollector()
    t_start = time.perf_counter()

    test_file = str(Path(__file__).parent.parent / "tests" / "coding" / "test_b08_suite.py")
    ret_code = pytest.main(["-v", test_file], plugins=[collector])

    total_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

    scenarios_results = []
    passed_count = 0
    failed_count = 0

    for test_fn, meta in SCENARIO_METADATA.items():
        rep = collector.reports.get(test_fn, {"outcome": "missing", "duration": 0.0})
        status = "PASSED" if rep["outcome"] == "passed" else "FAILED"
        if status == "PASSED":
            passed_count += 1
        else:
            failed_count += 1

        duration_ms = round(rep["duration"] * 1000, 2)
        scenarios_results.append({
            "scenario_id": meta["scenario_id"],
            "name": meta["name"],
            "evidence_class": meta["evidence_class"],
            "status": status,
            "duration_ms": duration_ms,
            "description": meta["description"],
        })

    # Sort by scenario_id
    scenarios_results.sort(key=lambda s: s["scenario_id"])

    benchmark_output = {
        "benchmark_suite": "HINAA OS Phase 08 — Code Execution & Developer Sandbox",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "total_scenarios": len(scenarios_results),
            "passed": passed_count,
            "failed": failed_count,
            "pass_rate_percent": round((passed_count / len(scenarios_results)) * 100, 2) if scenarios_results else 0.0,
            "total_suite_duration_ms": total_duration_ms,
        },
        "environment": {
            "os": platform.platform(),
            "python_version": platform.python_version(),
            "processor_count": os.cpu_count(),
            "primary_isolation_backend": "RESTRICTED_HOST_PROCESS",
            "security_profile": "Windows Job Object + scrubbed environment + path traversal boundary",
        },
        "evidence_class_breakdown": {
            "Sandbox Security (S)": len([s for s in scenarios_results if "Sandbox Security" in s["evidence_class"]]),
            "Component Integration (I)": len([s for s in scenarios_results if "Component Integration" in s["evidence_class"]]),
            "End-to-End Workflow (E2E)": len([s for s in scenarios_results if "End-to-End" in s["evidence_class"]]),
            "UI Observation (UI)": len([s for s in scenarios_results if "UI Observation" in s["evidence_class"]]),
        },
        "scenarios": scenarios_results,
    }

    out_path = Path(__file__).parent.parent.parent.parent / "docs" / "coding" / "benchmark_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(benchmark_output, f, indent=2)

    print(f"\n[BENCHMARK COMPLETE]")
    print(f"Total Scenarios: {benchmark_output['summary']['total_scenarios']}")
    print(f"Passed:          {benchmark_output['summary']['passed']}")
    print(f"Failed:          {benchmark_output['summary']['failed']}")
    print(f"Pass Rate:       {benchmark_output['summary']['pass_rate_percent']}%")
    print(f"Total Duration:  {benchmark_output['summary']['total_suite_duration_ms']} ms")
    print(f"Saved to:        {out_path}")

    sys.exit(0 if failed_count == 0 else 1)


if __name__ == "__main__":
    main()
