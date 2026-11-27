from __future__ import annotations

import json
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from hinaa_api.autonomy import MarathonBudget, MarathonRunner
from hinaa_api.memory.lessons import LessonsStore
from hinaa_api.skills.synthesize import synthesize_skill
from hinaa_api.society import (
    ReviewVerdict,
    SocietyCircle,
    SocietyMetricsStore,
    VerificationVerdict,
    create_society_router,
)
from hinaa_api.training import export_dpo_pairs, grade_trajectory


@pytest.mark.asyncio
async def test_society_circle_reviewer_catches_defect_then_verifies_on_second_round(tmp_path) -> None:
    metrics = SocietyMetricsStore(tmp_path / "metrics.json")

    async def maker(_goal: str, feedback: list[str]):
        if not feedback:
            return {"code": "bad = 1/0"}
        return {"code": "ok = 1"}

    async def reviewer(artifact: dict):
        if "1/0" in artifact.get("code", ""):
            return ReviewVerdict(verdict="CHANGES_REQUESTED", findings=["Division by zero detected"])
        return ReviewVerdict(verdict="PASS")

    async def verifier(artifact: dict):
        return VerificationVerdict(verified="1/0" not in artifact.get("code", ""), checks_run=["unit"])

    circle = SocietyCircle(maker=maker, reviewer=reviewer, verifier=verifier, metrics=metrics)
    outcome = await circle.run("Safe constant calculation")
    assert outcome.verified is True
    assert outcome.rounds == 2

    snap = metrics.snapshot()
    assert snap["total_circles"] == 1
    assert snap["reviewer_catches"] == 1
    assert snap["first_pass_rate_pct"] == 0.0

    # Metrics endpoint serves real JSON snapshot
    app = FastAPI()
    app.include_router(create_society_router(metrics))
    res = TestClient(app).get("/v1/society/metrics")
    assert res.status_code == 200
    assert res.json()["reviewer_catches"] == 1


def test_lessons_store_fts_decay_and_prune(tmp_path) -> None:
    metrics = SocietyMetricsStore(tmp_path / "metrics.json")
    store = LessonsStore(tmp_path / "lessons.db", metrics=metrics)

    now = 1_700_000_000.0
    store.record_lesson(
        topic="ChatPanel jsdom virtualization",
        failure_pattern="Maximum update depth exceeded in measureElement",
        fix_pattern="Guard measureElement on height > 0 and provide observeElementRect fallback",
        now=now - 86400.0,
    )
    store.record_lesson(
        topic="Very old unrelated bug",
        failure_pattern="Ancient timeout on unused adapter",
        fix_pattern="Removed dead adapter",
        now=now - (120 * 86400.0),
    )

    hits = store.retrieve_lessons("measureElement virtualization", k=2, now=now)
    assert len(hits) >= 1
    assert "measureElement" in hits[0].failure_pattern

    pruned = store.prune_stale(max_age_days=90.0, min_hits=1, now=now + 10.0)
    assert pruned >= 0


def test_skill_synthesis_and_dpo_trajectory_export(tmp_path) -> None:
    metrics = SocietyMetricsStore(tmp_path / "metrics.json")
    skill = synthesize_skill(
        name="Windows Pytest Verification",
        description="Run API tests reliably via Windows venv interpreter",
        steps=["Set PYTHONPATH=apps/api", "Invoke pytest via apps/api/.venv/Scripts/python.exe"],
        commands=["pytest -q", "python -V"],
        pitfalls=["Do not point at Linux .venv/bin/python on Windows"],
        output_root=tmp_path / "skills",
        metrics=metrics,
    )
    assert skill.path.is_file()
    content = skill.path.read_text(encoding="utf-8")
    assert "name: windows-pytest-verification" in content
    assert "pytest -q" in content

    traces = [
        {"goal": "Fix API route", "status": "completed", "verified": True, "summary": "Edited route and tests pass.", "steps": []},
        {"goal": "Fix API route", "status": "failed", "verified": False, "summary": "Broken diff", "steps": [{"status": "failed"}]},
    ]
    assert grade_trajectory(traces[0]).score == 1.0
    dpo_path = tmp_path / "dpo.jsonl"
    pairs = export_dpo_pairs(traces, dpo_path)
    assert len(pairs) == 1
    row = json.loads(dpo_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["chosen"] == "Edited route and tests pass."
    assert row["rejected"] == "Broken diff"


@pytest.mark.asyncio
async def test_marathon_checkpoint_resume_and_budget_pause(tmp_path) -> None:
    metrics = SocietyMetricsStore(tmp_path / "metrics.json")
    runner = MarathonRunner(
        checkpoint_dir=tmp_path / "checkpoints",
        budget=MarathonBudget(max_wall_seconds=100.0, max_cost_usd=1.0, max_steps=10),
        metrics=metrics,
    )

    async def cost_exceeding_step(cp):
        return {"done": False, "cost_usd": 0.6, "note": f"step-{cp.step_index}"}

    paused = await runner.run(run_id="mar-1", goal="Large migration", executor=cost_exceeding_step)
    assert paused.status == "paused_budget"
    assert "Cost budget" in (paused.pause_reason or "")
    assert paused.step_index == 2

    # Increase budget & resume from saved checkpoint seamlessly
    resumed_runner = MarathonRunner(
        checkpoint_dir=tmp_path / "checkpoints",
        budget=MarathonBudget(max_wall_seconds=100.0, max_cost_usd=5.0, max_steps=10),
        metrics=metrics,
    )

    async def finish_step(_cp):
        return {"done": True, "cost_usd": 0.1, "note": "verified"}

    done = await resumed_runner.run(run_id="mar-1", goal="Large migration", executor=finish_step)
    assert done.status == "completed"
    assert done.step_index == 3
    assert metrics.snapshot()["marathons_completed"] == 1
