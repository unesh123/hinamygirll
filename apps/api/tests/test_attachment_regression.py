import pytest
from pydantic import ValidationError
from hinaa_api.models import TurnRequest, ToolExecutionRequest
from hinaa_api.providers.fabric import ModelRouter, TaskType


def test_turn_request_accepts_image_attachment():
    """REGRESSION TEST: TurnRequest must explicitly accept imageUrl and attachment_ids

    without throwing 422 or dropping them.
    """
    payload = {
        "sessionId": "session_123",
        "text": "use this image and make another version",
        "imageUrl": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "attachment_ids": ["asset_abc123"],
    }
    # This will fail before our fix because TurnRequest inherits StrictModel (extra='forbid')
    # and lacks imageUrl and attachment_ids fields!
    req = TurnRequest.model_validate(payload)
    assert req.imageUrl is not None
    assert req.attachment_ids == ["asset_abc123"]


def test_tool_execution_request_has_explicit_attachment_fields():
    """REGRESSION TEST: ToolExecutionRequest must explicitly declare attachment_ids

    and reference_images so FastAPI does not silently drop them under extra='ignore'.
    """
    payload = {
        "toolName": "image_generate",
        "parameters": {"prompt": "make her anime"},
        "attachment_ids": ["asset_1", "asset_2"],
        "reference_images": ["https://example.com/ref.png"],
    }
    req = ToolExecutionRequest.model_validate(payload)
    # Both must be preserved as accessible attributes
    assert hasattr(req, "attachment_ids")
    assert req.attachment_ids == ["asset_1", "asset_2"]
    assert hasattr(req, "reference_images")
    assert req.reference_images == ["https://example.com/ref.png"]


def test_model_router_uses_valid_extraction_model():
    """REGRESSION TEST: ModelRouter must select an existing model ID from Google catalog

    (gemini-3.5-flash-lite), NOT the non-existent gemini-3.6-flash-lite.
    """
    router = ModelRouter()
    selected = router.select_model(TaskType.EXTRACTION)
    assert selected == "gemini-3.5-flash-lite", f"Invalid model ID: {selected}"
