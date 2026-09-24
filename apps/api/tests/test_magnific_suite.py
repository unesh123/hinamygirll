from __future__ import annotations

import pytest
from hinaa_api.errors import HinaaError
from hinaa_api.tools.freepik_suite import (
    assert_no_video_generation,
    usage_tracker,
    _handle_video_blocked,
)
from hinaa_api.tools.registry import registry


def test_video_generation_strictly_prohibited():
    """Verify video generation is rejected across all actions with HTTP 403."""
    for action in ["video_generate", "text_to_video", "image_to_video", "generate video of girl", "animate this image"]:
        with pytest.raises(HinaaError) as exc_info:
            assert_no_video_generation(action)
        assert exc_info.value.code == "CAPABILITY_DISABLED"
        assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_video_tool_registry_handler_blocked():
    """Verify executing the video_generate tool directly in registry fails with 403."""
    handler = registry._handlers["video_generate"]
    with pytest.raises(HinaaError) as exc_info:
        await handler({"prompt": "cinematic anime video"})
    assert exc_info.value.code == "CAPABILITY_DISABLED"
    assert exc_info.value.status_code == 403


def test_magnific_tools_registered():
    """Verify Magnific and Freepik image tools are registered."""
    tool_names = [t.name for t in registry.get_all_tools()]
    assert "magnific_image_generate" in tool_names
    assert "freepik_image_generate" in tool_names
    assert "magnific_upscale" in tool_names
    assert "freepik_stock_search" in tool_names
    assert "video_generate" in tool_names


def test_usage_tracker_credit_accounting():
    """Verify credits and quota tracking work accurately."""
    summary = usage_tracker.get_summary()
    assert "dailyCredits" in summary
    assert "tierOptions" in summary
    assert summary["videoAllowed"] is False
    assert summary["videoCapabilityStatus"] == "HARD_DISABLED_PER_POLICY"

    has_quota, used, limit = usage_tracker.check_quota(credits_needed=1)
    assert isinstance(has_quota, bool)
    assert limit >= 100
