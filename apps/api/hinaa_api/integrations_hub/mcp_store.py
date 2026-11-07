"""Persisted MCP server configs and discovered-tool cache (JSON under .runtime/mcp)."""
from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..runtime_paths import runtime_dir

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")
_ENV_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


@dataclass
class McpServerConfig:
    name: str
    transport: str  # "http" | "stdio"
    url: str = ""
    command: str = ""
    args: list[str] = field(default_factory=list)
    # Env var NAMES only; values are read from the process environment at connect time.
    env_names: list[str] = field(default_factory=list)  # stdio: passed to the child
    header_env: dict[str, str] = field(default_factory=dict)  # http: header -> env var name
    bearer_env: str = ""  # http: env var holding a bearer token
    enabled: bool = True
    trusted: bool = False
    tools: list[dict[str, Any]] = field(default_factory=list)
    last_refreshed: str | None = None
    last_error: str | None = None

    def public(self) -> dict[str, Any]:
        data = asdict(self)
        data["tools"] = [t.get("name") for t in self.tools]
        data["toolCount"] = len(self.tools)
        return data


def validate(config: McpServerConfig) -> None:
    if not _NAME_RE.match(config.name):
        raise ValueError("name must be 1-40 chars of a-z, 0-9, '_' or '-'")
    if config.transport == "http":
        parsed = urlparse(config.url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise ValueError("url must be an http(s) URL")
        if parsed.scheme == "http" and parsed.hostname not in _LOCAL_HOSTS:
            raise ValueError("plain http is only allowed for localhost")
        if parsed.username or parsed.password:
            raise ValueError("credentials must not be embedded in the url")
    elif config.transport == "stdio":
        if not config.command.strip():
            raise ValueError("command is required for stdio servers")
    else:
        raise ValueError("transport must be 'http' or 'stdio'")
    names = [*config.env_names, *config.header_env.values(), *([config.bearer_env] if config.bearer_env else [])]
    if any(not _ENV_RE.match(n) for n in names):
        raise ValueError("env names must be valid environment variable names")


class McpStore:
    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.Lock()

    def _load(self) -> dict[str, McpServerConfig]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        servers: dict[str, McpServerConfig] = {}
        for item in raw.get("servers", []) if isinstance(raw, dict) else []:
            try:
                cfg = McpServerConfig(**item)
            except TypeError:
                continue
            servers[cfg.name] = cfg
        return servers

    def _save(self, servers: dict[str, McpServerConfig]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"servers": [asdict(s) for s in servers.values()]}, indent=2)
        fd, tmp = tempfile.mkstemp(dir=self.path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(payload)
        os.replace(tmp, self.path)

    def list_servers(self) -> list[McpServerConfig]:
        with self._lock:
            return list(self._load().values())

    def get(self, name: str) -> McpServerConfig | None:
        with self._lock:
            return self._load().get(name)

    def upsert(self, config: McpServerConfig) -> McpServerConfig:
        validate(config)
        with self._lock:
            servers = self._load()
            previous = servers.get(config.name)
            if previous and not config.tools:  # keep discovery cache across config edits
                config.tools = previous.tools
            servers[config.name] = config
            self._save(servers)
        return config

    def delete(self, name: str) -> bool:
        with self._lock:
            servers = self._load()
            if name not in servers:
                return False
            del servers[name]
            self._save(servers)
            return True

    def record_discovery(self, name: str, tools: list[dict[str, Any]] | None, error: str | None) -> None:
        with self._lock:
            servers = self._load()
            cfg = servers.get(name)
            if cfg is None:
                return
            if tools is not None:
                cfg.tools = tools
            cfg.last_error = error
            cfg.last_refreshed = datetime.now(timezone.utc).isoformat()
            self._save(servers)


def get_store() -> McpStore:
    return McpStore(runtime_dir("mcp", "servers.json"))
