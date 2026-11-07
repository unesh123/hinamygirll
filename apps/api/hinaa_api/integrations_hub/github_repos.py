"""List GitHub repositories reachable with the configured token and track the active set."""
from __future__ import annotations

import json
import os
import re
import tempfile
from typing import Any

import httpx

from ..errors import HinaaError
from ..runtime_paths import runtime_dir

API = "https://api.github.com"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

# Tests inject an httpx transport here instead of touching the network.
transport: httpx.AsyncBaseTransport | None = None


def _token() -> str:
    from ..config import get_settings

    secret = get_settings().github_token
    token = secret.get_secret_value() if secret else os.environ.get("GITHUB_TOKEN", "")
    if not token.strip():
        raise HinaaError("GITHUB_NOT_CONFIGURED", "GitHub is not connected. Add GITHUB_TOKEN to the backend env.", 400, True)
    return token


def _summarize(repo: dict[str, Any]) -> dict[str, Any]:
    return {
        "fullName": repo.get("full_name"),
        "private": bool(repo.get("private")),
        "description": repo.get("description"),
        "defaultBranch": repo.get("default_branch"),
        "language": repo.get("language"),
        "updatedAt": repo.get("pushed_at") or repo.get("updated_at"),
        "archived": bool(repo.get("archived")),
        "url": repo.get("html_url"),
    }


async def list_repos(max_pages: int = 5, per_page: int = 100) -> list[dict[str, Any]]:
    """Repos the token can see: /user/repos, falling back to /installation/repositories."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "HINAA-companion",
        "Authorization": f"Bearer {_token()}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repos: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=20.0, transport=transport, headers=headers) as client:
        endpoint, params = "/user/repos", {"sort": "updated", "affiliation": "owner,collaborator,organization_member"}
        for page in range(1, max_pages + 1):
            try:
                resp = await client.get(API + endpoint, params={**params, "per_page": per_page, "page": page})
            except httpx.HTTPError as exc:
                raise HinaaError("GITHUB_REQUEST_FAILED", f"GitHub request failed: {exc}", 502, True) from exc
            if resp.status_code in (403, 404) and page == 1 and endpoint == "/user/repos":
                # Installation tokens cannot read /user.
                endpoint, params = "/installation/repositories", {}
                resp = await client.get(API + endpoint, params={"per_page": per_page, "page": page})
            if resp.status_code == 401:
                raise HinaaError("GITHUB_UNAUTHORIZED", "GitHub rejected the configured token.", 401, True)
            if resp.status_code >= 400:
                raise HinaaError("GITHUB_REQUEST_FAILED", f"GitHub returned HTTP {resp.status_code}.", 502, True)
            body = resp.json()
            batch = body.get("repositories", []) if isinstance(body, dict) else body
            repos.extend(_summarize(r) for r in batch)
            if len(batch) < per_page:
                break
    return repos


def _state_path():
    return runtime_dir("integrations", "github_active_repos.json")


def get_active_repos() -> list[str]:
    try:
        raw = json.loads(_state_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    repos = raw.get("repos", []) if isinstance(raw, dict) else []
    return [r for r in repos if isinstance(r, str) and _REPO_RE.match(r)]


def set_active_repos(repos: list[str]) -> list[str]:
    cleaned: list[str] = []
    for repo in repos:
        repo = repo.strip()
        if not _REPO_RE.match(repo):
            raise HinaaError("GITHUB_REPO_INVALID", f"'{repo}' is not in 'owner/name' form.", 400, True)
        if repo not in cleaned:
            cleaned.append(repo)
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump({"repos": cleaned}, fh)
    os.replace(tmp, path)
    return cleaned


async def check_health() -> dict[str, Any]:
    """Cheap token validity probe (GET /rate_limit does not consume quota)."""
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "HINAA-companion",
               "Authorization": f"Bearer {_token()}"}
    try:
        async with httpx.AsyncClient(timeout=10.0, transport=transport, headers=headers) as client:
            resp = await client.get(API + "/rate_limit")
    except httpx.HTTPError:
        return {"ok": False, "detail": "unreachable"}
    return {"ok": resp.status_code == 200, "detail": f"HTTP {resp.status_code}"}
