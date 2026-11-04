"""Benchmark runner for HINAA OS Phase 07 Browser Automation & Web Operations.

Executes all 36 B07 scenarios, measures per-test duration, verifies assertions,
and serializes results to docs/browser/benchmark_results.json.
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
    "test_b07_01_start_close_real_browser": {
        "scenario_id": "B07-01",
        "name": "Start/close real browser and context; no orphaned processes",
        "evidence_class": "Browser Integration",
        "description": "Validates real Playwright Chromium lifecycle, connection health, and clean process termination without zombie PIDs.",
    },
    "test_b07_02_open_permitted_https_page": {
        "scenario_id": "B07-02",
        "name": "Open permitted HTTPS page and confirm title, URL and heading",
        "evidence_class": "Safe Public-Web Read-Only",
        "description": "Navigates to safe public HTTPS origin and verifies observed URL and title match browser reality.",
    },
    "test_b07_03_reject_unsafe_schemes": {
        "scenario_id": "B07-03",
        "name": "Reject malformed, unsupported and unsafe URL schemes",
        "evidence_class": "Unit / Mocked",
        "description": "Blocks file://, javascript:, data: and unsupported schemes before browser dispatch.",
    },
    "test_b07_04_block_redirect_to_ssrf": {
        "scenario_id": "B07-04",
        "name": "Validate redirects; block redirect to prohibited internal address",
        "evidence_class": "Browser Integration",
        "description": "Intercepts HTTP 302 redirect attempting to pivot from safe origin to internal loopback/metadata IP.",
    },
    "test_b07_05_read_hydrated_spa_page": {
        "scenario_id": "B07-05",
        "name": "Read JavaScript-rendered page after hydration and verify content",
        "evidence_class": "Browser Integration",
        "description": "Auto-waits for client-side JavaScript DOM hydration and verifies postcondition before extraction.",
    },
    "test_b07_06_navigate_and_switch_tabs": {
        "scenario_id": "B07-06",
        "name": "Navigate tabs/popups; associate ownership and selected tab",
        "evidence_class": "Browser Integration",
        "description": "Verifies multi-tab registration, tab listing, and switching active tab in single browser context.",
    },
    "test_b07_07_click_accessible_locator": {
        "scenario_id": "B07-07",
        "name": "Click accessible locator; assert genuine outcome",
        "evidence_class": "Browser Integration",
        "description": "Uses get_by_role('link', name='...') to navigate and verifies postcondition url_contains.",
    },
    "test_b07_08_fill_controlled_form": {
        "scenario_id": "B07-08",
        "name": "Fill and validate a controlled form without consequential submission",
        "evidence_class": "Browser Integration",
        "description": "Fills form field via accessible label and asserts actual input value in DOM.",
    },
    "test_b07_09_authorized_form_submission": {
        "scenario_id": "B07-09",
        "name": "Submit authorized seeded test form and verify backend mutation",
        "evidence_class": "Authorized End-to-End Workflow",
        "description": "Full end-to-end form fill and Tier C submission with cryptographic approval token, verifying seeded backend DB.",
    },
    "test_b07_10_element_detachment_recovery": {
        "scenario_id": "B07-10",
        "name": "Handle element detachment and retry once safely",
        "evidence_class": "Unit / Mocked",
        "description": "RecoveryHandler catches transient DOM detachment error and safely succeeds on retry.",
    },
    "test_b07_11_modal_dialog_proceed": {
        "scenario_id": "B07-11",
        "name": "Detect dialog/modal and proceed only on approved target",
        "evidence_class": "Browser Integration",
        "description": "Interacts with modal dialog elements and verifies modal confirmation postcondition.",
    },
    "test_b07_12_extract_paginated_table": {
        "scenario_id": "B07-12",
        "name": "Extract paginated table without duplicates or missing rows",
        "evidence_class": "Browser Integration",
        "description": "Extracts structured tabular data across multiple pages and asserts unique complete row set.",
    },
    "test_b07_13_iframe_nested_navigation": {
        "scenario_id": "B07-13",
        "name": "Navigate iframe or nested structure within permitted site",
        "evidence_class": "Browser Integration",
        "description": "Accesses child frame locator within permitted origin and extracts nested frame content.",
    },
    "test_b07_14_timeout_navigation_recovery": {
        "scenario_id": "B07-14",
        "name": "Recover from timed-out navigation with bounded retry/clear failure",
        "evidence_class": "Safe Public-Web Read-Only",
        "description": "Navigates to non-routable address with bounded timeout and asserts clear failure classification.",
    },
    "test_b07_15_bounded_five_step_workflow": {
        "scenario_id": "B07-15",
        "name": "Bounded plan completes a 5+ step local task without inventing results",
        "evidence_class": "Browser Integration",
        "description": "Executes 5-step sequence (open, click, fill, check, screenshot) and verifies complete execution.",
    },
    "test_b07_16_screenshot_evidence_match": {
        "scenario_id": "B07-16",
        "name": "Screenshot, trace, timestamp and visited URL match actual browser state",
        "evidence_class": "Browser Integration",
        "description": "Captures PNG screenshot to sandboxed storage with verified SHA-256 hash and non-empty byte payload.",
    },
    "test_b07_17_extract_to_crag_source": {
        "scenario_id": "B07-17",
        "name": "Extract page text to Phase 06 CRAG with source provenance intact",
        "evidence_class": "Browser Integration",
        "description": "Bridges live DOM extraction into Phase 06 CRAG Source schema with provenance and trust tier intact.",
    },
    "test_b07_18_contradictory_web_pages_flagged": {
        "scenario_id": "B07-18",
        "name": "Inject contradictory pages; final answer flags disagreement",
        "evidence_class": "Unit / Mocked",
        "description": "Feed conflicting web assertions to ClaimGroundingVerifier and verify dispute status.",
    },
    "test_b07_19_fake_citation_rejected": {
        "scenario_id": "B07-19",
        "name": "Inject website text with fake citation [999]; citation gate rejects it",
        "evidence_class": "Unit / Mocked",
        "description": "Ensures anti-fabrication citation gate strips unverified hallucinated bracket markers.",
    },
    "test_b07_20_download_permitted_file": {
        "scenario_id": "B07-20",
        "name": "Download permitted test file, verify checksum and sandbox location",
        "evidence_class": "Browser Integration",
        "description": "Downloads CSV into quarantine directory, computes SHA-256, and confirms safe file receipt.",
    },
    "test_b07_21_reject_dangerous_download": {
        "scenario_id": "B07-21",
        "name": "Reject dangerous download (.exe quarantine)",
        "evidence_class": "Browser Integration",
        "description": "Detects executable payload (.exe) during browser download and rejects it immediately.",
    },
    "test_b07_22_upload_approved_test_fixture": {
        "scenario_id": "B07-22",
        "name": "Upload explicitly approved test fixture only; block sensitive files",
        "evidence_class": "Unit / Mocked",
        "description": "Allows files within authorized boundary and blocks sensitive patterns like .env and private keys.",
    },
    "test_b07_23_sse_task_event_streaming": {
        "scenario_id": "B07-23",
        "name": "Frontend task panel updates from actual SSE/task state",
        "evidence_class": "Browser Integration",
        "description": "Streams real-time execution events over queue subscription matching SSE wire schema.",
    },
    "test_b07_24_failed_action_records_accurate_error": {
        "scenario_id": "B07-24",
        "name": "Failed browser action generates accurate error UI and no success card",
        "evidence_class": "Browser Integration",
        "description": "Attempts action on non-existent element and records accurate failure code without false completion.",
    },
    "test_b07_25_prompt_injection_neutralization": {
        "scenario_id": "B07-25",
        "name": "Prompt injection in page body cannot alter agent rules",
        "evidence_class": "Unit / Mocked",
        "description": "Sanitizes malicious instruction overrides and wraps raw DOM in <untrusted_browser_content> tags.",
    },
    "test_b07_26_spoofed_system_tag_defense": {
        "scenario_id": "B07-26",
        "name": "Spoofed HTML <system>/'approval granted' does not authorize action",
        "evidence_class": "Unit / Mocked",
        "description": "Neutralizes spoofed XML markup attempting privilege escalation inside untrusted webpage text.",
    },
    "test_b07_27_ssrf_prohibited_ips": {
        "scenario_id": "B07-27",
        "name": "SSRF tests deny localhost, RFC1918, link-local, IPv6 loopback, metadata IP",
        "evidence_class": "Unit / Mocked",
        "description": "Exhaustive validation against 127.0.0.1, 10.0.0.0/8, 192.168.0.0/16, 172.16.0.0/12, and 169.254.169.254.",
    },
    "test_b07_28_tenant_context_isolation": {
        "scenario_id": "B07-28",
        "name": "Separate tenants/contexts share no cookies, storage, or page content",
        "evidence_class": "Browser Integration",
        "description": "Confirms cookies and storage set in Tenant A context do not leak into Tenant B context.",
    },
    "test_b07_29_tier_c_action_requires_confirmation": {
        "scenario_id": "B07-29",
        "name": "Tier C action without explicit user confirmation is blocked and audited",
        "evidence_class": "Browser Integration",
        "description": "Consequential action (submit/purchase) without user approval token returns APPROVAL_REQUIRED.",
    },
    "test_b07_30_tampered_approval_token_rejected": {
        "scenario_id": "B07-30",
        "name": "Changed recipient, price, or parameters causes fresh approval requirement",
        "evidence_class": "Unit / Mocked",
        "description": "HMAC-SHA256 token verification rejects tampered action parameters or target URL changes.",
    },
    "test_b07_31_mfa_login_safe_handoff": {
        "scenario_id": "B07-31",
        "name": "Unauthorized site login/CAPTCHA/MFA triggers safe handoff",
        "evidence_class": "Browser Integration",
        "description": "Detects authentication/MFA challenge and halts automated traversal safely.",
    },
    "test_b07_32_secret_redaction_in_policy": {
        "scenario_id": "B07-32",
        "name": "No credentials, cookies, personal files appear in UI logs or traces",
        "evidence_class": "Unit / Mocked",
        "description": "Automatically classifies password fields as Tier C and redacts sensitive parameters from logs.",
    },
    "test_b07_33_cancel_active_task": {
        "scenario_id": "B07-33",
        "name": "Cancel active task during navigation and verify no subsequent mutation",
        "evidence_class": "Browser Integration",
        "description": "Aborts in-flight navigation and subsequent actions immediately upon cancellation request.",
    },
    "test_b07_34_restart_service_recovery": {
        "scenario_id": "B07-34",
        "name": "Restart backend while task is active; restore state safely",
        "evidence_class": "Browser Integration",
        "description": "Ensures clean shutdown of service without leaving orphaned headless browser processes.",
    },
    "test_b07_35_concurrency_capacity_limit": {
        "scenario_id": "B07-35",
        "name": "Run concurrent independent tasks; enforce max sessions",
        "evidence_class": "Unit / Mocked",
        "description": "Validates hard concurrency slot boundary and capacity semaphore release.",
    },
    "test_b07_36_repeated_e2e_stability": {
        "scenario_id": "B07-36",
        "name": "Re-run a 5+ step controlled E2E workflow repeatedly; report stability",
        "evidence_class": "Authorized End-to-End Workflow",
        "description": "Executes 3 back-to-back complete browser inspection lifecycles and records consistent latency.",
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
    print("HINAA OS Phase 07 — 36-Scenario Benchmark Execution")
    print("=" * 70)

    collector = BenchmarkCollector()
    t_start = time.perf_counter()

    test_file = str(Path(__file__).parent.parent / "tests" / "browser" / "test_b07_suite.py")
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
        "benchmark_suite": "HINAA OS Phase 07 — Browser Automation & Web Operations",
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
            "browser_engine": "Chromium (Playwright async)",
            "headless": True,
            "concurrency_limit": 5,
        },
        "evidence_class_breakdown": {
            "Unit / Mocked": len([s for s in scenarios_results if s["evidence_class"] == "Unit / Mocked"]),
            "Browser Integration": len([s for s in scenarios_results if s["evidence_class"] == "Browser Integration"]),
            "Safe Public-Web Read-Only": len([s for s in scenarios_results if s["evidence_class"] == "Safe Public-Web Read-Only"]),
            "Authorized End-to-End Workflow": len([s for s in scenarios_results if s["evidence_class"] == "Authorized End-to-End Workflow"]),
        },
        "scenarios": scenarios_results,
    }

    out_path = Path(__file__).parent.parent.parent.parent / "docs" / "browser" / "benchmark_results.json"
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
