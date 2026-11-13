"""Agent tools for News AI: create watchlists, run a digest now, read the latest digests.

The owner's identity is injected server-side as `userId`; the model never picks it.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from ..errors import HinaaError
from ..news import service
from ..news.schemas import WatchlistCreate
from .registry import ToolDefinition, registry


def _failed(message: str, code: str = "NEWS_INVALID") -> dict[str, Any]:
    return {"status": "failed", "code": code, "message": message}


def _list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(v) for v in value or []]


def _compact(digest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": digest["id"],
        "title": digest["title"],
        "generatedBy": digest["generatedBy"],
        "items": [{"text": i["text"], "urls": i["urls"]} for i in digest["items"]],
    }


def _describe(digest: dict[str, Any]) -> str:
    lines = [f"{digest['title']}:"]
    lines += [f"- {i['text']} ({i['urls'][0]})" for i in digest["items"]]
    return "\n".join(lines)


async def news_watch_create(params: dict[str, Any]) -> dict[str, Any]:
    user_id = str(params.get("userId") or "anonymous")
    try:
        data = {
            "name": params.get("name") or params.get("topic") or "News watchlist",
            "topics": _list(params.get("topics") or params.get("topic")),
            "keywords": _list(params.get("keywords")),
            "sources": _list(params.get("feeds")),
        }
        for key, field in (("cadence", "cadence"), ("daily_hour", "dailyHour")):
            if params.get(key) not in (None, ""):
                data[field] = params[key]
        watchlist = service.create_watchlist(None, user_id, WatchlistCreate(**data))
    except ValidationError as error:
        first = error.errors()[0]
        return _failed(
            f"I could not use {'.'.join(str(p) for p in first['loc']) or 'input'}: {first['msg']}."
        )
    except HinaaError as error:
        return _failed(error.message, error.code)
    return {
        "status": "success",
        "watchlist": watchlist,
        "summaryText": f"Watching '{watchlist['name']}' ({watchlist['cadence']}, Nepal time).",
    }


async def news_digest_now(params: dict[str, Any]) -> dict[str, Any]:
    user_id = str(params.get("userId") or "anonymous")
    try:
        runs = await service.run_now_for_user(
            None, user_id, str(params.get("watchlist_id") or "").strip() or None
        )
    except HinaaError as error:
        return _failed(error.message, error.code)
    digests = [r["digest"] for r in runs if r["digest"]]
    warnings = [w for r in runs for w in r["warnings"]]
    if not runs:
        return _failed(
            "There are no watchlists yet; create one with news_watch_create.", "NEWS_NO_WATCHLIST"
        )
    if not digests:
        return {
            "status": "success",
            "digests": [],
            "warnings": warnings,
            "summaryText": "No new stories were found. I did not invent any.",
        }
    return {
        "status": "success",
        "digests": [_compact(d) for d in digests],
        "warnings": warnings,
        "summaryText": "\n\n".join(_describe(d) for d in digests),
    }


async def news_latest(params: dict[str, Any]) -> dict[str, Any]:
    user_id = str(params.get("userId") or "anonymous")
    try:
        limit = max(1, min(int(params.get("limit") or 3), 10))
    except (TypeError, ValueError):
        limit = 3
    digests = service.latest_digests(
        None, user_id, watchlist_id=str(params.get("watchlist_id") or "") or None, limit=limit
    )["items"]
    if not digests:
        return {"status": "success", "digests": [], "summaryText": "No saved digests yet."}
    return {
        "status": "success",
        "digests": [_compact(d) for d in digests],
        "summaryText": "\n\n".join(_describe(d) for d in digests),
    }


_S = {"type": "string"}

registry.register(
    ToolDefinition(
        name="news_watch_create",
        display_name="Create News Watchlist",
        description="Watch topics/keywords (and optional RSS/Atom feeds) and get cited news digests, hourly or daily at Nepal time.",
        parameters={
            "name": {**_S, "description": "Watchlist name."},
            "topics": {**_S, "description": "Comma-separated topics, e.g. 'Nepal economy, AI'."},
            "keywords": {**_S, "description": "Comma-separated keywords."},
            "feeds": {**_S, "description": "Comma-separated RSS/Atom feed URLs."},
            "cadence": {
                **_S,
                "enum": ["manual", "hourly", "daily"],
                "description": "How often to run (default daily).",
            },
            "daily_hour": {
                "type": "integer",
                "description": "Nepal-time hour 0-23 for daily runs (default 8).",
            },
        },
        required_parameters=[],
        risk_level="low",
        voice_aliases=["watch the news", "track news about", "news watchlist"],
    ),
    news_watch_create,
)
registry.register(
    ToolDefinition(
        name="news_digest_now",
        display_name="News Digest Now",
        description="Fetch and summarise fresh news for one watchlist (or all) right now. Every point cites a fetched URL.",
        parameters={
            "watchlist_id": {**_S, "description": "Optional watchlist id; default all enabled."}
        },
        required_parameters=[],
        risk_level="low",
        is_long_running=True,
        voice_aliases=["news digest", "what's the news", "run news now"],
    ),
    news_digest_now,
)
registry.register(
    ToolDefinition(
        name="news_latest",
        display_name="Latest News Digests",
        description="Read the most recent saved news digests with their source links.",
        parameters={
            "watchlist_id": {**_S, "description": "Optional watchlist id."},
            "limit": {"type": "integer", "description": "How many digests (1-10, default 3)."},
        },
        required_parameters=[],
        risk_level="low",
        is_read_only=True,
        voice_aliases=["latest news", "last digest"],
    ),
    news_latest,
)

# ruff: noqa: E501
