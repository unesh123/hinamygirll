"""
HINAA OS — Phase 12 80-Scenario Acceptance Benchmark Runner
Executes all 80 scenarios across Groups A-J and records structured performance metrics.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[3]
API_DIR = PROJECT_ROOT / "apps" / "api"
if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

import pytest


def run_benchmark() -> int:
    output_dir = PROJECT_ROOT / "docs" / "agents"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json_path = output_dir / "benchmark_results_phase12_suite.json"

    print("=" * 80)
    print("HINAA OS — Phase 12: 80-Scenario Hierarchical Team Orchestration Benchmark")
    print("=" * 80)

    t0 = time.perf_counter()

    test_file = str(API_DIR / "tests" / "agents" / "test_h12_suite.py")
    ret_code = pytest.main(["-v", test_file])

    duration = round(time.perf_counter() - t0, 2)

    results_data = {
        "benchmark": "HINAA OS Phase 12 — Hierarchical Team Orchestration",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
        "exit_code": int(ret_code),
        "total_scenarios": 80,
        "passed": 80 if ret_code == 0 else "check pytest summary",
        "duration_seconds": duration,
        "groups": {
            "Group A": "Execution Mode Decision Gate (H12-01 to H12-08)",
            "Group B": "Canonical Team Registry & Scopes (H12-09 to H12-16)",
            "Group C": "Typed Delegation Packets & Outcome Verification (H12-17 to H12-24)",
            "Group D": "Context Isolation, Scrubbing & Provenance (H12-25 to H12-32)",
            "Group E": "Nested Budget Slicing & Conservation (H12-33 to H12-40)",
            "Group F": "Hierarchical DAG Validation & Ceilings (H12-41 to H12-48)",
            "Group G": "Complete Ancestry Binding in Tier C Approvals (H12-49 to H12-56)",
            "Group H": "Independent QA Verification & Conflict Resolution (H12-57 to H12-64)",
            "Group I": "The Six Canonical Workflows W1-W6 (H12-65 to H12-72)",
            "Group J": "Long-Horizon Telemetry, Events & Resilience (H12-73 to H12-80)",
        },
    }

    with open(report_json_path, "w", encoding="utf-8") as f:
        json.dump(results_data, f, indent=2)

    print("=" * 80)
    print(f"Benchmark results recorded to: {report_json_path}")
    print(f"Total duration: {duration}s | Status: {'SUCCESS (100% Pass)' if ret_code == 0 else 'FAILURE'}")
    print("=" * 80)

    return int(ret_code)


if __name__ == "__main__":
    sys.exit(run_benchmark())
