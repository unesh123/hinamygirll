"""Agent tool for publishing to social platforms. Irreversible, so it always needs the user's confirmation.

Two independent gates: the registry's `requires_confirmation` (checked by /v1/tools/execute) and
the handler, which only proceeds when that endpoint has marked the request as user-approved.
"""

from __future__ import annotations

from typing import Any

from ..errors import HinaaError
from ..integrations_hub import mcp_agent_tools
from ..social import service
from .registry import ToolDefinition, registry


def _tags(value: Any) -> list[str] | None:
    if value in (None, ""):
        return None
    return (
        [t.strip() for t in value.split(",") if t.strip()]
        if isinstance(value, str)
        else [str(t) for t in value]
    )


async def social_publish(params: dict[str, Any]) -> dict[str, Any]:
    user_id = str(params.get("userId") or "anonymous")
    try:
        result = await service.publish(
            None,
            user_id,
            confirm=mcp_agent_tools._user_approved.get(),
            platform=str(params.get("platform") or "youtube"),
            title=params.get("title"),
            description=params.get("description"),
            tags=_tags(params.get("tags")),
            privacy=params.get("privacy"),
            publish_at=params.get("publish_at"),
            media_path=params.get("media_path"),
            post_id=params.get("post_id"),
        )
    except HinaaError as error:
        return {"status": "failed", "code": error.code, "message": error.message}
    where = (
        f"scheduled for {result['publishAt']}"
        if result["publishAt"]
        else f"uploaded as {result['privacyStatus']}"
    )
    return {
        **result,
        "publishStatus": result["status"],
        "status": "success",
        "summaryText": f"YouTube video {where}: {result['url']}",
    }


registry.register(
    ToolDefinition(
        name="social_publish",
        display_name="Publish to Social Media",
        description=(
            "Upload a video to YouTube (title, description, tags, privacy, optional scheduled publish time). "
            "IRREVERSIBLE and always needs the user's confirmation. Privacy defaults to private; "
            "only use public or unlisted when the user explicitly asked. Other platforms are not available yet."
        ),
        parameters={
            "platform": {"type": "string", "description": "youtube (others require setup)."},
            "title": {"type": "string", "description": "Video title."},
            "description": {"type": "string", "description": "Video description."},
            "tags": {"type": "string", "description": "Comma-separated tags."},
            "privacy": {
                "type": "string",
                "enum": ["private", "unlisted", "public"],
                "description": "Defaults to private.",
            },
            "publish_at": {
                "type": "string",
                "description": "ISO 8601 time with offset (e.g. 2026-11-10T18:00:00+05:45); video stays private until then.",
            },
            "media_path": {
                "type": "string",
                "description": "Video file inside the social media folder.",
            },
            "post_id": {
                "type": "string",
                "description": "Optional content-calendar post id to take title/caption/media from.",
            },
        },
        required_parameters=[],
        requires_confirmation=True,
        risk_level="high",
        is_destructive=True,
        is_concurrency_safe=False,
        is_long_running=True,
        timeout_seconds=600,
        voice_aliases=["upload to youtube", "post to youtube", "publish video"],
    ),
    social_publish,
)

# ruff: noqa: E501
