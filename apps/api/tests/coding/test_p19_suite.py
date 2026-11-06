"""Phase 19 Acceptance Test Suite: The Visible AI Developer.

Comprehensive verification of:
- Class U: Unbacked Progress Rejection & Disk Truthfulness
- Class I: Sandboxed Preview Runtime, CSP Containment & Traversal Protection
- Class E: Monotonic Event Streaming & WAL Cursor Resumption
- Class O: Objective Design Critic Quality & Nepali Cultural Fidelity
- Class H: Autonomous Self-Repair & Quality Convergence
- Class A: Cryptographic Evidence Manifest & ZIP Artifact Export
- Class R: Flagship Missions Catalog & Execution
"""

from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
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
    DeveloperEvent,
    DeveloperEventStore,
    get_developer_event_store,
)
from hinaa_api.coding.preview_runtime import PreviewRuntimeManager, get_preview_manager
from hinaa_api.coding.design_critic import DesignAuditScorecard, DesignCritic, DesignFinding
from hinaa_api.coding.flagship_catalog import (
    FLAGSHIP_MISSIONS,
    FlagshipMission,
    get_flagship_catalog,
    get_mission,
)
from hinaa_api.coding.project_engine import AutonomousProjectEngine, ProjectTask, get_project_engine


# ==============================================================================
# CLASS U: Unbacked Progress Rejection & Disk Truthfulness
# ==============================================================================

@pytest.mark.asyncio
async def test_u01_unbacked_progress_rejected():
    """Verify that every file recorded in events must genuinely exist on disk."""
    engine = AutonomousProjectEngine()
    task = engine.create_task("Test Task", "Verification task")
    ws_path = Path(task.workspace_path)

    # Write a genuine file
    res = await engine.write_file(task.task_id, "test.txt", "Genuine disk content")
    assert res["success"] is True

    # Confirm it exists on disk with matching content
    dest = ws_path / "test.txt"
    assert dest.exists()
    assert dest.read_text(encoding="utf-8") == "Genuine disk content"


@pytest.mark.asyncio
async def test_u02_workspace_tree_truthfulness():
    """Verify get_workspace_tree reflects exact files on disk."""
    engine = AutonomousProjectEngine()
    task = engine.create_task("Tree Task", "Tree test")
    
    await engine.write_file(task.task_id, "index.html", "<h1>Hello</h1>")
    await engine.write_file(task.task_id, "css/main.css", "body { margin: 0; }")

    tree = engine.get_workspace_tree(task.task_id)
    paths = [f["path"] for f in tree]
    assert "index.html" in paths
    assert "css/main.css" in paths


@pytest.mark.asyncio
async def test_u03_command_execution_records_real_metrics():
    """Verify commands record real timestamps and exit codes."""
    engine = AutonomousProjectEngine()
    task = await engine.run_mission("MISSION-01")
    assert len(task.command_history) > 0
    cmd = task.command_history[0]
    assert cmd["exit_code"] == 0
    assert "started_at" in cmd
    assert "finished_at" in cmd


# ==============================================================================
# CLASS I: Sandboxed Preview Runtime, CSP Containment & Traversal Protection
# ==============================================================================

def test_i01_preview_runtime_strict_csp():
    """Verify HTML assets are served with strict Content-Security-Policy headers."""
    pm = PreviewRuntimeManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.html").write_text("<!doctype html><html><head></head><body><h1>Preview</h1></body></html>")
        
        session = pm.create_session("task-123", "ws-123", root, "index.html")
        asset = pm.serve_asset(session.preview_id, "index.html")

        assert asset is not None
        assert asset.media_type == "text/html"
        assert "Content-Security-Policy" in asset.headers
        csp = asset.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'self'" in csp


def test_i02_preview_bridge_script_injected():
    """Verify hot-reload and error forwarding bridge script is injected into HTML."""
    pm = PreviewRuntimeManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.html").write_text("<!doctype html><html><head><title>Test</title></head><body></body></html>")
        
        session = pm.create_session("task-br", "ws-br", root, "index.html")
        asset = pm.serve_asset(session.preview_id, "index.html")

        html_out = asset.content_bytes.decode("utf-8")
        assert "window.__HINAA_PREVIEW_SESSION__" in html_out
        assert "hinaa:preview-error" in html_out


def test_i03_path_traversal_blocked():
    """Verify directory traversal attempts outside workspace root are blocked."""
    pm = PreviewRuntimeManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "index.html").write_text("<h1>Index</h1>")
        session = pm.create_session("task-trav", "ws-trav", root)

        # Attempt directory traversal attacks
        assert pm.serve_asset(session.preview_id, "../../../../etc/passwd") is None
        assert pm.serve_asset(session.preview_id, "..\\..\\Windows\\win.ini") is None
        assert pm.serve_asset(session.preview_id, "/etc/shadow") is None


def test_i04_correct_mimetypes_served():
    """Verify CSS, JS, SVG and JSON assets are served with accurate MIME types."""
    pm = PreviewRuntimeManager()
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "style.css").write_text("body { color: red; }")
        (root / "app.js").write_text("console.log('hi');")
        (root / "icon.svg").write_text("<svg></svg>")
        (root / "data.json").write_text('{"a": 1}')

        session = pm.create_session("task-mime", "ws-mime", root)
        
        css_asset = pm.serve_asset(session.preview_id, "style.css")
        assert css_asset.media_type == "text/css"

        js_asset = pm.serve_asset(session.preview_id, "app.js")
        assert "javascript" in js_asset.media_type

        svg_asset = pm.serve_asset(session.preview_id, "icon.svg")
        assert svg_asset.media_type == "image/svg+xml"

        json_asset = pm.serve_asset(session.preview_id, "data.json")
        assert json_asset.media_type == "application/json"


# ==============================================================================
# CLASS E: Monotonic Event Streaming & WAL Cursor Resumption
# ==============================================================================

@pytest.mark.asyncio
async def test_e01_monotonic_sequence_numbers():
    """Verify seq starts at 1 and increases monotonically without gaps."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "events.db"
        store = DeveloperEventStore(db_path=db_path)

        ev1 = await store.emit_event("t-mono", "ws-1", "task.started")
        ev2 = await store.emit_event("t-mono", "ws-1", "file.opened", file_path="index.html")
        ev3 = await store.emit_event("t-mono", "ws-1", "file.saved", file_path="index.html")

        assert ev1.seq == 1
        assert ev2.seq == 2
        assert ev3.seq == 3
        assert ev1.task_id == "t-mono"


@pytest.mark.asyncio
async def test_e02_wal_cursor_resumption_zero_loss():
    """Verify get_events_after correctly replays missed events from specified seq."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "events.db"
        store = DeveloperEventStore(db_path=db_path)

        for i in range(10):
            await store.emit_event("t-resume", "ws-1", f"event.{i}")

        # Request events after seq=4
        resumed = store.get_events_after("t-resume", after_seq=4)
        assert len(resumed) == 6
        assert resumed[0].seq == 5
        assert resumed[-1].seq == 10


@pytest.mark.asyncio
async def test_e03_pub_sub_realtime_broadcast():
    """Verify subscriber receives live events in real-time."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "events.db"
        store = DeveloperEventStore(db_path=db_path)

        queue = store.subscribe("t-pubsub")
        await store.emit_event("t-pubsub", "ws-1", "test.broadcast", payload={"message": "hello world"})

        event = await asyncio.wait_for(queue.get(), timeout=2.0)
        assert event.kind == "test.broadcast"
        assert event.payload["message"] == "hello world"
        store.unsubscribe("t-pubsub", queue)


# ==============================================================================
# CLASS O: Objective Design Critic Quality & Nepali Cultural Fidelity
# ==============================================================================

def test_o01_critic_scores_high_quality_design():
    """Verify a professional responsive design scores >= 85."""
    html = """<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1"><title>Studio</title></head>
    <body><main class="page"><nav aria-label="Main"><div class="logo">Acme</div><button aria-label="Menu">Menu</button></nav>
    <section class="hero"><h1>Exceptional Digital Experiences</h1><p>Crafted for ambitious global teams.</p><button>Get Started</button></section>
    </main></body></html>"""
    css = """
    :root { --primary: #0f172a; --accent: #0284c7; }
    body { font-family: 'Inter', sans-serif; color: #1e293b; background: #ffffff; }
    @media (max-width: 768px) { .hero { padding: 20px; } }
    @media (max-width: 390px) { h1 { font-size: 24px; } }
    """
    js = "document.addEventListener('DOMContentLoaded', () => { console.log('Ready'); });"

    card = DesignCritic.evaluate(html, css, js)
    assert card.overall_score >= 85
    assert card.layout_responsiveness >= 85
    assert card.accessibility_wcag >= 80


def test_o02_critic_catches_lorem_ipsum_violation():
    """Verify critic flags placeholder lorem-ipsum text with HIGH severity."""
    html = "<h1>Heading</h1><p>Lorem ipsum dolor sit amet, consectetur adipiscing elit.</p>"
    card = DesignCritic.evaluate(html, "", "")
    findings = [f for f in card.findings if "lorem" in f.title.lower() or f.rule_id in ("crit-cont-01", "CONTENT_ZERO_LOREM_IPSUM")]
    assert len(findings) > 0
    assert findings[0].severity in ("high", "HIGH")


def test_o03_critic_validates_nepali_cultural_fidelity():
    """Verify critic rewards authentic Devanagari script and NPR currency."""
    html = """<!doctype html><html lang="ne"><head><meta name="viewport" content="width=device-width,initial-scale=1"></head>
    <body><main><h1>मिठो मान्डु रेस्टुरेन्ट</h1><p>प्रामाणिक नेपाली स्वाद र हिमाली मसला। मूल्य: रु. ४५० (NPR)</p></main></body></html>"""
    css = "body { font-family: 'Mukta', 'Noto Sans Devanagari', sans-serif; } @media (max-width: 768px) { body { margin: 0; } }"
    
    card = DesignCritic.evaluate(html, css, "")
    assert card.nepali_cultural_fidelity >= 90


# ==============================================================================
# CLASS H: Autonomous Self-Repair & Quality Convergence
# ==============================================================================

@pytest.mark.asyncio
async def test_h01_autonomous_mission_self_repair_convergence():
    """Verify mission execution achieves >= 85 overall score after audit loop."""
    engine = AutonomousProjectEngine()
    task = await engine.run_mission("MISSION-01")
    assert task.status == "COMPLETED"
    assert task.scorecard is not None
    assert task.scorecard["overall_score"] >= 85


# ==============================================================================
# CLASS A: Cryptographic Evidence Manifest & ZIP Artifact Export
# ==============================================================================

@pytest.mark.asyncio
async def test_a01_cryptographic_evidence_manifest():
    """Verify evidence manifest generates SHA256 checksum for all files."""
    engine = AutonomousProjectEngine()
    task = await engine.run_mission("MISSION-01")
    
    evidence = engine.generate_evidence(task.task_id)
    assert evidence["verified"] is True
    assert "file_hashes" in evidence
    assert "index.html" in evidence["file_hashes"]
    assert len(evidence["file_hashes"]["index.html"]) == 64  # SHA256 length


@pytest.mark.asyncio
async def test_a02_zip_artifact_export_integrity():
    """Verify export_zip generates a valid decompressable ZIP archive."""
    engine = AutonomousProjectEngine()
    task = await engine.run_mission("MISSION-01")

    zip_bytes = engine.export_zip(task.task_id)
    assert len(zip_bytes) > 0

    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as z:
        names = z.namelist()
        assert "index.html" in names
        assert "style.css" in names
        assert "app.js" in names


# ==============================================================================
# CLASS R: Flagship Missions Catalog Verification
# ==============================================================================

def test_r01_flagship_catalog_completeness():
    """Verify all 12 flagship missions exist with complete files and metadata."""
    catalog = get_flagship_catalog()
    assert len(catalog) == 12

    required_missions = [
        "MISSION-01", "MISSION-02", "MISSION-03", "MISSION-04",
        "MISSION-05", "MISSION-06", "MISSION-07", "MISSION-08",
        "MISSION-09", "MISSION-10", "MISSION-11", "MISSION-12"
    ]
    for m_id in required_missions:
        assert m_id in catalog
        m = catalog[m_id]
        assert len(m.title) > 0
        assert "index.html" in m.files
        assert "style.css" in m.files
        assert "app.js" in m.files
