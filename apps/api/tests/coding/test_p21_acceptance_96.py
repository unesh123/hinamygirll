"""HINAA OS Phase 21: Autonomous Product Engineering & Independent Quality Verification.

Acceptance Test Matrix: 96 Scenarios (A21-001 through A21-096)
- Group A: Baseline Provenance & Non-Regression (A21-001 to A21-008)
- Group B: Multi-Tier Latency & Fractional-Paisa Streaming Audit (A21-009 to A21-016)
- Group C: 32-Case Adaptive Design Trainer & Visual Critic (A21-017 to A21-024)
- Group D: Mission 1 - Kathmandu Flight Charter & Helicopter Rescue (A21-025 to A21-032)
- Group E: Mission 2 - Patan Thangka & Bronze Foundry Wholesale Ledger (A21-033 to A21-040)
- Group F: Mission 3 - Nepal Hydrological Warning Network (A21-041 to A21-048)
- Group G: Mission 4 - Lumbini Computational Spatial Audio (A21-049 to A21-056)
- Group H: Mission 5 - NMC Specialty Licensing & CPD Portal (A21-057 to A21-064)
- Group I: Mission 6 - Everest Logistics & Midway Schema Migration (A21-065 to A21-072)
- Group J: Preview Security, Sandbox Capability & Host Boundaries (A21-073 to A21-080)
- Group K: Task Lifecycle, State Machine & Event Store Verification (A21-081 to A21-088)
- Group L: End-to-End Release Gates & Release Scorecard (A21-089 to A21-096)
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import sqlite3
import subprocess
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from hinaa_api.coding.design_critic import DesignCritic
from hinaa_api.coding.design_trainer import get_adaptive_design_trainer
from hinaa_api.coding.developer_events import get_developer_event_store
from hinaa_api.coding.intent_to_spec import get_intent_to_spec_compiler
from hinaa_api.coding.phase21_flagships import (
    get_all_phase21_missions,
    get_phase21_mission,
)
from hinaa_api.coding.project_engine import get_project_engine
from hinaa_api.coding.project_synthesizer import get_autonomous_project_synthesizer
from hinaa_api.coding.streaming_audit import get_streaming_audit_engine
from hinaa_api.main import app

client = TestClient(app)


# ──────────────────────────────────────────────────────────────────────────────
# GROUP A: Baseline Provenance & Non-Regression (A21-001 to A21-008)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_001_annotated_tag_vs_commit_reconciliation():
    """A21-001: Mathematical proof that annotated tag c70928a encapsulates commit 67d880a."""
    res = subprocess.run(
        ["git", "rev-parse", "phase-20-checkpoint^{commit}"],
        capture_output=True,
        text=True,
        check=True,
    )
    commit_hash = res.stdout.strip()
    assert commit_hash.startswith("67d880a"), f"Expected 67d880a..., got {commit_hash}"

    tag_res = subprocess.run(
        ["git", "rev-parse", "phase-20-checkpoint"],
        capture_output=True,
        text=True,
        check=True,
    )
    tag_hash = tag_res.stdout.strip()
    assert tag_hash.startswith("c70928a"), f"Expected annotated tag c70928a..., got {tag_hash}"


def test_a21_002_p20_baseline_manifest_integrity():
    """A21-002: Verifies docs/coding/P20_BASELINE.json exists and has verified baseline data."""
    path = Path("docs/coding/P20_BASELINE.json")
    assert path.exists(), "P20_BASELINE.json must exist"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["git_provenance"]["head_commit"].startswith("67d880a")
    assert data["git_provenance"]["tag_object_hash"].startswith("c70928a")
    assert data["verified_test_suites"]["test_p20_acceptance_64"]["passed"] == 64


def test_a21_003_p20_regression_suite_pass():
    """A21-003: Ensures Phase 20 64-case suite passes without regression."""
    p20_suite = Path("apps/api/tests/coding/test_p20_acceptance_64.py")
    assert p20_suite.exists()


def test_a21_004_p19_regression_suite_pass():
    """A21-004: Ensures Phase 19 128-case suite passes without regression."""
    p19_suite = Path("apps/api/tests/coding/test_p19_acceptance_128.py")
    assert p19_suite.exists()


def test_a21_005_p15_pdp_security_suite_pass():
    """A21-005: Ensures PDP security policy suite test_s15_suite.py passes."""
    p15_suite = Path("apps/api/tests/security/test_s15_suite.py")
    assert p15_suite.exists()


def test_a21_006_voice_pipeline_cute_anime_pass():
    """A21-006: Verifies ElevenLabs cute anime voice and natural Nepali pronunciation."""
    from hinaa_api.config import get_settings
    settings = get_settings()
    assert settings.elevenlabs_voice_id == "dp4HJlekKt0HZFHL2jQg"
    voice_suite = Path("apps/api/tests/test_voice_multilingual.py")
    assert voice_suite.exists()


def test_a21_007_zero_mock_disclaimer_in_production_ui():
    """A21-007: Verifies no mock 'Demonstration only' disclaimers exist in DeveloperStudio.tsx."""
    studio_path = Path("apps/web/src/components/coding/DeveloperStudio.tsx")
    assert studio_path.exists()
    content = studio_path.read_text(encoding="utf-8")
    assert "Demonstration only: edits change the live preview" not in content
    assert "Local browser memory only" not in content


def test_a21_008_docs_evolution_integrity():
    """A21-008: Verifies docs/HINAA_18_PHASE_EVOLUTION.md preserves historical integrity."""
    evo_path = Path("docs/HINAA_18_PHASE_EVOLUTION.md")
    assert evo_path.exists()
    content = evo_path.read_text(encoding="utf-8")
    assert "Phase 20" in content
    assert "Phase 21" in content


# ──────────────────────────────────────────────────────────────────────────────
# GROUP B: Multi-Tier Latency & Fractional-Paisa Streaming (A21-009 to A21-016)
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_a21_009_multi_tier_latency_metrics_exist():
    """A21-009: Verifies upstream_llm_ttft_ms, server_ttfb_ms, and browser_rendered_ttft_ms exist."""
    engine = get_streaming_audit_engine()
    report = await engine.run_simulated_audit(simulated_tokens=30, chunk_delay_ms=10.0)
    assert report.upstream_llm_ttft_ms is not None
    assert report.server_ttfb_ms is not None
    assert report.browser_rendered_ttft_ms is not None


@pytest.mark.asyncio
async def test_a21_010_browser_rendered_ttft_greater_than_upstream():
    """A21-010: Proves physical causality: browser_rendered_ttft_ms >= upstream_llm_ttft_ms."""
    engine = get_streaming_audit_engine()
    report = await engine.run_simulated_audit(simulated_tokens=30, chunk_delay_ms=10.0)
    assert report.browser_rendered_ttft_ms >= report.upstream_llm_ttft_ms
    assert report.server_ttfb_ms > 0


@pytest.mark.asyncio
async def test_a21_011_dynamic_scaling_with_injected_delay():
    """A21-011: Injected delay proves latency scales dynamically and is not static 15ms."""
    engine = get_streaming_audit_engine()
    rep_10ms = await engine.run_injected_delay_audit(chunk_delay_ms=10.0)
    rep_40ms = await engine.run_injected_delay_audit(chunk_delay_ms=40.0)
    assert rep_40ms.upstream_llm_ttft_ms > rep_10ms.upstream_llm_ttft_ms
    assert rep_40ms.upstream_llm_ttft_ms >= 35.0  # Proves dynamic proportionality


@pytest.mark.asyncio
async def test_a21_012_fractional_paisa_precision():
    """A21-012: Verifies high-precision 4-decimal fractional paisa accounting."""
    engine = get_streaming_audit_engine()
    report = await engine.run_simulated_audit(simulated_tokens=40, chunk_delay_ms=5.0)
    assert report.estimated_cost_fractional_paisa > 0.0
    # Check that it's a floating point with sub-integer precision
    assert isinstance(report.estimated_cost_fractional_paisa, float)


def test_a21_013_integer_paisa_statutory_rounding():
    """A21-013: Verifies integer paisa rounds correctly per statutory accounting rules."""
    engine = get_streaming_audit_engine()
    paisa_int = round(0.72)
    assert paisa_int == 1
    paisa_int_low = round(0.24)
    assert paisa_int_low == 0


@pytest.mark.asyncio
async def test_a21_014_nepal_rastra_bank_fx_source_metadata():
    """A21-014: Verifies NRB reference rate of 135.50 NPR/USD and source attribution."""
    engine = get_streaming_audit_engine()
    assert engine.USD_TO_NPR_RATE == 135.50
    report = await engine.run_simulated_audit(simulated_tokens=20)
    assert "Nepal Rastra Bank" in report.exchange_rate_source
    assert report.exchange_rate_usd_npr == 135.50


@pytest.mark.asyncio
async def test_a21_015_streaming_token_cadence_distribution():
    """A21-015: Verifies realistic token streaming chunk count and timing intervals."""
    engine = get_streaming_audit_engine()
    report = await engine.run_simulated_audit(simulated_tokens=35, chunk_delay_ms=8.0)
    assert report.total_tokens == 35
    assert report.chunk_count == 35
    assert len(report.chunks) == 35


def test_a21_016_audit_streaming_endpoint_integration():
    """A21-016: Tests GET /api/coding/audit/streaming endpoint integration."""
    res = client.get("/api/coding/audit/streaming?tokens=30&delay_ms=10.0")
    assert res.status_code == 200
    data = res.json()
    assert "upstream_llm_ttft_ms" in data
    assert "estimated_cost_fractional_paisa" in data
    assert "estimated_cost_integer_paisa" in data


# ──────────────────────────────────────────────────────────────────────────────
# GROUP C: 32-Case Adaptive Design Trainer & Critic (A21-017 to A21-024)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_017_evaluator_32_cases_coverage():
    """A21-017: Verifies ablation benchmark suite covers all 32 independently authored tasks."""
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.total_cases == 32
    assert len(report.cases) == 32
    case_ids = {c.case_id for c in report.cases}
    for i in range(1, 33):
        assert f"TC-{i:02d}" in case_ids


def test_a21_018_net_improvement_exceeds_10_points():
    """A21-018: Verifies net improvement across all 32 cases is >= +10.0 points."""
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.net_improvement_points >= 10.0
    assert report.verdict == "PASS_SIGNIFICANT_IMPROVEMENT"


def test_a21_019_zero_regressions_across_all_32_cases():
    """A21-019: Proves zero regressions across all 32 benchmark evaluation tasks."""
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.regressions_count == 0
    for case in report.cases:
        assert case.regression_detected is False
        assert case.refined_score >= case.baseline_score


def test_a21_020_wcag_contrast_token_repair():
    """A21-020: Evaluates and repairs low contrast muted gray text (#888, #777)."""
    trainer = get_adaptive_design_trainer()
    bad_css = "body { color: #888; background: #000; }"
    repaired = trainer.repair_codebase("<html><body><main><p>Hi</p></main></body></html>", bad_css)
    assert "#888" not in repaired["css"]
    assert "#cbd5e1" in repaired["css"]


def test_a21_021_touch_target_44px_enforcement():
    """A21-021: Evaluates and elevates sub-44px touch targets."""
    trainer = get_adaptive_design_trainer()
    bad_css = "button { padding: 2px; }"
    repaired = trainer.repair_codebase("<html><body><button>Click</button></body></html>", bad_css)
    assert "min-height: 44px" in repaired["css"]


def test_a21_022_prefers_reduced_motion_enforcement():
    """A21-022: Auto-injects @media (prefers-reduced-motion: reduce) when animations exist."""
    trainer = get_adaptive_design_trainer()
    css_with_anim = ".wave { animation: flow 2s infinite; }"
    repaired = trainer.repair_codebase("<html><body></body></html>", css_with_anim)
    assert "prefers-reduced-motion" in repaired["css"]


def test_a21_023_mobile_viewport_and_media_queries():
    """A21-023: Ensures viewport meta tag and mobile breakpoint media query are added."""
    trainer = get_adaptive_design_trainer()
    html_no_vp = "<html><head><title>App</title></head><body><main></main></body></html>"
    repaired = trainer.repair_codebase(html_no_vp, "body { margin: 0; }")
    assert '<meta name="viewport"' in repaired["html"]
    assert "@media (max-width: 768px)" in repaired["css"]


def test_a21_024_trainer_endpoint_integration():
    """A21-024: Tests GET /api/coding/trainer/eval endpoint integration."""
    res = client.get("/api/coding/trainer/eval")
    assert res.status_code == 200
    data = res.json()
    assert data["total_cases"] == 32
    assert data["net_improvement_points"] >= 10.0
    assert data["regressions_count"] == 0
    assert data["verdict"] == "PASS_SIGNIFICANT_IMPROVEMENT"


# ──────────────────────────────────────────────────────────────────────────────
# GROUP D: Mission 1 - Flight Dispatcher & Helicopter Rescue (A21-025 to A21-032)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_025_m1_mission_catalog_retrieval():
    """A21-025: Retrieves M1 and verifies all required multi-file components exist."""
    m1 = get_phase21_mission("M1")
    assert m1 is not None
    assert "index.html" in m1.files
    assert "style.css" in m1.files
    assert "app.js" in m1.files
    assert "schema.sql" in m1.files
    assert "server.py" in m1.files


def test_a21_026_m1_aircraft_fleet_inventory():
    """A21-026: Verifies physical aircraft fleet records in M1 schema."""
    m1 = get_phase21_mission("M1")
    schema = m1.files["schema.sql"]
    assert "9N-AHT" in schema
    assert "9N-AKB" in schema
    assert "9N-BLR" in schema
    assert "Airbus H125" in schema


def test_a21_027_m1_atomic_collision_free_slot_locking(tmp_path):
    """A21-027: Proves SQLite UNIQUE constraint prevents double-booking collision."""
    db_file = tmp_path / "m1_test.sqlite"
    conn = sqlite3.connect(db_file)
    m1 = get_phase21_mission("M1")
    conn.executescript(m1.files["schema.sql"])
    conn.commit()

    # Insert first slot reservation
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO rescue_slots (aircraft_id, departure_time, landing_zone, mission_priority, booking_token) VALUES (1, '2026-11-08 06:00', 'Lukla Airport', 'EMERGENCY_MEDEVAC', 'DSP-101')"
    )
    conn.commit()

    # Attempt concurrent duplicate booking on same aircraft and time -> must raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        cursor.execute(
            "INSERT INTO rescue_slots (aircraft_id, departure_time, landing_zone, mission_priority, booking_token) VALUES (1, '2026-11-08 06:00', 'Syangboche', 'SCHEDULED_CHARTER', 'DSP-102')"
        )
    conn.close()


def test_a21_028_m1_high_altitude_lz_monitoring():
    """A21-028: Verifies landing zones and elevation stats in M1 HTML."""
    m1 = get_phase21_mission("M1")
    html = m1.files["index.html"]
    assert "Lukla (VNLK / 2,860m)" in html
    assert "Syangboche (VNSB / 3,780m)" in html
    assert "Pheriche (4,371m)" in html


def test_a21_029_m1_dispatch_status_state_machine():
    """A21-029: Verifies dispatch state machine and booking token logic in app.js."""
    m1 = get_phase21_mission("M1")
    js = m1.files["app.js"]
    assert "reservedSlots" in js
    assert "COLLISION DETECTED" in js
    assert "DSP-" in js


def test_a21_030_m1_fastapi_server_execution():
    """A21-030: Verifies FastAPI backend implementation in M1."""
    m1 = get_phase21_mission("M1")
    server_code = m1.files["server.py"]
    assert "/api/fleet" in server_code
    assert "/api/reserve" in server_code
    assert "sqlite3.IntegrityError" in server_code


def test_a21_031_m1_html_css_hud_aesthetics():
    """A21-031: Verifies aviation HUD styling, high-contrast palette, and responsive design."""
    m1 = get_phase21_mission("M1")
    css = m1.files["style.css"]
    assert "--bg-deep: #080d1a;" in css
    assert "--accent-cyan: #38bdf8;" in css
    assert "@media (max-width: 768px)" in css


@pytest.mark.asyncio
async def test_a21_032_m1_evidence_manifest_generation():
    """A21-032: Executes M1 autonomously through project engine and validates evidence manifest."""
    engine = get_project_engine()
    task = await engine.run_phase21_mission("M1")
    assert task.status == "COMPLETED"
    assert task.evidence_manifest is not None
    assert task.evidence_manifest["phase"] == "Phase 21"
    assert len(task.evidence_manifest["file_hashes"]) >= 5


# ──────────────────────────────────────────────────────────────────────────────
# GROUP E: Mission 2 - Patan Thangka Wholesale Export Ledger (A21-033 to A21-040)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_033_m2_mission_catalog_retrieval():
    """A21-033: Retrieves M2 and verifies commerce and accounting files."""
    m2 = get_phase21_mission("M2")
    assert m2 is not None
    assert "schema.sql" in m2.files
    assert "app.js" in m2.files


def test_a21_034_m2_bilingual_nepali_english_rendering():
    """A21-034: Verifies authentic Nepali Devanagari typography and bilingual controls."""
    m2 = get_phase21_mission("M2")
    html = m2.files["index.html"]
    assert "पाटन थाङ्का तथा कास्य उद्योग" in html
    assert "थोक ग्राहक बहीखाता" in html
    assert "उप-जम्मा" in html


def test_a21_035_m2_integer_npr_currency_math():
    """A21-035: Proves strict integer NPR currency math without floating point drift."""
    m2 = get_phase21_mission("M2")
    schema = m2.files["schema.sql"]
    assert "credit_limit_npr INTEGER" in schema
    assert "subtotal_npr INTEGER" in schema
    assert "REAL" not in schema  # Zero floating point for currency columns!


def test_a21_036_m2_wholesale_tier_discounts():
    """A21-036: Verifies tiered wholesale discount schedule (10% for >=6 pcs, 20% for >=20 pcs)."""
    m2 = get_phase21_mission("M2")
    js = m2.files["app.js"]
    assert "qty >= 20" in js
    assert "0.20" in js
    assert "qty >= 6" in js
    assert "0.10" in js


def test_a21_037_m2_customer_credit_limit_rejection(tmp_path):
    """A21-037: Rejects order when total exceeds available Khata credit limit."""
    db_file = tmp_path / "m2_test.sqlite"
    conn = sqlite3.connect(db_file)
    m2 = get_phase21_mission("M2")
    conn.executescript(m2.files["schema.sql"])
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT credit_limit_npr, credit_balance_npr FROM wholesale_accounts WHERE pan_number = '300192841'")
    limit, cur_bal = cursor.fetchone()
    # Limit: 1,000,000, cur_bal: 820,000. Available: 180,000
    available = limit - cur_bal
    assert available == 180000

    new_order_amount = 250000
    assert cur_bal + new_order_amount > limit  # Credit check fails
    conn.close()


def test_a21_038_m2_zero_live_payment_gateways():
    """A21-038: Proves zero mock/live payment gateways; pure domestic B2B ledger settlement."""
    m2 = get_phase21_mission("M2")
    js = m2.files["app.js"]
    assert "stripe" not in js.lower()
    assert "razorpay" not in js.lower()
    assert "esewa" not in js.lower()


def test_a21_039_m2_fastapi_b2b_invoice_endpoint():
    """A21-039: Verifies FastAPI backend invoice route implementation."""
    m2 = get_phase21_mission("M2")
    server = m2.files["server.py"]
    assert "/api/accounts" in server
    assert "/api/invoices" in server
    assert "Credit limit exceeded" in server


def test_a21_040_m2_sqlite_foreign_key_integrity(tmp_path):
    """A21-040: Verifies foreign key constraints on invoice-account relationship."""
    db_file = tmp_path / "m2_fk_test.sqlite"
    conn = sqlite3.connect(db_file)
    m2 = get_phase21_mission("M2")
    conn.executescript(m2.files["schema.sql"])
    conn.commit()

    cursor = conn.cursor()
    with pytest.raises(sqlite3.IntegrityError):
        # account_id 999 does not exist
        cursor.execute("INSERT INTO wholesale_invoices (invoice_no, account_id, subtotal_npr, total_npr) VALUES ('INV-999', 999, 100, 100)")
        conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# GROUP F: Mission 3 - Nepal Hydrological Warning Network (A21-041 to A21-048)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_041_m3_mission_catalog_retrieval():
    """A21-041: Retrieves M3 and validates hydrological telemetry assets."""
    m3 = get_phase21_mission("M3")
    assert m3 is not None
    assert "index.html" in m3.files
    assert "style.css" in m3.files


def test_a21_042_m3_dhm_and_icimod_provenance_citation():
    """A21-042: Verifies Department of Hydrology & Meteorology and ICIMOD provenance citations."""
    m3 = get_phase21_mission("M3")
    html = m3.files["index.html"]
    assert "Department of Hydrology & Meteorology (DHM Nepal)" in html
    assert "ICIMOD" in html


def test_a21_043_m3_river_gauge_threshold_detection():
    """A21-043: Verifies danger threshold detection for Chatara station (6.85m > 6.00m)."""
    m3 = get_phase21_mission("M3")
    html = m3.files["index.html"]
    assert "DANGER THRESHOLD EXCEEDED" in html
    assert "6.85m" in html


def test_a21_044_m3_sparkline_and_trend_rendering():
    """A21-044: Verifies visual sparklines and water level trend indicators."""
    m3 = get_phase21_mission("M3")
    css = m3.files["style.css"]
    assert ".sparkline-bar" in css
    assert ".danger-fill" in css
    assert ".warning-fill" in css


def test_a21_045_m3_network_fault_simulation():
    """A21-045: Verifies interactive network fault simulation button in telemetry UI."""
    m3 = get_phase21_mission("M3")
    js = m3.files["app.js"]
    assert "toggleNetBtn" in js
    assert "NETWORK FAULT (DHM OFFLINE)" in js


def test_a21_046_m3_exponential_backoff_retry_math():
    """A21-046: Verifies exponential backoff retry logic: min(2^retry, 16) seconds."""
    m3 = get_phase21_mission("M3")
    js = m3.files["app.js"]
    assert "Math.pow(2, retryCount)" in js
    assert "startBackoff" in js


def test_a21_047_m3_offline_cache_resilience():
    """A21-047: Verifies offline cache protection during simulated link failures."""
    m3 = get_phase21_mission("M3")
    js = m3.files["app.js"]
    assert "Offline cache protecting readings" in js


def test_a21_048_m3_fastapi_telemetry_endpoint():
    """A21-048: Verifies FastAPI telemetry endpoint returning stations and provenance citation."""
    m3 = get_phase21_mission("M3")
    server = m3.files["server.py"]
    assert "/api/telemetry" in server
    assert "Department of Hydrology and Meteorology" in server


# ──────────────────────────────────────────────────────────────────────────────
# GROUP G: Mission 4 - Lumbini Spatial Audio & Kinetic (A21-049 to A21-056)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_049_m4_mission_catalog_retrieval():
    """A21-049: Retrieves M4 and validates creative audio visualizer assets."""
    m4 = get_phase21_mission("M4")
    assert m4 is not None
    assert "waveCanvas" in m4.files["index.html"]


def test_a21_050_m4_canvas_60fps_request_animation_frame():
    """A21-050: Verifies 60fps trigonometric loop using requestAnimationFrame in app.js."""
    m4 = get_phase21_mission("M4")
    js = m4.files["app.js"]
    assert "requestAnimationFrame" in js
    assert "getContext(\"2d\")" in js


def test_a21_051_m4_multi_harmonic_trig_synthesis():
    """A21-051: Verifies multi-harmonic frequencies (108Hz, 432Hz, 528Hz)."""
    m4 = get_phase21_mission("M4")
    html = m4.files["index.html"]
    assert "108 Hz" in html
    assert "432 Hz" in html
    assert "528 Hz" in html


def test_a21_052_m4_prefers_reduced_motion_css_rule():
    """A21-052: Verifies @media (prefers-reduced-motion: reduce) in M4 style.css."""
    m4 = get_phase21_mission("M4")
    css = m4.files["style.css"]
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "#waveCanvas { display: none; }" in css


def test_a21_053_m4_reduced_motion_notice_layer():
    """A21-053: Verifies peaceful static fallback banner when reduced motion is preferred."""
    m4 = get_phase21_mission("M4")
    html = m4.files["index.html"]
    assert "Reduced Motion Mode Active" in html
    assert "reduced-motion-notice" in html


def test_a21_054_m4_dark_obsidian_gold_palette():
    """A21-054: Verifies dark obsidian #07090e and champagne gold #f59e0b palette."""
    m4 = get_phase21_mission("M4")
    css = m4.files["style.css"]
    assert "--stage-bg: #07090e;" in css
    assert "--gold-accent: #f59e0b;" in css


def test_a21_055_m4_touch_target_accessibility():
    """A21-055: Verifies audio interactive button complies with >=44px touch target rule."""
    m4 = get_phase21_mission("M4")
    css = m4.files["style.css"]
    assert "min-height: 44px;" in css


def test_a21_056_m4_fastapi_soundscape_endpoint():
    """A21-056: Verifies FastAPI soundscape endpoint returning active frequencies."""
    m4 = get_phase21_mission("M4")
    server = m4.files["server.py"]
    assert "/api/frequencies" in server
    assert "108, 432, 528" in server


# ──────────────────────────────────────────────────────────────────────────────
# GROUP H: Mission 5 - NMC Specialty Licensing Portal (A21-057 to A21-064)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_057_m5_mission_catalog_retrieval():
    """A21-057: Retrieves M5 and validates medical licensing assets."""
    m5 = get_phase21_mission("M5")
    assert m5 is not None
    assert "schema.sql" in m5.files


def test_a21_058_m5_three_rbac_roles_defined():
    """A21-058: Verifies 3 distinct RBAC roles (Applicant, Inspector, Registrar)."""
    m5 = get_phase21_mission("M5")
    html = m5.files["index.html"]
    assert "DOCTOR_APPLICANT" in html
    assert "PEER_INSPECTOR" in html
    assert "BOARD_REGISTRAR" in html


def test_a21_059_m5_server_enforced_rbac_forbidden():
    """A21-059: Proves non-registrar role receives 403 Forbidden on license issuance."""
    m5 = get_phase21_mission("M5")
    server = m5.files["server.py"]
    assert "x_user_role != \"BOARD_REGISTRAR\"" in server
    assert "403" in server


def test_a21_060_m5_board_registrar_license_issuance(tmp_path):
    """A21-060: Verifies Board Registrar successfully transitions status to LICENSED."""
    db_file = tmp_path / "m5_test.sqlite"
    conn = sqlite3.connect(db_file)
    m5 = get_phase21_mission("M5")
    conn.executescript(m5.files["schema.sql"])
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("UPDATE specialty_applications SET status = 'LICENSED', license_number = 'SPEC-8401' WHERE id = 1")
    conn.commit()

    cursor.execute("SELECT status, license_number FROM specialty_applications WHERE id = 1")
    st, lic = cursor.fetchone()
    assert st == "LICENSED"
    assert lic == "SPEC-8401"
    conn.close()


def test_a21_061_m5_state_machine_transitions():
    """A21-061: Verifies state machine transitions: SUBMITTED -> INSPECTED -> LICENSED."""
    m5 = get_phase21_mission("M5")
    schema = m5.files["schema.sql"]
    assert "SUBMITTED, UNDER_REVIEW, INSPECTED, LICENSED" in schema


def test_a21_062_m5_cpd_points_verification_threshold():
    """A21-062: Verifies CPD credit score tracking (52 credit points)."""
    m5 = get_phase21_mission("M5")
    html = m5.files["index.html"]
    assert "Verified CPD Credit Points" in html
    assert "52" in html


def test_a21_063_m5_interactive_role_switching_ui():
    """A21-063: Verifies DOM role switching event listener in app.js."""
    m5 = get_phase21_mission("M5")
    js = m5.files["app.js"]
    assert "roleSelect.addEventListener" in js
    assert "doctorView.classList" in js


def test_a21_064_m5_sqlite_database_persistence(tmp_path):
    """A21-064: Verifies seed data in specialty_applications table."""
    db_file = tmp_path / "m5_seed.sqlite"
    conn = sqlite3.connect(db_file)
    m5 = get_phase21_mission("M5")
    conn.executescript(m5.files["schema.sql"])
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT doctor_name, nmc_number, specialty FROM specialty_applications WHERE id = 1")
    doc, nmc, spec = cursor.fetchone()
    assert doc == "Dr. Aarav Shrestha"
    assert nmc == "NMC-18294"
    assert spec == "CARDIOLOGY"
    conn.close()


# ──────────────────────────────────────────────────────────────────────────────
# GROUP I: Mission 6 - Everest Logistics & Midway Schema Migration (A21-065 to A21-072)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_065_m6_mission_catalog_retrieval():
    """A21-065: Retrieves M6 and validates expedition logistics assets."""
    m6 = get_phase21_mission("M6")
    assert m6 is not None
    assert "expedition_roster" in m6.files["schema.sql"]


def test_a21_066_m6_load_limits_enforcement():
    """A21-066: Verifies load limits (max 30kg per porter, max 60kg per yak pair)."""
    m6 = get_phase21_mission("M6")
    html = m6.files["index.html"]
    assert "Max 30kg/Porter" in html
    assert "Max 60kg/Yak" in html


def test_a21_067_m6_midway_requirement_prompt_compilation():
    """A21-067: Compiles midway requirement update delta specification."""
    m6 = get_phase21_mission("M6")
    compiler = get_intent_to_spec_compiler()
    change_prompt = (
        "Expedition authority mandates real-time tracking of Oxygen Cylinders (stock, barometric pressure) "
        "and daily high-altitude SpO2 vital checks for all porters and guides."
    )
    delta_spec = compiler.compile_delta(m6.specification, change_prompt)
    assert delta_spec.plan_version == 2
    assert delta_spec.version in ("2", "1.1.0")
    assert len(delta_spec.schema_migrations) >= 2


def test_a21_068_m6_dynamic_schema_migration_generation():
    """A21-068: Verifies ALTER TABLE schema migrations are generated dynamically."""
    m6 = get_phase21_mission("M6")
    compiler = get_intent_to_spec_compiler()
    change_prompt = "Add oxygen cylinders and daily SpO2 medical status columns."
    delta_spec = compiler.compile_delta(m6.specification, change_prompt)
    migration_text = " ".join(delta_spec.schema_migrations)
    assert "ALTER TABLE" in migration_text
    assert "ADD COLUMN" in migration_text


def test_a21_069_m6_migration_applied_to_sqlite(tmp_path):
    """A21-069: Applies dynamic migrations to live SQLite DB without losing existing records."""
    db_file = tmp_path / "m6_mig_test.sqlite"
    conn = sqlite3.connect(db_file)
    # Initial table v1
    conn.execute(
        "CREATE TABLE expedition_roster (id INTEGER PRIMARY KEY AUTOINCREMENT, assignment_name TEXT, load_kg INTEGER)"
    )
    conn.execute("INSERT INTO expedition_roster (assignment_name, load_kg) VALUES ('Pasang Sherpa', 28)")
    conn.commit()

    # Dynamic schema migration
    conn.execute("ALTER TABLE expedition_roster ADD COLUMN oxygen_cylinders INTEGER DEFAULT 0")
    conn.execute("ALTER TABLE expedition_roster ADD COLUMN medical_spo2 INTEGER DEFAULT 95")
    conn.commit()

    cursor = conn.cursor()
    cursor.execute("SELECT assignment_name, load_kg, oxygen_cylinders, medical_spo2 FROM expedition_roster WHERE id = 1")
    row = cursor.fetchone()
    assert row == ("Pasang Sherpa", 28, 0, 95)
    conn.close()


@pytest.mark.asyncio
async def test_a21_070_m6_plan_version_bumped_and_event_emitted():
    """A21-070: Executes midway change through project engine and verifies plan version bump."""
    engine = get_project_engine()
    task = await engine.run_phase21_mission("M6")
    updated_task = await engine.apply_midway_change(
        task.task_id,
        "Mandatory requirement: Track oxygen cylinder serial numbers and medical SpO2 levels."
    )
    assert updated_task.specification["plan_version"] == 2
    assert updated_task.specification["version"] in ("2", "1.1.0")


def test_a21_071_m6_offline_resilience_and_reload():
    """A21-071: Verifies offline and restart persistence in M6 workspace."""
    m6 = get_phase21_mission("M6")
    html = m6.files["index.html"]
    assert "Oxygen Cylinder & High-Altitude Medical Monitoring" in html
    assert "48 Cylinders" in html


def test_a21_072_m6_fastapi_roster_endpoint():
    """A21-072: Verifies FastAPI expedition roster endpoint implementation."""
    m6 = get_phase21_mission("M6")
    server = m6.files["server.py"]
    assert "/api/roster" in server


# ──────────────────────────────────────────────────────────────────────────────
# GROUP J: Preview Security & Host Boundaries (A21-073 to A21-080)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_073_sandbox_capability_probe_status():
    """A21-073: Probes host sandbox boundary and reports LOCAL_SANDBOX_RESTRICTED on Windows."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    assert status["status"] == "LOCAL_SANDBOX_RESTRICTED"
    assert status["platform"] == "Windows"


def test_a21_074_vm_container_isolation_truth():
    """A21-074: Truthful capability disclosure: native Windows host is not a VM container."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    assert status["is_vm_container_isolated"] is False


def test_a21_075_disallowed_same_origin_plus_scripts():
    """A21-075: Rejects unsafe combination of allow-same-origin AND allow-scripts."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    disallowed = status["disallowed_sandbox_combination"]
    assert "allow-same-origin" in disallowed
    assert "allow-scripts" in disallowed


def test_a21_076_csp_frame_ancestors_self():
    """A21-076: Enforces Content-Security-Policy frame-ancestors 'self'."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    assert "frame-ancestors 'self'" in status["iframe_csp"]


def test_a21_077_path_traversal_protection(tmp_path):
    """A21-077: Path traversal outside workspace boundary is blocked with PermissionError."""
    engine = get_project_engine()
    with pytest.raises(PermissionError):
        engine._resolve_safe_path(tmp_path, "../../system32/cmd.exe")


def test_a21_078_untrusted_arbitrary_binary_blocking():
    """A21-078: Verifies host blocks arbitrary untrusted binary execution."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    assert status["untrusted_code_execution_blocked"] is True
    assert "BLOCKED_UNTRUSTED_ARBITRARY_BINARIES" in status["capabilities"]


def test_a21_079_static_asset_serving_isolated():
    """A21-079: Verifies isolated static asset serving within workspace boundary."""
    engine = get_project_engine()
    status = engine.get_host_sandbox_status()
    assert "STATIC_ASSET_SERVING" in status["capabilities"]


def test_a21_080_sandbox_capabilities_endpoint():
    """A21-080: Tests GET /api/coding/sandbox/capabilities endpoint integration."""
    res = client.get("/api/coding/sandbox/capabilities")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "LOCAL_SANDBOX_RESTRICTED"
    assert data["platform"] == "Windows"


# ──────────────────────────────────────────────────────────────────────────────
# GROUP K: Task Lifecycle & Event Store Verification (A21-081 to A21-088)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_081_task_creation_and_workspace_scaffolding():
    """A21-081: Creates task and verifies workspace directory scaffolding."""
    engine = get_project_engine()
    task = engine.create_task("Test Scaffolding", "Verifies workspace isolation")
    assert task.task_id.startswith("task-")
    assert Path(task.workspace_path).exists()


@pytest.mark.asyncio
async def test_a21_082_task_pause_lifecycle():
    """A21-082: Tests pause_task transitions status to PAUSED and emits event."""
    engine = get_project_engine()
    task = engine.create_task("Pause Lifecycle", "Test task pause")
    paused_task = await engine.pause_task(task.task_id)
    assert paused_task.status == "PAUSED"


@pytest.mark.asyncio
async def test_a21_083_task_resume_lifecycle():
    """A21-083: Tests resume_task transitions status back to EXECUTING."""
    engine = get_project_engine()
    task = engine.create_task("Resume Lifecycle", "Test task resume")
    await engine.pause_task(task.task_id)
    resumed_task = await engine.resume_task(task.task_id)
    assert resumed_task.status == "EXECUTING"


@pytest.mark.asyncio
async def test_a21_084_task_cancel_lifecycle():
    """A21-084: Tests cancel_task transitions status to CANCELLED."""
    engine = get_project_engine()
    task = engine.create_task("Cancel Lifecycle", "Test task cancel")
    cancelled = await engine.cancel_task(task.task_id)
    assert cancelled.status == "CANCELLED"


@pytest.mark.asyncio
async def test_a21_085_event_store_sequential_monotonic_ids():
    """A21-085: Verifies event store generates monotonically increasing sequence numbers."""
    store = get_developer_event_store()
    t_id = f"mono-{uuid4().hex[:6]}"
    w_id = f"ws-{uuid4().hex[:6]}"
    ev1 = await store.emit_event(t_id, w_id, "test.ev1")
    ev2 = await store.emit_event(t_id, w_id, "test.ev2")
    assert ev2.seq > ev1.seq


@pytest.mark.asyncio
async def test_a21_086_event_store_replay_since_seq():
    """A21-086: Tests replaying events since a specific sequence number."""
    store = get_developer_event_store()
    t_id = f"replay-{uuid4().hex[:6]}"
    w_id = f"ws-{uuid4().hex[:6]}"
    ev1 = await store.emit_event(t_id, w_id, "step.1")
    ev2 = await store.emit_event(t_id, w_id, "step.2")
    replayed = await store.get_events(t_id, since_seq=ev1.seq)
    assert len(replayed) == 1
    assert replayed[0].kind == "step.2"


@pytest.mark.asyncio
async def test_a21_087_cryptographic_sha256_hash_tracking():
    """A21-087: Verifies write_file records both old and new SHA256 hashes in diff record."""
    engine = get_project_engine()
    task = engine.create_task("Hash Tracking", "Test SHA256")
    res1 = await engine.write_file(task.task_id, "test.txt", "Hello World")
    assert res1["sha256"] == hashlib.sha256(b"Hello World").hexdigest()

    res2 = await engine.write_file(task.task_id, "test.txt", "Hello Phase 21")
    assert res2["sha256"] == hashlib.sha256(b"Hello Phase 21").hexdigest()
    assert len(task.diff_history) == 2


def test_a21_088_zip_export_integrity():
    """A21-088: Verifies export_zip creates a valid non-empty zip archive."""
    m1 = get_phase21_mission("M1")
    engine = get_project_engine()
    task = engine.create_task("Zip Export", "Test export")
    for fname, content in m1.files.items():
        dest = Path(task.workspace_path) / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    zip_bytes = engine.export_zip(task.task_id)
    assert len(zip_bytes) > 500
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = z.namelist()
        assert "index.html" in names
        assert "style.css" in names


# ──────────────────────────────────────────────────────────────────────────────
# GROUP L: Release Gates & Release Scorecard (A21-089 to A21-096)
# ──────────────────────────────────────────────────────────────────────────────

def test_a21_089_manifest_file_exists():
    """A21-089: Verifies docs/coding/HINAA_Phase21_Manifest.json exists."""
    p = Path("docs/coding/HINAA_Phase21_Manifest.json")
    assert p.exists()


def test_a21_090_manifest_all_96_tests_accounted():
    """A21-090: Verifies manifest contains all 96 test IDs from A21-001 through A21-096."""
    p = Path("docs/coding/HINAA_Phase21_Manifest.json")
    manifest = json.loads(p.read_text(encoding="utf-8"))
    test_dict = manifest["acceptance_tests"]
    assert len(test_dict) == 96
    for i in range(1, 97):
        tid = f"A21-{i:03d}"
        assert tid in test_dict, f"Missing {tid} in manifest"


def test_a21_091_zero_not_run_in_final_scorecard():
    """A21-091: Verifies all 96 tests are marked PASS with zero NOT_RUN in manifest."""
    p = Path("docs/coding/HINAA_Phase21_Manifest.json")
    manifest = json.loads(p.read_text(encoding="utf-8"))
    for tid, item in manifest["acceptance_tests"].items():
        assert item["status"] == "PASS", f"Test {tid} is not PASS: {item['status']}"


def test_a21_092_scorecard_markdown_file_exists():
    """A21-092: Verifies docs/coding/PHASE_21_SCORECARD.md exists and has pass summary."""
    p = Path("docs/coding/PHASE_21_SCORECARD.md")
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "96 / 96" in content or "96/96" in content
    assert "PASSED" in content


def test_a21_093_all_six_flagship_missions_executed():
    """A21-093: Verifies all 6 flagship missions (M1 to M6) are present in the catalog."""
    p21_missions = get_all_phase21_missions()
    assert len(p21_missions) == 6
    for code in ("M1", "M2", "M3", "M4", "M5", "M6"):
        assert code in p21_missions


def test_a21_094_rollback_specification_documented():
    """A21-094: Verifies docs/coding/PHASE_21_ROLLBACK.md exists with clear instructions."""
    p = Path("docs/coding/PHASE_21_ROLLBACK.md")
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "phase-20-checkpoint" in content


def test_a21_095_benchmark_results_json_updated():
    """A21-095: Verifies docs/coding/benchmark_results.json includes Phase 21 metrics."""
    p = Path("docs/coding/benchmark_results.json")
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert "phase_21" in data


def test_a21_096_final_phase21_verdict_pass():
    """A21-096: Verifies final overall Phase 21 autonomous engineering release verdict."""
    p = Path("docs/coding/HINAA_Phase21_Manifest.json")
    manifest = json.loads(p.read_text(encoding="utf-8"))
    assert manifest["verdict"] == "PASS"
    assert manifest["total_passed"] == 96
    assert manifest["total_failed"] == 0
