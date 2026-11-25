"""Phase 1 Workspace Coding Surface: line-numbered read, exact-match edit, glob, grep.

Provides bounded, workspace-confined coding primitives modeled on production
coding agents:
- ``workspace_read_file``: line-numbered slices with SHA-256 base hash and
  explicit truncation notices so callers never reason from partial reads silently.
- ``workspace_edit_file``: exact-string replacement with ambiguity refusal,
  optional base-hash conflict guard, AST syntax verification, atomic write, and
  unified diff output.
- ``workspace_glob``: workspace-confined file discovery skipping vendor/build
  trees (``.git``, ``.venv``, ``node_modules``, ``__pycache__``).
- ``workspace_grep``: workspace-confined text/regex search returning structured
  ``path:line:content`` matches.
"""

from __future__ import annotations

import fnmatch
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..agent.coding_agent import CodePatch, apply_code_patch, compute_file_hash
from ..runtime_paths import project_root
from .registry import RiskTier, ToolDefinition, ToolEffect, registry

_SKIP_DIRS = frozenset({
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".hina",
})
_MAX_READ_LINES = 400
_MAX_READ_CHARS = 45_000
_MAX_SEARCH_FILE_BYTES = 1_048_576


def _resolve_workspace_root(override: str | None = None) -> Path:
    raw = (override or "").strip() or os.environ.get("HINAA_LOCAL_WORKSPACE_DIR") or str(project_root())
    return Path(os.path.realpath(os.path.abspath(raw)))


def _resolve_inside_workspace(root: Path, rel_path: str) -> Path:
    if os.path.isabs(rel_path):
        candidate = Path(os.path.realpath(os.path.abspath(rel_path)))
    else:
        candidate = Path(os.path.realpath(os.path.abspath(root / rel_path)))
    if candidate != root and root not in candidate.parents:
        raise ValueError(f"Path {rel_path!r} escapes workspace root {root}")
    return candidate


def _relative_posix(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


class WorkspaceReadFileParams(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=500, description="Path relative to workspace root.")
    start_line: int = Field(1, ge=1, description="1-based first line to return.")
    end_line: int = Field(200, ge=1, description="1-based inclusive last line to return.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceEditFileParams(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=500, description="Target file relative to workspace root.")
    target_content: str = Field(..., min_length=1, description="Exact verbatim existing snippet to replace.")
    replacement_content: str = Field(..., description="Exact replacement snippet.")
    base_hash: str = Field("", description="Optional SHA-256 base hash from workspace_read_file.")
    allow_multiple: bool = Field(False, description="Allow replacing multiple identical occurrences.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceGlobParams(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=250, description="Glob pattern such as '**/*.py'.")
    subpath: str = Field(".", max_length=500, description="Directory relative to workspace root.")
    max_results: int = Field(200, ge=1, le=500, description="Maximum matching file paths to return.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceGrepParams(BaseModel):
    pattern: str = Field(..., min_length=1, max_length=500, description="Regex or text pattern to search.")
    subpath: str = Field(".", max_length=500, description="File or directory relative to workspace root.")
    file_glob: str = Field("*", max_length=120, description="Optional filename glob filter (e.g. '*.py').")
    max_matches: int = Field(100, ge=1, le=300, description="Maximum matching lines to return.")
    case_sensitive: bool = Field(False, description="Whether search matching is case-sensitive.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


async def workspace_read_file_handler(params: WorkspaceReadFileParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    if not target.exists() or not target.is_file():
        return {"status": "error", "code": "FILE_NOT_FOUND", "error": f"File not found: {params.file_path}"}

    content = target.read_text(encoding="utf-8", errors="replace")
    all_lines = content.splitlines()
    total_lines = len(all_lines)
    start = min(params.start_line, max(1, total_lines))
    requested_end = max(start, params.end_line)
    capped_end = min(requested_end, start + _MAX_READ_LINES - 1, total_lines)

    rendered_lines: list[str] = []
    char_count = 0
    actual_end = start - 1
    truncated_by_chars = False
    for line_no in range(start, capped_end + 1):
        formatted = f"{line_no}: {all_lines[line_no - 1]}"
        if rendered_lines and char_count + len(formatted) + 1 > _MAX_READ_CHARS:
            truncated_by_chars = True
            break
        rendered_lines.append(formatted)
        char_count += len(formatted) + 1
        actual_end = line_no

    if total_lines == 0:
        actual_end = 0
    truncated = (start > 1) or (actual_end < total_lines) or truncated_by_chars
    notice = (
        f"[Output truncated: showing lines {start}-{actual_end} of {total_lines}]"
        if truncated and total_lines > 0
        else ""
    )

    return {
        "status": "success",
        "filePath": _relative_posix(root, target),
        "startLine": start if total_lines > 0 else 0,
        "endLine": actual_end,
        "totalLines": total_lines,
        "baseHash": compute_file_hash(content),
        "truncated": truncated,
        "truncationNotice": notice,
        "content": "\n".join(rendered_lines),
    }


async def workspace_edit_file_handler(params: WorkspaceEditFileParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    rel = _relative_posix(root, target)
    result = apply_code_patch(
        str(root),
        CodePatch(
            file_path=rel,
            target_content=params.target_content,
            replacement_content=params.replacement_content,
            base_hash=params.base_hash,
            allow_multiple=params.allow_multiple,
        ),
        validate_syntax=True,
    )
    if not result.success:
        return {
            "status": "error",
            "code": result.failure_category.value.upper() if result.failure_category else "EDIT_FAILED",
            "filePath": rel,
            "error": result.error or "Patch could not be applied.",
        }
    return {
        "status": "success",
        "filePath": rel,
        "newHash": result.new_hash,
        "diff": result.diff,
    }


def _iter_workspace_files(root: Path, base: Path):
    if base.is_file():
        yield base
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        for name in sorted(filenames):
            p = Path(dirpath) / name
            # Skip symlinks pointing outside root
            try:
                resolved = Path(os.path.realpath(p))
            except OSError:
                continue
            if resolved == root or root in resolved.parents:
                yield p


async def workspace_glob_handler(params: WorkspaceGlobParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        base = _resolve_inside_workspace(root, params.subpath)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    if not base.exists():
        return {"status": "error", "code": "NOT_FOUND", "error": f"Path not found: {params.subpath}"}

    pattern = params.pattern.replace("\\", "/").lstrip("./")
    matches: list[str] = []
    truncated = False
    for file_path in _iter_workspace_files(root, base):
        rel = _relative_posix(root, file_path)
        sub_rel = _relative_posix(base, file_path) if base.is_dir() else file_path.name
        if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(sub_rel, pattern) or fnmatch.fnmatch(file_path.name, pattern):
            matches.append(rel)
            if len(matches) >= params.max_results:
                truncated = True
                break

    return {
        "status": "success",
        "pattern": params.pattern,
        "count": len(matches),
        "truncated": truncated,
        "files": matches,
    }


async def workspace_grep_handler(params: WorkspaceGrepParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        base = _resolve_inside_workspace(root, params.subpath)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    if not base.exists():
        return {"status": "error", "code": "NOT_FOUND", "error": f"Path not found: {params.subpath}"}

    flags = 0 if params.case_sensitive else re.IGNORECASE
    try:
        regex = re.compile(params.pattern, flags)
    except re.error:
        regex = re.compile(re.escape(params.pattern), flags)

    matches: list[dict[str, Any]] = []
    truncated = False
    for file_path in _iter_workspace_files(root, base):
        if not fnmatch.fnmatch(file_path.name, params.file_glob):
            continue
        try:
            if file_path.stat().st_size > _MAX_SEARCH_FILE_BYTES:
                continue
            raw = file_path.read_bytes()
        except OSError:
            continue
        if b"\x00" in raw[:4096]:
            continue
        text = raw.decode("utf-8", errors="replace")
        rel = _relative_posix(root, file_path)
        for line_no, line in enumerate(text.splitlines(), 1):
            if regex.search(line):
                matches.append({
                    "file": rel,
                    "line": line_no,
                    "text": line[:400],
                    "formatted": f"{rel}:{line_no}: {line[:400]}",
                })
                if len(matches) >= params.max_matches:
                    truncated = True
                    break
        if truncated:
            break

    return {
        "status": "success",
        "pattern": params.pattern,
        "count": len(matches),
        "truncated": truncated,
        "matches": matches,
    }


registry.register(
    ToolDefinition(
        name="workspace_read_file",
        display_name="Workspace: Read File (Line-Numbered)",
        description="Read a line-numbered range of a workspace file with base SHA-256 hash and explicit truncation notice.",
        parameters={
            "file_path": {"type": "string", "description": "Relative path inside workspace root."},
            "start_line": {"type": "integer", "description": "1-based start line (default 1)."},
            "end_line": {"type": "integer", "description": "1-based end line (default 200)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["file_path"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    workspace_read_file_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_edit_file",
        display_name="Workspace: Exact-Match File Edit",
        description="Atomically edit a workspace file via exact-string replacement with ambiguity, base-hash, and AST validation.",
        parameters={
            "file_path": {"type": "string", "description": "Relative path inside workspace root."},
            "target_content": {"type": "string", "description": "Exact existing snippet to replace."},
            "replacement_content": {"type": "string", "description": "Replacement snippet."},
            "base_hash": {"type": "string", "description": "Optional base hash from workspace_read_file."},
            "allow_multiple": {"type": "boolean", "description": "Allow replacing multiple identical snippets."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["file_path", "target_content", "replacement_content"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=True,
        risk_tier=RiskTier.TIER_3_PROCESS,
        risk_level="high",
        effect=ToolEffect.MUTATE_WORKSPACE,
    ),
    workspace_edit_file_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_glob",
        display_name="Workspace: Glob File Search",
        description="Discover files inside the workspace root by glob pattern without spawning shell find.",
        parameters={
            "pattern": {"type": "string", "description": "Glob pattern such as '**/*.py'."},
            "subpath": {"type": "string", "description": "Subdirectory inside workspace (default '.')."},
            "max_results": {"type": "integer", "description": "Maximum paths to return (default 200)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["pattern"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    workspace_glob_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_grep",
        display_name="Workspace: Grep Content Search",
        description="Search workspace files by regex/text and return file:line:content matches.",
        parameters={
            "pattern": {"type": "string", "description": "Regex or literal search pattern."},
            "subpath": {"type": "string", "description": "File or directory inside workspace (default '.')."},
            "file_glob": {"type": "string", "description": "Filename glob filter (default '*')."},
            "max_matches": {"type": "integer", "description": "Maximum matches to return (default 100)."},
            "case_sensitive": {"type": "boolean", "description": "Case-sensitive search (default false)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["pattern"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    workspace_grep_handler,
)
