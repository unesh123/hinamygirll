from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

from hinaa_api.integrations_hub import mcp_service
from hinaa_api.integrations_hub.mcp_client import McpHttpClient, McpStdioClient, parse_sse

FAKE_STDIO = str(Path(__file__).with_name("fake_mcp_stdio.py"))
LOCAL = {"host": "127.0.0.1"}
REMOTE = {"host": "hinaa.example.com"}


class FakeHttpServer:
    """Streamable-HTTP MCP server: JSON for most calls, SSE for tools/call."""

    def __init__(self):
        self.seen: list[tuple[str, dict[str, str]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.method == "DELETE":
            return httpx.Response(204)
        msg = json.loads(request.content)
        method = msg.get("method")
        self.seen.append((method, dict(request.headers)))
        if "id" not in msg:
            return httpx.Response(202)
        if method == "initialize":
            body = {"jsonrpc": "2.0", "id": msg["id"],
                    "result": {"protocolVersion": "2025-06-18", "capabilities": {}}}
            return httpx.Response(200, json=body, headers={"Mcp-Session-Id": "sess-1"})
        assert request.headers.get("mcp-session-id") == "sess-1"
        if method == "tools/list":
            cursor = msg["params"].get("cursor")
            tools = [{"name": "b"}] if cursor else [{"name": "a", "description": "A", "inputSchema": {}}]
            result = {"tools": tools, **({} if cursor else {"nextCursor": "c2"})}
            return httpx.Response(200, json={"jsonrpc": "2.0", "id": msg["id"], "result": result})
        if method == "tools/call":
            event = {"jsonrpc": "2.0", "id": msg["id"],
                     "result": {"content": [{"type": "text", "text": "hi " + msg["params"]["arguments"]["who"]}]}}
            sse = "event: message\ndata: " + json.dumps(event) + "\n\n"
            return httpx.Response(200, text=sse, headers={"content-type": "text/event-stream"})
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": msg["id"], "error": {"code": -1, "message": "x"}})


def test_parse_sse():
    text = 'event: message\ndata: {"id": 1,\ndata: "result": {}}\n\n: comment\ndata: {"id": 2}\n\n'
    assert [e["id"] for e in parse_sse(text)] == [1, 2]


async def test_http_client_handshake_session_sse_and_pagination():
    server = FakeHttpServer()
    async with McpHttpClient("https://mcp.example/mcp", {"Authorization": "Bearer t"},
                             transport=httpx.MockTransport(server)) as client:
        assert client.session_id == "sess-1"
        assert [t["name"] for t in await client.list_tools()] == ["a", "b"]
        result = await client.call_tool("a", {"who": "you"})
    assert result["content"][0]["text"] == "hi you"
    methods = [m for m, _ in server.seen]
    assert methods[:2] == ["initialize", "notifications/initialized"]
    assert server.seen[0][1]["authorization"] == "Bearer t"
    assert server.seen[2][1]["mcp-protocol-version"] == "2025-06-18"


async def test_stdio_client_roundtrip_and_env_isolation(monkeypatch):
    monkeypatch.setenv("FAKE_MCP_SECRET", "should-not-leak")
    async with McpStdioClient(sys.executable, [FAKE_STDIO], {}) as client:
        assert [t["name"] for t in await client.list_tools()] == ["echo"]
        out = await client.call_tool("echo", {"text": "yo"})
    assert out["content"][0]["text"] == "yo|"  # unlisted env var not passed through
    async with McpStdioClient(sys.executable, [FAKE_STDIO], {"FAKE_MCP_SECRET": "ok"}) as client:
        out = await client.call_tool("echo", {"text": "yo"})
    assert out["content"][0]["text"] == "yo|ok"


@pytest.fixture
def hub(monkeypatch, tmp_path):
    monkeypatch.setenv("HINAA_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setattr(mcp_service, "http_transport", httpx.MockTransport(FakeHttpServer()))


def test_http_server_lifecycle_and_confirmation_gate(client, hub):
    created = client.post("/v1/mcp/servers", json={"name": "demo", "url": "https://mcp.example/mcp",
                                                   "bearerEnv": "DEMO_TOKEN"})
    assert created.status_code == 200 and created.json()["server"]["trusted"] is False
    assert client.get("/v1/mcp/servers").json()["total"] == 1
    refreshed = client.post("/v1/mcp/servers/demo/refresh").json()["server"]
    assert refreshed["tools"] == ["a", "b"]

    tools = client.get("/v1/mcp/tools").json()["tools"]
    assert tools[0]["name"] == "mcp__demo__a" and tools[0]["requiresConfirmation"] is True

    call = {"name": "mcp__demo__a", "arguments": {"who": "me"}}
    assert client.post("/v1/mcp/tools/call", json=call).status_code == 409
    ok = client.post("/v1/mcp/tools/call", json={**call, "confirmed": True, "approvalSource": "user"})
    assert ok.status_code == 200
    assert ok.json()["result"]["content"][0]["text"] == "hi me"

    assert client.post("/v1/mcp/tools/call", json={"server": "demo", "tool": "zzz"}).status_code == 404
    assert client.delete("/v1/mcp/servers/demo").status_code == 200
    assert client.delete("/v1/mcp/servers/demo").status_code == 404


def test_trusted_server_skips_confirmation(client, hub):
    client.post("/v1/mcp/servers", json={"name": "t", "url": "https://mcp.example/mcp", "trusted": True})
    client.post("/v1/mcp/servers/t/refresh")
    res = client.post("/v1/mcp/tools/call", json={"server": "t", "tool": "a", "arguments": {"who": "x"}})
    assert res.status_code == 200
    assert client.get("/v1/mcp/tools").json()["tools"][0]["requiresConfirmation"] is False


def test_validation_rejects_bad_configs(client, hub):
    for payload in (
        {"name": "Bad Name", "url": "https://x.example"},
        {"name": "ok", "url": "http://remote.example/mcp"},
        {"name": "ok", "url": "https://u:p@x.example"},
        {"name": "ok", "url": "https://x.example", "bearerEnv": "not valid"},
        {"name": "ok", "transport": "stdio", "command": ""},
    ):
        assert client.post("/v1/mcp/servers", json=payload, headers=LOCAL).status_code == 400, payload


def test_stdio_server_endpoints_require_local_host(client, hub, monkeypatch):
    monkeypatch.setenv("FAKE_MCP_SECRET", "sek")
    payload = {"name": "loc", "transport": "stdio", "command": sys.executable, "args": [FAKE_STDIO],
               "envNames": ["FAKE_MCP_SECRET"]}
    assert client.post("/v1/mcp/servers", json=payload, headers=REMOTE).status_code == 403
    assert client.post("/v1/mcp/servers", json=payload, headers=LOCAL).status_code == 200
    assert client.post("/v1/mcp/servers/loc/refresh", headers=REMOTE).status_code == 403
    assert client.post("/v1/mcp/servers/loc/refresh", headers=LOCAL).json()["server"]["tools"] == ["echo"]
    call = {"server": "loc", "tool": "echo", "arguments": {"text": "a"}, "confirmed": True,
            "approvalSource": "user"}
    assert client.post("/v1/mcp/tools/call", json=call, headers=REMOTE).status_code == 403
    res = client.post("/v1/mcp/tools/call", json=call, headers=LOCAL)
    assert res.json()["result"]["content"][0]["text"] == "a|sek"
    assert "sek" not in client.get("/v1/mcp/servers").text  # only env names are stored
