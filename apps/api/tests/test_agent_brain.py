"""Agent-brain wiring: MCP tools in the tool list, GitHub active repos, proactive reminder calls."""
from __future__ import annotations

import functools
import json
import uuid
from datetime import datetime, timedelta

import httpx
import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.integrations_hub import github_repos, mcp_agent_tools, mcp_service
from hinaa_api.integrations_hub.mcp_store import McpServerConfig, get_store
from hinaa_api.persistence import migrations
from hinaa_api.persistence.db import get_session_factory, make_engine, reset_session_factory
from hinaa_api.persistence.orm import Base
from hinaa_api.reminder_scheduler import fire_due, place_due_calls
from hinaa_api.telephony import calls
from hinaa_api.tools import github_tools, policy
from hinaa_api.tools.dynamic_tools import sync_dynamic_tools
from hinaa_api.tools.registry import registry
from hinaa_api.tools.reminder import schedule_reminder

TOOL = {
    "name": "lookup",
    "description": "Look a thing up",
    "inputSchema": {
        "type": "object",
        "properties": {"q": {"type": "string", "description": "query"}, "n": {"type": "integer"}},
        "required": ["q"],
    },
}


@pytest.fixture
def hub(monkeypatch, tmp_path):
    monkeypatch.setenv("HINAA_PROJECT_ROOT", str(tmp_path))
    yield
    mcp_agent_tools.sync_mcp_tools()  # store is gone with tmp_path: drops mcp__ entries
    for tool in [t.name for t in registry.get_all_tools() if t.name.startswith("mcp__")]:
        registry.unregister(tool)


def _server(name="demo", *, trusted=False, enabled=True, transport="http", tools=None):
    cfg = McpServerConfig(
        name=name,
        transport=transport,
        url="https://mcp.example/mcp" if transport == "http" else "",
        command="srv" if transport == "stdio" else "",
        trusted=trusted,
        enabled=enabled,
        tools=[TOOL] if tools is None else tools,
    )
    return get_store().upsert(cfg)


def _text_server(payload: str):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(204)
        msg = json.loads(request.content)
        if "id" not in msg:
            return httpx.Response(202)
        if msg["method"] == "initialize":
            return httpx.Response(
                200,
                json={"jsonrpc": "2.0", "id": msg["id"], "result": {"protocolVersion": "2025-06-18", "capabilities": {}}},
                headers={"Mcp-Session-Id": "s"},
            )
        result = {"content": [{"type": "text", "text": payload}]}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": msg["id"], "result": result})

    return httpx.MockTransport(handler)


# --- MCP tools in the agent tool list -------------------------------------------------


def test_mcp_tools_appear_from_cache_with_schema_and_hide_when_disabled(hub):
    _server()
    sync_dynamic_tools()
    tool = registry.get_tool("mcp__demo__lookup")
    assert tool is not None
    assert tool.requires_confirmation is True and tool.risk_level == "high"
    assert set(tool.parameters) == {"q", "n"} and tool.required_parameters == ["q"]
    assert "[MCP server demo]" in tool.description

    _server(enabled=False)
    sync_dynamic_tools()
    assert registry.get_tool("mcp__demo__lookup") is None
    assert "mcp__demo__lookup" not in mcp_agent_tools.names_for_turn("use mcp", always=True)


def test_trusted_server_needs_no_confirmation_and_turn_names_are_scoped(hub):
    _server(trusted=True)
    assert mcp_agent_tools.names_for_turn("hello there", always=False) == ()
    assert mcp_agent_tools.names_for_turn("please lookup the weather", always=False) == ("mcp__demo__lookup",)
    assert mcp_agent_tools.names_for_turn("anything", always=True) == ("mcp__demo__lookup",)
    assert registry.get_tool("mcp__demo__lookup").requires_confirmation is False


async def test_untrusted_tool_refuses_without_user_approval_and_runs_with_it(hub, monkeypatch):
    monkeypatch.setattr(mcp_service, "http_transport", _text_server("found it"))
    _server()
    mcp_agent_tools.sync_mcp_tools()
    handler = registry._handlers["mcp__demo__lookup"]

    with pytest.raises(HinaaError) as denied:
        await handler({"q": "x"})
    assert denied.value.code == "TOOL_CONFIRMATION_REQUIRED"

    token = mcp_agent_tools.set_user_approved(True)
    try:
        out = await handler({"q": "x", "userId": "u"})
    finally:
        mcp_agent_tools.reset_user_approved(token)
    assert out["status"] == "success" and out["untrusted"] is True
    assert "found it" in out["content"] and "<untrusted_mcp_result" in out["content"]


async def test_mcp_result_is_truncated_to_cap(hub, monkeypatch):
    monkeypatch.setattr(mcp_service, "http_transport", _text_server("A" * 50_000))
    _server(trusted=True)
    mcp_agent_tools.sync_mcp_tools()
    out = await registry._handlers["mcp__demo__lookup"]({"q": "x"})
    assert out["truncated"] is True
    assert out["content"].count("A") == mcp_agent_tools.MAX_RESULT_CHARS


def test_stdio_mcp_tools_obey_the_loopback_rule(hub):
    _server("shell", transport="stdio")
    settings = Settings(_env_file=None, HINAA_ALLOW_REMOTE_LOCAL_TOOLS=False)
    assert not policy.decide("mcp__shell__lookup", settings, "hinaa.example.com").permitted
    assert policy.decide("mcp__shell__lookup", settings, "127.0.0.1:8000").permitted
    _server("web")
    assert policy.decide("mcp__web__lookup", settings, "hinaa.example.com").permitted


# --- GitHub active repos -----------------------------------------------------------------


def test_github_repo_resolution_prefers_active_then_default(hub, monkeypatch):
    monkeypatch.setattr(github_tools, "get_settings", lambda: Settings(_env_file=None, HINAA_GITHUB_DEFAULT_REPO="o/default"))
    resolve = github_tools._GithubClient._repo
    assert resolve(None, None) == "o/default"
    github_repos.set_active_repos(["o/one"])
    assert resolve(None, None) == "o/one"
    assert resolve(None, "o/explicit") == "o/explicit"
    github_repos.set_active_repos(["o/one", "o/two"])
    assert resolve(None, None) == "o/default"  # several active: keep the old default fallback

    monkeypatch.setattr(github_tools, "get_settings", lambda: Settings(_env_file=None))
    with pytest.raises(HinaaError) as err:
        resolve(None, None)
    assert err.value.code == "GITHUB_REPO_AMBIGUOUS" and "o/two" in err.value.message


def test_github_tool_description_lists_active_repos(hub):
    github_repos.set_active_repos(["o/one", "o/two"])
    sync_dynamic_tools()
    assert "o/one, o/two" in registry.get_tool("github_list_issues").parameters["repo"]["description"]
    github_repos.set_active_repos(["o/one"])
    sync_dynamic_tools()
    assert "selected repo o/one" in registry.get_tool("github_list_issues").parameters["repo"]["description"]
    github_repos.set_active_repos([])
    sync_dynamic_tools()
    assert "default repo" in registry.get_tool("github_list_issues").parameters["repo"]["description"]


# --- Proactive reminder calls ---------------------------------------------------------------


def _settings(db_url: str, **extra) -> Settings:
    return Settings(
        _env_file=None,
        HINAA_PROVIDER_MODE="mock",
        HINAA_DATABASE_URL=db_url,
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        TWILIO_ACCOUNT_SID="ACtest",
        TWILIO_AUTH_TOKEN="tok",
        TWILIO_FROM_NUMBER="+15551230000",
        HINAA_OWNER_PHONE_NUMBER="+15551230001",
        HINAA_PUBLIC_BASE_URL="https://hina.example.test",
        ELEVENLABS_API_KEY="",
        **extra,
    )


@pytest.fixture
def clock(tmp_path, monkeypatch):
    reset_session_factory()
    base = _settings(f"sqlite+pysqlite:///{(tmp_path / 'c.db').as_posix()}")
    get_session_factory(base)
    engine = make_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
    monkeypatch.setattr(calls, "get_session_factory", lambda _s: factory)
    calls.reset_runtime_state()
    yield tmp_path
    calls.reset_runtime_state()
    reset_session_factory()


def _due(settings, title="Take pills", call=True):
    at = (datetime.now() - timedelta(minutes=1)).isoformat(timespec="minutes")
    schedule_reminder(user_id="u", title=title, at=at, call=call, settings=settings)


class _Recorder:
    def __init__(self):
        self.calls = []

    async def __call__(self, settings, **kwargs):
        self.calls.append(kwargs)
        return {"status": "queued"}


async def test_flagged_reminder_calls_when_enabled(clock):
    settings = _settings(f"sqlite+pysqlite:///{(clock / 'c.db').as_posix()}", HINAA_TELEPHONY_PROACTIVE=True)
    _due(settings)
    _due(settings, title="Plain", call=False)
    fired = fire_due(settings=settings)
    rec = _Recorder()
    results = await place_due_calls(fired, settings=settings, caller=rec)
    assert [r["called"] for r in results] == [True]
    assert rec.calls == [{"reason": "Reminder: Take pills"}]


async def test_no_call_when_disabled_or_unconfigured(clock):
    url = f"sqlite+pysqlite:///{(clock / 'c.db').as_posix()}"
    off = _settings(url)
    _due(off)
    fired = fire_due(settings=off)
    rec = _Recorder()
    assert await place_due_calls(fired, settings=off, caller=rec) == []

    bare = Settings(_env_file=None, HINAA_TELEPHONY_PROACTIVE=True)
    assert await place_due_calls(fired, settings=bare, caller=rec) == []
    assert rec.calls == []


async def test_hourly_cap_and_allowlist_still_apply(clock):
    url = f"sqlite+pysqlite:///{(clock / 'c.db').as_posix()}"
    settings = _settings(url, HINAA_TELEPHONY_PROACTIVE=True, HINAA_TELEPHONY_MAX_CALLS_PER_HOUR=1)

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"sid": "CA" + uuid.uuid4().hex, "status": "queued"})

    caller = functools.partial(calls.place_outbound_call, transport=httpx.MockTransport(handler))
    _due(settings, title="One")
    _due(settings, title="Two")
    results = await place_due_calls(fire_due(settings=settings), settings=settings, caller=caller)
    assert [r["called"] for r in results] == [True, False]
    assert results[1]["code"] == "TELEPHONY_RATE_LIMITED"


async def test_missed_reminder_never_calls(clock):
    settings = _settings(f"sqlite+pysqlite:///{(clock / 'c.db').as_posix()}", HINAA_TELEPHONY_PROACTIVE=True)
    at = (datetime.now() - timedelta(days=2)).isoformat(timespec="minutes")
    schedule_reminder(user_id="u", title="Old", at=at, call=True, settings=settings)
    rec = _Recorder()
    assert await place_due_calls(fire_due(settings=settings), settings=settings, caller=rec) == []


def test_migration_adds_place_call_to_existing_reminders_table(tmp_path):
    engine = create_engine(f"sqlite+pysqlite:///{(tmp_path / 'old.db').as_posix()}")
    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE reminders (id VARCHAR(36) PRIMARY KEY, user_id VARCHAR(36), conversation_id VARCHAR(36), "
            "title TEXT, at DATETIME, timezone_name VARCHAR(64), status VARCHAR(20), created_at DATETIME, updated_at DATETIME)"
        ))
        conn.execute(text("INSERT INTO reminders (id, user_id, title, at, timezone_name, status) VALUES ('r1','u','Old','2026-01-01 10:00:00','','scheduled')"))
    migrations._migration_0015_reminder_place_call(engine)
    migrations._migration_0015_reminder_place_call(engine)  # idempotent
    assert "place_call" in [c["name"] for c in inspect(engine).get_columns("reminders")]
    with engine.connect() as conn:
        assert conn.execute(text("SELECT place_call FROM reminders WHERE id='r1'")).scalar() is None
    with sessionmaker(bind=engine)() as session:
        from hinaa_api.persistence.orm import Reminder

        assert bool(session.get(Reminder, "r1").place_call) is False
