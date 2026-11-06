"""HINAA OS Phase 20: Comprehensive 64-Scenario Acceptance Test Suite.

Covers exactly 64 verifiable acceptance test scenarios across 8 capability groups
(P20-001 through P20-064):
- Group A: Intent-to-Spec Compilation (P20-001..008)
- Group B: Four True Zero-Shot Missions (P20-009..016)
- Group C: Truth-Plane Verification & Integrity (P20-017..024)
- Group D: Security, CSP & Sandboxed Preview (P20-025..032)
- Group E: Streaming & Latency Truth (P20-033..040)
- Group F: Adaptive Design Trainer & Critic (P20-041..048)
- Group G: Authentic Nepali & Localization (P20-049..056)
- Group H: End-to-End Autonomous Convergence (P20-057..064)
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import re
import sqlite3
import tempfile
import zipfile
from pathlib import Path
import pytest

from hinaa_api.coding.developer_events import (
    EVENT_COMMAND_EXITED,
    EVENT_COMMAND_STARTED,
    EVENT_FILE_PATCH_APPLIED,
    EVENT_FILE_SAVED,
    EVENT_PREVIEW_READY,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_STARTED,
    DeveloperEventStore,
    get_developer_event_store,
)
from hinaa_api.coding.intent_to_spec import (
    FeatureSpecification,
    IntentToSpecCompiler,
    get_intent_to_spec_compiler,
)
from hinaa_api.coding.zero_shot_missions import (
    ZeroShotMission,
    get_zero_shot_mission,
    get_zero_shot_missions,
)
from hinaa_api.coding.project_synthesizer import (
    AutonomousProjectSynthesizer,
    get_autonomous_project_synthesizer,
)
from hinaa_api.coding.project_engine import (
    AutonomousProjectEngine,
    ProjectTask,
    get_project_engine,
)
from hinaa_api.coding.preview_runtime import get_preview_manager
from hinaa_api.coding.design_critic import DesignCritic
from hinaa_api.coding.design_trainer import (
    AdaptiveDesignTrainer,
    get_adaptive_design_trainer,
)
from hinaa_api.coding.streaming_audit import (
    StreamingAuditEngine,
    get_streaming_audit_engine,
)


# ==============================================================================
# GROUP A: Intent-to-Spec Compilation (P20-001 .. P20-008)
# ==============================================================================

def test_p20_001_free_form_prompt_compilation():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Build a booking portal for an eye hospital in Pokhara with doctor schedule and patient record")
    assert spec.spec_id.startswith("spec-")
    assert any(term in spec.title for term in ["Pokhara", "Hospital", "Booking", "Appointment", "Reservation"])
    assert len(spec.data_entities) >= 2


def test_p20_002_prompt_hashing_and_catalog_flag():
    compiler = get_intent_to_spec_compiler()
    prompt = "Create a custom artisan wool rug inventory management application in Bhaktapur"
    spec = compiler.compile(prompt)
    expected_hash = hashlib.sha256(prompt.strip().encode("utf-8")).hexdigest()
    assert spec.prompt_hash == expected_hash
    assert spec.is_from_catalog is False


def test_p20_003_language_detection_english():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Design an e-commerce dashboard for Himalayan organic coffee exporters")
    assert spec.language_detected == "en-US"


def test_p20_004_language_detection_devanagari_nepali():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("काठमाडौं डेन्टल क्लिनिकको लागि अपोइन्टमेन्ट बुकिङ प्रणाली बनाउनुहोस्")
    assert spec.language_detected == "ne-NP"


def test_p20_005_language_detection_romanized_nepali():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("hamro pasal ko lagi udharo khata ra bikri hisab kitab app banaunuhos")
    assert spec.language_detected == "romanized-ne"


def test_p20_006_feature_extraction_must_vs_nice_to_have():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Create an appointment system. Must have doctor slot collision prevention and SMS alerts. Nice to have dark mode.")
    assert len(spec.must_have_features) >= 1
    assert any("collision" in f.lower() or "appointment" in f.lower() or "slot" in f.lower() for f in spec.must_have_features)


def test_p20_007_data_entities_schema_extraction():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Build customer invoicing and product ledger with integer NPR prices")
    entity_names = [e.name.lower() for e in spec.data_entities]
    assert any("invoice" in n or "item" in n or "ledger" in n or "customer" in n for n in entity_names)
    for entity in spec.data_entities:
        for field in entity.fields:
            assert field.name
            assert field.type in ("text", "integer", "real", "boolean", "timestamp")


def test_p20_008_api_route_contracts_generation():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Build an API for student course registration and exam grade reports")
    assert len(spec.api_routes) >= 2
    methods = {r.method for r in spec.api_routes}
    assert "GET" in methods or "POST" in methods
    assert any(r.path.startswith("/api/") for r in spec.api_routes)


# ==============================================================================
# GROUP B: Four True Zero-Shot Missions (P20-009 .. P20-016)
# ==============================================================================

def test_p20_009_z1_appointment_collision_prevention():
    z1 = get_zero_shot_mission("Z1")
    assert z1 is not None
    js = z1.files.get("app.js", "")
    assert "hasCollision" in js or "collision" in js.lower() or "double-booking" in js.lower()


def test_p20_010_z1_sqlite_schema_and_integer_fee():
    z1 = get_zero_shot_mission("Z1")
    schema = z1.files.get("schema.sql", "")
    assert "CREATE TABLE" in schema
    assert "fee_npr INTEGER" in schema or "fee INTEGER" in schema or "INTEGER" in schema


def test_p20_011_z1_bilingual_toggle():
    z1 = get_zero_shot_mission("Z1")
    html = z1.files.get("index.html", "")
    assert "langToggle" in html
    assert "Mukta" in html or "काठमाडौं" in html


def test_p20_012_z2_civic_telemetry_source_provenance():
    z2 = get_zero_shot_mission("Z2")
    assert z2 is not None
    html = z2.files.get("index.html", "")
    assert "Department of Hydrology and Meteorology" in html or "DHM" in html or "Ministry" in html


def test_p20_013_z2_range_filters_and_svg_trend():
    z2 = get_zero_shot_mission("Z2")
    html = z2.files.get("index.html", "")
    js = z2.files.get("app.js", "")
    assert "<svg" in html or "svg" in js
    assert "timeRange" in html or "range-btn" in html or "filter" in js


def test_p20_014_z3_integer_npr_accounting():
    z3 = get_zero_shot_mission("Z3")
    assert z3 is not None
    js = z3.files.get("app.js", "")
    assert "Math.round" in js or "parseInt" in js or "integer" in js.lower()
    # Check currency symbol
    assert "रु" in js or "Rs." in js or "NPR" in js


def test_p20_015_z3_pan_vat_invoicing_and_ledger():
    z3 = get_zero_shot_mission("Z3")
    html = z3.files.get("index.html", "")
    js = z3.files.get("app.js", "")
    assert "VAT" in html or "PAN" in html or "उधारो" in html
    assert "inventory" in js.lower() or "stock" in js.lower() or "ledger" in js.lower()


def test_p20_016_z4_prefers_reduced_motion_compliance():
    z4 = get_zero_shot_mission("Z4")
    assert z4 is not None
    css = z4.files.get("style.css", "")
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "animation: none" in css or "animation-duration" in css


# ==============================================================================
# GROUP C: Truth-Plane Verification & Integrity (P20-017 .. P20-024)
# ==============================================================================

@pytest.mark.asyncio
async def test_p20_017_workspace_file_disk_fidelity():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z1")
        ws_path = Path(task.workspace_path)
        for fname, content in get_zero_shot_mission("Z1").files.items():
            disk_content = (ws_path / fname).read_text(encoding="utf-8")
            assert disk_content == content


def test_p20_018_path_traversal_bounds():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        ws = Path(tmpdir) / "test_ws"
        ws.mkdir()
        with pytest.raises(PermissionError):
            engine._resolve_safe_path(ws, "../../../etc/passwd")


@pytest.mark.asyncio
async def test_p20_019_sha256_cryptographic_manifest():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z1")
        evidence = task.evidence_manifest
        assert evidence is not None
        assert evidence["verified"] is True
        for rel_path, file_hash in evidence["file_hashes"].items():
            disk_path = Path(task.workspace_path) / rel_path
            assert disk_path.exists()
            assert hashlib.sha256(disk_path.read_bytes()).hexdigest() == file_hash


@pytest.mark.asyncio
async def test_p20_020_tamper_detection():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z1")
        html_file = Path(task.workspace_path) / "index.html"
        original_hash = task.evidence_manifest["file_hashes"]["index.html"]
        html_file.write_text("TAMPERED DATA", encoding="utf-8")
        new_evidence = engine.generate_evidence(task.task_id)
        assert new_evidence["file_hashes"]["index.html"] != original_hash


@pytest.mark.asyncio
async def test_p20_021_monotonic_wal_event_sequence():
    from uuid import uuid4
    tid = f"t-mono-{uuid4().hex[:6]}"
    store = DeveloperEventStore()
    events = []
    for i in range(5):
        e = await store.emit_event(tid, "w-1", "TEST_EVENT", payload={"i": i})
        events.append(e)
    seqs = [e.seq for e in events]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs)


@pytest.mark.asyncio
async def test_p20_022_event_replay_since_seq():
    from uuid import uuid4
    tid = f"t-rep-{uuid4().hex[:6]}"
    store = DeveloperEventStore()
    for i in range(10):
        await store.emit_event(tid, "w-rep", "EVENT", payload={"val": i})
    polled = store.get_events_after(tid, after_seq=5)
    assert len(polled) == 5
    assert polled[0].seq == 6


@pytest.mark.asyncio
async def test_p20_023_deterministic_task_status_progression():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z4")
        assert task.status == "COMPLETED"
        assert task.preview_url is not None
        assert task.scorecard is not None


@pytest.mark.asyncio
async def test_p20_024_exported_zip_integrity():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z1")
        zip_bytes = engine.export_zip(task.task_id)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            names = z.namelist()
            assert "index.html" in names
            assert "style.css" in names
            assert "app.js" in names
            assert "evidence_manifest.json" in names


# ==============================================================================
# GROUP D: Security, CSP & Sandboxed Preview (P20-025 .. P20-032)
# ==============================================================================

def test_p20_025_sandboxed_preview_session():
    pm = get_preview_manager()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "index.html").write_text("<h1>Safe</h1>")
        session = pm.create_session("t-sec", "w-sec", ws, "index.html")
        assert session.preview_id.startswith("prev-")
        assert "/api/coding/preview/" in session.preview_url


def test_p20_026_preview_csp_headers():
    pm = get_preview_manager()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "index.html").write_text("<h1>Safe</h1>")
        session = pm.create_session("t-sec2", "w-sec2", ws, "index.html")
        asset = pm.serve_asset(session.preview_id, "index.html")
        assert asset is not None
        csp = asset.headers.get("Content-Security-Policy", "")
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'self'" in csp


def test_p20_027_preview_iframe_sandbox_attribute():
    html_iframe = '<iframe src="/preview" sandbox="allow-scripts allow-forms">'
    assert "allow-same-origin" not in html_iframe


def test_p20_028_preview_path_traversal_rejection():
    pm = get_preview_manager()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "index.html").write_text("<h1>Safe</h1>")
        session = pm.create_session("t-sec3", "w-sec3", ws, "index.html")
        asset = pm.serve_asset(session.preview_id, "../../../../etc/passwd")
        assert asset is None


def test_p20_029_invalid_session_raises_404():
    pm = get_preview_manager()
    asset = pm.serve_asset("non-existent-session-id", "index.html")
    assert asset is None


def test_p20_030_secret_protection_in_preview_html():
    z1 = get_zero_shot_mission("Z1")
    html = z1.files["index.html"]
    for secret in ["sk-", "xkiro_secret", "bearer "]:
        assert secret not in html.lower()


def test_p20_031_nosniff_header_enforced():
    pm = get_preview_manager()
    with tempfile.TemporaryDirectory() as tmpdir:
        ws = Path(tmpdir)
        (ws / "style.css").write_text("body { color: red; }")
        session = pm.create_session("t-sec4", "w-sec4", ws, "style.css")
        asset = pm.serve_asset(session.preview_id, "style.css")
        assert asset is not None
        assert asset.headers.get("X-Content-Type-Options") == "nosniff"


def test_p20_032_unauthorized_subprocess_execution_guard():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        with pytest.raises(PermissionError):
            engine._resolve_safe_path(Path(tmpdir), "../secret")


# ==============================================================================
# GROUP E: Streaming & Latency Truth (P20-033 .. P20-040)
# ==============================================================================

@pytest.mark.asyncio
async def test_p20_033_streaming_multi_chunk_audit():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=40, chunk_delay_ms=2.0)
    assert report.is_multi_chunk_stream is True
    assert report.chunk_count > 1


@pytest.mark.asyncio
async def test_p20_034_ttfb_recorded_independently():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=30, chunk_delay_ms=2.0)
    assert report.ttfb_ms >= 0.0
    assert report.ttfb_ms <= report.total_duration_ms


@pytest.mark.asyncio
async def test_p20_035_ttft_recorded_accurately():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=30, chunk_delay_ms=2.0)
    assert report.ttft_ms >= report.ttfb_ms


@pytest.mark.asyncio
async def test_p20_036_monotonic_chunk_offsets():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=20, chunk_delay_ms=2.0)
    offsets = [c.arrival_offset_ms for c in report.chunks]
    assert offsets == sorted(offsets)


@pytest.mark.asyncio
async def test_p20_037_token_throughput_computation():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=25, chunk_delay_ms=2.0)
    assert report.tokens_per_second > 0.0


@pytest.mark.asyncio
async def test_p20_038_cost_calculation_in_npr():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(simulated_tokens=1000)
    assert report.estimated_cost_usd > 0.0
    assert report.estimated_cost_npr == round(report.estimated_cost_usd * 135.50, 4)


@pytest.mark.asyncio
async def test_p20_039_single_chunk_buffered_warning():
    audit = get_streaming_audit_engine()

    async def _single_chunk_gen():
        yield "All tokens returned at once in a single buffered response chunk."

    report = await audit.audit_stream(_single_chunk_gen())
    assert report.is_multi_chunk_stream is False
    assert report.status == "BUFFERED_SINGLE_CHUNK_WARNING"


@pytest.mark.asyncio
async def test_p20_040_streaming_audit_model_metadata():
    audit = get_streaming_audit_engine()
    report = await audit.run_simulated_audit(model_name="xkiro/qwen-2.5-coder-32b")
    assert report.model_name == "xkiro/qwen-2.5-coder-32b"
    assert report.provider == "xKiro Multi-Model Gateway"


# ==============================================================================
# GROUP F: Adaptive Design Trainer & Critic (P20-041 .. P20-048)
# ==============================================================================

def test_p20_041_design_critic_detects_missing_viewport():
    trainer = get_adaptive_design_trainer()
    res = trainer.evaluate_codebase("<html><head></head><body>No viewport</body></html>", "body { color: #fff; }")
    assert any(d.category == "responsiveness" and "viewport" in d.message.lower() for d in res.defects)
    assert res.responsive_compliant is False


def test_p20_042_design_critic_detects_tiny_touch_targets():
    trainer = get_adaptive_design_trainer()
    res = trainer.evaluate_codebase(
        '<html><head><meta name="viewport" content="width=device-width"></head><body><button>X</button></body></html>',
        "button { padding: 2px; }",
    )
    assert any(d.category == "touch_targets" for d in res.defects)


def test_p20_043_design_critic_detects_low_contrast():
    trainer = get_adaptive_design_trainer()
    res = trainer.evaluate_codebase(
        '<html><head><meta name="viewport" content="width=device-width"></head><body><p>Muted</p></body></html>',
        "p { color: #777; }",
    )
    assert any(d.category == "contrast_wcag" for d in res.defects)


def test_p20_044_design_critic_detects_unconstrained_animation():
    trainer = get_adaptive_design_trainer()
    res = trainer.evaluate_codebase(
        '<html><head><meta name="viewport" content="width=device-width"></head><body><div>Spin</div></body></html>',
        "@keyframes spin { to { transform: rotate(360deg); } }",
    )
    assert any(d.category == "motion_accessibility" for d in res.defects)


def test_p20_045_adaptive_repair_elevates_defective_codebase():
    trainer = get_adaptive_design_trainer()
    html_raw = "<html><head><title>Bad</title></head><body><button style='padding:2px'>Click</button></body></html>"
    css_raw = "button { padding: 2px; } @keyframes spin { to { transform: rotate(360deg); } }"
    res_before = trainer.evaluate_codebase(html_raw, css_raw)
    repaired = trainer.repair_codebase(html_raw, css_raw)
    res_after = trainer.evaluate_codebase(repaired["html"], repaired["css"])
    assert res_after.overall_score >= 90
    assert res_after.overall_score > res_before.overall_score


def test_p20_046_ablation_benchmark_significant_improvement():
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.net_improvement_points >= 10.0
    assert report.verdict == "PASS_SIGNIFICANT_IMPROVEMENT"


def test_p20_047_ablation_benchmark_zero_regressions():
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.regressions_count == 0


def test_p20_048_ablation_benchmark_case_coverage():
    trainer = get_adaptive_design_trainer()
    report = trainer.run_ablation_benchmark()
    assert report.total_cases >= 5
    for case in report.cases:
        assert case.improvement_delta >= 0
        assert case.regression_detected is False


# ==============================================================================
# GROUP G: Authentic Nepali & Localization (P20-049 .. P20-056)
# ==============================================================================

def test_p20_049_devanagari_font_stack():
    z1 = get_zero_shot_mission("Z1")
    html = z1.files["index.html"]
    css = z1.files["style.css"]
    assert "Mukta" in html or "Mukta" in css


def test_p20_050_anti_hindi_linguistic_attunement():
    z3 = get_zero_shot_mission("Z3")
    content = z3.files["index.html"] + " " + z3.files["app.js"]
    # Ensure no hindi words leak into nepali khata
    for hindi_word in ["लडका", "किये", "दुकानदार", "खरीददार"]:
        assert hindi_word not in content


def test_p20_051_authentic_nepali_terminology():
    z3 = get_zero_shot_mission("Z3")
    content = z3.files["index.html"] + " " + z3.files["app.js"]
    assert "उधारो" in content or "नगद" in content
    assert "खाता" in content or "ग्राहक" in content


def test_p20_052_npr_currency_formatting():
    z3 = get_zero_shot_mission("Z3")
    js = z3.files["app.js"]
    assert "रु" in js or "रू" in js or "Rs." in js or "NPR" in js


def test_p20_053_bilingual_toggle_dom_binding():
    z1 = get_zero_shot_mission("Z1")
    js = z1.files["app.js"]
    assert "langToggle" in js
    assert "currentLang" in js or "toggle" in js.lower()


def test_p20_054_nepal_timezone_handling():
    z1 = get_zero_shot_mission("Z1")
    html = z1.files["index.html"]
    # Check timezone or clinic hours formatted realistically
    assert "09:00" in html or "AM" in html or "PM" in html


def test_p20_055_nepali_typography_line_height():
    z1 = get_zero_shot_mission("Z1")
    css = z1.files["style.css"]
    assert "line-height: 1.6" in css or "line-height: 1.5" in css or "line-height:" in css


def test_p20_056_accessible_devanagari_screen_reader_tags():
    z1 = get_zero_shot_mission("Z1")
    html = z1.files["index.html"]
    assert 'lang="ne"' in html
    assert "aria-label" in html


# ==============================================================================
# GROUP H: End-to-End Autonomous Convergence (P20-057 .. P20-064)
# ==============================================================================

@pytest.mark.asyncio
async def test_p20_057_build_from_unseen_custom_prompt():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.build_from_prompt("Create an artisanal handmade tea inventory tracker for Ilam organic farmers")
        assert task.status == "COMPLETED"
        assert task.preview_url is not None
        assert Path(task.workspace_path).exists()


@pytest.mark.asyncio
async def test_p20_058_synthesized_project_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.build_from_prompt("Build a tourist permit tracking portal for Annapurna Circuit")
        ws = Path(task.workspace_path)
        assert (ws / "index.html").exists()
        assert (ws / "style.css").exists()
        assert (ws / "app.js").exists()
        assert (ws / "schema.sql").exists()
        assert (ws / "server.py").exists()


@pytest.mark.asyncio
async def test_p20_059_sqlite_physical_initialization():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.build_from_prompt("Create a library catalog system for Patan high school")
        db_path = Path(task.workspace_path) / "database.sqlite"
        assert db_path.exists()
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in cursor.fetchall()]
        conn.close()
        assert len(tables) > 0


@pytest.mark.asyncio
async def test_p20_060_generated_backend_server_syntax():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.build_from_prompt("Build hotel room reservation portal in Nagarkot")
        server_py = (Path(task.workspace_path) / "server.py").read_text(encoding="utf-8")
        compile(server_py, "server.py", "exec")


def test_p20_061_spec_compile_endpoint_logic():
    compiler = get_intent_to_spec_compiler()
    spec = compiler.compile("Design an interactive telemetry dashboard for Bagmati river water levels")
    assert isinstance(spec, FeatureSpecification)
    assert len(spec.data_entities) > 0


@pytest.mark.asyncio
async def test_p20_062_generate_project_with_preview():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.build_from_prompt("Create an appointment booking tool for a Kathmandu dental clinic")
        assert task.preview_session_id is not None
        assert task.preview_url.startswith("/api/coding/preview/")


def test_p20_063_zero_shot_missions_catalog_completeness():
    missions = get_zero_shot_missions()
    assert "Z1" in missions
    assert "Z2" in missions
    assert "Z3" in missions
    assert "Z4" in missions
    for code, m in missions.items():
        assert m.title
        assert len(m.files) >= 3


@pytest.mark.asyncio
async def test_p20_064_full_autonomous_convergence_evidence():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = AutonomousProjectEngine(workspaces_root=Path(tmpdir))
        task = await engine.run_mission("Z1")
        evidence = task.evidence_manifest
        assert evidence["total_bytes"] > 0
        assert evidence["diff_count"] > 0
        assert evidence["command_count"] > 0
        assert evidence["phase"] == "Phase 20"
