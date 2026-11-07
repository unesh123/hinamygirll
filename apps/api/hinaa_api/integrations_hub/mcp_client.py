"""Minimal MCP client (JSON-RPC 2.0): streamable HTTP and stdio transports.

Implements only what the hub needs: initialize, notifications/initialized,
tools/list (with pagination) and tools/call.
"""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import httpx

PROTOCOL_VERSION = "2025-06-18"
CLIENT_INFO = {"name": "hinaa-hub", "version": "1.0"}
_SAFE_BASE_ENV = ("PATH", "HOME", "USER", "LANG", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT", "COMSPEC", "PATHEXT")


class McpError(RuntimeError):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


def _init_params() -> dict[str, Any]:
    return {"protocolVersion": PROTOCOL_VERSION, "capabilities": {}, "clientInfo": CLIENT_INFO}


def _result(message: dict[str, Any]) -> Any:
    if "error" in message:
        err = message["error"] or {}
        raise McpError(str(err.get("message", "MCP error")), err.get("code"))
    return message.get("result")


def parse_sse(text: str) -> list[dict[str, Any]]:
    """Return the JSON payload of every SSE event in ``text``."""
    events: list[dict[str, Any]] = []
    data: list[str] = []
    for line in [*text.splitlines(), ""]:
        if line.startswith("data:"):
            data.append(line[5:].lstrip(" "))
        elif not line.strip() and data:
            try:
                payload = json.loads("\n".join(data))
            except ValueError:
                payload = None
            data = []
            if isinstance(payload, dict):
                events.append(payload)
            elif isinstance(payload, list):
                events.extend(p for p in payload if isinstance(p, dict))
    return events


class McpHttpClient:
    """Streamable HTTP transport. Responses may be JSON or an SSE stream."""

    def __init__(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        *,
        timeout: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.url = url
        self._headers = dict(headers or {})
        self._client = httpx.AsyncClient(timeout=timeout, transport=transport, follow_redirects=False)
        self.session_id: str | None = None
        self.protocol_version = PROTOCOL_VERSION
        self._serial = 0

    async def __aenter__(self) -> "McpHttpClient":
        await self.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    def _request_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
            "MCP-Protocol-Version": self.protocol_version,
            **self._headers,
        }
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        return headers

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        response = await self._client.post(self.url, json=payload, headers=self._request_headers())
        sid = response.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        if response.status_code >= 400:
            raise McpError(f"MCP server returned HTTP {response.status_code}", response.status_code)
        return response

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._serial += 1
        rid = self._serial
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        response = await self._post(payload)
        ctype = response.headers.get("content-type", "").lower()
        if "text/event-stream" in ctype:
            messages = parse_sse(response.text)
        else:
            try:
                body = response.json()
            except ValueError as exc:
                raise McpError("MCP server returned a non-JSON response") from exc
            messages = body if isinstance(body, list) else [body]
        for message in messages:
            if isinstance(message, dict) and message.get("id") == rid and ("result" in message or "error" in message):
                return _result(message)
        raise McpError(f"No response to {method}")

    async def _notify(self, method: str) -> None:
        await self._post({"jsonrpc": "2.0", "method": method})

    async def initialize(self) -> dict[str, Any]:
        result = await self._rpc("initialize", _init_params()) or {}
        negotiated = result.get("protocolVersion")
        if isinstance(negotiated, str):
            self.protocol_version = negotiated
        await self._notify("notifications/initialized")
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        return await _paginate(self._rpc)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._rpc("tools/call", {"name": name, "arguments": arguments or {}}) or {}

    async def close(self) -> None:
        if self.session_id:
            try:
                await self._client.delete(self.url, headers=self._request_headers())
            except httpx.HTTPError:
                pass
        await self._client.aclose()


class McpStdioClient:
    """Newline-delimited JSON-RPC over a spawned subprocess."""

    def __init__(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        *,
        timeout: float = 30.0,
    ):
        self.command = command
        self.args = list(args or [])
        self.extra_env = dict(env or {})
        self.timeout = timeout
        self._proc: asyncio.subprocess.Process | None = None
        self._serial = 0

    async def __aenter__(self) -> "McpStdioClient":
        await self.start()
        try:
            await self.initialize()
        except BaseException:
            await self.close()
            raise
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def start(self) -> None:
        env = {k: os.environ[k] for k in _SAFE_BASE_ENV if k in os.environ}
        env.update(self.extra_env)
        try:
            self._proc = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                env=env,
            )
        except OSError as exc:
            raise McpError(f"Could not start MCP server: {exc}") from exc

    async def _send(self, payload: dict[str, Any]) -> None:
        assert self._proc and self._proc.stdin
        self._proc.stdin.write((json.dumps(payload) + "\n").encode())
        await self._proc.stdin.drain()

    async def _rpc(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._serial += 1
        rid = self._serial
        payload: dict[str, Any] = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            payload["params"] = params
        await self._send(payload)
        try:
            return await asyncio.wait_for(self._read_response(rid), self.timeout)
        except asyncio.TimeoutError as exc:
            raise McpError(f"Timed out waiting for {method}") from exc

    async def _read_response(self, rid: int) -> Any:
        assert self._proc and self._proc.stdout
        while True:
            line = await self._proc.stdout.readline()
            if not line:
                raise McpError("MCP server closed the connection")
            try:
                message = json.loads(line)
            except ValueError:
                continue
            if isinstance(message, dict) and message.get("id") == rid and ("result" in message or "error" in message):
                return _result(message)

    async def initialize(self) -> dict[str, Any]:
        result = await self._rpc("initialize", _init_params()) or {}
        await self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return result

    async def list_tools(self) -> list[dict[str, Any]]:
        return await _paginate(self._rpc)

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._rpc("tools/call", {"name": name, "arguments": arguments or {}}) or {}

    async def close(self) -> None:
        proc, self._proc = self._proc, None
        if proc is None:
            return
        if proc.stdin:
            proc.stdin.close()
        try:
            await asyncio.wait_for(proc.wait(), 2)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


async def _paginate(rpc: Any) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    cursor: str | None = None
    for _ in range(20):
        result = await rpc("tools/list", {"cursor": cursor} if cursor else {}) or {}
        tools.extend(t for t in result.get("tools", []) if isinstance(t, dict) and t.get("name"))
        cursor = result.get("nextCursor")
        if not cursor:
            break
    return tools
