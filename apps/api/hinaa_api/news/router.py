"""REST surface for news watchlists and digests, mounted under /v1/news and /api/v1/news."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, Query, Response

from ..config import Settings
from ..errors import HinaaError
from . import service
from .schemas import WatchlistCreate, WatchlistPatch


def build_news_router(settings: Settings, conversation_auth: Callable[..., Any]) -> APIRouter:
    router = APIRouter(tags=["News"])

    async def owner(auth: Any = Depends(conversation_auth)) -> str:
        if auth is None:
            raise HinaaError("AUTH_REQUIRED", "Authentication required for news", 401, True)
        return str(auth.user_id)

    @router.get("/watchlists")
    async def watchlists_list(user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.list_watchlists(settings, user_id)

    @router.post("/watchlists", status_code=201)
    async def watchlists_create(
        body: WatchlistCreate, user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return service.create_watchlist(settings, user_id, body)

    @router.get("/watchlists/{watchlist_id}")
    async def watchlists_get(watchlist_id: str, user_id: str = Depends(owner)) -> dict[str, Any]:
        return service.get_watchlist(settings, user_id, watchlist_id)

    @router.patch("/watchlists/{watchlist_id}")
    async def watchlists_update(
        watchlist_id: str, body: WatchlistPatch, user_id: str = Depends(owner)
    ) -> dict[str, Any]:
        return service.update_watchlist(settings, user_id, watchlist_id, body)

    @router.delete("/watchlists/{watchlist_id}", status_code=204)
    async def watchlists_delete(watchlist_id: str, user_id: str = Depends(owner)) -> Response:
        service.delete_watchlist(settings, user_id, watchlist_id)
        return Response(status_code=204)

    @router.post("/watchlists/{watchlist_id}/run")
    async def watchlists_run(watchlist_id: str, user_id: str = Depends(owner)) -> dict[str, Any]:
        return await service.run_watchlist(settings, user_id, watchlist_id)

    @router.get("/digests")
    async def digests_latest(
        watchlist_id: str | None = None,
        limit: int = Query(10, ge=1, le=50),
        user_id: str = Depends(owner),
    ) -> dict[str, Any]:
        return service.latest_digests(settings, user_id, watchlist_id=watchlist_id, limit=limit)

    return router
