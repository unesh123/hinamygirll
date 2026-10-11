from __future__ import annotations
import time
import httpx
import pytest
from fastapi.testclient import TestClient
from hinaa_api.integrations import remote_pc
from hinaa_api.integrations.github_mcp import GitHubMCP
from hinaa_api import realtime_tickets
from hinaa_api.tools import policy
from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError


def test_pc_grants_owner_scope_expiry_revoke(monkeypatch):
    vault = remote_pc.PCGrants()
    token, _ = vault.issue("owner", frozenset({"terminal_hands"}))
    assert vault.allows(token, "owner", "terminal_hands")
    assert not vault.allows(token, "other", "terminal_hands")
    assert not vault.allows(token, "owner", "send_email")
    vault.revoke(token, "other")
    assert vault.allows(token, "owner", "terminal_hands")
    vault.revoke(token, "owner")
    assert not vault.allows(token, "owner", "terminal_hands")
    token, expiry = vault.issue("owner", frozenset({"terminal_hands"}))
    monkeypatch.setattr(remote_pc.time, "time", lambda: expiry+1)
    assert not vault.allows(token, "owner", "terminal_hands")


def test_policy_remote_grant_does_not_enable_mail_or_other_owner():
    settings = Settings(_env_file=None, HINAA_ALLOW_REMOTE_LOCAL_TOOLS=False)
    token, _ = remote_pc.pc_grants.issue("owner", frozenset({"terminal_hands"}))
    bound = remote_pc.request_pc.set((token, "owner"))
    try:
        assert policy.decide("terminal_hands", settings, "remote.example").permitted
        assert not policy.decide("send_email", settings, "remote.example").permitted
        remote_pc.pc_grants.revoke(token, "owner")
        assert not policy.decide("terminal_hands", settings, "remote.example").permitted
    finally:
        remote_pc.request_pc.reset(bound)


def test_voice_ticket_carries_pc_session_once_and_cleans_expiry(monkeypatch):
    ticket = realtime_tickets.issue("owner-id", pc_context=("private-grant", "owner-subject"))
    assert realtime_tickets.consume_bundle(ticket) == ("owner-id", ("private-grant", "owner-subject"))
    assert realtime_tickets.consume_bundle(ticket) == (None, None)
    monkeypatch.setattr(realtime_tickets, "TICKET_TTL_SECONDS", -1)
    ticket = realtime_tickets.issue("owner-id", pc_context=("expired", "owner"))
    assert realtime_tickets.consume_bundle(ticket) == (None, None)
    assert ticket not in realtime_tickets._pc_pending

@pytest.mark.asyncio
async def test_github_mcp_json_sse_discovery_read_only_and_session_cleanup(monkeypatch):
    events = []
    class Client:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            assert url == "https://api.githubcopilot.com/mcp/readonly"
            events.append(json["method"])
            method = json["method"]
            if method == "notifications/initialized": return httpx.Response(202)
            if method == "initialize": result = {"protocolVersion": "2025-03-26", "serverInfo": {"name": "GitHub"}}
            elif method == "tools/list": result = {"tools": [{"name": "get_me", "annotations": {"readOnlyHint": True}}, {"name": "write_file", "annotations": {"readOnlyHint": False}}]}
            else: result = {"content": [{"type": "text", "text": "Synthetic result"}]}
            payload = {"jsonrpc": "2.0", "id": json["id"], "result": result}
            import json as encoder
            return httpx.Response(200, text="event: message\ndata: " + encoder.dumps(payload) + "\n\n", headers={"Content-Type": "text/event-stream", "Mcp-Session-Id": "test-session"})
        async def delete(self, url, headers): events.append("delete")
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: Client())
    result = await GitHubMCP("test-token").run()
    assert result["status"] == "verified"
    assert [tool["name"] for tool in result["tools"]] == ["get_me"]
    with pytest.raises(HinaaError): await GitHubMCP("test-token").run("write_file", {})
    result = await GitHubMCP("test-token").run("get_me", {})
    assert result["status"] == "success"
    assert events.count("delete") == 3

@pytest.mark.asyncio
async def test_mcp_rejects_mismatched_response_and_auth_errors():
    class Client:
        async def post(self, *args, **kwargs): return httpx.Response(200, json={"jsonrpc": "2.0", "id": 999, "result": {}})
    with pytest.raises(HinaaError): await GitHubMCP("test-token").rpc(Client(), "tools/list", {})


def test_http_pairing_owner_auth_and_remote_enforcement(tmp_path, monkeypatch):
    import sys
    from pathlib import Path

    tests_dir = str(Path(__file__).resolve().parent)
    if tests_dir not in sys.path:
        sys.path.insert(0, tests_dir)
    from test_clerk_auth import _keys, _token
    from hinaa_api.main import create_app
    from hinaa_api.tools import terminal_hands
    private, public = _keys()
    settings = Settings(_env_file=None, HINAA_AUTH_MODE="clerk", CLERK_JWT_KEY=public,
        CLERK_AUTHORIZED_PARTIES="https://hinaa.example", HINAA_ALLOWED_USER_IDS="user_owner",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:", HINAA_PERSISTENCE_ENABLED=True,
        HINAA_PROVIDER_MODE="mock", HINAA_ALLOW_REMOTE_LOCAL_TOOLS=False, HINAA_LOCAL_WORKSPACE_DIR=tmp_path, HINAA_VMC_PORT=0)
    app = create_app(settings)
    monkeypatch.setattr(terminal_hands, "_wsl_distributions", lambda: [])
    remote_headers = {"host": "hinaa.example", "cf-connecting-ip": "203.0.113.1", "Authorization": "Bearer " + _token(private, subject="user_owner")}
    with TestClient(app) as client:
        assert client.post("/api/v1/pc/pair", headers=remote_headers).status_code == 403
        local = client.post("/api/v1/pc/pair", headers={"host": "127.0.0.1", "X-HINAA-Dev-User": "local-dev-user"})
        assert local.status_code == 200
        token = local.json()["token"]
        assert client.get("/api/v1/terminal/status", headers=remote_headers).json()["execution_allowed"] is False
        paired = {**remote_headers, "X-HINAA-PC-Session": token}
        assert client.get("/api/v1/terminal/status", headers=paired).json()["execution_allowed"] is True
        stranger = {**paired, "Authorization": "Bearer " + _token(private, subject="user_other")}
        assert client.get("/api/v1/terminal/status", headers=stranger).status_code == 403
        assert client.post("/api/v1/pc/disconnect", headers=paired).status_code == 200
        assert client.get("/api/v1/terminal/status", headers=paired).json()["execution_allowed"] is False
