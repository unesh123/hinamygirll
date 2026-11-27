"""Runtime tool declaration bridge re-exporting the live HINAA ToolRegistry."""
from __future__ import annotations

from hinaa_api.tools.registry import ToolDefinition, ToolRegistry, registry

__all__ = ["ToolDefinition", "ToolRegistry", "registry"]
