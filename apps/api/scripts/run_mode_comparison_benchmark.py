"""
HINAA OS — Phase 12 Comparative Benchmark Runner
Evaluates 3 Execution Modes on a frozen 30-task evaluation set:
  Mode A: Single-Agent Fast Path
  Mode B: Phase 11 Flat Multi-Agent Swarm
  Mode C: Phase 12 Hierarchical Team Orchestration
Outputs: docs/agents/benchmark_results_phase12.json and comparative analysis.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

# Ensure apps/api is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_DIR = PROJECT_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

from hinaa_api.agents.contracts import ExecutionMode, TaskStatus
from hinaa_api.agents.service import AgentOrchestrationService


FROZEN_30_TASKS = [
    # Tier 1: 10 Simple Single-Step Queries (T01 - T10)
    {"id": "T01", "goal": "Namaste! What is the current time in Kathmandu?", "tier": "simple"},
    {"id": "T02", "goal": "Who are you and what are your capabilities?", "tier": "simple"},
    {"id": "T03", "goal": "Convert 5000 NPR to paisa", "tier": "simple"},
    {"id": "T04", "goal": "What is the capital of Nepal?", "tier": "simple"},
    {"id": "T05", "goal": "How do you say thank you in Nepali?", "tier": "simple"},
    {"id": "T06", "goal": "List the seven provinces of Nepal", "tier": "simple"},
    {"id": "T07", "goal": "What is the official currency code of Nepal?", "tier": "simple"},
    {"id": "T08", "goal": "Translate 'Good morning' into Devanagari script", "tier": "simple"},
    {"id": "T09", "goal": "What is the height of Mount Everest in meters?", "tier": "simple"},
    {"id": "T10", "goal": "Check system health and active specialist count", "tier": "simple"},

    # Tier 2: 10 Moderate Single-Workstream Tasks (T11 - T20)
    {"id": "T11", "goal": "Refactor error handling in auth module and check exit code", "tier": "moderate"},
    {"id": "T12", "goal": "Research Nepal Labor Act 2074 overtime regulations with citations", "tier": "moderate"},
    {"id": "T13", "goal": "Implement rate limiting middleware and run pytest suite", "tier": "moderate"},
    {"id": "T14", "goal": "Investigate eSewa SDK webhook signature verification steps", "tier": "moderate"},
    {"id": "T15", "goal": "Translate UI button labels to Nepali and validate Devanagari encoding", "tier": "moderate"},
    {"id": "T16", "goal": "Write a Python script to validate VAT PAN numbers in Nepal", "tier": "moderate"},
    {"id": "T17", "goal": "Audit secret canaries and prompt injection boundaries in chat stream", "tier": "moderate"},
    {"id": "T18", "goal": "Export timeline video clip of product walkthrough via FFmpeg", "tier": "moderate"},
    {"id": "T19", "goal": "Verify file hash checksums for build artifacts in dist folder", "tier": "moderate"},
    {"id": "T20", "goal": "Scrape public notice table from Nepal Law Commission portal", "tier": "moderate"},

    # Tier 3: 10 Complex Multi-Workstream Missions (T21 - T30)
    {"id": "T21", "goal": "Build a complete bilingual website with tests and browser verification (Workflow W1)", "tier": "complex"},
    {"id": "T22", "goal": "Research Nepal tax slabs and implement runnable tax calculator microservice (Workflow W2)", "tier": "complex"},
    {"id": "T23", "goal": "Coordinate engineering and QA teams with conflict detection and failure override (Workflow W3)", "tier": "complex"},
    {"id": "T24", "goal": "Execute multi-step build, simulate worker crash mid-nested run, and recover leases (Workflow W4)", "tier": "complex"},
    {"id": "T25", "goal": "Simulate eSewa 250 NPR checkout with integer paisa accounting and Tier C ancestry approval (Workflow W5)", "tier": "complex"},
    {"id": "T26", "goal": "Process text-to-video creative request, declare truthful model limits, and export timeline MP4 (Workflow W6)", "tier": "complex"},
    {"id": "T27", "goal": "Develop full-stack Nepal company registration portal with bilingual forms and QA test suite", "tier": "complex"},
    {"id": "T28", "goal": "Multi-hop research on Nepal cyber law, code generation for compliance validator, and browser testing", "tier": "complex"},
    {"id": "T29", "goal": "Create cross-team marketing package: bilingual copy, raster assets, timeline video, and security check", "tier": "complex"},
    {"id": "T30", "goal": "Full-horizon microservice migration: schema refactor, CRAG documentation sync, bilingual error messages, and integration tests", "tier": "complex"},
]


def run_comparative_benchmark() -> Dict[str, Any]:
    temp_events = API_DIR / "data" / "benchmark_events.db"
    temp_tasks = API_DIR / "data" / "benchmark_tasks.db"
    temp_events.unlink(missing_ok=True)
    temp_tasks.unlink(missing_ok=True)

    service = AgentOrchestrationService(db_path_events=temp_events, db_path_tasks=temp_tasks)

    modes = [
        ("Mode A (Single Agent)", ExecutionMode.SINGLE_AGENT_FAST_PATH),
        ("Mode B (Flat Swarm)", ExecutionMode.FLAT_MULTI_AGENT),
        ("Mode C (Hierarchical Teams)", ExecutionMode.HIERARCHICAL_TEAM),
    ]

    all_results: Dict[str, List[Dict[str, Any]]] = {
        "Mode A (Single Agent)": [],
        "Mode B (Flat Swarm)": [],
        "Mode C (Hierarchical Teams)": [],
    }

    print("=" * 80)
    print("HINAA OS — Phase 12: 3-Mode Comparative Benchmark (30 Frozen Tasks)")
    print("=" * 80)

    for mode_name, mode_enum in modes:
        print(f"\n--- Running: {mode_name} ---")
        for item in FROZEN_30_TASKS:
            task_id = f"bm-{mode_enum.value.lower()[:4]}-{item['id']}-{int(time.time()*1000)%100000}"
            t0 = time.perf_counter()

            # Create task with forced mode
            task = service.create_task(
                goal=item["goal"],
                tenant_id="benchmark",
                user_id="bench-runner",
                execution_mode=mode_enum,
            )

            # Run task
            res = service.run_task(task.task_id)

            # If waiting for approval (e.g. W5 commerce), approve automatically for benchmark measurement
            if res and res.status == TaskStatus.WAITING_APPROVAL:
                apprs = [a for a in service.policy_bridge._approvals.values() if a.task_id == task.task_id]
                if apprs:
                    service.approve_action(
                        task_id=task.task_id,
                        approval_id=apprs[0].approval_id,
                        signature="bm_valid_sig",
                        tenant_id="benchmark",
                    )
                    # Re-run to completion
                    res = service.run_task(task.task_id)

            duration_ms = round((time.perf_counter() - t0) * 1000, 2)

            status_str = res.status.value if res else "UNKNOWN"
            passed = res.verification_passed if res else False
            tokens = res.budget_used.consumed_tokens if res else 0
            paisa = res.budget_used.consumed_cost_paisa if res else 0
            node_count = len(task.nodes)
            team_count = len(task.team_runs)

            record = {
                "task_id": item["id"],
                "goal": item["goal"],
                "tier": item["tier"],
                "mode": mode_name,
                "status": status_str,
                "verification_passed": passed,
                "duration_ms": duration_ms,
                "tokens": tokens,
                "cost_paisa": paisa,
                "node_count": node_count,
                "team_count": team_count,
            }
            all_results[mode_name].append(record)
            print(f"[{item['id']}] {item['tier'].upper():<8} -> status: {status_str:<12} | passed: {str(passed):<5} | latency: {duration_ms:>7.2f}ms | tokens: {tokens:>5}")

    # Compute Summary Statistics
    summary: Dict[str, Any] = {}
    for mode_name, records in all_results.items():
        total = len(records)
        completed = sum(1 for r in records if r["status"] == "COMPLETED")
        verified = sum(1 for r in records if r["verification_passed"])
        avg_latency = round(sum(r["duration_ms"] for r in records) / total, 2)
        total_tokens = sum(r["tokens"] for r in records)
        total_paisa = sum(r["cost_paisa"] for r in records)

        # By Tier breakdowns
        by_tier = {}
        for t in ["simple", "moderate", "complex"]:
            tier_recs = [r for r in records if r["tier"] == t]
            by_tier[t] = {
                "count": len(tier_recs),
                "completed": sum(1 for r in tier_recs if r["status"] == "COMPLETED"),
                "verified": sum(1 for r in tier_recs if r["verification_passed"]),
                "avg_latency_ms": round(sum(r["duration_ms"] for r in tier_recs) / len(tier_recs), 2),
                "avg_tokens": round(sum(r["tokens"] for r in tier_recs) / len(tier_recs), 1),
            }

        summary[mode_name] = {
            "total_tasks": total,
            "completed_rate_pct": round((completed / total) * 100, 1),
            "verified_rate_pct": round((verified / total) * 100, 1),
            "avg_latency_ms": avg_latency,
            "total_tokens": total_tokens,
            "total_paisa": total_paisa,
            "by_tier": by_tier,
        }

    output_payload = {
        "benchmark_name": "HINAA OS Phase 12 Comparative Evaluation (30 Tasks x 3 Modes)",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "summary": summary,
        "detailed_results": all_results,
    }

    out_file = PROJECT_ROOT / "docs" / "agents" / "benchmark_results_phase12.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2)

    print("\n" + "=" * 80)
    print("COMPARATIVE BENCHMARK SUMMARY:")
    print("=" * 80)
    for m, s in summary.items():
        print(f"\n{m}:")
        print(f"  Completion Rate:   {s['completed_rate_pct']}%")
        print(f"  Verification Rate: {s['verified_rate_pct']}%")
        print(f"  Avg Latency:       {s['avg_latency_ms']} ms")
        print(f"  Total Tokens:      {s['total_tokens']:,}")
        print(f"  Total Cost:        NPR {(s['total_paisa']/100):.2f}")
        for tier_name, tstats in s["by_tier"].items():
            print(f"    - {tier_name.capitalize()}: {tstats['verified']}/{tstats['count']} verified ({tstats['avg_latency_ms']} ms avg)")

    print(f"\nSaved full results to: {out_file}")
    return output_payload


if __name__ == "__main__":
    run_comparative_benchmark()
