from __future__ import annotations

from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.creative import CreativeModelRegistry, MagnificBudgetManager
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app


def test_creative_registry_canonical_pricing():
    m1 = CreativeModelRegistry.get_model("classic-fast")
    assert m1.cost_credits == 1
    assert m1.tier == "economy"

    m5 = CreativeModelRegistry.get_model("classic")
    assert m5.cost_credits == 5

    m_flux_fast = CreativeModelRegistry.get_model("flux-fast")
    assert m_flux_fast.cost_credits == 5

    m_flux_std = CreativeModelRegistry.get_model("flux-1")
    assert m_flux_std.cost_credits == 10

    m_mystic = CreativeModelRegistry.get_model("mystic-2.5")
    assert m_mystic.cost_credits == 50

    models = CreativeModelRegistry.list_models()
    assert len(models) >= 8


def test_strict_video_ban_in_registry():
    with pytest.raises(HinaaError) as exc_info:
        CreativeModelRegistry.get_model("runway-gen3-video")
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "VIDEO_GENERATION_FORBIDDEN"

    with pytest.raises(HinaaError) as exc_info:
        CreativeModelRegistry.recommend_model("render short video clip")
    assert exc_info.value.status_code == 403


def test_budget_manager_dynamic_daily_pacing():
    settings = Settings(
        HINAA_ENV="dev",
        MAGNIFIC_MONTHLY_PLAN_CREDITS=45000,
        MAGNIFIC_BILLING_CYCLE_ANCHOR_DAY=3,
    )
    bm = MagnificBudgetManager(settings=settings)

    # Test anchor day bounds
    test_now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
    start, end, days_left = bm.get_billing_cycle_bounds(test_now)
    assert start == datetime(2026, 9, 3, 0, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 10, 3, 0, 0, 0, tzinfo=timezone.utc)
    assert days_left == 23

    status = bm.get_budget_status()
    assert status["planCredits"] == 45000
    assert status["anchorDay"] == 3
    assert status["dailyPace"] > 1000
    assert status["videoGenerationEnabled"] is False

    # Test pacing modes
    rec_early = CreativeModelRegistry.recommend_model("create hero concept", pacing_mode="economy")
    assert rec_early.id in ("classic-fast", "flux-fast")

    rec_late = CreativeModelRegistry.recommend_model("render final art", pacing_mode="use-it-wisely")
    assert rec_late.id == "mystic-2.5"


def test_creative_rest_endpoints(client: TestClient):
    resp = client.get("/v1/creative/budget")
    assert resp.status_code == 200
    data = resp.json()
    assert data["planCredits"] == 45000
    assert "dailyPace" in data
    assert data["videoGenerationEnabled"] is False

    # Snapshot endpoint
    snap = client.post("/v1/creative/budget/snapshot", json={"balance": 38000})
    assert snap.status_code == 200
    assert snap.json()["effectiveRemaining"] == 38000

    # Models endpoint
    models_resp = client.get("/v1/creative/models")
    assert models_resp.status_code == 200
    assert any(m["id"] == "mystic-2.5" and m["costCredits"] == 50 for m in models_resp.json())

    # Video ban
    video_resp = client.post("/v1/creative/jobs", json={"prompt": "test video", "model": "video-ai"})
    assert video_resp.status_code == 403
    assert video_resp.json()["code"] == "VIDEO_GENERATION_FORBIDDEN"