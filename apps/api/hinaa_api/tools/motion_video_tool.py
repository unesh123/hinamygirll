"""Local editable motion graphics exposed through Hina's creative job lifecycle."""
import asyncio
from pydantic import BaseModel, Field
from ..creative.motion import MotionScene
from ..creative.models import CreativeJobSpec, CreativeOperation, JobState
from ..creative.jobs.service import creative_service
from .registry import ToolDefinition, registry


class MotionVideoParams(BaseModel):
    title: str = Field(default="Motion video", max_length=120)
    scenes: list[MotionScene] = Field(min_length=1, max_length=8)
    userId: str = "default_user"


async def create_motion_video_handler(params: MotionVideoParams):
    if sum(scene.duration for scene in params.scenes)>30:
        return {"status":"error","error":"Motion video must be at most 30 seconds."}
    spec=CreativeJobSpec(operation=CreativeOperation.TIMELINE_EXPORT,prompt=params.title,
                         width=960,height=540,fps=24,motion_scenes=params.scenes,user_id=params.userId)
    job=await creative_service.submit_job(spec)
    try:
        async for _ in creative_service.stream_events(job.job_id,job.tenant_id):
            pass
    except asyncio.CancelledError:
        await creative_service.cancel_job(job.job_id,job.tenant_id)
        raise
    job=await creative_service.store.get_job(job.job_id)
    if job.state != JobState.COMPLETED or not job.output_assets:
        return {"status":"error","job_id":job.job_id,"error":job.error_reason or job.state.value}
    asset=job.output_assets[0]
    return {"status":"success","job_id":job.job_id,"asset_id":asset.asset_id,
            "download_url":f"/v1/creative/assets/{asset.asset_id}/download",
            "duration_seconds":asset.duration_seconds,"width":asset.width,"height":asset.height,
            "editable_spec":spec.model_dump(mode="json"),"render_method":"local code-driven motion graphics"}


registry.register(ToolDefinition(
    name="create_motion_video",display_name="Create Motion Graphics",
    description="Render an explicitly requested animated explainer or title video locally as MP4. Plan 1–8 editable scenes, total at most 30 seconds. No realistic footage or cloud video model. Use concise titles and subtitles; choose orbit, bars or steps layouts.",
    parameters={"title":{"type":"string"},"scenes":{"type":"array","items":MotionScene.model_json_schema()}},
    required_parameters=["scenes"],requires_confirmation=False,risk_level="medium",
    timeout_seconds=180,is_long_running=True,is_concurrency_safe=False,max_retries=0,
),create_motion_video_handler)
