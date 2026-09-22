import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from hinaa_api.config import Settings
from hinaa_api.creative.registry import CreativeModelRegistry
from hinaa_api.creative.flows import inspect_flow_safety, APPROVED_CANONICAL_FLOWS
from hinaa_api.creative.budget_manager import MagnificBudgetManager
from hinaa_api.persistence.auth import resolve_auth
from hinaa_api.persistence.memory_service import MemoryService
from hinaa_api.errors import HinaaError
from hinaa_api.main import create_app


def test_dynamic_tool_costs():
    """Verify upscaler and relight have dynamic cost schemas and compute dynamically."""
    upscaler = CreativeModelRegistry.get_model("upscale-2x")
    assert upscaler.cost_type == "dynamic"
    assert upscaler.requires_cost_calculation is True

    relight = CreativeModelRegistry.get_model("relight")
    assert relight.cost_type == "dynamic"
    assert relight.requires_cost_calculation is True

    # Test dynamic upscale calculation: 1024x1024 at 2x = 2048x2048 = 4.19 MP * 5 = ~20 credits
    credits = CreativeModelRegistry.calculate_upscale_credits(1024, 1024, 2.0)
    assert credits >= 20


def test_flow_video_node_rejection():
    """Verify deep graph inspection detects and blocks any flow with video nodes."""
    safe_flow = {
        "id": "portrait-clean",
        "name": "Portrait Polish",
        "nodes": [
            {"name": "Crop", "type": "crop", "operator": "crop"},
            {"name": "Upscale", "type": "upscale", "operator": "upscale_2x"},
        ],
    }
    is_safe, _ = inspect_flow_safety(safe_flow)
    assert is_safe is True

    # Disguised video node inside innocent-looking flow
    toxic_flow = {
        "id": "brand-campaign",
        "name": "Brand Campaign Generator",
        "nodes": [
            {"name": "Copywriter", "type": "text", "operator": "generate"},
            {"name": "Secret Animate", "type": "video_gen", "operator": "animate_portrait", "model": "gen-3"},
        ],
    }
    is_safe, reason = inspect_flow_safety(toxic_flow)
    assert is_safe is False
    assert "video" in reason.lower()


def test_magnific_honest_status_when_key_missing():
    """Verify budget manager honestly reports KEY_MISSING when key is empty."""
    settings = Settings(
        MAGNIFIC_API_KEY=None,
        FREEPIK_API_KEY=None,
        MAGNIFIC_MONTHLY_PLAN_CREDITS=45000,
        MAGNIFIC_BILLING_CYCLE_ANCHOR_DAY=3,
    )
    mgr = MagnificBudgetManager(settings=settings)
    status = mgr.get_budget_status()

    assert status["configured"] is False
    assert status["state"] == "KEY_MISSING"
    assert status["liveVerified"] is False
    assert "not configured" in status["statusMessage"].lower()


def test_single_owner_auth_gate():
    """Verify HINAA_ALLOWED_USER_IDS blocks non-owners with HTTP 403."""
    from unittest.mock import MagicMock
    mock_memory = MagicMock(spec=MemoryService)
    mock_user = MagicMock()
    mock_user.id = "user_owner_1"
    mock_memory.ensure_user.return_value = mock_user

    # Settings with owner restricted to 'owner_hinaa'
    settings = Settings(
        HINAA_AUTH_MODE="dev",
        HINAA_ALLOWED_USER_IDS="owner_hinaa,backup_admin",
    )
    # A local caller: resolve_auth reads the Host to tell this off the internet.
    mock_req = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/v1/privacy/memories",
            "headers": [(b"host", b"127.0.0.1:8000")],
        }
    )

    # Authorized user should succeed
    auth = resolve_auth(mock_req, settings, mock_memory, x_hinaa_dev_user="owner_hinaa")
    assert auth.auth_subject == "owner_hinaa"

    # Unauthorized user must receive HTTP 403
    with pytest.raises(HinaaError) as exc_info:
        resolve_auth(mock_req, settings, mock_memory, x_hinaa_dev_user="imposter_user")
    assert exc_info.value.status_code == 403
    assert "not authorized" in str(exc_info.value.message).lower()


def test_video_rejection_zero_call_assertion(monkeypatch):
    """Verify video generation attempts are rejected locally with HTTP 403 and exactly 0 upstream network calls."""
    from unittest.mock import AsyncMock
    import httpx
    from hinaa_api.creative.magnific_client import MagnificClient

    mock_post = AsyncMock()
    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)

    client = MagnificClient()

    # 1. Attempt submitting video model
    import asyncio
    with pytest.raises(HinaaError) as exc_info:
        asyncio.run(client.submit_image_job(prompt="Anime walking video", model_id="kling-video"))
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "VIDEO_GENERATION_FORBIDDEN"

    # 2. Strict assertion: zero network calls reached the provider
    assert mock_post.call_count == 0


def test_dynamic_estimate_endpoint():
    """Verify /v1/creative/estimate calculates dynamic cost and returns calculated_estimate."""
    app = create_app()
    client = TestClient(app)

    # Fixed model estimate
    resp_fixed = client.get("/v1/creative/estimate?model=classic-fast")
    assert resp_fixed.status_code == 200
    data_fixed = resp_fixed.json()
    assert data_fixed["modelId"] == "classic-fast"
    assert data_fixed["costCredits"] == 1
    assert data_fixed["costSource"] == "fixed"

    # Dynamic upscale estimate: 1024x1024 at 2.0x scale -> 2048x2048 = 4.19 MP * 5 = 20 credits
    resp_dynamic = client.post(
        "/v1/creative/estimate",
        json={"model": "upscale-2x", "width": 1024, "height": 1024, "scale": 2.0},
    )
    assert resp_dynamic.status_code == 200
    data_dynamic = resp_dynamic.json()
    assert data_dynamic["modelId"] == "upscale-2x"
    assert data_dynamic["costCredits"] >= 20
    assert data_dynamic["costSource"] == "calculated_estimate"
    assert data_dynamic["costType"] == "dynamic"
    assert data_dynamic["outputResolution"] == "2048x2048"


def test_magnific_ready_status_when_live_verified():
    """Verify budget manager reports READY and liveVerified=True once verified."""
    from pydantic import SecretStr

    settings = Settings(
        MAGNIFIC_API_KEY=SecretStr("mock_valid_key_12345"),
        MAGNIFIC_MONTHLY_PLAN_CREDITS=45000,
        MAGNIFIC_BILLING_CYCLE_ANCHOR_DAY=3,
    )
    mgr = MagnificBudgetManager(settings=settings)
    # Before live verification
    s1 = mgr.get_budget_status()
    assert s1["configured"] is True
    assert s1["liveVerified"] is False
    assert s1["state"] == "ACTIVE"

    # Mark live verified
    mgr.mark_live_verified(True)
    s2 = mgr.get_budget_status()
    assert s2["configured"] is True
    assert s2["liveVerified"] is True
    assert s2["state"] == "READY"
    assert "ready for creative workloads" in s2["statusMessage"]