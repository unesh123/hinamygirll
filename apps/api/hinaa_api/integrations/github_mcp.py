"""Official remote GitHub MCP transport, restricted to read-only tools."""
from __future__ import annotations
import asyncio
import json
import httpx
from hinaa_api.config import get_settings
from hinaa_api.errors import HinaaError

ENDPOINT = "https://api.githubcopilot.com/mcp/readonly"

class GitHubMCP:
    def __init__(self, token: str | None = None):
        secret = get_settings().github_token
        self.token = token or (secret.get_secret_value() if secret else "")
        if not self.token:
            raise HinaaError("GITHUB_NOT_CONFIGURED", "Connect GitHub with a repository-scoped GITHUB_TOKEN in the backend secret store.", 400, True)
        self.session = None
        self.version = "2025-03-26"
        self.serial = 0

    def headers(self):
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json, text/event-stream",
                   "Content-Type": "application/json", "MCP-Protocol-Version": self.version}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        return headers

    async def rpc(self, client, method: str, params: dict, *, notification: bool = False):
        self.serial += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            payload["id"] = self.serial
        response = await client.post(ENDPOINT, headers=self.headers(), json=payload)
        if response.is_error:
            message = "GitHub authorization was rejected." if response.status_code in (401, 403) else f"GitHub MCP failed ({response.status_code})."
            raise HinaaError("GITHUB_MCP_ERROR", message, 502, True)
        self.session = response.headers.get("Mcp-Session-Id", self.session)
        if notification and response.status_code in (200, 202, 204):
            return {}
        if len(response.content) > 2_000_000:
            raise HinaaError("GITHUB_MCP_ERROR", "GitHub MCP response exceeded the size limit.", 502, True)
        if "text/event-stream" in response.headers.get("Content-Type", ""):
            data = None
            for event in response.text.replace("\r\n", "\n").split("\n\n"):
                lines = [line[5:].strip() for line in event.splitlines() if line.startswith("data:")]
                if lines:
                    candidate = json.loads("\n".join(lines))
                    if candidate.get("id") == payload.get("id"):
                        data = candidate
                        break
            if data is None:
                raise HinaaError("GITHUB_MCP_ERROR", "GitHub MCP returned no matching result.", 502, True)
        else:
            data = response.json()
        if data.get("id") != payload.get("id") or "error" in data:
            raise HinaaError("GITHUB_MCP_ERROR", "GitHub MCP rejected the request or returned an invalid result.", 502, True)
        return data.get("result", {})

    async def run(self, name: str | None = None, arguments: dict | None = None):
        try:
            async with asyncio.timeout(18):
                return await self._run(name, arguments)
        except (TimeoutError, httpx.HTTPError) as exc:
            raise HinaaError("GITHUB_MCP_UNAVAILABLE", "GitHub MCP connection timed out or failed. Retry after checking credentials and connectivity.", 503, True) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HinaaError("GITHUB_MCP_ERROR", "GitHub MCP returned a malformed response.", 502, True) from exc

    async def _run(self, name: str | None = None, arguments: dict | None = None):
        async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
            initialized = await self.rpc(client, "initialize", {"protocolVersion": self.version,
                "capabilities": {}, "clientInfo": {"name": "Hina", "version": "1.0"}})
            self.version = initialized.get("protocolVersion", self.version)
            try:
                await self.rpc(client, "notifications/initialized", {}, notification=True)
                tools = []
                cursor = None
                for _ in range(10):
                    page = await self.rpc(client, "tools/list", {"cursor": cursor} if cursor else {})
                    tools.extend(page.get("tools", []))
                    cursor = page.get("nextCursor")
                    if not cursor: break
                else:
                    raise HinaaError("GITHUB_MCP_ERROR", "GitHub tool discovery exceeded the page limit.", 502, True)
                readable = [tool for tool in tools if tool.get("annotations", {}).get("readOnlyHint") is True]
                if not name:
                    return {"status": "verified", "server": initialized.get("serverInfo", {}), "tools": readable}
                if name not in {tool["name"] for tool in readable}:
                    raise HinaaError("GITHUB_MCP_TOOL_DENIED", "Choose a discovered read-only GitHub tool. Writes require a separately authorized workflow.", 403)
                result = await self.rpc(client, "tools/call", {"name": name, "arguments": arguments or {}})
                return {"status": "failed" if result.get("isError") else "success", "result": result}
            finally:
                if self.session:
                    try:
                        await client.delete(ENDPOINT, headers=self.headers())
                    except httpx.HTTPError:
                        pass
