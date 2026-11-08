"""Let Hina run the content calendar, sales log and project list by conversation.

The owner's identity is injected server-side as `userId`; the model never picks it.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from pydantic import ValidationError

from ..errors import HinaaError
from ..productivity import service
from ..productivity.schemas import (
    ContentPostCreate,
    ContentPostPatch,
    ProjectCreate,
    ProjectPatch,
    SalesRecordCreate,
)
from .registry import ToolDefinition, registry


def _failed(message: str, code: str = "PRODUCTIVITY_INVALID") -> dict[str, Any]:
    return {"status": "failed", "code": code, "message": message}


def _validation_message(error: ValidationError) -> str:
    first = error.errors()[0]
    field = ".".join(str(part) for part in first["loc"]) or "input"
    return f"I could not use {field}: {first['msg']}."


async def _guarded(params: dict[str, Any], run: Callable[[str], dict[str, Any]]) -> dict[str, Any]:
    try:
        return {"status": "success", **run(str(params.get("userId") or "anonymous"))}
    except ValidationError as error:
        return _failed(_validation_message(error))
    except HinaaError as error:
        return _failed(error.message, error.code)
    except ValueError as error:
        return _failed(str(error))


def _fields(params: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    """Pick supplied tool arguments, renamed to API field names; empty strings count as absent."""
    out: dict[str, Any] = {}
    for tool_key, field in mapping.items():
        value = params.get(tool_key)
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        out[field] = value
    return out


def _tags(value: Any) -> Any:
    if isinstance(value, str):
        return [t.strip() for t in value.split(",") if t.strip()]
    return value


def _compact_post(post: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": post["id"],
        "title": post["title"],
        "platform": post["platform"],
        "at": post["scheduledFor"],
        "status": post["status"],
    }


def _describe_post(post: dict[str, Any]) -> str:
    when = post["scheduledFor"].replace("T", " ") if post["scheduledFor"] else "unscheduled"
    return f"{post['title']} ({post['platform']}, {post['status']}, {when})"


_POST_FIELDS = {
    "title": "title",
    "platform": "platform",
    "caption": "caption",
    "scheduled_for": "scheduledFor",
    "status": "status",
    "tags": "tags",
    "notes": "notes",
}


async def plan_content_post(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        data = _fields(params, _POST_FIELDS)
        if "tags" in data:
            data["tags"] = _tags(data["tags"])
        if "scheduledFor" in data:
            data.setdefault("status", "scheduled")
        post = service.create_post(None, user_id, ContentPostCreate(**data))
        return {"post": _compact_post(post), "summaryText": f"Planned {_describe_post(post)}."}

    return await _guarded(params, run)


async def list_content_week(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        raw = str(params.get("week_start") or "").strip()
        start = service.monday_of(date.fromisoformat(raw)) if raw else None
        week = service.week_view(None, user_id, start)
        days = [
            {"date": d["date"], "weekday": d["weekday"], "posts": [_compact_post(p) for p in d["posts"]]}
            for d in week["days"]
            if d["posts"]
        ]
        return {
            "weekStart": week["weekStart"],
            "weekEnd": week["weekEnd"],
            "total": week["total"],
            "days": days,
            "summaryText": f"{week['total']} post(s) planned for {week['weekStart']} to {week['weekEnd']}.",
        }

    return await _guarded(params, run)


def _resolve_post_id(user_id: str, params: dict[str, Any]) -> str:
    post_id = str(params.get("post_id") or "").strip()
    if post_id:
        return post_id
    title = str(params.get("match_title") or "").strip()
    if not title:
        raise ValueError("Tell me which post: give its post_id or match_title.")
    matches = service.find_posts_by_title(None, user_id, title)
    if not matches:
        raise HinaaError("POST_NOT_FOUND", f"I could not find a post called '{title}'.", 404)
    if len(matches) > 1:
        names = "; ".join(f"{m['title']} [{m['id']}]" for m in matches[:5])
        raise ValueError(f"More than one post matches '{title}': {names}. Use a post_id.")
    return matches[0]["id"]


async def update_content_post(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        post_id = _resolve_post_id(user_id, params)
        mapping = {**{k: v for k, v in _POST_FIELDS.items() if k != "title"}, "new_title": "title"}
        data = _fields(params, mapping)
        if "tags" in data:
            data["tags"] = _tags(data["tags"])
        if not data:
            raise ValueError("Nothing to change: give a new platform, time, status, caption, tags or notes.")
        post = service.update_post(None, user_id, post_id, ContentPostPatch(**data))
        return {"post": _compact_post(post), "summaryText": f"Updated {_describe_post(post)}."}

    return await _guarded(params, run)


async def delete_content_post(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        post_id = _resolve_post_id(user_id, params)
        post = service.get_post(None, user_id, post_id)
        service.delete_post(None, user_id, post_id)
        return {"deletedId": post_id, "summaryText": f"Deleted {_describe_post(post)}."}

    return await _guarded(params, run)


async def log_sale(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        data = _fields(
            params,
            {
                "amount": "amount",
                "date": "occurredOn",
                "currency": "currency",
                "source": "source",
                "customer": "customer",
                "product": "product",
                "notes": "notes",
            },
        )
        sale = service.create_sale(None, user_id, SalesRecordCreate(**data))
        extra = f" via {sale['source']}" if sale["source"] else ""
        return {
            "sale": {
                "id": sale["id"],
                "amount": sale["amount"],
                "currency": sale["currency"],
                "date": sale["occurredOn"],
            },
            "summaryText": f"Logged sale of {sale['currency']} {sale['amount']:,.2f}{extra} on {sale['occurredOn']}.",
        }

    return await _guarded(params, run)


async def sales_summary(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        period = str(params.get("period") or "week").lower()
        if period not in {"day", "week", "month"}:
            raise ValueError("period must be day, week or month.")
        currency = str(params.get("currency") or "").strip() or None
        summary = service.sales_summary(None, user_id, period=period, currency=currency)
        trend = summary["trend"]
        pct = f"{trend['changePct']:+.1f}%" if trend["changePct"] is not None else "no prior sales to compare"
        return {
            "summary": {k: summary[k] for k in ("period", "start", "end", "currency", "total", "count", "byChannel", "trend")},
            "summaryText": (
                f"{period.capitalize()} sales: {summary['currency']} {summary['total']:,.2f} "
                f"from {summary['count']} sale(s) ({pct} vs previous {period})."
            ),
        }

    return await _guarded(params, run)


_PROJECT_FIELDS = {
    "status": "status",
    "priority": "priority",
    "due_date": "dueDate",
    "progress": "progress",
    "next_action": "nextAction",
    "notes": "notes",
}


def _compact_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project["id"],
        "name": project["name"],
        "status": project["status"],
        "priority": project["priority"],
        "progress": project["progress"],
        "due": project["dueDate"],
        "next": project["nextAction"],
    }


async def upsert_project(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        data = _fields(params, _PROJECT_FIELDS)
        project_id = str(params.get("project_id") or "").strip()
        name = str(params.get("name") or "").strip()
        existing = None
        if project_id:
            existing = service.get_project(None, user_id, project_id)
        elif name:
            existing = service.find_project_by_name(None, user_id, name)
        else:
            raise ValueError("A project needs a name.")
        if existing:
            if name and project_id:
                data["name"] = name
            project = service.update_project(None, user_id, existing["id"], ProjectPatch(**data))
            verb = "Updated"
        else:
            project = service.create_project(None, user_id, ProjectCreate(name=name, **data))
            verb = "Created"
        return {
            "project": _compact_project(project),
            "summaryText": f"{verb} project {project['name']} ({project['status']}, {project['progress']}%).",
        }

    return await _guarded(params, run)


async def list_projects(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        status = str(params.get("status") or "").strip().lower() or None
        if status and status not in {"planning", "active", "blocked", "done"}:
            raise ValueError("status must be planning, active, blocked or done.")
        result = service.list_projects(None, user_id, status=status, limit=50)
        return {
            "total": result["total"],
            "projects": [_compact_project(p) for p in result["items"]],
            "summaryText": f"{result['total']} project(s)" + (f" with status {status}." if status else "."),
        }

    return await _guarded(params, run)


async def delete_project(params: dict[str, Any]) -> dict[str, Any]:
    def run(user_id: str) -> dict[str, Any]:
        project_id = str(params.get("project_id") or "").strip()
        if not project_id:
            found = service.find_project_by_name(None, user_id, str(params.get("name") or ""))
            if not found:
                raise HinaaError("PROJECT_NOT_FOUND", "I could not find that project.", 404)
            project_id = found["id"]
        project = service.get_project(None, user_id, project_id)
        service.delete_project(None, user_id, project_id)
        return {"deletedId": project_id, "summaryText": f"Deleted project {project['name']}."}

    return await _guarded(params, run)


def _p(description: str, type_: str = "string") -> dict[str, Any]:
    return {"type": type_, "description": description}


_POST_PROPS = {
    "platform": _p("instagram, tiktok, youtube, x, linkedin, facebook or other."),
    "scheduled_for": _p("Local ISO date-time, e.g. 2026-11-10T18:00."),
    "caption": _p("Post caption text."),
    "status": _p("idea, draft, scheduled or published."),
    "tags": _p("Comma separated tags."),
    "notes": _p("Private notes."),
}

_TOOLS: list[tuple[ToolDefinition, Callable[..., Any]]] = [
    (
        ToolDefinition(
            name="plan_content_post",
            display_name="Plan Content Post",
            description="Add a social-media post or idea to the weekly content calendar.",
            parameters={"title": _p("Short title of the post."), **_POST_PROPS},
            required_parameters=["title"],
            risk_level="medium",
            voice_aliases=["plan a post", "schedule a post", "add to content calendar"],
        ),
        plan_content_post,
    ),
    (
        ToolDefinition(
            name="list_content_week",
            display_name="List Content Week",
            description="Show the posts planned for a week of the content calendar (default: this week).",
            parameters={"week_start": _p("Optional YYYY-MM-DD inside the week wanted.")},
            required_parameters=[],
            risk_level="low",
            is_read_only=True,
            voice_aliases=["content this week", "what am I posting"],
        ),
        list_content_week,
    ),
    (
        ToolDefinition(
            name="update_content_post",
            display_name="Update Content Post",
            description=(
                "Change a calendar post: reschedule, change status, caption, platform, tags. "
                "Identify it by post_id, or by match_title."
            ),
            parameters={
                "post_id": _p("Id of the post."),
                "match_title": _p("Existing title (or part of it) when no post_id is known."),
                "new_title": _p("New title, if renaming."),
                **_POST_PROPS,
            },
            required_parameters=[],
            risk_level="medium",
        ),
        update_content_post,
    ),
    (
        ToolDefinition(
            name="delete_content_post",
            display_name="Delete Content Post",
            description="Permanently remove a post from the content calendar.",
            parameters={"post_id": _p("Id of the post."), "match_title": _p("Existing title when no post_id.")},
            required_parameters=[],
            requires_confirmation=True,
            is_destructive=True,
            risk_level="high",
        ),
        delete_content_post,
    ),
    (
        ToolDefinition(
            name="log_sale",
            display_name="Log Sale",
            description="Record a sale in the sales tracker.",
            parameters={
                "amount": _p("Sale amount as a positive number.", "number"),
                "date": _p("YYYY-MM-DD, defaults to today."),
                "currency": _p("3-letter code; defaults to the configured currency (NPR)."),
                "source": _p("Channel, e.g. instagram, walk-in, website."),
                "customer": _p("Customer name."),
                "product": _p("What was sold."),
                "notes": _p("Notes."),
            },
            required_parameters=["amount"],
            risk_level="medium",
            voice_aliases=["log a sale", "record a sale", "i sold"],
        ),
        log_sale,
    ),
    (
        ToolDefinition(
            name="sales_summary",
            display_name="Sales Summary",
            description="Totals, count, per-channel breakdown and trend versus the previous period.",
            parameters={
                "period": _p("day, week or month (default week)."),
                "currency": _p("3-letter code; defaults to the configured currency."),
            },
            required_parameters=[],
            risk_level="low",
            is_read_only=True,
            voice_aliases=["sales today", "how are sales", "sales summary"],
        ),
        sales_summary,
    ),
    (
        ToolDefinition(
            name="upsert_project",
            display_name="Save Project",
            description=(
                "Create a project, or update the one with the same name (or project_id): "
                "status, priority, due date, progress, next action."
            ),
            parameters={
                "name": _p("Project name (matched case-insensitively)."),
                "project_id": _p("Id of an existing project."),
                "status": _p("planning, active, blocked or done."),
                "priority": _p("low, medium or high."),
                "due_date": _p("YYYY-MM-DD."),
                "progress": _p("0 to 100.", "integer"),
                "next_action": _p("The single next step."),
                "notes": _p("Notes."),
            },
            required_parameters=[],
            risk_level="medium",
            voice_aliases=["add a project", "update project"],
        ),
        upsert_project,
    ),
    (
        ToolDefinition(
            name="list_projects",
            display_name="List Projects",
            description="List projects with status, priority, progress, due date and next action.",
            parameters={"status": _p("Optional filter: planning, active, blocked or done.")},
            required_parameters=[],
            risk_level="low",
            is_read_only=True,
            voice_aliases=["my projects", "project status"],
        ),
        list_projects,
    ),
    (
        ToolDefinition(
            name="delete_project",
            display_name="Delete Project",
            description="Permanently remove a project.",
            parameters={"project_id": _p("Id of the project."), "name": _p("Project name when no id.")},
            required_parameters=[],
            requires_confirmation=True,
            is_destructive=True,
            risk_level="high",
        ),
        delete_project,
    ),
]

for _definition, _handler in _TOOLS:
    registry.register(_definition, _handler)
