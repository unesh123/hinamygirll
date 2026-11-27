"""HINAA Foundry REST API endpoints (/api/v1/foundry/sites/*)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from ..foundry.service import get_foundry_service

router = APIRouter(tags=["HINAA Foundry"])


class FoundryCreateBody(BaseModel):
    brief: str = Field(min_length=3, max_length=4000)
    palette: Optional[str] = None
    logos: List[str] = Field(default_factory=list)
    features: Optional[List[str]] = None


class FoundryReviseBody(BaseModel):
    instructions: str = ""
    palette: Optional[str] = None
    tagline: Optional[str] = None
    logos: Optional[List[str]] = None


@router.post("/api/v1/foundry/sites")
@router.post("/v1/foundry/sites")
async def create_foundry_site(body: FoundryCreateBody) -> Dict[str, Any]:
    svc = get_foundry_service()
    try:
        rec = svc.create_site(body.brief, palette=body.palette, logos=body.logos, features=body.features)
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    return {
        **rec.model_dump(),
        "previewUrl": f"/api/v1/foundry/sites/{rec.site_id}/preview",
        "downloadUrl": f"/api/v1/foundry/sites/{rec.site_id}/download",
    }


@router.get("/api/v1/foundry/sites")
@router.get("/v1/foundry/sites")
async def list_foundry_sites() -> Dict[str, Any]:
    return {"sites": get_foundry_service().list_sites()}


@router.get("/api/v1/foundry/sites/{site_id}")
@router.get("/v1/foundry/sites/{site_id}")
async def get_foundry_site(site_id: str) -> Dict[str, Any]:
    rec = get_foundry_service().get_site(site_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return {
        **rec.model_dump(),
        "previewUrl": f"/api/v1/foundry/sites/{rec.site_id}/preview",
        "downloadUrl": f"/api/v1/foundry/sites/{rec.site_id}/download",
    }


@router.get("/api/v1/foundry/sites/{site_id}/preview")
@router.get("/v1/foundry/sites/{site_id}/preview")
async def preview_foundry_site(site_id: str) -> HTMLResponse:
    html_doc = get_foundry_service().render_self_contained_preview_html(site_id)
    if html_doc is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return HTMLResponse(html_doc)


@router.get("/api/v1/foundry/sites/{site_id}/files")
@router.get("/v1/foundry/sites/{site_id}/files")
async def files_foundry_site(site_id: str) -> Dict[str, Any]:
    rec = get_foundry_service().get_site(site_id)
    if rec is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"site_id": rec.site_id, "revision": rec.revision, "files": rec.files}


@router.get("/api/v1/foundry/sites/{site_id}/download")
@router.get("/v1/foundry/sites/{site_id}/download")
async def download_foundry_site(site_id: str) -> Response:
    z = get_foundry_service().build_zip_bytes(site_id)
    if z is None:
        raise HTTPException(status_code=404, detail="Site not found")
    raw, digest = z
    return Response(
        raw,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{site_id}.zip"',
            "X-HINAA-Sha256": digest,
        },
    )


@router.post("/api/v1/foundry/sites/{site_id}/revise")
@router.post("/v1/foundry/sites/{site_id}/revise")
async def revise_foundry_site(site_id: str, body: FoundryReviseBody) -> Dict[str, Any]:
    try:
        rec = get_foundry_service().revise_site(
            site_id,
            instructions=body.instructions,
            palette=body.palette,
            tagline=body.tagline,
            logos=body.logos,
        )
    except ValueError as err:
        raise HTTPException(status_code=422, detail=str(err)) from err
    if rec is None:
        raise HTTPException(status_code=404, detail="Site not found")
    return {
        **rec.model_dump(),
        "previewUrl": f"/api/v1/foundry/sites/{rec.site_id}/preview",
        "downloadUrl": f"/api/v1/foundry/sites/{rec.site_id}/download",
    }


@router.delete("/api/v1/foundry/sites/{site_id}")
@router.delete("/v1/foundry/sites/{site_id}")
async def delete_foundry_site(site_id: str) -> Dict[str, Any]:
    deleted = get_foundry_service().delete_site(site_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Site not found")
    return {"deleted": True, "site_id": site_id}
