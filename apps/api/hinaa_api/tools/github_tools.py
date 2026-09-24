"""github_tools.py — GitHub repository work-tree tools for HINAA.

Lets HINAA connect to the user's GitHub (token via GITHUB_TOKEN), inspect a
repo, read and edit files with real commits, manage branches, open pull
requests, and track issues — the backbone of continuous repo work.
Read-only tools are low risk; write tools require confirmation by default.
"""

from __future__ import annotations

import base64
import logging
import re
from typing import Any

import httpx

from ..config import get_settings
from ..errors import HinaaError
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.github")

GITHUB_API = "https://api.github.com"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_BRANCH_RE = re.compile(r"^[^ ~^:?*\[\\]+$")


class _GithubClient:
    """Thin authenticated REST client; token comes from settings."""

    def __init__(self) -> None:
        settings = get_settings()
        token = settings.github_token
        if not token:
            raise HinaaError(
                "GITHUB_NOT_CONFIGURED",
                "GitHub is not connected. Add GITHUB_TOKEN to the backend env.",
                400,
                True,
            )
        self._headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "HINAA-companion",
            "Authorization": f"Bearer {token.get_secret_value()}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _repo(self, repo: str | None) -> str:
        resolved = repo or get_settings().github_default_repo
        if not resolved or not _REPO_RE.match(resolved):
            raise HinaaError(
                "GITHUB_REPO_INVALID",
                "A repository in 'owner/name' form is required.",
                400,
                True,
            )
        return resolved

    async def _request(
        self, method: str, path: str, *, json: dict[str, Any] | None = None, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, f"{GITHUB_API}{path}", headers=self._headers, json=json, params=params
            )
        if response.status_code >= 400:
            detail = _safe_api_error(response)
            raise HinaaError("GITHUB_API_ERROR", detail, 502, True)
        if response.status_code == 204 or not response.content:
            return {}
        return response.json()  # type: ignore[no-any-return]

    async def get_json(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return await self._request("GET", path, params=params)

    async def post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, json=body)

    async def patch_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PATCH", path, json=body)

    async def put_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return await self._request("PUT", path, json=body)


def _safe_api_error(response: httpx.Response) -> str:
    try:
        body = response.json()
        message = str(body.get("message") or "")
    except Exception:
        message = ""
    return f"GitHub API {response.status_code}: {message or response.reason_phrase}"[:300]


def _require_repo(params: dict[str, Any], client: _GithubClient) -> str:
    return client._repo(params.get("repo"))


async def github_repo_overview_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    meta = await client.get_json(f"/repos/{repo}")
    branches = await client.get_json(f"/repos/{repo}/branches", params={"per_page": 30})
    return {
        "status": "ok",
        "repo": repo,
        "description": meta.get("description") or "",
        "defaultBranch": meta.get("default_branch") or "main",
        "visibility": meta.get("visibility") or ("private" if meta.get("private") else "public"),
        "stars": meta.get("stargazers_count", 0),
        "openIssues": meta.get("open_issues_count", 0),
        "language": meta.get("language") or "",
        "updatedAt": meta.get("updated_at") or "",
        "branches": [
            {"name": b.get("name"), "sha": (b.get("commit") or {}).get("sha", "")[:8]}
            for b in (branches.get("branches") if isinstance(branches, dict) else branches) or []  # type: ignore[union-attr]
        ][:30],
    }


async def github_read_file_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    path = str(params.get("path") or "").strip().lstrip("/")
    if not path:
        raise HinaaError("GITHUB_PATH_REQUIRED", "A file path is required.", 400, True)
    ref = str(params.get("ref") or "").strip() or None
    query = {"ref": ref} if ref else None
    data = await client.get_json(f"/repos/{repo}/contents/{path}", params=query)
    if isinstance(data, dict) and data.get("type") == "file":
        content = ""
        if data.get("encoding") == "base64" and data.get("content"):
            content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
        return {
            "status": "ok",
            "repo": repo,
            "path": data.get("path"),
            "size": data.get("size"),
            "sha": data.get("sha"),
            "content": content[:100_000],
            "truncated": (data.get("size") or 0) > 100_000,
        }
    if isinstance(data, list):
        return {
            "status": "ok",
            "repo": repo,
            "path": path,
            "isDirectory": True,
            "entries": [
                {"name": e.get("name"), "type": e.get("type"), "size": e.get("size")} for e in data[:100]
            ],
        }
    return {"status": "ok", "repo": repo, "path": path, "content": ""}


async def _resolve_branch_sha(client: _GithubClient, repo: str, branch: str) -> tuple[str, str]:
    branch_data = await client.get_json(f"/repos/{repo}/git/ref/heads/{branch}")
    ref_obj = branch_data.get("object") or {}
    return ref_obj.get("sha", ""), branch_data.get("ref") or f"refs/heads/{branch}"


async def github_write_file_handler(params: dict[str, Any]) -> dict[str, Any]:
    """Create or update a file with a real commit (safe: requires confirmation)."""
    client = _GithubClient()
    repo = _require_repo(params, client)
    path = str(params.get("path") or "").strip().lstrip("/")
    content = str(params.get("content") or "")
    if not path:
        raise HinaaError("GITHUB_PATH_REQUIRED", "A file path is required.", 400, True)
    message = str(params.get("message") or f"HINAA: update {path}").strip()[:200]
    branch = str(params.get("branch") or "").strip()
    if not branch:
        meta = await client.get_json(f"/repos/{repo}")
        branch = meta.get("default_branch") or "main"

    sha: str | None = None
    try:
        existing = await client.get_json(f"/repos/{repo}/contents/{path}", params={"ref": branch})
        if isinstance(existing, dict) and existing.get("type") == "file":
            sha = existing.get("sha")
    except HinaaError:
        sha = None  # new file

    body: dict[str, Any] = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    result = await client.put_json(f"/repos/{repo}/contents/{path}", body)
    commit = result.get("commit") or {}
    return {
        "status": "ok",
        "repo": repo,
        "path": path,
        "branch": branch,
        "commitSha": (commit.get("sha") or "")[:10],
        "commitUrl": (commit.get("html_url") or ""),
        "action": "updated" if sha else "created",
    }


async def github_create_branch_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    branch = str(params.get("branch") or "").strip()
    if not branch or not _BRANCH_RE.match(branch):
        raise HinaaError("GITHUB_BRANCH_INVALID", "A valid branch name is required.", 400, True)
    base = str(params.get("from") or "").strip() or None
    if base:
        source_sha, _ = await _resolve_branch_sha(client, repo, base)
    else:
        meta = await client.get_json(f"/repos/{repo}")
        base = meta.get("default_branch") or "main"
        source_sha, _ = await _resolve_branch_sha(client, repo, base)
    await client.post_json(f"/repos/{repo}/git/refs", {"ref": f"refs/heads/{branch}", "sha": source_sha})
    return {"status": "ok", "repo": repo, "branch": branch, "from": base, "sha": source_sha[:10]}


async def github_list_commits_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    branch = str(params.get("branch") or "").strip() or None
    query: dict[str, Any] = {"per_page": min(int(params.get("limit") or 10), 30)}
    if branch:
        query["sha"] = branch
    data = await client.get_json(f"/repos/{repo}/commits", params=query)
    commits = data.get("commits") if isinstance(data, dict) else data
    return {
        "status": "ok",
        "repo": repo,
        "commits": [
            {
                "sha": (c.get("sha") or "")[:10],
                "message": ((c.get("commit") or {}).get("message") or "").splitlines()[0][:140],
                "author": ((c.get("commit") or {}).get("author") or {}).get("name", ""),
                "date": ((c.get("commit") or {}).get("author") or {}).get("date", ""),
            }
            for c in (commits or [])[:30]
        ],
    }


async def github_create_pull_request_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    title = str(params.get("title") or "").strip()
    head = str(params.get("head") or "").strip()
    base = str(params.get("base") or "").strip()
    if not title or not head or not base:
        raise HinaaError(
            "GITHUB_PR_PARAMS_REQUIRED",
            "title, head (source branch) and base (target branch) are required.",
            400,
            True,
        )
    body = {
        "title": title[:200],
        "head": head,
        "base": base,
        "body": str(params.get("body") or "")[:60_000],
    }
    result = await client.post_json(f"/repos/{repo}/pulls", body)
    return {
        "status": "ok",
        "repo": repo,
        "number": result.get("number"),
        "url": result.get("html_url"),
        "title": result.get("title"),
        "state": result.get("state"),
    }


async def github_list_issues_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    query: dict[str, Any] = {
        "state": str(params.get("state") or "open"),
        "per_page": min(int(params.get("limit") or 10), 30),
    }
    data = await client.get_json(f"/repos/{repo}/issues", params=query)
    issues = data.get("issues") if isinstance(data, dict) else data
    return {
        "status": "ok",
        "repo": repo,
        "issues": [
            {
                "number": i.get("number"),
                "title": (i.get("title") or "")[:160],
                "url": i.get("html_url"),
                "author": ((i.get("user") or {}).get("login") or ""),
                "labels": [l.get("name") for l in (i.get("labels") or [])][:6],
            }
            for i in (issues or [])
            if "pull_request" not in i  # issues endpoint also returns PRs
        ][:30],
    }


async def github_create_issue_handler(params: dict[str, Any]) -> dict[str, Any]:
    client = _GithubClient()
    repo = _require_repo(params, client)
    title = str(params.get("title") or "").strip()
    if not title:
        raise HinaaError("GITHUB_ISSUE_TITLE_REQUIRED", "An issue title is required.", 400, True)
    result = await client.post_json(
        f"/repos/{repo}/issues",
        {"title": title[:200], "body": str(params.get("body") or "")[:60_000]},
    )
    return {"status": "ok", "repo": repo, "number": result.get("number"), "url": result.get("html_url")}


def _def(name: str, display: str, description: str, params: dict[str, dict[str, Any]], required: list[str], *, confirm: bool = False, risk: str = "low") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        display_name=display,
        description=description,
        parameters=params,
        required_parameters=required,
        requires_confirmation=confirm,
        risk_level=risk,
    )


_REPO_PARAM = {
    "repo": {"type": "string", "description": "Repository as 'owner/name'. Falls back to the configured default repo."}
}
_PATH_PARAM = {"path": {"type": "string", "description": "File path inside the repository"}}

registry.register(
    _def(
        "github_repo_overview",
        "GitHub Repo Overview",
        "Inspect a connected GitHub repository: default branch, branches, open issues, language, recent activity.",
        {**_REPO_PARAM},
        [],
    ),
    github_repo_overview_handler,
)
registry.register(
    _def(
        "github_read_file",
        "GitHub Read File",
        "Read a file (or list a directory) from a connected GitHub repository at an optional branch/ref.",
        {**_REPO_PARAM, **_PATH_PARAM, "ref": {"type": "string", "description": "Branch, tag or SHA (optional)"}},
        ["path"],
    ),
    github_read_file_handler,
)
registry.register(
    _def(
        "github_write_file",
        "GitHub Write File",
        "Create or update a file in a connected GitHub repository as a real commit on a branch.",
        {
            **_REPO_PARAM,
            **_PATH_PARAM,
            "content": {"type": "string", "description": "Full new file content"},
            "message": {"type": "string", "description": "Commit message"},
            "branch": {"type": "string", "description": "Target branch (default: repo default branch)"},
        },
        ["path", "content"],
        confirm=True,
        risk="medium",
    ),
    github_write_file_handler,
)
registry.register(
    _def(
        "github_create_branch",
        "GitHub Create Branch",
        "Create a new branch from an existing branch or the default branch.",
        {**_REPO_PARAM, "branch": {"type": "string", "description": "New branch name"}, "from": {"type": "string", "description": "Source branch (optional)"}},
        ["branch"],
        confirm=True,
    ),
    github_create_branch_handler,
)
registry.register(
    _def(
        "github_list_commits",
        "GitHub List Commits",
        "List recent commits on a repository branch.",
        {**_REPO_PARAM, "branch": {"type": "string", "description": "Branch (optional)"}, "limit": {"type": "integer", "description": "Max commits (default 10)"}},
        [],
    ),
    github_list_commits_handler,
)
registry.register(
    _def(
        "github_create_pull_request",
        "GitHub Create Pull Request",
        "Open a pull request from a working branch into a base branch.",
        {**_REPO_PARAM, "title": {"type": "string", "description": "PR title"}, "head": {"type": "string", "description": "Source branch"}, "base": {"type": "string", "description": "Target branch"}, "body": {"type": "string", "description": "PR description (markdown)"}},
        ["title", "head", "base"],
        confirm=True,
        risk="medium",
    ),
    github_create_pull_request_handler,
)
registry.register(
    _def(
        "github_list_issues",
        "GitHub List Issues",
        "List open or closed issues on a connected repository.",
        {**_REPO_PARAM, "state": {"type": "string", "enum": ["open", "closed", "all"], "description": "Issue state (default open)"}, "limit": {"type": "integer", "description": "Max issues (default 10)"}},
        [],
    ),
    github_list_issues_handler,
)
registry.register(
    _def(
        "github_create_issue",
        "GitHub Create Issue",
        "Create an issue on a connected repository.",
        {**_REPO_PARAM, "title": {"type": "string", "description": "Issue title"}, "body": {"type": "string", "description": "Issue body (markdown)"}},
        ["title"],
        confirm=True,
    ),
    github_create_issue_handler,
)
