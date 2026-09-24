from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from hinaa_api.main import create_app
from hinaa_api.config import get_settings


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app, headers={"X-HINAA-Dev-User": "image-fabric-test-user"})


def test_asset_upload_and_retrieve_lifecycle(client: TestClient):
    """Test POST /v1/assets and GET /v1/assets/{asset_id}/file."""
    # 1x1 transparent PNG
    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    
    response = client.post(
        "/v1/assets",
        files={"file": ("test_avatar.png", io.BytesIO(png_bytes), "image/png")},
    )
    assert response.status_code == 201
    data = response.json()
    assert "asset_id" in data
    assert "url" in data
    asset_id = data["asset_id"]

    # Retrieve file
    get_res = client.get(f"/v1/assets/{asset_id}/file")
    assert get_res.status_code == 200
    assert get_res.headers["content-type"].startswith("image/png")
    assert get_res.content == png_bytes


def test_turns_stream_with_asset_attachment(client: TestClient):
    """Test POST /v1/conversations/turns:stream accepts attachment_ids and imageUrl without 422."""
    payload = {
        "sessionId": "session_test_multimodal",
        "text": "Check this image attachment",
        "imageUrl": "http://127.0.0.1:8000/v1/assets/test_id/file",
        "attachment_ids": ["test_asset_123"],
        "providerMode": "mock",
    }
    response = client.post(
        "/v1/conversations/turns:stream",
        json=payload,
    )
    # Must not be 422 Unprocessable Entity
    assert response.status_code == 200
    assert "application/x-ndjson" in response.headers.get("content-type", "")


def test_tool_execute_image_upscale_and_relight(client: TestClient, monkeypatch):
    """Test POST /v1/tools/execute forwards attachments to image_upscale and image_relight."""
    from hinaa_api.tools.image_fabric import image_fabric
    monkeypatch.setattr(type(image_fabric.magnific), "is_configured", property(lambda self: False))

    png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    upload_res = client.post(
        "/v1/assets",
        files={"file": ("input.png", io.BytesIO(png_bytes), "image/png")},
    )
    asset_id = upload_res.json()["asset_id"]

    # Upscale execution
    upscale_payload = {
        "toolName": "image_upscale",
        "parameters": {"scale": 2},
        "attachment_ids": [asset_id],
        "confirmed": True,
        "approvalSource": "user",
    }
    up_res = client.post("/v1/tools/execute", json=upscale_payload)
    assert up_res.status_code == 200
    up_data = up_res.json()
    assert up_data.get("status") == "success"
    up_inner = up_data["data"]["data"] if isinstance(up_data.get("data"), dict) and "data" in up_data["data"] else up_data.get("data", {})
    assert "asset_id" in up_inner
    assert "url" in up_inner

    # Relight execution
    relight_payload = {
        "toolName": "image_relight",
        "parameters": {"lighting_prompt": "golden hour sunset"},
        "attachment_ids": [asset_id],
        "confirmed": True,
        "approvalSource": "user",
    }
    rl_res = client.post("/v1/tools/execute", json=relight_payload)
    assert rl_res.status_code == 200
    rl_data = rl_res.json()
    assert rl_data.get("status") == "success"
    rl_inner = rl_data["data"]["data"] if isinstance(rl_data.get("data"), dict) and "data" in rl_data["data"] else rl_data.get("data", {})
    assert "asset_id" in rl_inner


def test_resolve_upscale_follows_mode_and_setting(monkeypatch):
    """The flag /image reports must be the pass run_image_job actually performs."""
    from hinaa_api.tools import image_generate as tool

    def params(mode: str, upscale=None):
        return tool.ImageGenerateParams(prompt="a lantern-lit harbour", mode=mode, upscale=upscale)

    monkeypatch.setattr(tool.settings, "magnific_upscale_default", True, raising=False)
    assert tool.resolve_upscale(params("quality")) is True
    assert tool.resolve_upscale(params("ultra")) is True
    assert tool.resolve_upscale(params("fast")) is False
    assert tool.resolve_upscale(params("quality", upscale=False)) is False
    assert tool.resolve_upscale(params("fast", upscale=True)) is True

    monkeypatch.setattr(tool.settings, "magnific_upscale_default", False, raising=False)
    assert tool.resolve_upscale(params("quality")) is False
    assert tool.resolve_upscale(params("ultra")) is True
