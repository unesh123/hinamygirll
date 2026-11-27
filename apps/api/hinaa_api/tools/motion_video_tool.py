"""Local editable motion graphics exposed through Hina's creative job lifecycle."""
from __future__ import annotations

import asyncio
from typing import Any
from pydantic import BaseModel, Field, field_validator, model_validator
from ..creative.motion import MotionScene
from ..creative.models import CreativeJobSpec, CreativeOperation, JobState
from ..creative.jobs.service import creative_service
from .registry import ToolDefinition, registry


class MotionVideoParams(BaseModel):
    title: str = Field(default="Motion video", max_length=120)
    scenes: list[MotionScene] = Field(min_length=1, max_length=8)
    userId: str = "default_user"

    @model_validator(mode="before")
    @classmethod
    def _coerce_llm_aliases(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        out = dict(data)
        if not out.get("title"):
            out["title"] = out.get("prompt") or out.get("topic") or "Motion video"
        raw_scenes = out.get("scenes")
        if isinstance(raw_scenes, str) and raw_scenes.strip():
            raw_scenes = [{"title": s.strip()} for s in raw_scenes.splitlines() if s.strip()][:8]
        if isinstance(raw_scenes, list):
            allowed_keys = {"title", "subtitle", "label", "duration", "accent", "layout"}
            normalized: list[Any] = []
            for idx, item in enumerate(raw_scenes):
                if isinstance(item, str):
                    txt = item.strip()[:90]
                    if txt:
                        normalized.append({"title": txt})
                    continue
                if not isinstance(item, dict):
                    normalized.append(item)
                    continue
                d = dict(item)
                # Reject explicit injection attempts while normalizing honest LLM key synonyms
                if "title" not in d or not str(d.get("title") or "").strip():
                    candidate = d.get("headline") or d.get("heading") or d.get("text") or d.get("name") or d.get("eyebrow") or f"Scene {idx + 1}"
                    d["title"] = str(candidate).strip()[:90] or f"Scene {idx + 1}"
                if "subtitle" not in d:
                    sub = d.get("description") or d.get("visual") or d.get("body") or d.get("caption") or d.get("subline")
                    if isinstance(sub, str):
                        d["subtitle"] = sub.strip()[:180]
                if "label" not in d and isinstance(d.get("eyebrow") or d.get("tag"), str):
                    d["label"] = str(d.get("eyebrow") or d.get("tag"))[:40]
                if "duration" not in d:
                    dur_alias = d.get("duration_seconds") or d.get("seconds") or d.get("dur")
                    if dur_alias is not None:
                        d["duration"] = dur_alias
                normalized.append({k: v for k, v in d.items() if k in allowed_keys})
            out["scenes"] = normalized
        from ..agent.hooks import apply_guards
        return apply_guards("create_motion_video", out)

    @field_validator("title", mode="before")
    @classmethod
    def _clamp_title(cls, value: object) -> str:
        raw = str(value or "").strip().splitlines()[0].strip() if value else ""
        if not raw:
            return "Motion video"
        return raw[:120].strip() or "Motion video"


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
