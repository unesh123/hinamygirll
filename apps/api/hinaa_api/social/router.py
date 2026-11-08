"""REST surface for social connectors, mounted under /v1/social and /api/v1/social."""

from __future__ import annotations

from collections.abc import Callable
from html import escape
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from ..config import Settings
from ..errors import HinaaError
from . import service


class PublishBody(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    confirm: bool = False
    platform: str = "youtube"
    title: str | None = Field(None, max_length=200)
    description: str | None = Field(None, max_length=5000)
    tags: list[str] | None = Field(None, max_length=30)
    privacyStatus: str | None = None
    publishAt: str | None = None
    mediaPath: str | None = Field(None, max_length=500)
    postId: str | None = None


def build_social_router(settings: Settings, conversation_auth: Callable[..., Any]) -> APIRouter:
    router = APIRouter(tags=["Social"])

    async def owner(auth: Any = Depends(conversation_auth)) -> str:
        if auth is None:
            raise HinaaError(
                "AUTH_REQUIRED", "Authentication required for social publishing", 401, True
            )
        return str(auth.user_id)

    @router.get("/connections")
    async def connections(user_id: str = Depends(owner)) -> dict[str, Any]:
        return {"items": service.connections(settings, user_id)}

    @router.get("/youtube/connect")
    async def youtube_connect(user_id: str = Depends(owner)) -> dict[str, str]:
        return service.start_youtube_connect(settings, user_id)

    # Google redirects the browser here without our auth headers; the signed, expiring
    # `state` minted by /youtube/connect identifies the user instead.
    @router.get("/youtube/callback", response_class=HTMLResponse)
    async def youtube_callback(
        state: str = Query(""), code: str = Query(""), error: str = Query("")
    ) -> HTMLResponse:
        if error or not code:
            return HTMLResponse(
                f"<h1>YouTube not connected</h1><p>{escape(error or 'No authorization code was returned.')}</p>",
                status_code=400,
            )
        await service.complete_youtube_connect(settings, state, code)
        return HTMLResponse(
            "<h1>YouTube connected</h1><p>You can close this tab and return to Hinaa.</p>"
        )

    @router.post("/youtube/disconnect")
    async def youtube_disconnect(user_id: str = Depends(owner)) -> dict[str, bool]:
        return {"disconnected": service.disconnect(settings, user_id)}

    @router.get("/youtube/uploads")
    async def youtube_uploads(
        limit: int = Query(10, ge=1, le=50), user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return {"items": await service.list_uploads(settings, user_id, limit)}

    @router.post("/publish")
    async def publish(body: PublishBody, user_id: str = Depends(owner)) -> dict[str, Any]:
        return await service.publish(
            settings,
            user_id,
            confirm=body.confirm,
            platform=body.platform,
            title=body.title,
            description=body.description,
            tags=body.tags,
            privacy=body.privacyStatus,
            publish_at=body.publishAt,
            media_path=body.mediaPath,
            post_id=body.postId,
        )

    @router.get("/publish-log")
    async def publish_log(
        limit: int = Query(20, ge=1, le=100), user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return {"items": service.publish_log(settings, user_id, limit)}

    return router

# ruff: noqa: E501
