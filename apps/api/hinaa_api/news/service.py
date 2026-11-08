"""Watchlist persistence and the fetch → dedupe → rank → digest → deliver pipeline.

Every query filters on user_id. HTTP, search, summariser and delivery channels are
injectable so tests (and other tracks) never need the network.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..nepal_calendar import NEPAL_TZ
from ..persistence.db import get_session_factory
from ..persistence.orm import NewsDigest, NewsWatchlist
from . import delivery
from .digest import Summarizer, build_items, default_summarizer, fetched_urls, validate_items
from .feeds import fetch_feed
from .ranker import rank, relevance
from .schemas import WatchlistCreate, WatchlistPatch
from .text import Article, canonicalize_url, dedupe

logger = logging.getLogger("hinaa.news")

MAX_AGE = timedelta(hours=72)
MAX_WATCHLISTS = 25
SEEN_DIGESTS = 10
SearchFn = Callable[[str, int], Awaitable[list[Article]]]


def _session(settings: Settings | None) -> Callable[[], Session]:
    return get_session_factory(settings or get_settings())


def _aware(moment: datetime | None) -> datetime | None:
    return moment.replace(tzinfo=UTC) if moment is not None and moment.tzinfo is None else moment


def _not_found(kind: str) -> HinaaError:
    return HinaaError(
        f"{kind.upper()}_NOT_FOUND", f"There is no such {kind} for this account.", 404, False
    )


def _owned_watchlist(session: Session, user_id: str, watchlist_id: str) -> NewsWatchlist:
    row = session.scalar(
        select(NewsWatchlist).where(
            NewsWatchlist.id == watchlist_id, NewsWatchlist.user_id == user_id
        )
    )
    if row is None:
        raise _not_found("watchlist")
    return row


def next_run_after(cadence: str, daily_hour: int, now: datetime) -> datetime | None:
    """Next fire time (UTC). Daily runs fire at `daily_hour` Nepal time; hourly on the next full hour."""
    if cadence == "manual":
        return None
    now = _aware(now) or datetime.now(UTC)
    if cadence == "hourly":
        return now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    local = now.astimezone(NEPAL_TZ)
    target = local.replace(hour=daily_hour, minute=0, second=0, microsecond=0)
    if target <= local:
        target += timedelta(days=1)
    return target.astimezone(UTC)


def watchlist_public(row: NewsWatchlist) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "topics": json.loads(row.topics or "[]"),
        "keywords": json.loads(row.keywords or "[]"),
        "sources": json.loads(row.sources or "[]"),
        "cadence": row.cadence,
        "dailyHour": row.daily_hour,
        "enabled": row.enabled,
        "lastRunAt": _aware(row.last_run_at).isoformat() if row.last_run_at else None,
        "nextRunAt": _aware(row.next_run_at).isoformat() if row.next_run_at else None,
    }


def digest_public(row: NewsDigest) -> dict[str, Any]:
    return {
        "id": row.id,
        "watchlistId": row.watchlist_id,
        "title": row.title,
        "items": json.loads(row.items or "[]"),
        "sources": json.loads(row.sources or "[]"),
        "generatedBy": row.generated_by,
        "articleCount": row.article_count,
        "createdAt": _aware(row.created_at).isoformat() if row.created_at else None,
    }


# ---- watchlists -------------------------------------------------------------


def create_watchlist(
    settings: Settings | None, user_id: str, data: WatchlistCreate
) -> dict[str, Any]:
    if not (data.topics or data.keywords or data.sources):
        raise HinaaError(
            "WATCHLIST_EMPTY",
            "Give the watchlist at least one topic, keyword or feed.",
            422,
            False,
            True,
        )
    with _session(settings)() as session:
        count = len(
            session.scalars(select(NewsWatchlist.id).where(NewsWatchlist.user_id == user_id)).all()
        )
        if count >= MAX_WATCHLISTS:
            raise HinaaError(
                "WATCHLIST_LIMIT",
                f"At most {MAX_WATCHLISTS} watchlists are allowed.",
                409,
                False,
                True,
            )
        row = NewsWatchlist(
            user_id=user_id,
            name=data.name,
            topics=json.dumps(data.topics),
            keywords=json.dumps(data.keywords),
            sources=json.dumps(data.sources),
            cadence=data.cadence,
            daily_hour=data.dailyHour,
            enabled=data.enabled,
            next_run_at=next_run_after(data.cadence, data.dailyHour, datetime.now(UTC))
            if data.enabled
            else None,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return watchlist_public(row)


def list_watchlists(settings: Settings | None, user_id: str) -> dict[str, Any]:
    with _session(settings)() as session:
        rows = session.scalars(
            select(NewsWatchlist)
            .where(NewsWatchlist.user_id == user_id)
            .order_by(NewsWatchlist.created_at, NewsWatchlist.id)
        ).all()
        return {"items": [watchlist_public(r) for r in rows], "total": len(rows)}


def get_watchlist(settings: Settings | None, user_id: str, watchlist_id: str) -> dict[str, Any]:
    with _session(settings)() as session:
        return watchlist_public(_owned_watchlist(session, user_id, watchlist_id))


def update_watchlist(
    settings: Settings | None, user_id: str, watchlist_id: str, patch: WatchlistPatch
) -> dict[str, Any]:
    with _session(settings)() as session:
        row = _owned_watchlist(session, user_id, watchlist_id)
        for field in patch.model_fields_set:
            value = getattr(patch, field)
            if field in ("topics", "keywords", "sources"):
                setattr(row, field, json.dumps(value))
            elif field == "dailyHour":
                row.daily_hour = value
            else:
                setattr(row, field, value)
        row.next_run_at = (
            next_run_after(row.cadence, row.daily_hour, datetime.now(UTC)) if row.enabled else None
        )
        session.commit()
        session.refresh(row)
        return watchlist_public(row)


def delete_watchlist(settings: Settings | None, user_id: str, watchlist_id: str) -> None:
    with _session(settings)() as session:
        session.delete(_owned_watchlist(session, user_id, watchlist_id))
        for digest in session.scalars(
            select(NewsDigest).where(
                NewsDigest.user_id == user_id, NewsDigest.watchlist_id == watchlist_id
            )
        ):
            session.delete(digest)
        session.commit()


def latest_digests(
    settings: Settings | None, user_id: str, *, watchlist_id: str | None = None, limit: int = 10
) -> dict[str, Any]:
    with _session(settings)() as session:
        query = select(NewsDigest).where(NewsDigest.user_id == user_id)
        if watchlist_id:
            query = query.where(NewsDigest.watchlist_id == watchlist_id)
        rows = session.scalars(
            query.order_by(NewsDigest.created_at.desc(), NewsDigest.id).limit(limit)
        ).all()
        return {"items": [digest_public(r) for r in rows], "total": len(rows)}


# ---- pipeline ---------------------------------------------------------------


async def exa_search(query: str, limit: int) -> list[Article]:
    """Search articles through Exa when configured; [] otherwise."""
    from ..tools.exa_tool import ExaClient

    client = ExaClient()
    if not client.is_configured:
        return []
    response = await client.search(query, num_results=limit, highlights=True)
    articles = []
    for item in response.get("results", []):
        url = canonicalize_url(str(item.get("url") or ""))
        if not url:
            continue
        published = None
        raw = item.get("published_date")
        if raw:
            try:
                published = _aware(datetime.fromisoformat(str(raw).replace("Z", "+00:00")))
            except ValueError:
                published = None
        articles.append(
            Article(
                title=str(item.get("title") or url),
                url=url,
                source=str(item.get("domain") or ""),
                published=published,
                summary=str(item.get("snippet") or "")[:600],
                origin="search",
            )
        )
    return articles


async def gather(
    row_data: dict[str, Any],
    *,
    http: httpx.AsyncClient,
    search: SearchFn | None,
) -> tuple[list[Article], list[str]]:
    articles: list[Article] = []
    warnings: list[str] = []
    for url in row_data["sources"]:
        try:
            articles.extend(await fetch_feed(http, url))
        except Exception as error:
            warnings.append(f"Feed {url} failed: {str(error)[:120]}")
    queries = [*row_data["topics"], *row_data["keywords"]]
    if search is not None:
        for query in queries[:6]:
            try:
                articles.extend(await search(query, 8))
            except Exception as error:
                warnings.append(f"Search {query!r} failed: {str(error)[:120]}")
    elif queries and not row_data["sources"]:
        warnings.append("No search provider is configured and the watchlist has no feeds.")
    return articles, warnings


def _recent_filter(articles: list[Article], queries: list[str], now: datetime) -> list[Article]:
    kept = []
    for a in articles:
        if a.published is not None and now - a.published > MAX_AGE:
            continue
        # Feeds carry everything a publisher posts; search results were already query-matched.
        if a.origin == "feed" and queries and relevance(a, queries) == 0:
            continue
        kept.append(a)
    return kept


async def run_watchlist(
    settings: Settings | None,
    user_id: str,
    watchlist_id: str,
    *,
    http: httpx.AsyncClient | None = None,
    search: SearchFn | None = None,
    summarizer: Summarizer | None = None,
    deliverers: list[delivery.Deliverer] | None = None,
    now: datetime | None = None,
    use_defaults: bool = True,
) -> dict[str, Any]:
    """Run one watchlist now. Returns {"digest": dict|None, "warnings": [...], "deliveries": [...]}."""
    active = settings or get_settings()
    moment = now or datetime.now(UTC)
    with _session(active)() as session:
        data = watchlist_public(_owned_watchlist(session, user_id, watchlist_id))
        seen: set[str] = set()
        for previous in session.scalars(
            select(NewsDigest.sources)
            .where(NewsDigest.user_id == user_id, NewsDigest.watchlist_id == watchlist_id)
            .order_by(NewsDigest.created_at.desc())
            .limit(SEEN_DIGESTS)
        ):
            seen.update(json.loads(previous or "[]"))

    if use_defaults:
        if search is None and active.exa_configured:
            search = exa_search
        if summarizer is None:
            summarizer = default_summarizer(active)
    if not data["sources"] and search is None:
        raise HinaaError(
            "NEWS_NO_SOURCES",
            "This watchlist has no feeds and no search provider is configured. Add an RSS/Atom feed or set EXA_API_KEY.",
            409,
            False,
            True,
        )

    queries = [*data["topics"], *data["keywords"]]
    owns_client = http is None
    client = http or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
    try:
        articles, warnings = await gather(data, http=client, search=search)
    finally:
        if owns_client:
            await client.aclose()

    articles = _recent_filter(articles, queries, moment)
    fresh = [a for a in articles if (canonicalize_url(a.url) or a.url) not in seen]
    skipped_seen = len(articles) - len(fresh)
    ranked = rank(dedupe(rank(fresh, queries, moment)), queries, moment)
    result: dict[str, Any] = {
        "digest": None,
        "warnings": warnings,
        "deliveries": [],
        "skippedSeen": skipped_seen,
    }

    with _session(active)() as session:
        row = _owned_watchlist(session, user_id, watchlist_id)
        row.last_run_at = moment
        row.next_run_at = (
            next_run_after(row.cadence, row.daily_hour, moment) if row.enabled else None
        )
        digest_row = None
        if ranked:
            items, generated_by = await build_items(ranked, summarizer)
            sources = sorted(fetched_urls(ranked))
            validate_items(items, set(sources))  # last gate before anything is saved
            stamp = moment.astimezone(NEPAL_TZ).strftime("%d %b %H:%M")
            digest_row = NewsDigest(
                user_id=user_id,
                watchlist_id=watchlist_id,
                title=f"{row.name} — {stamp} NPT",
                items=json.dumps(items, ensure_ascii=False),
                sources=json.dumps(sources),
                generated_by=generated_by,
                article_count=len(ranked),
                created_at=moment,
            )
            session.add(digest_row)
        session.commit()
        if digest_row is not None:
            session.refresh(digest_row)
            result["digest"] = digest_public(digest_row)

    if result["digest"] is not None:
        result["deliveries"] = await delivery.deliver_all(user_id, result["digest"], deliverers)
    return result


def advance_after_failure(
    settings: Settings | None, user_id: str, watchlist_id: str, moment: datetime
) -> None:
    """A watchlist that keeps failing must not be retried every tick."""
    with _session(settings)() as session:
        row = _owned_watchlist(session, user_id, watchlist_id)
        row.next_run_at = next_run_after(row.cadence, row.daily_hour, moment)
        session.commit()


async def run_now_for_user(
    settings: Settings | None, user_id: str, watchlist_id: str | None = None, **kwargs: Any
) -> list[dict[str, Any]]:
    """Run one watchlist, or every enabled one of this user."""
    if watchlist_id:
        return [await run_watchlist(settings, user_id, watchlist_id, **kwargs)]
    runs = []
    for item in list_watchlists(settings, user_id)["items"]:
        if item["enabled"]:
            runs.append(await run_watchlist(settings, user_id, item["id"], **kwargs))
    return runs

# ruff: noqa: E501
