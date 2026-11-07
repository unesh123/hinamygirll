"""FastAPI routes for the Integration Hub (connectors, GitHub repos, MCP servers)."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..errors import HinaaError
from ..tools import policy as tool_policy
from . import connectors, github_repos, mcp_service
from .mcp_store import McpServerConfig, get_store, validate

router = APIRouter(tags=["integrations-hub"])


class ActiveReposPayload(BaseModel):
    repos: list[str] = Field(default_factory=list, max_length=200)


class McpServerPayload(BaseModel):
    name: str
    transport: str = "http"
    url: str = ""
    command: str = ""
    args: list[str] = Field(default_factory=list)
    envNames: list[str] = Field(default_factory=list)
    headerEnv: dict[str, str] = Field(default_factory=dict)
    bearerEnv: str = ""
    enabled: bool = True
    trusted: bool = False


class McpCallPayload(BaseModel):
    server: str | None = None
    tool: str | None = None
    name: str | None = Field(None, description="Qualified name mcp__<server>__<tool>")
    arguments: dict[str, Any] = Field(default_factory=dict)
    confirmed: bool = False
    approvalSource: str = "none"


def _guard_local(request: Request, cfg_transport: str) -> None:
    """stdio servers run commands on the host machine: same rule as local-effect tools."""
    if cfg_transport != "stdio":
        return
    from ..config import get_settings

    if not tool_policy.local_effects_permitted(get_settings(), request.headers.get("host")):
        raise HinaaError(
            "LOCAL_TOOL_NOT_PERMITTED",
            "stdio MCP servers run on the machine hosting HINAA and can only be managed from that machine.",
            403,
            False,
            True,
        )


@router.get("/integrations")
async def list_integrations(category: str | None = Query(None)) -> dict[str, Any]:
    items = connectors.list_connectors(category)
    return {
        "status": "ok",
        "total": len(items),
        "configured": sum(1 for i in items if i["configured"]),
        "integrations": items,
        "mcp": connectors.mcp_summary(),
    }


@router.get("/integrations/github/repos")
async def github_repos_list(max_pages: int = Query(5, ge=1, le=20)) -> dict[str, Any]:
    repos = await github_repos.list_repos(max_pages=max_pages)
    active = set(github_repos.get_active_repos())
    for repo in repos:
        repo["active"] = repo["fullName"] in active
    return {"status": "ok", "total": len(repos), "repos": repos}


@router.get("/integrations/github/active-repos")
async def github_active_get() -> dict[str, Any]:
    return {"status": "ok", "repos": github_repos.get_active_repos()}


@router.post("/integrations/github/active-repos")
async def github_active_set(payload: ActiveReposPayload) -> dict[str, Any]:
    return {"status": "ok", "repos": github_repos.set_active_repos(payload.repos)}


@router.get("/integrations/{connector_id}")
async def get_integration(connector_id: str, health: bool = Query(False)) -> dict[str, Any]:
    connector = connectors.get_connector(connector_id)
    if connector is None:
        raise HTTPException(status_code=404, detail="Integration not found")
    data = connectors.describe(connector)
    if health and connector.health == "github" and data["configured"]:
        data["health"] = await github_repos.check_health()
    return {"status": "ok", "integration": data}


@router.get("/mcp/servers")
async def mcp_servers_list() -> dict[str, Any]:
    servers = get_store().list_servers()
    return {"status": "ok", "total": len(servers), "servers": [s.public() for s in servers]}


@router.post("/mcp/servers")
async def mcp_servers_upsert(request: Request, payload: McpServerPayload) -> dict[str, Any]:
    cfg = McpServerConfig(
        name=payload.name.strip().lower(),
        transport=payload.transport,
        url=payload.url.strip(),
        command=payload.command.strip(),
        args=payload.args,
        env_names=payload.envNames,
        header_env=payload.headerEnv,
        bearer_env=payload.bearerEnv,
        enabled=payload.enabled,
        trusted=payload.trusted,
    )
    try:
        validate(cfg)
    except ValueError as exc:
        raise HinaaError("MCP_SERVER_INVALID", str(exc), 400, False) from exc
    _guard_local(request, cfg.transport)
    return {"status": "ok", "server": get_store().upsert(cfg).public()}


@router.delete("/mcp/servers/{name}")
async def mcp_servers_delete(name: str) -> dict[str, Any]:
    if not get_store().delete(name):
        raise HTTPException(status_code=404, detail="MCP server not found")
    return {"status": "ok", "deleted": name}


@router.post("/mcp/servers/{name}/refresh")
async def mcp_servers_refresh(request: Request, name: str) -> dict[str, Any]:
    cfg = get_store().get(name)
    if cfg is None:
        raise HTTPException(status_code=404, detail="MCP server not found")
    _guard_local(request, cfg.transport)
    updated = await mcp_service.refresh(name)
    return {"status": "ok", "server": updated.public()}


@router.get("/mcp/tools")
async def mcp_tools_list() -> dict[str, Any]:
    tools = mcp_service.describe_tools()
    return {"status": "ok", "total": len(tools), "tools": tools}


@router.post("/mcp/tools/call")
async def mcp_tools_call(request: Request, payload: McpCallPayload) -> dict[str, Any]:
    server, tool = payload.server, payload.tool
    if payload.name:
        parts = payload.name.split("__", 2)
        if len(parts) != 3 or parts[0] != "mcp":
            raise HinaaError("MCP_TOOL_NAME_INVALID", "Expected mcp__<server>__<tool>.", 400, False)
        server, tool = parts[1], parts[2]
    if not server or not tool:
        raise HinaaError("MCP_TOOL_NAME_INVALID", "Provide server and tool, or a qualified name.", 400, False)
    cfg = get_store().get(server)
    if cfg is not None:
        _guard_local(request, cfg.transport)
    return {
        "status": "ok",
        **await mcp_service.call_tool(
            server,
            tool,
            payload.arguments,
            confirmed=payload.confirmed,
            approval_source=payload.approvalSource,
        ),
    }
