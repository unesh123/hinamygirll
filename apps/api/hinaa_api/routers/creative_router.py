"""
Router for Phase 09 Creative Studio Endpoints.
Extracted from main.py to maintain modular enterprise architecture.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Body, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, ValidationError

from ..creative.registry import CreativeModelRegistry


class CreativeJobBody(BaseModel):
    prompt: Annotated[str, Field(min_length=1, max_length=50_000)]
    model: Annotated[str, Field(min_length=1, max_length=120)]


def build_creative_router(creative_jobs: Any) -> APIRouter:
    router = APIRouter(tags=["creative"])

    @router.get("/api/creative/capabilities")
    @router.get("/v1/creative/capabilities")
    async def get_creative_capabilities() -> dict[str, Any]:
        """Returns discovered hardware, runtime capabilities, and honest model availability."""
        from ..creative import creative_registry
        return creative_registry.matrix.model_dump()

    @router.post("/api/creative/jobs")
    @router.post("/v1/creative/jobs")
    async def submit_creative_job(spec: Any = Body(...), request: Request = None) -> Any:
        """Submits a creative studio job (image, edit/inpaint, video timeline export)."""
        from ..creative import CreativeJobSpec, creative_service
        if not isinstance(spec, (dict, CreativeJobSpec)):
            raise HTTPException(status_code=422, detail="Creative job body must be a JSON object")
        if isinstance(spec, dict) and "operation" not in spec:
            try:
                legacy = CreativeJobBody.model_validate(spec)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_url=False, include_context=False))) from exc
            model = CreativeModelRegistry.get_model(legacy.model)
            legacy_job = await creative_jobs.create_job(legacy.prompt, model.id, model.cost_credits)
            return JSONResponse(status_code=201, content=legacy_job.to_dict())
        if isinstance(spec, dict):
            try:
                spec = CreativeJobSpec.model_validate(spec)
            except ValidationError as exc:
                raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_url=False, include_context=False))) from exc
        tenant_id = request.headers.get("X-Tenant-ID", spec.tenant_id or "default_tenant") if request else spec.tenant_id
        user_id = request.headers.get("X-User-ID", spec.user_id or "default_user") if request else spec.user_id
        spec.tenant_id = tenant_id
        spec.user_id = user_id
        job = await creative_service.submit_job(spec)
        return job.model_dump()

    @router.get("/api/creative/jobs/{job_id}")
    @router.get("/v1/creative/jobs/{job_id}")
    async def get_creative_job(job_id: str, request: Request) -> dict[str, Any]:
        """Returns current status and telemetry for a creative job."""
        from ..creative import CreativeSecurityPolicy, creative_service
        job = await creative_service.store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Creative job '{job_id}' not found.")
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)
        return job.model_dump()

    @router.get("/api/creative/jobs/{job_id}/events")
    @router.get("/v1/creative/jobs/{job_id}/events")
    async def stream_creative_job_events(job_id: str, request: Request) -> StreamingResponse:
        """SSE stream for real-time progress and telemetry with reconnect support."""
        from ..creative import CreativeSecurityPolicy, creative_service
        job = await creative_service.store.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail=f"Creative job '{job_id}' not found.")
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        CreativeSecurityPolicy.verify_tenant_access(tenant_id, job.tenant_id)
        return StreamingResponse(
            creative_service.stream_events(job_id, tenant_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/api/creative/jobs/{job_id}/cancel")
    @router.post("/v1/creative/jobs/{job_id}/cancel")
    async def cancel_creative_job(job_id: str, request: Request) -> dict[str, Any]:
        """Cancels an active or queued creative job."""
        from ..creative import creative_service
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        job = await creative_service.cancel_job(job_id, tenant_id)
        return {"jobId": job.job_id, "status": job.state.value}

    @router.post("/api/creative/lyric-video")
    @router.post("/v1/creative/lyric-video")
    async def submit_lyric_video(spec: dict[str, Any] = Body(...), request: Request = None) -> Any:
        """Starts a deterministic motion-graphics lyric-video render (async job)."""
        from ..creative.lyric_video import LyricVideoSpec
        from ..creative.lyric_video.jobs import lyric_video_service
        try:
            parsed = LyricVideoSpec.model_validate(spec)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors(include_url=False, include_context=False))) from exc
        job = await lyric_video_service.submit(
            parsed,
            tenant_id=request.headers.get("X-Tenant-ID", "default_tenant") if request else "default_tenant",
            user_id=request.headers.get("X-User-ID", "default_user") if request else "default_user",
        )
        return JSONResponse(status_code=202, content=job.to_dict())

    @router.get("/api/creative/lyric-video/{job_id}")
    @router.get("/v1/creative/lyric-video/{job_id}")
    async def get_lyric_video(job_id: str, request: Request) -> dict[str, Any]:
        from ..creative.lyric_video.jobs import lyric_video_service
        return lyric_video_service.get(job_id, request.headers.get("X-Tenant-ID", "default_tenant")).to_dict()

    @router.post("/api/creative/lyric-video/{job_id}/cancel")
    @router.post("/v1/creative/lyric-video/{job_id}/cancel")
    async def cancel_lyric_video(job_id: str, request: Request) -> dict[str, Any]:
        from ..creative.lyric_video.jobs import lyric_video_service
        return (await lyric_video_service.cancel(job_id, request.headers.get("X-Tenant-ID", "default_tenant"))).to_dict()

    @router.post("/api/creative/jobs/{job_id}/retry")
    @router.post("/v1/creative/jobs/{job_id}/retry")
    async def retry_creative_job(job_id: str, request: Request) -> dict[str, Any]:
        """Retries a failed creative job within retry bounds."""
        from ..creative import creative_service
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        new_job = await creative_service.retry_job(job_id, tenant_id)
        return new_job.model_dump()

    @router.post("/api/creative/assets/upload")
    @router.post("/v1/creative/assets/upload")
    async def upload_creative_asset(
        request: Request,
        file: UploadFile = File(...),
        operation: str = Form("IMAGE_TO_IMAGE"),
    ) -> dict[str, Any]:
        """Uploads source image or mask asset with MIME validation."""
        from ..creative import CreativeOperation, creative_asset_manager
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        user_id = request.headers.get("X-User-ID", "default_user")
        data = await file.read()
        op = CreativeOperation.IMAGE_TO_IMAGE
        try:
            op = CreativeOperation(operation)
        except Exception:
            pass
        meta = creative_asset_manager.store_asset(
            data=data,
            filename=file.filename or "upload.png",
            operation=op,
            provider="user_upload",
            model_version="upload",
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return meta.model_dump()

    @router.get("/api/creative/assets/{asset_id}")
    @router.get("/v1/creative/assets/{asset_id}")
    async def get_creative_asset(asset_id: str, request: Request) -> dict[str, Any]:
        """Returns asset metadata and provenance."""
        from ..creative import creative_asset_manager
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        meta = creative_asset_manager.get_asset_metadata(asset_id, tenant_id)
        if not meta:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        return meta.model_dump()

    @router.get("/api/creative/assets/{asset_id}/download")
    @router.get("/v1/creative/assets/{asset_id}/download")
    async def download_creative_asset(asset_id: str, request: Request) -> Response:
        """Streams verified asset media bytes with safe headers."""
        from ..creative import creative_asset_manager
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        p = creative_asset_manager.get_asset_path(asset_id, tenant_id)
        meta = creative_asset_manager.get_asset_metadata(asset_id, tenant_id)
        if not p or not meta:
            raise HTTPException(status_code=404, detail=f"Asset '{asset_id}' not found.")
        data = p.read_bytes()
        headers = {
            "Content-Disposition": f'attachment; filename="{meta.filename}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Length": str(len(data)),
            "ETag": f'"{meta.sha256_hash}"',
        }
        return Response(content=data, media_type=meta.mime_type, headers=headers)

    @router.get("/api/creative/assets")
    @router.get("/v1/creative/assets")
    async def list_creative_assets(request: Request, limit: int = 50) -> dict[str, Any]:
        """Lists tenant-owned creative assets."""
        from ..creative import creative_asset_manager
        tenant_id = request.headers.get("X-Tenant-ID", "default_tenant")
        user_id = request.headers.get("X-User-ID", None)
        assets = creative_asset_manager.list_assets(tenant_id, user_id, limit=limit)
        return {"tenant_id": tenant_id, "assets": [a.model_dump() for a in assets], "count": len(assets)}

    return router
