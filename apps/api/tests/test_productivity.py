"""Content calendar, sales tracker and projects: REST, isolation, maths and agent tools."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.persistence.db import get_session_factory, reset_session_factory
from hinaa_api.productivity import service
from hinaa_api.tools.registry import registry

ALICE = {"X-HINAA-Dev-User": "alice"}
BOB = {"X-HINAA-Dev-User": "bob"}
BASE = "/v1/productivity"


def _settings(url: str) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=url,
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        HINAA_VMC_PORT=0,
        AZURE_SPEECH_KEY="",
        AZURE_SPEECH_REGION="",
        ELEVENLABS_API_KEY="",
    )


@pytest.fixture
def prod_settings(tmp_path):
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'prod.db').as_posix()}")
    get_session_factory(settings)
    yield settings
    reset_session_factory()


@pytest.fixture
def client(prod_settings):
    with TestClient(create_app(prod_settings)) as test_client:
        yield test_client


def _post(client, headers=ALICE, **overrides):
    body = {"title": "Reel: studio tour", "platform": "instagram", **overrides}
    response = client.post(f"{BASE}/content/posts", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def _sale(client, amount, on, source="instagram", headers=ALICE, **extra):
    response = client.post(
        f"{BASE}/sales/records",
        json={"amount": amount, "occurredOn": on, "source": source, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


# ---- schema -----------------------------------------------------------------

def test_migration_creates_productivity_tables(prod_settings):
    tables = set(inspect(get_session_factory(prod_settings)().get_bind()).get_table_names())
    assert {"content_posts", "sales_records", "projects"} <= tables


def test_anonymous_identity_fails_closed(tmp_path):
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'anon.db').as_posix()}")
    settings = settings.model_copy(update={"persistence_enabled": False})
    with TestClient(create_app(settings)) as anonymous:
        for path in ("/projects", "/sales/summary", "/content/week", "/content/posts"):
            assert anonymous.get(f"{BASE}{path}").status_code == 401, path
    reset_session_factory()


def test_clerk_mode_middleware_protects_the_routes(tmp_path):
    reset_session_factory()
    settings = _settings(f"sqlite+pysqlite:///{(tmp_path / 'clerk.db').as_posix()}")
    settings = settings.model_copy(update={"auth_mode": "clerk"})
    with TestClient(create_app(settings)) as guarded:
        for prefix in ("/v1/productivity", "/api/v1/productivity"):
            assert guarded.get(f"{prefix}/projects").status_code in (401, 503)
            assert guarded.post(f"{prefix}/projects", json={"name": "x"}).status_code in (401, 503)
    reset_session_factory()


# ---- content ----------------------------------------------------------------

def test_content_post_crud(client):
    created = _post(client, scheduledFor="2026-11-10T18:00", status="scheduled", tags=["bts", "bts", "studio"])
    assert created["tags"] == ["bts", "studio"]
    assert created["scheduledFor"] == "2026-11-10T18:00"

    fetched = client.get(f"{BASE}/content/posts/{created['id']}", headers=ALICE).json()
    assert fetched["title"] == "Reel: studio tour"

    patched = client.patch(
        f"{BASE}/content/posts/{created['id']}",
        json={"status": "published", "scheduledFor": None, "caption": "Hello"},
        headers=ALICE,
    ).json()
    assert patched["status"] == "published" and patched["scheduledFor"] is None
    assert patched["caption"] == "Hello" and patched["title"] == "Reel: studio tour"

    assert client.delete(f"{BASE}/content/posts/{created['id']}", headers=ALICE).status_code == 204
    assert client.get(f"{BASE}/content/posts/{created['id']}", headers=ALICE).status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"title": "", "platform": "instagram"},
        {"title": "x", "platform": "myspace"},
        {"title": "x", "status": "someday"},
        {"title": "x" * 201},
    ],
)
def test_content_post_validation(client, body):
    assert client.post(f"{BASE}/content/posts", json=body, headers=ALICE).status_code == 422


def test_patch_rejects_null_for_required_field(client):
    post = _post(client)
    response = client.patch(f"{BASE}/content/posts/{post['id']}", json={"title": None}, headers=ALICE)
    assert response.status_code == 422


def test_week_view_groups_seven_days(client):
    _post(client, title="Mon A", scheduledFor="2026-11-09T09:00", status="scheduled")
    _post(client, title="Mon B", scheduledFor="2026-11-09T18:30", status="scheduled")
    _post(client, title="Sun", scheduledFor="2026-11-15T23:59", status="draft")
    _post(client, title="Next week", scheduledFor="2026-11-16T00:00")
    _post(client, title="Prev week", scheduledFor="2026-11-08T23:59")
    _post(client, title="Unscheduled idea")

    # Any day of the week snaps to its Monday.
    week = client.get(f"{BASE}/content/week", params={"week_start": "2026-11-12"}, headers=ALICE).json()
    assert week["weekStart"] == "2026-11-09" and week["weekEnd"] == "2026-11-15"
    assert [d["date"] for d in week["days"]][0] == "2026-11-09" and len(week["days"]) == 7
    assert week["total"] == 3
    assert [p["title"] for p in week["days"][0]["posts"]] == ["Mon A", "Mon B"]
    assert [p["title"] for p in week["days"][6]["posts"]] == ["Sun"]
    assert all(not d["posts"] for d in week["days"][1:6])


def test_list_posts_filters_and_paginates(client):
    for index in range(5):
        _post(client, title=f"Post {index}", platform="tiktok" if index % 2 else "x")
    page = client.get(f"{BASE}/content/posts", params={"limit": 2, "offset": 2}, headers=ALICE).json()
    assert page["total"] == 5 and len(page["items"]) == 2 and page["offset"] == 2
    only = client.get(f"{BASE}/content/posts", params={"platform": "tiktok"}, headers=ALICE).json()
    assert only["total"] == 2
    assert client.get(f"{BASE}/content/posts", params={"limit": 500}, headers=ALICE).status_code == 422


# ---- isolation --------------------------------------------------------------

def test_users_cannot_see_or_touch_each_others_data(client):
    post = _post(client, scheduledFor="2026-11-10T10:00")
    sale = _sale(client, 500, "2026-11-10")
    project = client.post(f"{BASE}/projects", json={"name": "Launch"}, headers=ALICE).json()

    for path in (
        f"/content/posts/{post['id']}",
        f"/sales/records/{sale['id']}",
        f"/projects/{project['id']}",
    ):
        assert client.get(f"{BASE}{path}", headers=BOB).status_code == 404
        assert client.patch(f"{BASE}{path}", json={}, headers=BOB).status_code == 404
        assert client.delete(f"{BASE}{path}", headers=BOB).status_code == 404
        assert client.get(f"{BASE}{path}", headers=ALICE).status_code == 200

    assert client.get(f"{BASE}/content/posts", headers=BOB).json()["total"] == 0
    assert client.get(f"{BASE}/sales/records", headers=BOB).json()["total"] == 0
    assert client.get(f"{BASE}/projects", headers=BOB).json()["total"] == 0
    assert client.get(f"{BASE}/content/week", params={"week_start": "2026-11-09"}, headers=BOB).json()["total"] == 0
    summary = client.get(f"{BASE}/sales/summary", params={"period": "month", "on": "2026-11-10"}, headers=BOB).json()
    assert summary["total"] == 0 and summary["count"] == 0


# ---- sales ------------------------------------------------------------------

def test_sales_defaults_and_validation(client):
    sale = client.post(f"{BASE}/sales/records", json={"amount": "1250.50"}, headers=ALICE).json()
    assert sale["currency"] == "NPR" and sale["amount"] == 1250.5
    assert sale["occurredOn"] == date.today().isoformat()
    usd = client.post(f"{BASE}/sales/records", json={"amount": 10, "currency": "usd"}, headers=ALICE).json()
    assert usd["currency"] == "USD"
    for bad in ({"amount": 0}, {"amount": -5}, {"amount": "abc"}, {"amount": 1, "currency": "RUPEES"}):
        assert client.post(f"{BASE}/sales/records", json=bad, headers=ALICE).status_code == 422


def test_sales_summary_math_and_trend(client):
    # Week of 2026-11-09 (Mon) .. 2026-11-15; previous week 2026-11-02 .. 2026-11-08.
    _sale(client, 100, "2026-11-09", source="instagram")
    _sale(client, 300, "2026-11-11", source="walk-in")
    _sale(client, 100, "2026-11-11", source="instagram")
    _sale(client, 250, "2026-11-04", source="instagram")
    _sale(client, 999, "2026-11-04", source="instagram", currency="USD")
    _sale(client, 5000, "2026-10-20")

    week = client.get(f"{BASE}/sales/summary", params={"period": "week", "on": "2026-11-12"}, headers=ALICE).json()
    assert (week["start"], week["end"]) == ("2026-11-09", "2026-11-15")
    assert week["total"] == 500 and week["count"] == 3 and week["average"] == pytest.approx(166.67)
    assert week["byChannel"] == [
        {"channel": "walk-in", "total": 300.0, "count": 1},
        {"channel": "instagram", "total": 200.0, "count": 2},
    ]
    assert week["trend"]["previousTotal"] == 250 and week["trend"]["changePct"] == 100.0
    assert week["trend"]["direction"] == "up"
    assert len(week["series"]) == 7
    assert [point["total"] for point in week["series"]][:3] == [100.0, 0.0, 400.0]

    day = client.get(f"{BASE}/sales/summary", params={"period": "day", "on": "2026-11-11"}, headers=ALICE).json()
    assert day["total"] == 400 and day["count"] == 2
    assert day["trend"]["previousTotal"] == 0 and day["trend"]["changePct"] is None
    assert len(day["series"]) == 7 and day["series"][-1]["date"] == "2026-11-11"

    month = client.get(f"{BASE}/sales/summary", params={"period": "month", "on": "2026-11-20"}, headers=ALICE).json()
    assert (month["start"], month["end"]) == ("2026-11-01", "2026-11-30")
    assert month["total"] == 750 and month["trend"]["previousTotal"] == 5000
    assert month["trend"]["direction"] == "down" and month["trend"]["changePct"] == -85.0
    assert len(month["series"]) == 30

    usd = client.get(
        f"{BASE}/sales/summary", params={"period": "month", "on": "2026-11-20", "currency": "usd"}, headers=ALICE
    ).json()
    assert usd["currency"] == "USD" and usd["total"] == 999


def test_summary_period_bounds_cross_year():
    assert service.period_bounds("month", date(2026, 12, 31)) == (date(2026, 12, 1), date(2026, 12, 31))
    assert service.period_bounds("week", date(2027, 1, 1)) == (date(2026, 12, 28), date(2027, 1, 3))


def test_sales_update_delete_and_range(client):
    sale = _sale(client, 100, "2026-11-01")
    _sale(client, 50, "2026-12-01")
    patched = client.patch(f"{BASE}/sales/records/{sale['id']}", json={"amount": 175, "customer": "Sile"}, headers=ALICE)
    assert patched.json()["amount"] == 175 and patched.json()["customer"] == "Sile"
    ranged = client.get(f"{BASE}/sales/records", params={"start": "2026-11-01", "end": "2026-11-30"}, headers=ALICE)
    assert ranged.json()["total"] == 1
    assert client.delete(f"{BASE}/sales/records/{sale['id']}", headers=ALICE).status_code == 204


# ---- projects ---------------------------------------------------------------

def test_project_crud_and_validation(client):
    created = client.post(
        f"{BASE}/projects",
        json={"name": "Website", "status": "active", "priority": "high", "progress": 40, "dueDate": "2026-12-01"},
        headers=ALICE,
    ).json()
    assert created["progress"] == 40 and created["dueDate"] == "2026-12-01"
    patched = client.patch(
        f"{BASE}/projects/{created['id']}", json={"progress": 100, "status": "done", "dueDate": None}, headers=ALICE
    ).json()
    assert patched["status"] == "done" and patched["dueDate"] is None
    for bad in ({"name": "x", "progress": 101}, {"name": "x", "status": "stuck"}, {"name": "x", "priority": "urgent"}):
        assert client.post(f"{BASE}/projects", json=bad, headers=ALICE).status_code == 422
    assert client.get(f"{BASE}/projects", params={"status": "done"}, headers=ALICE).json()["total"] == 1
    assert client.get(f"{BASE}/projects", params={"status": "active"}, headers=ALICE).json()["total"] == 0
    assert client.delete(f"{BASE}/projects/{created['id']}", headers=ALICE).status_code == 204


def test_api_prefix_alias_is_mounted(client):
    assert client.get("/api/v1/productivity/projects", headers=ALICE).status_code == 200


# ---- agent tools ------------------------------------------------------------

TOOL_NAMES = [
    "plan_content_post",
    "list_content_week",
    "update_content_post",
    "log_sale",
    "sales_summary",
    "upsert_project",
    "list_projects",
    "delete_content_post",
    "delete_project",
]


def test_tools_are_registered_with_expected_risk():
    from hinaa_api.tools import load_all_tools

    load_all_tools()
    for name in TOOL_NAMES:
        assert registry.get_tool(name) is not None, name
    for name in ("list_content_week", "sales_summary", "list_projects"):
        tool = registry.get_tool(name)
        assert tool.risk_level == "low" and tool.is_read_only and not tool.requires_confirmation
    for name in ("plan_content_post", "update_content_post", "log_sale", "upsert_project"):
        tool = registry.get_tool(name)
        assert tool.risk_level == "medium" and not tool.requires_confirmation
    for name in ("delete_content_post", "delete_project"):
        tool = registry.get_tool(name)
        assert tool.requires_confirmation and tool.is_destructive


def _call(tool_name, /, **params):
    return asyncio.run(registry._handlers[tool_name](params))


def test_tools_run_end_to_end(prod_settings):
    planned = _call(
        "plan_content_post", userId="alice", title="Launch teaser", platform="tiktok",
        scheduled_for="2026-11-10T18:00", tags="launch, teaser",
    )
    assert planned["status"] == "success" and planned["post"]["status"] == "scheduled"
    post_id = planned["post"]["id"]

    week = _call("list_content_week", userId="alice", week_start="2026-11-09")
    assert week["total"] == 1 and week["days"][0]["posts"][0]["title"] == "Launch teaser"
    assert _call("list_content_week", userId="bob", week_start="2026-11-09")["total"] == 0

    moved = _call("update_content_post", userId="alice", match_title="launch", status="published", new_title="Launched")
    assert moved["post"]["status"] == "published" and moved["post"]["title"] == "Launched"
    assert _call("update_content_post", userId="bob", post_id=post_id, status="draft")["status"] == "failed"
    assert _call("update_content_post", userId="alice", post_id=post_id)["status"] == "failed"
    assert _call("plan_content_post", userId="alice", title="x", platform="myspace")["status"] == "failed"

    today = date.today().isoformat()
    sale = _call("log_sale", userId="alice", amount=1500, source="instagram", date=today)
    assert sale["status"] == "success" and "NPR 1,500.00" in sale["summaryText"]
    assert _call("log_sale", userId="alice", amount=-3)["status"] == "failed"
    summary = _call("sales_summary", userId="alice", period="day")
    assert summary["summary"]["total"] == 1500 and summary["summary"]["byChannel"][0]["channel"] == "instagram"
    assert _call("sales_summary", userId="alice", period="year")["status"] == "failed"
    assert _call("sales_summary", userId="bob", period="day")["summary"]["total"] == 0

    created = _call("upsert_project", userId="alice", name="Website", status="active", progress=20)
    assert created["summaryText"].startswith("Created")
    updated = _call("upsert_project", userId="alice", name="website", progress=60, next_action="Ship pricing page")
    assert updated["summaryText"].startswith("Updated") and updated["project"]["progress"] == 60
    assert updated["project"]["id"] == created["project"]["id"]
    assert _call("list_projects", userId="alice", status="active")["total"] == 1
    assert _call("list_projects", userId="bob")["total"] == 0
    assert _call("upsert_project", userId="alice", name="Bad", progress=500)["status"] == "failed"

    assert _call("delete_content_post", userId="bob", post_id=post_id)["status"] == "failed"
    assert _call("delete_content_post", userId="alice", match_title="Launched")["status"] == "success"
    assert _call("delete_project", userId="alice", name="Website")["status"] == "success"
    assert _call("list_projects", userId="alice")["total"] == 0


def test_ambiguous_title_is_not_guessed(prod_settings):
    _call("plan_content_post", userId="alice", title="Reel one")
    _call("plan_content_post", userId="alice", title="Reel two")
    result = _call("update_content_post", userId="alice", match_title="reel", status="draft")
    assert result["status"] == "failed" and "More than one" in result["message"]


def test_week_default_is_current_monday(prod_settings):
    today = date.today()
    week = service.week_view(prod_settings, "alice")
    assert week["weekStart"] == (today - timedelta(days=today.weekday())).isoformat()
