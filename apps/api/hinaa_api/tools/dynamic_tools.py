"""Per-turn refresh of tools whose shape depends on user settings (MCP servers, GitHub repos)."""
from __future__ import annotations

import logging

logger = logging.getLogger("hinaa.tools")


def sync_dynamic_tools() -> None:
    """Cheap, cache-only refresh; a failure must never take a turn down."""
    try:
        from ..integrations_hub.mcp_agent_tools import sync_mcp_tools

        sync_mcp_tools()
    except Exception:
        logger.warning("MCP tool sync failed", exc_info=True)
    try:
        from .github_tools import refresh_repo_hints

        refresh_repo_hints()
    except Exception:
        logger.warning("GitHub repo hint refresh failed", exc_info=True)
