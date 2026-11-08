"""create_lyric_video: render a kinetic-typography lyric video to a local MP4."""
# ruff: noqa: E501

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from hinaa_api.creative.lyric_video import LyricVideoSpec
from hinaa_api.creative.lyric_video.jobs import lyric_video_service
from hinaa_api.creative.models import JobState
from hinaa_api.errors import HinaaError
from hinaa_api.tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.lyric_video")


class LyricVideoParams(BaseModel):
    model_config = ConfigDict(extra="ignore")

    userId: str | None = None
    title: str = "Lyric Video"
    lines: list[str | dict[str, Any]] = Field(min_length=1)
    audio_path: str | None = None
    character_image: str | None = None
    palette: dict[str, str] | None = None
    stickers: list[dict[str, Any]] | None = None
    aspect: str = "9:16"
    draft: bool = False


async def create_lyric_video_handler(params: LyricVideoParams) -> dict[str, Any]:
    try:
        spec = LyricVideoSpec.model_validate({
            "title": params.title,
            "lines": [{"text": x} if isinstance(x, str) else x for x in params.lines],
            "audio_path": params.audio_path, "character_image": params.character_image,
            "stickers": params.stickers or [], "aspect": params.aspect, "draft": params.draft,
            **({"palette": params.palette} if params.palette else {}),
        })
    except ValidationError as exc:
        return {"status": "error", "code": "INVALID_LYRIC_VIDEO_SPEC",
                "error": "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())}
    try:
        job = await lyric_video_service.submit(spec, user_id=params.userId or "default_user")
    except HinaaError as exc:
        return {"status": "error", "code": exc.code, "error": exc.message}
    await lyric_video_service.wait(job.job_id)
    if job.state != JobState.COMPLETED or not job.asset:
        return {"status": "error", "code": f"LYRIC_VIDEO_{job.state.value}", "error": job.error or job.progress_label, "job_id": job.job_id}
    asset = job.asset
    return {
        "status": "success", "job_id": job.job_id, "asset_id": asset["asset_id"],
        "download_url": f"/v1/creative/assets/{asset['asset_id']}/download",
        "duration_seconds": asset["duration_seconds"], "width": asset["width"], "height": asset["height"],
        "render_seconds": job.render_seconds,
    }


create_lyric_video_tool_def = ToolDefinition(
    name="create_lyric_video",
    display_name="Create Lyric Video",
    description=(
        "Render a motion-graphics lyric video (MP4): each lyric line pops in word by word as big bubbly "
        "outlined text around a cute anime-style character, on its own pastel scene (dreamy-sky, hills-day, "
        "starry-night-flags, snow-window, love-burst) with camera pushes, transitions and sticker captions. "
        "Deterministic, local, no AI video models. Optionally synced to an mp3/wav under the data directory."
    ),
    parameters={
        "title": {"type": "string", "description": "Video title."},
        "lines": {"type": "array", "items": {"type": "string"}, "description": "Lyric lines in order. Objects {text,start,end,scene} are also accepted for explicit timing."},
        "audio_path": {"type": "string", "description": "Optional .mp3/.wav path inside the data directory; lines are timed across its duration."},
        "character_image": {"type": "string", "description": "Optional PNG path for a custom character (transparent background). Defaults to a built-in chibi girl."},
        "stickers": {"type": "array", "items": {"type": "object"}, "description": "Optional [{text, at}] caption stickers; 'at' is seconds."},
        "aspect": {"type": "string", "enum": ["9:16", "16:9", "1:1"], "description": "Defaults to 9:16 (1080x1920)."},
        "draft": {"type": "boolean", "description": "Half-resolution quick preview."},
    },
    required_parameters=["lines"],
    requires_confirmation=False,
    risk_level="medium",
    timeout_seconds=600,
    is_long_running=True,
    is_concurrency_safe=False,
    max_retries=0,
)

registry.register(create_lyric_video_tool_def, create_lyric_video_handler)
