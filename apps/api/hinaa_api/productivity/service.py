"""Persistence and maths for the productivity trackers. Every query filters on user_id."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..persistence.db import get_session_factory
from ..persistence.orm import ContentPost, Project, SalesRecord
from .schemas import (
    ContentPostCreate,
    ContentPostPatch,
    ProjectCreate,
    ProjectPatch,
    SalesRecordCreate,
    SalesRecordPatch,
)

MAX_PAGE = 200


def session_factory(settings: Settings | None) -> Callable[[], Session]:
    return get_session_factory(settings or get_settings())


def default_currency(settings: Settings | None) -> str:
    return (settings or get_settings()).productivity_currency.upper()


def _not_found(kind: str) -> HinaaError:
    return HinaaError(f"{kind.upper()}_NOT_FOUND", f"There is no such {kind} of yours.", 404)


def _money(value: Decimal | float | int) -> float:
    return float(Decimal(value).quantize(Decimal("0.01")))


def monday_of(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _split_tags(raw: str) -> list[str]:
    return [t for t in (raw or "").split(",") if t]


def _owned(session: Session, model: Any, user_id: str, row_id: str, kind: str) -> Any:
    row = session.scalar(select(model).where(model.id == row_id, model.user_id == user_id))
    if row is None:
        raise _not_found(kind)
    return row


# ---- content posts ----------------------------------------------------------

def post_public(row: ContentPost) -> dict[str, Any]:
    return {
        "id": row.id,
        "platform": row.platform,
        "title": row.title,
        "caption": row.caption,
        "scheduledFor": row.scheduled_for.isoformat(timespec="minutes") if row.scheduled_for else None,
        "status": row.status,
        "tags": _split_tags(row.tags),
        "notes": row.notes,
        "mediaPath": row.media_path,
        "publishPrivacy": row.publish_privacy,
        "externalId": row.external_id,
        "externalUrl": row.external_url,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


def _tag_string(tags: list[str]) -> str:
    seen: dict[str, None] = {}
    for tag in tags:
        seen.setdefault(tag.replace(",", " ").strip(), None)
    return ",".join(t for t in seen if t)


def create_post(settings: Settings | None, user_id: str, data: ContentPostCreate) -> dict[str, Any]:
    row = ContentPost(
        user_id=user_id,
        platform=data.platform,
        title=data.title,
        caption=data.caption,
        scheduled_for=data.scheduledFor,
        status=data.status,
        tags=_tag_string(data.tags),
        notes=data.notes,
        media_path=data.mediaPath,
        publish_privacy=data.publishPrivacy,
    )
    with session_factory(settings)() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return post_public(row)


def get_post(settings: Settings | None, user_id: str, post_id: str) -> dict[str, Any]:
    with session_factory(settings)() as session:
        return post_public(_owned(session, ContentPost, user_id, post_id, "post"))


def update_post(
    settings: Settings | None, user_id: str, post_id: str, patch: ContentPostPatch
) -> dict[str, Any]:
    with session_factory(settings)() as session:
        row = _owned(session, ContentPost, user_id, post_id, "post")
        for field in patch.model_fields_set:
            value = getattr(patch, field)
            if field == "scheduledFor":
                row.scheduled_for = value
            elif field == "tags":
                row.tags = _tag_string(value)
            elif field == "mediaPath":
                row.media_path = value
            elif field == "publishPrivacy":
                row.publish_privacy = value
            else:
                setattr(row, field, value)
        session.commit()
        session.refresh(row)
        return post_public(row)


def delete_post(settings: Settings | None, user_id: str, post_id: str) -> None:
    with session_factory(settings)() as session:
        session.delete(_owned(session, ContentPost, user_id, post_id, "post"))
        session.commit()


def list_posts(
    settings: Settings | None,
    user_id: str,
    *,
    status: str | None = None,
    platform: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_PAGE))
    query = select(ContentPost).where(ContentPost.user_id == user_id)
    if status:
        query = query.where(ContentPost.status == status)
    if platform:
        query = query.where(ContentPost.platform == platform)
    with session_factory(settings)() as session:
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.scalars(
            query.order_by(
                ContentPost.scheduled_for.is_(None), ContentPost.scheduled_for, ContentPost.created_at
            )
            .limit(limit)
            .offset(max(0, offset))
        ).all()
        return {"items": [post_public(r) for r in rows], "total": total, "limit": limit, "offset": offset}


def find_posts_by_title(settings: Settings | None, user_id: str, title: str) -> list[dict[str, Any]]:
    needle = title.strip().lower()
    with session_factory(settings)() as session:
        rows = session.scalars(
            select(ContentPost)
            .where(ContentPost.user_id == user_id, func.lower(ContentPost.title).contains(needle))
            .order_by(ContentPost.scheduled_for.is_(None), ContentPost.scheduled_for)
            .limit(10)
        ).all()
        exact = [r for r in rows if r.title.lower() == needle]
        return [post_public(r) for r in (exact or rows)]


def week_view(settings: Settings | None, user_id: str, week_start: date | None = None) -> dict[str, Any]:
    start = week_start or monday_of(date.today())
    begin = datetime.combine(start, time.min)
    end = begin + timedelta(days=7)
    with session_factory(settings)() as session:
        rows = session.scalars(
            select(ContentPost)
            .where(
                ContentPost.user_id == user_id,
                ContentPost.scheduled_for >= begin,
                ContentPost.scheduled_for < end,
            )
            .order_by(ContentPost.scheduled_for)
        ).all()
    by_day: dict[date, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_day[row.scheduled_for.date()].append(post_public(row))
    days = []
    for offset in range(7):
        day = start + timedelta(days=offset)
        days.append({"date": day.isoformat(), "weekday": day.strftime("%A"), "posts": by_day.get(day, [])})
    return {
        "weekStart": start.isoformat(),
        "weekEnd": (start + timedelta(days=6)).isoformat(),
        "total": len(rows),
        "days": days,
    }


# ---- sales ------------------------------------------------------------------

def sale_public(row: SalesRecord) -> dict[str, Any]:
    return {
        "id": row.id,
        "occurredOn": row.occurred_on.isoformat(),
        "amount": _money(row.amount),
        "currency": row.currency,
        "source": row.source,
        "customer": row.customer,
        "product": row.product,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
    }


def create_sale(settings: Settings | None, user_id: str, data: SalesRecordCreate) -> dict[str, Any]:
    row = SalesRecord(
        user_id=user_id,
        occurred_on=data.occurredOn or date.today(),
        amount=data.amount,
        currency=data.currency or default_currency(settings),
        source=data.source,
        customer=data.customer,
        product=data.product,
        notes=data.notes,
    )
    with session_factory(settings)() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return sale_public(row)


def get_sale(settings: Settings | None, user_id: str, sale_id: str) -> dict[str, Any]:
    with session_factory(settings)() as session:
        return sale_public(_owned(session, SalesRecord, user_id, sale_id, "sale"))


_SALE_COLUMNS = {
    "occurredOn": "occurred_on",
    "amount": "amount",
    "currency": "currency",
    "source": "source",
    "customer": "customer",
    "product": "product",
    "notes": "notes",
}


def update_sale(
    settings: Settings | None, user_id: str, sale_id: str, patch: SalesRecordPatch
) -> dict[str, Any]:
    with session_factory(settings)() as session:
        row = _owned(session, SalesRecord, user_id, sale_id, "sale")
        for field in patch.model_fields_set:
            setattr(row, _SALE_COLUMNS[field], getattr(patch, field))
        session.commit()
        session.refresh(row)
        return sale_public(row)


def delete_sale(settings: Settings | None, user_id: str, sale_id: str) -> None:
    with session_factory(settings)() as session:
        session.delete(_owned(session, SalesRecord, user_id, sale_id, "sale"))
        session.commit()


def list_sales(
    settings: Settings | None,
    user_id: str,
    *,
    start: date | None = None,
    end: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_PAGE))
    query = select(SalesRecord).where(SalesRecord.user_id == user_id)
    if start:
        query = query.where(SalesRecord.occurred_on >= start)
    if end:
        query = query.where(SalesRecord.occurred_on <= end)
    with session_factory(settings)() as session:
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.scalars(
            query.order_by(SalesRecord.occurred_on.desc(), SalesRecord.created_at.desc())
            .limit(limit)
            .offset(max(0, offset))
        ).all()
        return {"items": [sale_public(r) for r in rows], "total": total, "limit": limit, "offset": offset}


def period_bounds(period: str, on: date) -> tuple[date, date]:
    """Inclusive first and last day of the day, Monday-week or calendar month holding `on`."""
    if period == "day":
        return on, on
    if period == "week":
        first = monday_of(on)
        return first, first + timedelta(days=6)
    first = on.replace(day=1)
    nxt = (first + timedelta(days=32)).replace(day=1)
    return first, nxt - timedelta(days=1)


def _previous_bounds(period: str, first: date) -> tuple[date, date]:
    if period == "day":
        prev = first - timedelta(days=1)
        return prev, prev
    if period == "week":
        return first - timedelta(days=7), first - timedelta(days=1)
    return period_bounds("month", first - timedelta(days=1))


def sales_summary(
    settings: Settings | None,
    user_id: str,
    *,
    period: str = "week",
    on: date | None = None,
    currency: str | None = None,
) -> dict[str, Any]:
    """Totals for one period, the period before it, and a daily series for a sparkline.

    Only one currency is summed at a time; adding rupees to dollars would be a wrong number.
    """
    today = on or date.today()
    code = (currency or default_currency(settings)).upper()
    first, last = period_bounds(period, today)
    prev_first, prev_last = _previous_bounds(period, first)
    # A single day has no shape, so its sparkline shows the trailing week instead.
    series_first = today - timedelta(days=6) if period == "day" else first
    series_last = today if period == "day" else last
    window_first = min(prev_first, series_first)

    with session_factory(settings)() as session:
        rows = session.scalars(
            select(SalesRecord).where(
                SalesRecord.user_id == user_id,
                SalesRecord.currency == code,
                SalesRecord.occurred_on >= window_first,
                SalesRecord.occurred_on <= max(last, series_last),
            )
        ).all()

    total = Decimal(0)
    count = 0
    previous = Decimal(0)
    channels: dict[str, list[Any]] = {}
    daily: dict[date, Decimal] = defaultdict(Decimal)
    for row in rows:
        if first <= row.occurred_on <= last:
            total += row.amount
            count += 1
            entry = channels.setdefault(row.source or "unspecified", [Decimal(0), 0])
            entry[0] += row.amount
            entry[1] += 1
        if prev_first <= row.occurred_on <= prev_last:
            previous += row.amount
        daily[row.occurred_on] += row.amount

    change = total - previous
    pct = _money(change / previous * 100) if previous > 0 else None
    series = []
    cursor = series_first
    while cursor <= series_last:
        series.append({"date": cursor.isoformat(), "total": _money(daily.get(cursor, Decimal(0)))})
        cursor += timedelta(days=1)
    return {
        "period": period,
        "start": first.isoformat(),
        "end": last.isoformat(),
        "currency": code,
        "total": _money(total),
        "count": count,
        "average": _money(total / count) if count else 0.0,
        "byChannel": [
            {"channel": name, "total": _money(vals[0]), "count": vals[1]}
            for name, vals in sorted(channels.items(), key=lambda kv: -kv[1][0])
        ],
        "trend": {
            "previousTotal": _money(previous),
            "change": _money(change),
            "changePct": pct,
            "direction": "up" if change > 0 else "down" if change < 0 else "flat",
        },
        "series": series,
    }


# ---- projects ---------------------------------------------------------------

def project_public(row: Project) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "status": row.status,
        "priority": row.priority,
        "dueDate": row.due_date.isoformat() if row.due_date else None,
        "progress": row.progress,
        "nextAction": row.next_action,
        "notes": row.notes,
        "createdAt": row.created_at.isoformat() if row.created_at else None,
        "updatedAt": row.updated_at.isoformat() if row.updated_at else None,
    }


_PROJECT_COLUMNS = {
    "name": "name",
    "status": "status",
    "priority": "priority",
    "dueDate": "due_date",
    "progress": "progress",
    "nextAction": "next_action",
    "notes": "notes",
}


def create_project(settings: Settings | None, user_id: str, data: ProjectCreate) -> dict[str, Any]:
    row = Project(
        user_id=user_id,
        name=data.name,
        status=data.status,
        priority=data.priority,
        due_date=data.dueDate,
        progress=data.progress,
        next_action=data.nextAction,
        notes=data.notes,
    )
    with session_factory(settings)() as session:
        session.add(row)
        session.commit()
        session.refresh(row)
        return project_public(row)


def get_project(settings: Settings | None, user_id: str, project_id: str) -> dict[str, Any]:
    with session_factory(settings)() as session:
        return project_public(_owned(session, Project, user_id, project_id, "project"))


def update_project(
    settings: Settings | None, user_id: str, project_id: str, patch: ProjectPatch
) -> dict[str, Any]:
    with session_factory(settings)() as session:
        row = _owned(session, Project, user_id, project_id, "project")
        for field in patch.model_fields_set:
            setattr(row, _PROJECT_COLUMNS[field], getattr(patch, field))
        session.commit()
        session.refresh(row)
        return project_public(row)


def delete_project(settings: Settings | None, user_id: str, project_id: str) -> None:
    with session_factory(settings)() as session:
        session.delete(_owned(session, Project, user_id, project_id, "project"))
        session.commit()


def list_projects(
    settings: Settings | None,
    user_id: str,
    *,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    limit = max(1, min(limit, MAX_PAGE))
    query = select(Project).where(Project.user_id == user_id)
    if status:
        query = query.where(Project.status == status)
    with session_factory(settings)() as session:
        total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = session.scalars(
            query.order_by(Project.due_date.is_(None), Project.due_date, Project.created_at)
            .limit(limit)
            .offset(max(0, offset))
        ).all()
        return {"items": [project_public(r) for r in rows], "total": total, "limit": limit, "offset": offset}


def find_project_by_name(settings: Settings | None, user_id: str, name: str) -> dict[str, Any] | None:
    with session_factory(settings)() as session:
        row = session.scalar(
            select(Project).where(
                Project.user_id == user_id, func.lower(Project.name) == name.strip().lower()
            )
        )
        return project_public(row) if row else None
