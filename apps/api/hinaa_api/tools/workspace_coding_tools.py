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

import difflib
import fnmatch
import hashlib
import json
import os
import re
import shlex
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from collections import deque
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
    ".pytest_tmp",
    ".runtime",
    ".ruff_cache",
    ".mypy_cache",
    ".turbo",
    ".next",
    "coverage",
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


class WorkspaceListDirParams(BaseModel):
    subpath: str = Field(".", max_length=500, description="Directory relative to workspace root.")
    max_depth: int = Field(3, ge=1, le=5, description="Maximum recursion depth (1..5).")
    max_entries: int = Field(250, ge=1, le=600, description="Maximum files/directories to return.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceWriteFileParams(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=500, description="Target file path relative to workspace root.")
    content: str = Field(..., description="Full file contents to write atomically.")
    overwrite: bool = Field(True, description="Allow overwriting if file already exists.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceRunCommandParams(BaseModel):
    command: str = Field(..., min_length=1, max_length=600, description="Executable command or verification line (no shell operators).")
    args: list[str] | None = Field(None, description="Optional explicit argument list.")
    timeout_seconds: int = Field(45, ge=1, le=120, description="Execution timeout in seconds (1..120).")
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


def _check_js_or_html_syntax(ext: str, content: str) -> str | None:
    """Validate `.js`/`.mjs` files and inline non-JSON `<script>` blocks via `node --check` when available."""
    import shutil as _shutil

    if ext not in (".js", ".mjs", ".html", ".htm"):
        return None
    node_bin = _shutil.which("node")
    if not node_bin:
        return None
    if ext in (".js", ".mjs"):
        blocks = [content]
        label_prefix = "JavaScript syntax error"
    else:
        blocks = re.findall(
            r"<script(?![^>]*\btype\s*=\s*[\"'](?:application/(?:json|ld\+json)|importmap)[\"'])[^>]*>([\s\S]*?)</script>",
            content,
            flags=re.IGNORECASE,
        )
        label_prefix = "Inline <script> syntax error"
    for idx_b, js_body in enumerate(blocks):
        if not js_body.strip():
            continue
        fd_js, tmp_js = tempfile.mkstemp(prefix=".hinaa_chk_", suffix=".js")
        try:
            with os.fdopen(fd_js, "w", encoding="utf-8") as fh:
                fh.write(js_body)
            chk = subprocess.run([node_bin, "--check", tmp_js], capture_output=True, text=True, timeout=8)
            if chk.returncode != 0:
                detail = (chk.stderr or chk.stdout or "").strip()[:300]
                prefix = f"{label_prefix} #{idx_b + 1}" if len(blocks) > 1 else label_prefix
                return f"{prefix}: {detail}"
        finally:
            if os.path.exists(tmp_js):
                os.unlink(tmp_js)
    return None


def _unique_normalized_target(existing_content: str, target_content: str) -> str | None:
    """Recover exact original slice when only CRLF, trailing spaces, or horizontal whitespace differs uniquely."""
    norm_file_lines = existing_content.replace("\r\n", "\n").splitlines()
    raw_file_lines = existing_content.splitlines(keepends=True)
    raw_target_lines = target_content.replace("\r\n", "\n").splitlines()
    if not raw_target_lines or len(raw_target_lines) > len(norm_file_lines):
        return None
    n = len(raw_target_lines)

    for norm_fn in (lambda s: s.rstrip(), lambda s: " ".join(s.split())):
        target_norm = [norm_fn(ln) for ln in raw_target_lines]
        file_norm = [norm_fn(ln) for ln in norm_file_lines]
        matches = [i for i in range(len(file_norm) - n + 1) if file_norm[i : i + n] == target_norm]
        if len(matches) == 1:
            start = matches[0]
            joined = "".join(raw_file_lines[start : start + n])
            if target_content and not target_content.endswith(("\n", "\r")) and joined.endswith(("\r\n", "\n")):
                return joined.rstrip("\r\n")
            return joined
    return None


async def workspace_edit_file_handler(params: WorkspaceEditFileParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    rel = _relative_posix(root, target)
    if _is_sensitive_write_target(rel):
        return {
            "status": "error",
            "code": "SENSITIVE_PATH_BLOCKED",
            "filePath": rel,
            "error": f"Refusing to modify sensitive path {rel!r}.",
        }
    prior_content = target.read_text(encoding="utf-8", errors="replace") if target.exists() and target.is_file() else ""
    target_snippet = params.target_content
    if prior_content and target_snippet not in prior_content:
        recovered = _unique_normalized_target(prior_content, target_snippet)
        if recovered:
            target_snippet = recovered

    result = apply_code_patch(
        str(root),
        CodePatch(
            file_path=rel,
            target_content=target_snippet,
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
    ext = target.suffix.lower()
    if ext in (".js", ".mjs", ".html", ".htm"):
        patched_text = target.read_text(encoding="utf-8", errors="replace")
        js_err = _check_js_or_html_syntax(ext, patched_text)
        if js_err:
            # Roll back immediately so disk never retains broken HTML/JS syntax
            target.write_text(prior_content, encoding="utf-8")
            return {
                "status": "error",
                "code": "SYNTAX_ERROR",
                "filePath": rel,
                "error": js_err,
            }
    return {
        "status": "success",
        "filePath": rel,
        "newHash": result.new_hash,
        "diff": result.diff,
    }


class WorkspaceDeleteFileParams(BaseModel):
    file_path: str = Field(..., min_length=1, max_length=500, description="Relative path inside workspace root to delete.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


async def workspace_delete_file_handler(params: WorkspaceDeleteFileParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    rel = _relative_posix(root, target)
    if _is_sensitive_write_target(rel):
        return {
            "status": "error",
            "code": "SENSITIVE_PATH_BLOCKED",
            "filePath": rel,
            "error": f"Refusing to delete sensitive path {rel!r}.",
        }
    if not target.exists():
        return {"status": "error", "code": "FILE_NOT_FOUND", "filePath": rel, "error": f"File not found: {rel}"}
    if target.is_dir():
        return {"status": "error", "code": "IS_A_DIRECTORY", "filePath": rel, "error": f"Refusing to delete directory {rel!r}."}

    prior = target.read_text(encoding="utf-8", errors="replace")
    deleted_bytes = target.stat().st_size
    target.unlink()
    diff_lines = list(
        difflib.unified_diff(prior.splitlines(keepends=True), [], fromfile=f"a/{rel}", tofile="/dev/null")
    )
    return {
        "status": "success",
        "filePath": rel,
        "deletedBytes": deleted_bytes,
        "diff": "".join(diff_lines)[:4000],
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
        name="workspace_delete_file",
        display_name="Workspace: Delete Confined File",
        description="Safely delete a non-sensitive workspace file inside workspace_root and return deleted diff.",
        parameters={
            "file_path": {"type": "string", "description": "Relative path inside workspace root to delete."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["file_path"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_1_REVERSIBLE,
        risk_level="medium",
        effect=ToolEffect.MUTATE_WORKSPACE,
    ),
    workspace_delete_file_handler,
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

_MAX_WRITE_BYTES = 512_000
_SENSITIVE_WRITE_NAMES = frozenset({".env", ".env.local", ".env.production", "id_rsa", "id_ed25519"})
_SENSITIVE_WRITE_EXTS = frozenset({".pem", ".key", ".p12", ".pfx"})
_SHELL_METACHAR_RE = re.compile(r"[;&|`$<>]|&&|\|\|")
_SAFE_VERIFY_COMMANDS = frozenset({"pytest", "python", "python3", "node", "npm", "pnpm", "npx", "tsc", "vitest", "vite", "git", "ffprobe", "ffmpeg", "ruff", "eslint", "mypy"})
_SAFE_GIT_SUBCOMMANDS = frozenset({"status", "diff", "log", "branch", "show"})
_SAFE_NODE_PM_SUBCOMMANDS = frozenset({"test", "typecheck", "lint", "build"})
_SAFE_SERVER_EXECUTABLES = frozenset({"python", "python3", "uvicorn", "node", "npm", "pnpm", "npx", "vite"})
_UNSAFE_FLAGS = frozenset({"--force", "-f", "--hard", "push", "reset", "clean", "rm", "del", "erase"})


def _is_sensitive_write_target(rel_path: str) -> bool:
    norm = rel_path.replace("\\", "/").strip("/")
    parts = [p.lower() for p in norm.split("/") if p]
    if ".git" in parts or ".hina" in parts:
        return True
    if not parts:
        return True
    name = parts[-1]
    if name in _SENSITIVE_WRITE_NAMES or name.startswith(".env."):
        return True
    return any(name.endswith(ext) for ext in _SENSITIVE_WRITE_EXTS)


def _sanitized_command_env() -> dict[str, str]:
    keep = {
        "PATH", "SYSTEMROOT", "SYSTEMDRIVE", "COMSPEC", "WINDIR", "PATHEXT",
        "TEMP", "TMP", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "PYTHONPATH", "PYTHONIOENCODING", "PYTHONUTF8", "LANG", "LC_ALL",
        "TERM", "APPDATA", "LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
    }
    env = {k: v for k, v in os.environ.items() if k.upper() in keep}
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def _parse_command_argv(command: str, explicit_args: list[str] | None = None) -> list[str]:
    if _SHELL_METACHAR_RE.search(command):
        raise ValueError("Shell metacharacters (;, &, |, `, $, >, <) are disallowed in bounded workspace commands.")
    if explicit_args:
        argv = [command.strip(), *[str(a) for a in explicit_args]]
    else:
        argv = shlex.split(command, posix=(os.name != "nt"))
        argv = [a[1:-1] if len(a) >= 2 and a[0] == a[-1] and a[0] in ("'", '"') else a for a in argv]
    argv = [a for a in argv if a]
    if not argv:
        raise ValueError("Empty command.")
    for part in argv:
        if _SHELL_METACHAR_RE.search(part):
            raise ValueError("Shell metacharacters are disallowed in command arguments.")
    return argv


def is_safe_verify_command(command: str, explicit_args: list[str] | None = None) -> bool:
    """True when the command cleanly runs read-only inspect, test, typecheck, or build checks inside workspace."""
    try:
        argv = _parse_command_argv(command, explicit_args)
    except ValueError:
        return False
    exe = Path(argv[0]).name.lower()
    if exe.endswith(".exe") or exe.endswith(".cmd"):
        exe = exe.rsplit(".", 1)[0]
    if exe not in _SAFE_VERIFY_COMMANDS:
        return False
    lowered_rest = [a.lower() for a in argv[1:]]
    if any(tok in _UNSAFE_FLAGS for tok in lowered_rest):
        return False
    if exe == "git":
        return bool(lowered_rest) and lowered_rest[0] in _SAFE_GIT_SUBCOMMANDS
    if exe in ("npm", "pnpm"):
        if not lowered_rest:
            return False
        if lowered_rest[0] in _SAFE_NODE_PM_SUBCOMMANDS:
            return True
        if lowered_rest[0] == "run" and len(lowered_rest) >= 2 and lowered_rest[1] in _SAFE_NODE_PM_SUBCOMMANDS | {"build"}:
            return True
        if lowered_rest[0] == "exec" and len(lowered_rest) >= 2 and lowered_rest[1] in ("tsc", "vitest", "eslint", "vite"):
            return True
        return False
    if exe == "vite":
        return bool(lowered_rest) and lowered_rest[0] == "build"
    if exe in ("python", "python3"):
        if not lowered_rest:
            return False
        if lowered_rest[0] == "-c":
            return True
        if lowered_rest[0] == "-m" and len(lowered_rest) >= 2:
            return lowered_rest[1] in {"pytest", "unittest", "py_compile", "compileall", "json.tool", "pip"}
        # Running a local .py script inside workspace root cleanly
        return not lowered_rest[0].startswith("-")
    return True


def is_safe_server_command(command: str, explicit_args: list[str] | None = None) -> bool:
    """True when starting a bounded local server or preview daemon cleanly inside workspace root."""
    try:
        argv = _parse_command_argv(command, explicit_args)
    except ValueError:
        return False
    exe = Path(argv[0]).name.lower()
    if exe.endswith(".exe") or exe.endswith(".cmd"):
        exe = exe.rsplit(".", 1)[0]
    if exe not in _SAFE_SERVER_EXECUTABLES:
        return False
    lowered = [a.lower() for a in argv[1:]]
    if any(tok in _UNSAFE_FLAGS for tok in lowered):
        return False
    if exe in ("python", "python3"):
        if "-m" in lowered:
            idx = lowered.index("-m")
            mod = lowered[idx + 1] if idx + 1 < len(lowered) else ""
            return mod in {"http.server", "uvicorn", "flask"}
        return bool(lowered) and not lowered[0].startswith("-")
    if exe in ("npm", "pnpm"):
        return bool(lowered) and (
            lowered[0] in ("dev", "preview", "start")
            or (lowered[0] == "run" and len(lowered) >= 2 and lowered[1] in ("dev", "preview", "start"))
            or (lowered[0] == "exec" and len(lowered) >= 2 and lowered[1] == "vite")
        )
    if exe == "uvicorn":
        return True
    if exe in ("node", "vite", "npx"):
        return bool(lowered) if exe == "node" else True
    return False


def _resolve_command_executable(argv: list[str], root: Path) -> list[str]:
    exe = Path(argv[0]).name.lower()
    if exe in ("python", "python3"):
        return [sys.executable, *argv[1:]]
    if exe == "pytest":
        return [sys.executable, "-m", "pytest", *argv[1:]]
    if os.name == "nt" and exe in ("npm", "pnpm", "npx"):
        import shutil
        resolved = shutil.which(exe) or shutil.which(f"{exe}.cmd") or argv[0]
        return [resolved, *argv[1:]]
    return argv


async def workspace_list_dir_handler(params: WorkspaceListDirParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        base = _resolve_inside_workspace(root, params.subpath)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}
    if not base.exists() or not base.is_dir():
        return {"status": "error", "code": "NOT_FOUND", "error": f"Directory not found: {params.subpath}"}

    entries: list[dict[str, Any]] = []
    truncated = False
    base_parts = len(base.parts)
    for dirpath, dirnames, filenames in os.walk(base):
        cur = Path(dirpath)
        depth = len(cur.parts) - base_parts
        dirnames[:] = sorted(d for d in dirnames if d not in _SKIP_DIRS)
        if depth >= params.max_depth:
            dirnames[:] = []
        for d in dirnames:
            entries.append({"type": "dir", "path": _relative_posix(root, cur / d)})
            if len(entries) >= params.max_entries:
                truncated = True
                break
        if truncated:
            break
        for f in sorted(filenames):
            fp = cur / f
            entries.append({
                "type": "file",
                "path": _relative_posix(root, fp),
                "bytes": fp.stat().st_size if fp.exists() else 0,
            })
            if len(entries) >= params.max_entries:
                truncated = True
                break
        if truncated:
            break
    return {
        "status": "success",
        "subpath": _relative_posix(root, base),
        "count": len(entries),
        "truncated": truncated,
        "entries": entries,
    }


async def workspace_write_file_handler(params: WorkspaceWriteFileParams) -> dict[str, Any]:
    try:
        root = _resolve_workspace_root(params.workspace_root)
        target = _resolve_inside_workspace(root, params.file_path)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}

    rel = _relative_posix(root, target)
    if _is_sensitive_write_target(rel):
        return {
            "status": "error",
            "code": "SENSITIVE_PATH_BLOCKED",
            "filePath": rel,
            "error": f"Refusing to overwrite sensitive path {rel!r}.",
        }
    raw_bytes = params.content.encode("utf-8")
    if len(raw_bytes) > _MAX_WRITE_BYTES:
        return {
            "status": "error",
            "code": "FILE_TOO_LARGE",
            "filePath": rel,
            "error": f"File exceeds {_MAX_WRITE_BYTES} byte write cap.",
        }
    if target.exists() and not params.overwrite:
        return {
            "status": "error",
            "code": "FILE_EXISTS",
            "filePath": rel,
            "error": f"File {rel} already exists and overwrite=False.",
        }

    ext = target.suffix.lower()
    if ext == ".py":
        try:
            compile(params.content, rel, "exec")
        except SyntaxError as syn:
            return {
                "status": "error",
                "code": "SYNTAX_ERROR",
                "filePath": rel,
                "error": f"Python syntax error line {syn.lineno}: {syn.msg}",
            }
    elif ext == ".json":
        try:
            json.loads(params.content)
        except json.JSONDecodeError as je:
            return {
                "status": "error",
                "code": "SYNTAX_ERROR",
                "filePath": rel,
                "error": f"JSON syntax error line {je.lineno}: {je.msg}",
            }
    elif ext in (".js", ".mjs", ".html", ".htm"):
        js_err = _check_js_or_html_syntax(ext, params.content)
        if js_err:
            return {
                "status": "error",
                "code": "SYNTAX_ERROR",
                "filePath": rel,
                "error": js_err,
            }

    prior = target.read_text(encoding="utf-8", errors="replace") if target.exists() and target.is_file() else ""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=".hinaa_tmp_", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(params.content)
        os.replace(tmp_name, target)
    except Exception:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise

    diff_lines = list(
        difflib.unified_diff(
            prior.splitlines(keepends=True),
            params.content.splitlines(keepends=True),
            fromfile=f"a/{rel}" if prior else "/dev/null",
            tofile=f"b/{rel}",
        )
    )
    return {
        "status": "success",
        "filePath": rel,
        "created": not bool(prior),
        "bytesWritten": len(raw_bytes),
        "newHash": hashlib.sha256(raw_bytes).hexdigest(),
        "isHtml": ext in (".html", ".htm", ".svg"),
        "diff": "".join(diff_lines)[:6000],
    }


async def workspace_run_command_handler(params: WorkspaceRunCommandParams) -> dict[str, Any]:
    import asyncio
    from ..agent.runtime import _sanitize_value

    try:
        root = _resolve_workspace_root(params.workspace_root)
    except ValueError as err:
        return {"status": "error", "code": "WORKSPACE_ESCAPE", "error": str(err)}
    try:
        argv = _parse_command_argv(params.command, params.args)
    except ValueError as err:
        return {"status": "error", "code": "COMMAND_REJECTED", "error": str(err)}

    exec_argv = _resolve_command_executable(argv, root)
    t0 = time.perf_counter()

    def _run_sync() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            exec_argv,
            cwd=str(root),
            env=_sanitized_command_env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=float(params.timeout_seconds),
            shell=False,
        )

    try:
        proc = await asyncio.to_thread(_run_sync)
    except subprocess.TimeoutExpired:
        return {
            "status": "error",
            "code": "COMMAND_TIMEOUT",
            "command": " ".join(argv),
            "error": f"Command timed out after {params.timeout_seconds}s.",
        }
    except FileNotFoundError as fnf:
        return {
            "status": "error",
            "code": "EXECUTABLE_NOT_FOUND",
            "command": " ".join(argv),
            "error": f"Executable not found: {fnf.filename or argv[0]}",
        }

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
    stdout = _sanitize_value((proc.stdout or "")[-12_000:])
    stderr = _sanitize_value((proc.stderr or "")[-12_000:])
    return {
        "status": "success" if proc.returncode == 0 else "error",
        "code": "EXIT_NONZERO" if proc.returncode != 0 else None,
        "command": " ".join(argv),
        "exitCode": proc.returncode,
        "durationMs": elapsed_ms,
        "stdout": stdout,
        "stderr": stderr,
        "error": f"Exit code {proc.returncode}: {stderr[:300] or stdout[:300]}" if proc.returncode != 0 else None,
    }


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

registry.register(
    ToolDefinition(
        name="workspace_list_dir",
        display_name="Workspace: List Directory Tree",
        description="List files and subdirectories inside workspace root up to bounded depth.",
        parameters={
            "subpath": {"type": "string", "description": "Directory relative to workspace root (default '.')."},
            "max_depth": {"type": "integer", "description": "Recursion depth (1..5, default 3)."},
            "max_entries": {"type": "integer", "description": "Maximum entries to return (default 250)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=[],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    workspace_list_dir_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_write_file",
        display_name="Workspace: Create or Write File",
        description="Atomically create or overwrite a file (HTML, Python, JS/TS, JSON, tests) inside workspace root with syntax validation and unified diff.",
        parameters={
            "file_path": {"type": "string", "description": "Relative path inside workspace root (e.g. 'exports/app.html')."},
            "content": {"type": "string", "description": "Complete UTF-8 file content to write."},
            "overwrite": {"type": "boolean", "description": "Overwrite if file already exists (default true)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["file_path", "content"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_1_REVERSIBLE,
        risk_level="medium",
        effect=ToolEffect.MUTATE_WORKSPACE,
    ),
    workspace_write_file_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_run_command",
        display_name="Workspace: Bounded Command & Test Runner",
        description="Execute bounded tests, linters, typechecks, python/node scripts, git status/diff, or ffmpeg/ffprobe inside workspace root.",
        parameters={
            "command": {"type": "string", "description": "Executable + flags (e.g. 'pytest tests/test_app.py -q' or 'git diff --stat')."},
            "args": {"type": "array", "description": "Optional argument array."},
            "timeout_seconds": {"type": "integer", "description": "Execution timeout seconds (default 45)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["command"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=True,
        risk_tier=RiskTier.TIER_3_PROCESS,
        risk_level="high",
        effect=ToolEffect.EXECUTE_PROCESS,
    ),
    workspace_run_command_handler,
)


class _ManagedProcess:
    def __init__(self, process_id: str, command: str, proc: subprocess.Popen[str], ready_port: int | None) -> None:
        self.process_id = process_id
        self.command = command
        self.proc = proc
        self.ready_port = ready_port
        self.started_at = time.time()
        self.lines: deque[str] = deque(maxlen=300)
        self._lock = threading.Lock()
        self._reader = threading.Thread(target=self._drain, daemon=True)
        self._reader.start()

    def _drain(self) -> None:
        if not self.proc.stdout:
            return
        try:
            for line in iter(self.proc.stdout.readline, ""):
                if not line:
                    break
                with self._lock:
                    self.lines.append(line.rstrip("\r\n"))
        except Exception:
            pass

    def tail(self, n: int = 50) -> list[str]:
        with self._lock:
            return list(self.lines)[-max(1, n):]

    def running(self) -> bool:
        return self.proc.poll() is None


_PROCESS_POOL: dict[str, _ManagedProcess] = {}
_PROCESS_POOL_LOCK = threading.Lock()


def _wait_loopback_port(port: int, timeout_s: float = 5.0) -> bool:
    deadline = time.perf_counter() + timeout_s
    while time.perf_counter() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.3):
                return True
        except OSError:
            time.sleep(0.15)
    return False


class WorkspaceStartProcessParams(BaseModel):
    command: str = Field(..., min_length=1, max_length=600, description="Safe local server command (e.g. 'python -m http.server 8123' or 'uvicorn app:app --port 8123').")
    args: list[str] | None = Field(None, description="Optional explicit argument list.")
    ready_port: int | None = Field(None, ge=1024, le=65535, description="Optional local loopback port to wait for readiness.")
    ready_wait_ms: int = Field(2500, ge=200, le=10000, description="Milliseconds to wait for startup logs/port.")
    workspace_root: str | None = Field(None, max_length=500, description="Optional workspace root override.")


class WorkspaceProcessLogsParams(BaseModel):
    process_id: str = Field(..., min_length=1, max_length=80, description="Managed background process id.")
    tail: int = Field(50, ge=1, le=300, description="Trailing log lines to return.")


class WorkspaceStopProcessParams(BaseModel):
    process_id: str = Field(..., min_length=1, max_length=80, description="Managed background process id to terminate.")


async def workspace_start_process_handler(params: WorkspaceStartProcessParams) -> dict[str, Any]:
    import asyncio
    from ..agent.runtime import _sanitize_value

    try:
        root = _resolve_workspace_root(params.workspace_root)
        argv = _parse_command_argv(params.command, params.args)
    except ValueError as err:
        return {"status": "error", "code": "COMMAND_REJECTED", "error": str(err)}

    if not is_safe_server_command(params.command, params.args):
        return {
            "status": "error",
            "code": "SERVER_CMD_REJECTED",
            "error": "Only bounded local dev servers (python -m http.server/uvicorn/flask, node, npm/pnpm dev/preview/vite) are allowed.",
        }

    with _PROCESS_POOL_LOCK:
        for pid_k, mp in list(_PROCESS_POOL.items()):
            if not mp.running() and time.time() - mp.started_at > 300:
                _PROCESS_POOL.pop(pid_k, None)
        live_count = sum(1 for mp in _PROCESS_POOL.values() if mp.running())
        if live_count >= 6:
            return {"status": "error", "code": "PROCESS_LIMIT_REACHED", "error": "Too many active background processes (max 6). Stop old ones first."}

    exec_argv = _resolve_command_executable(argv, root)
    try:
        proc = subprocess.Popen(
            exec_argv,
            cwd=str(root),
            env=_sanitized_command_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except FileNotFoundError as fnf:
        return {"status": "error", "code": "EXECUTABLE_NOT_FOUND", "error": f"Executable not found: {fnf.filename or argv[0]}"}

    pid = f"proc-{uuid.uuid4().hex[:8]}"
    managed = _ManagedProcess(pid, " ".join(argv), proc, params.ready_port)
    with _PROCESS_POOL_LOCK:
        _PROCESS_POOL[pid] = managed

    listening = False
    if params.ready_port is not None:
        listening = await asyncio.to_thread(_wait_loopback_port, params.ready_port, params.ready_wait_ms / 1000.0)
    else:
        await asyncio.sleep(min(params.ready_wait_ms, 2000) / 1000.0)

    exit_code = proc.poll()
    recent = _sanitize_value("\n".join(managed.tail(40)))
    if exit_code is not None and exit_code != 0:
        return {
            "status": "error",
            "code": "PROCESS_EXITED",
            "processId": pid,
            "pid": proc.pid,
            "exitCode": exit_code,
            "recentOutput": recent,
            "error": f"Background process exited early with code {exit_code}: {recent[-300:]}",
        }
    return {
        "status": "success",
        "processId": pid,
        "pid": proc.pid,
        "command": managed.command,
        "running": managed.running(),
        "readyPort": params.ready_port,
        "listening": listening,
        "recentOutput": recent,
    }


async def workspace_process_logs_handler(params: WorkspaceProcessLogsParams) -> dict[str, Any]:
    from ..agent.runtime import _sanitize_value

    with _PROCESS_POOL_LOCK:
        managed = _PROCESS_POOL.get(params.process_id)
    if managed is None:
        return {"status": "error", "code": "PROCESS_NOT_FOUND", "error": f"No managed process {params.process_id}"}
    return {
        "status": "success",
        "processId": managed.process_id,
        "pid": managed.proc.pid,
        "running": managed.running(),
        "exitCode": managed.proc.poll(),
        "output": _sanitize_value("\n".join(managed.tail(params.tail))),
    }


async def workspace_stop_process_handler(params: WorkspaceStopProcessParams) -> dict[str, Any]:
    import asyncio

    with _PROCESS_POOL_LOCK:
        managed = _PROCESS_POOL.get(params.process_id)
    if managed is None:
        return {"status": "error", "code": "PROCESS_NOT_FOUND", "error": f"No managed process {params.process_id}"}
    if managed.running():
        managed.proc.terminate()
        try:
            await asyncio.to_thread(managed.proc.wait, 3)
        except subprocess.TimeoutExpired:
            managed.proc.kill()
            await asyncio.to_thread(managed.proc.wait, 2)
    return {
        "status": "success",
        "processId": managed.process_id,
        "running": managed.running(),
        "exitCode": managed.proc.poll(),
    }


registry.register(
    ToolDefinition(
        name="workspace_start_process",
        display_name="Workspace: Start Background Server/Daemon",
        description="Start a bounded local dev server or backend daemon inside workspace root with loopback readiness check and log capture.",
        parameters={
            "command": {"type": "string", "description": "Safe local server command (e.g. 'python -m http.server 8123')."},
            "ready_port": {"type": "integer", "description": "Optional localhost port to wait on before returning."},
            "ready_wait_ms": {"type": "integer", "description": "Startup wait milliseconds (default 2500)."},
            "workspace_root": {"type": "string", "description": "Optional workspace root override."},
        },
        required_parameters=["command"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=True,
        risk_tier=RiskTier.TIER_3_PROCESS,
        risk_level="high",
        effect=ToolEffect.EXECUTE_PROCESS,
    ),
    workspace_start_process_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_process_logs",
        display_name="Workspace: Read Background Process Logs",
        description="Inspect recent stdout/stderr lines and status of a managed background process.",
        parameters={
            "process_id": {"type": "string", "description": "Process ID returned by workspace_start_process."},
            "tail": {"type": "integer", "description": "Number of trailing log lines (default 50)."},
        },
        required_parameters=["process_id"],
        is_read_only=True,
        is_concurrency_safe=True,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_0_READ_ONLY,
        risk_level="low",
        effect=ToolEffect.READ,
    ),
    workspace_process_logs_handler,
)

registry.register(
    ToolDefinition(
        name="workspace_stop_process",
        display_name="Workspace: Stop Background Process",
        description="Terminate a managed background server/daemon started in the workspace.",
        parameters={
            "process_id": {"type": "string", "description": "Process ID returned by workspace_start_process."},
        },
        required_parameters=["process_id"],
        is_read_only=False,
        is_concurrency_safe=False,
        requires_confirmation=False,
        risk_tier=RiskTier.TIER_1_REVERSIBLE,
        risk_level="medium",
        effect=ToolEffect.EXECUTE_PROCESS,
    ),
    workspace_stop_process_handler,
)
