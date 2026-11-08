"""REST surface for the productivity trackers, mounted under /v1 and /api/v1."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from ..config import Settings
from ..errors import HinaaError
from . import service
from .schemas import (
    ContentPostCreate,
    ContentPostPatch,
    Period,
    Platform,
    PostStatus,
    ProjectCreate,
    ProjectPatch,
    ProjectStatus,
    SalesRecordCreate,
    SalesRecordPatch,
)


def build_productivity_router(settings: Settings, conversation_auth: Callable[..., Any]) -> APIRouter:
    router = APIRouter(tags=["Productivity"])

    async def owner(auth: Any = Depends(conversation_auth)) -> str:
        # An empty list for an anonymous caller would read as "nothing planned".
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for productivity", 401, True)
        return str(auth.user_id)

    # content
    @router.get("/content/week")
    async def content_week(
        week_start: date | None = Query(None, description="Any date; snapped to that week's Monday"),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.week_view(settings, user_id, service.monday_of(week_start) if week_start else None)

    @router.get("/content/posts")
    async def content_list(
        status: PostStatus | None = None,
        platform: Platform | None = None,
        limit: int = Query(50, ge=1, le=service.MAX_PAGE),
        offset: int = Query(0, ge=0),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.list_posts(
            settings, user_id, status=status, platform=platform, limit=limit, offset=offset
        )

    @router.post("/content/posts", status_code=201)
    async def content_create(body: ContentPostCreate, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.create_post(settings, user_id, body)

    @router.get("/content/posts/{post_id}")
    async def content_get(post_id: str, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.get_post(settings, user_id, post_id)

    @router.patch("/content/posts/{post_id}")
    async def content_update(
        post_id: str, body: ContentPostPatch, user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return service.update_post(settings, user_id, post_id, body)

    @router.delete("/content/posts/{post_id}", status_code=204)
    async def content_delete(post_id: str, user_id: str = Depends(owner)) -> Response:
        service.delete_post(settings, user_id, post_id)
        return Response(status_code=204)

    # sales
    @router.get("/sales/summary")
    async def sales_summary(
        period: Period = "week",
        on: date | None = None,
        currency: str | None = Query(None, min_length=3, max_length=3),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.sales_summary(settings, user_id, period=period, on=on, currency=currency)

    @router.get("/sales/records")
    async def sales_list(
        start: date | None = None,
        end: date | None = None,
        limit: int = Query(50, ge=1, le=service.MAX_PAGE),
        offset: int = Query(0, ge=0),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.list_sales(settings, user_id, start=start, end=end, limit=limit, offset=offset)

    @router.post("/sales/records", status_code=201)
    async def sales_create(body: SalesRecordCreate, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.create_sale(settings, user_id, body)

    @router.get("/sales/records/{sale_id}")
    async def sales_get(sale_id: str, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.get_sale(settings, user_id, sale_id)

    @router.patch("/sales/records/{sale_id}")
    async def sales_update(
        sale_id: str, body: SalesRecordPatch, user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return service.update_sale(settings, user_id, sale_id, body)

    @router.delete("/sales/records/{sale_id}", status_code=204)
    async def sales_delete(sale_id: str, user_id: str = Depends(owner)) -> Response:
        service.delete_sale(settings, user_id, sale_id)
        return Response(status_code=204)

    # projects
    @router.get("/projects")
    async def projects_list(
        status: ProjectStatus | None = None,
        limit: int = Query(50, ge=1, le=service.MAX_PAGE),
        offset: int = Query(0, ge=0),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.list_projects(settings, user_id, status=status, limit=limit, offset=offset)

    @router.post("/projects", status_code=201)
    async def projects_create(body: ProjectCreate, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.create_project(settings, user_id, body)

    @router.get("/projects/{project_id}")
    async def projects_get(project_id: str, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.get_project(settings, user_id, project_id)

    @router.patch("/projects/{project_id}")
    async def projects_update(
        project_id: str, body: ProjectPatch, user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return service.update_project(settings, user_id, project_id, body)

    @router.delete("/projects/{project_id}", status_code=204)
    async def projects_delete(project_id: str, user_id: str = Depends(owner)) -> Response:
        service.delete_project(settings, user_id, project_id)
        return Response(status_code=204)

    return router
