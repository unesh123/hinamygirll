"""Connects stored MCP server configs to the client and enforces tool gating."""
from __future__ import annotations

import os
from typing import Any

import httpx

from ..errors import HinaaError
from .mcp_client import McpError, McpHttpClient, McpStdioClient
from .mcp_store import McpServerConfig, McpStore, get_store

# Tests inject an httpx transport here instead of touching the network.
http_transport: httpx.AsyncBaseTransport | None = None

MAX_RESULT_CHARS = 60_000


def qualified_name(server: str, tool: str) -> str:
    return f"mcp__{server}__{tool}"


def build_client(cfg: McpServerConfig) -> McpHttpClient | McpStdioClient:
    if cfg.transport == "http":
        headers = {h: os.environ[e] for h, e in cfg.header_env.items() if os.environ.get(e)}
        if cfg.bearer_env and os.environ.get(cfg.bearer_env):
            headers["Authorization"] = f"Bearer {os.environ[cfg.bearer_env]}"
        return McpHttpClient(cfg.url, headers, transport=http_transport)
    env = {n: os.environ[n] for n in cfg.env_names if n in os.environ}
    return McpStdioClient(cfg.command, cfg.args, env)


def requires_confirmation(cfg: McpServerConfig) -> bool:
    return not cfg.trusted


def describe_tools(store: McpStore | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cfg in (store or get_store()).list_servers():
        for tool in cfg.tools:
            out.append(
                {
                    "name": qualified_name(cfg.name, tool["name"]),
                    "server": cfg.name,
                    "tool": tool["name"],
                    "description": tool.get("description", ""),
                    "inputSchema": tool.get("inputSchema", {}),
                    "riskLevel": "medium" if cfg.trusted else "high",
                    "requiresConfirmation": requires_confirmation(cfg),
                    "enabled": cfg.enabled,
                    "transport": cfg.transport,
                }
            )
    return out


async def refresh(name: str, store: McpStore | None = None) -> McpServerConfig:
    store = store or get_store()
    cfg = store.get(name)
    if cfg is None:
        raise HinaaError("MCP_SERVER_NOT_FOUND", f"No MCP server named {name}.", 404, False)
    try:
        async with build_client(cfg) as client:
            tools = await client.list_tools()
    except (McpError, httpx.HTTPError, OSError) as exc:
        store.record_discovery(name, None, str(exc)[:300])
        raise HinaaError("MCP_REFRESH_FAILED", f"Could not discover tools: {exc}", 502, True) from exc
    store.record_discovery(name, tools, None)
    return store.get(name) or cfg


async def call_tool(
    server: str,
    tool: str,
    arguments: dict[str, Any],
    *,
    confirmed: bool,
    approval_source: str,
    store: McpStore | None = None,
) -> dict[str, Any]:
    store = store or get_store()
    cfg = store.get(server)
    if cfg is None:
        raise HinaaError("MCP_SERVER_NOT_FOUND", f"No MCP server named {server}.", 404, False)
    if not cfg.enabled:
        raise HinaaError("MCP_SERVER_DISABLED", f"MCP server {server} is disabled.", 409, False)
    if tool not in {t["name"] for t in cfg.tools}:
        raise HinaaError("MCP_TOOL_NOT_FOUND", f"{server} has no discovered tool {tool}. Refresh first.", 404, False)
    if requires_confirmation(cfg) and not (confirmed and approval_source == "user"):
        raise HinaaError(
            "TOOL_CONFIRMATION_REQUIRED",
            f"Confirm the {qualified_name(server, tool)} action before HINAA runs it.",
            409,
            False,
            True,
        )
    try:
        async with build_client(cfg) as client:
            result = await client.call_tool(tool, arguments)
    except McpError as exc:
        raise HinaaError("MCP_CALL_FAILED", str(exc), 502, True) from exc
    except (httpx.HTTPError, OSError) as exc:
        raise HinaaError("MCP_CALL_FAILED", f"MCP transport error: {exc}", 502, True) from exc
    for block in result.get("content", []) if isinstance(result, dict) else []:
        text = block.get("text") if isinstance(block, dict) else None
        if isinstance(text, str) and len(text) > MAX_RESULT_CHARS:
            block["text"] = text[:MAX_RESULT_CHARS] + "\n[truncated]"
    return {"server": server, "tool": tool, "isError": bool(result.get("isError")), "result": result}
