"""Phase 19 Flagship Missions Verification Suite.

Runs end-to-end execution of primary flagship missions:
- MISSION-01: Nexa+ Creative Studio SaaS
- MISSION-02: Apex Financial Telemetry Dashboard
- MISSION-06: Mitho Mandu Culinary Studio (Bilingual English/Nepali)
"""

from __future__ import annotations

import pytest
from pathlib import Path
from hinaa_api.coding.project_engine import AutonomousProjectEngine
from hinaa_api.coding.flagship_catalog import get_flagship_catalog


@pytest.mark.asyncio
@pytest.mark.parametrize("mission_id", ["MISSION-01", "MISSION-02", "MISSION-06"])
async def test_flagship_mission_execution(mission_id: str):
    """Executes flagship mission and asserts design critique score >= 85 and file creation."""
    engine = AutonomousProjectEngine()
    task = await engine.run_mission(mission_id)

    assert task.status == "COMPLETED"
    assert task.scorecard is not None
    assert task.scorecard["overall_score"] >= 85, f"Mission {mission_id} score below threshold: {task.scorecard['overall_score']}"

    # Verify files created on disk
    ws_path = Path(task.workspace_path)
    assert (ws_path / "index.html").exists()
    assert (ws_path / "style.css").exists()
    assert (ws_path / "app.js").exists()

    # Verify preview session and URL
    assert task.preview_session_id is not None
    assert task.preview_url.startswith("/api/coding/preview/")

    # Verify diff history
    assert len(task.diff_history) >= 3

    # Verify evidence manifest
    evidence = engine.generate_evidence(task.task_id)
    assert evidence["verified"] is True
    assert len(evidence["file_hashes"]) >= 3
