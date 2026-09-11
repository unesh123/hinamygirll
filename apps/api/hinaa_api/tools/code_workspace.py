"""Workspace-confined coding tools — explore, read, patch, write.

HINAA can work inside a real project, but "work" here means *auditable*:

* every path resolves under ``HINAA_CODE_ROOT`` (default
  ``~/.hinaa/code-workspace``) with traversal and symlink escapes rejected;
* secrets are invisible: ``.env*``, key material, credential files and
  ``.git`` internals are skipped by reads/greps/tree **and** refused for
  writes (a prompt-injected model must not be able to read or rewrite the
  files that hold the keys);
* mutations are confirmation-gated upstream and always back up first into
  ``~/.hinaa/workspace/code-backups`` — outside the repo, never inside it;
* every read/write is size-capped so a runaway grep cannot eat the machine.

The self-healing edit-test-retry loop deliberately does NOT live here yet;
execution of arbitrary commands is a separate, harder decision (see
docs/78-advancement-plan.md Phase C).
"""

from __future__ import annotations

import difflib
import fnmatch
import os
import re
import shutil
import tempfile
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..config import get_settings
from .registry import ToolDefinition, registry

MAX_READ_LINES = 400
MAX_GREP_MATCHES = 80
MAX_GREP_FILES = 800
MAX_TREE_ENTRIES = 400
MAX_SCAN_FILE_BYTES = 2_000_000
MAX_WRITE_BYTES = 512_000
MAX_DIFF_LINES = 80

_IGNORED_DIRS = {
    ".git", ".hg", ".svn", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", ".cache", ".pytest_cache",
    ".ruff_cache", ".mypy_cache", ".idea", ".vscode", "target", "out",
}

# Files HINAA never reads (exfiltration) and never writes (tampering).
_SECRET_NAME = re.compile(
    r"(?:^|/)\.env(?:\.|$)|\.env\.\w+$|(?:^|/)(\.git|\.ssh|\.aws|\.gnupg)(/|$)|"
    r"\.(pem|key|p12|pfx|jks)$|(?:^|/)(id_rsa|id_ed25519|credentials(\.json)?|secrets?(\.json|\.ya?ml)?)$",
    re.IGNORECASE,
)
_BINARY_SNIFF_BYTES = 4096


class WorkspaceError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _workspace_root() -> Path:
    root = Path(get_settings().code_workspace_root).expanduser().resolve()
    if not root.is_dir():
        raise WorkspaceError(
            "CODE_WORKSPACE_MISSING",
            f"The code workspace '{root}' does not exist. Set HINAA_CODE_ROOT in "
            "apps/api/.env.local to a project directory and restart the API.",
        )
    home = Path.home().resolve()
    if root == home or len(root.parts) <= 2:
        raise WorkspaceError(
            "CODE_WORKSPACE_TOO_BROAD",
            "HINAA_CODE_ROOT must point at a specific project directory, not your "
            "home or drive root — the jail is only meaningful one project wide.",
        )
    return root


def _is_secret(rel: object) -> bool:
    return bool(_SECRET_NAME.search(str(rel).replace("\\", "/")))


def _resolve(rel: str, *, must_exist: bool) -> Path:
    raw = (rel or ".").strip().strip('"').strip("'")
    candidate = Path(unicodedata.normalize("NFC", raw))
    root = _workspace_root()
    if candidate.is_absolute():
        raise WorkspaceError("CODE_PATH_OUTSIDE_WORKSPACE", "Use paths relative to the workspace root.")
    if ".." in candidate.parts:
        raise WorkspaceError("CODE_PATH_OUTSIDE_WORKSPACE", "Parent-directory traversal is not allowed.")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:  # a symlink escaping the jail lands here
        raise WorkspaceError("CODE_PATH_OUTSIDE_WORKSPACE", "This path resolves outside the workspace.") from error
    if _is_secret(candidate) or _is_secret(resolved.relative_to(root)):
        raise WorkspaceError("CODE_PATH_REFUSED", "That path is treated as secret and is off-limits to HINAA.")
    if must_exist and not resolved.exists():
        raise WorkspaceError("CODE_PATH_NOT_FOUND", f"No such file or directory in the workspace: {candidate}")
    return resolved


def _looks_binary(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            chunk = handle.read(_BINARY_SNIFF_BYTES)
    except OSError:
        return True
    return b"\x00" in chunk


def _walk_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in _IGNORED_DIRS)
        rel_dir = Path(dirpath).relative_to(root)
        if _is_secret(rel_dir):
            dirnames[:] = []
            continue
        for name in sorted(filenames):
            rel = (rel_dir / name).as_posix()
            if _is_secret(rel):
                continue
            yield rel, Path(dirpath) / name


# ── explore primitives ──────────────────────────────────────────────────────

def _tree(rel_root: str, max_depth: int) -> tuple[list[str], int]:
    base = _resolve(rel_root, must_exist=True)
    if base.is_file():
        return [f"{base.name}  ({base.stat().st_size:,} B)"], 1
    lines: list[str] = []
    count = 0

    def walk(directory: Path, depth: int) -> None:
        nonlocal count
        if depth > max_depth:
            return
        for entry in sorted(directory.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
            if count >= MAX_TREE_ENTRIES:
                lines.append(f"… truncated at {MAX_TREE_ENTRIES} entries")
                return
            if entry.is_dir():
                if entry.name in _IGNORED_DIRS or _is_secret(entry.relative_to(base)):
                    continue
                count += 1
                lines.append(f"{'  ' * depth}{entry.name}/")
                walk(entry, depth + 1)
            else:
                if _is_secret(entry.relative_to(base)):
                    continue
                try:
                    size = entry.stat().st_size
                except OSError:
                    size = 0
                count += 1
                lines.append(f"{'  ' * depth}{entry.name}  ({size:,} B)")

    walk(base, 0)
    return lines, count


def _find(pattern: str, rel_root: str) -> list[str]:
    base = _resolve(rel_root, must_exist=True)
    matches: list[str] = []
    for rel, _path in _walk_files(base):
        if fnmatch.fnmatch(Path(rel).name, pattern) or fnmatch.fnmatch(rel, pattern):
            matches.append(rel)
            if len(matches) >= MAX_TREE_ENTRIES:
                matches.append(f"… truncated at {MAX_TREE_ENTRIES} files")
                break
    return matches


def _grep(pattern: str, glob: str, rel_root: str, ignore_case: bool) -> dict[str, Any]:
    try:
        regex = re.compile(pattern, re.IGNORECASE if ignore_case else 0)
    except re.error as error:
        raise WorkspaceError("CODE_BAD_REGEX", f"Invalid regex: {error}") from error
    base = _resolve(rel_root, must_exist=True)
    files_scanned = 0
    hits: list[dict[str, Any]] = []
    for rel, path in _walk_files(base):
        if glob and not (fnmatch.fnmatch(Path(rel).name, glob) or fnmatch.fnmatch(rel, glob)):
            continue
        try:
            if path.stat().st_size > MAX_SCAN_FILE_BYTES or _looks_binary(path):
                continue
        except OSError:
            continue
        files_scanned += 1
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                hits.append({"file": rel, "line": lineno, "text": line.strip()[:300]})
                if len(hits) >= MAX_GREP_MATCHES:
                    return {"matches": hits, "filesScanned": files_scanned, "truncated": True}
        if files_scanned >= MAX_GREP_FILES:
            break
    return {"matches": hits, "filesScanned": files_scanned, "truncated": False}


def _symbol(name: str, rel_root: str) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,80}", name):
        raise WorkspaceError("CODE_BAD_SYMBOL", "Symbol names must be plain identifiers.")
    base = _resolve(rel_root, must_exist=True)
    definitions: list[dict[str, Any]] = []
    pattern = re.compile(rf"^(?P<indent>[ \t]*)(?:async[ \t]+)?(?:def|class)[ \t]+{re.escape(name)}\b", re.M)
    for rel, path in _walk_files(base):
        if path.suffix.lower() not in {".py", ".ts", ".tsx", ".js", ".jsx"}:
            continue
        try:
            if path.stat().st_size > MAX_SCAN_FILE_BYTES:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in pattern.finditer(text):
            start_line = text.count("\n", 0, match.start()) + 1
            body_lines = text.splitlines()
            indent = len(match.group("indent"))
            body: list[str] = []
            for offset in range(start_line - 1, min(start_line + 40, len(body_lines))):
                body_line = body_lines[offset]
                if offset > start_line - 1 and body_line.strip() and len(body_line) - len(body_line.lstrip()) <= indent:
                    break
                body.append(body_line)
            definitions.append({
                "file": rel, "line": start_line,
                "head": match.group(0).strip(), "preview": "\n".join(body[:24]),
            })
            if len(definitions) >= 12:
                return definitions
    return definitions


# ── read / patch / write primitives ─────────────────────────────────────────

def _read_lines(path: Path, start: int, end: int) -> dict[str, Any]:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    start = max(1, min(start or 1, max(total, 1)))
    end = end or (start + MAX_READ_LINES - 1)
    end = max(start, min(end, total))
    window = lines[start - 1:end]
    numbered = "\n".join(f"{start + index:>5} | {line}" for index, line in enumerate(window))
    return {"content": numbered, "from": start, "to": end, "totalLines": total,
            "truncated": total > end or start > 1}


def _backup(path: Path, root: Path) -> Path | None:
    try:
        backup_dir = Path(get_settings().local_workspace_dir) / "code-backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        rel = path.relative_to(root).as_posix().replace("/", "__")
        target = backup_dir / f"{stamp}__{rel}"
        shutil.copy2(path, target)
        return target
    except OSError:
        return None


def _atomic_write(path: Path, content: str) -> None:
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".hinaa-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except OSError:
                pass


def _apply_patch_text(original: str, search: str, replace: str, replace_all: bool) -> tuple[str, str]:
    """Pure core of code_patch → (new_text, error_code). Exactness is the
    contract: ambiguous or missing targets fail closed, never "first guess"."""
    if not search:
        return original, "EMPTY_SEARCH"
    occurrences = original.count(search)
    if occurrences == 0:
        return original, "PATCH_TARGET_NOT_FOUND"
    if occurrences > 1 and not replace_all:
        return original, "PATCH_TARGET_AMBIGUOUS"
    new_text = original.replace(search, replace) if replace_all else original.replace(search, replace, 1)
    return new_text, ""


def _diff(original: str, updated: str, name: str) -> str:
    lines = list(difflib.unified_diff(
        original.splitlines(), updated.splitlines(),
        fromfile=f"a/{name}", tofile=f"b/{name}", lineterm="", n=3,
    ))
    if len(lines) > MAX_DIFF_LINES:
        lines = lines[:MAX_DIFF_LINES] + [f"… diff truncated ({MAX_DIFF_LINES} of {len(lines)} lines shown)"]
    return "\n".join(lines)


# ── handlers ────────────────────────────────────────────────────────────────

async def code_explore_handler(params: dict[str, Any]) -> dict[str, Any]:
    action = str(params.get("action", "tree")).lower()
    rel = str(params.get("path", "."))
    try:
        if action == "tree":
            depth = max(1, min(int(params.get("max_depth", 3) or 3), 8))
            lines, count = _tree(rel, depth)
            data: dict[str, Any] = {"action": "tree", "path": rel, "entries": lines, "count": count}
        elif action == "find_files":
            matches = _find(str(params.get("pattern", "*")), rel)
            data = {"action": "find_files", "path": rel, "pattern": str(params.get("pattern", "*")), "matches": matches}
        elif action == "grep":
            data = {"action": "grep", "path": rel, **_grep(
                str(params.get("pattern", "")), str(params.get("glob", "")), rel, bool(params.get("ignore_case")),
            )}
        elif action == "view_symbol":
            data = {"action": "view_symbol", "path": rel, "definitions": _symbol(str(params.get("symbol", "")), rel)}
        else:
            return {"status": "error",
                    "error": f"Unknown explore action '{action}'. Use tree, find_files, grep, or view_symbol.",
                    "code": "CODE_ACTION_UNKNOWN"}
    except WorkspaceError as error:
        return {"status": "error", "error": error.message, "code": error.code}
    except (ValueError, TypeError) as error:
        return {"status": "error", "error": f"Invalid parameters: {error}", "code": "CODE_BAD_PARAMS"}
    return {"status": "success", "data": data}


async def code_read_handler(params: dict[str, Any]) -> dict[str, Any]:
    try:
        path = _resolve(str(params.get("file_path", "")), must_exist=True)
        if not path.is_file():
            raise WorkspaceError("CODE_NOT_A_FILE", "code_read wants a file; use code_explore for directories.")
        if path.stat().st_size > 4_000_000:
            return {"status": "success", "data": {
                "file": params.get("file_path"), "content": "", "totalBytes": path.stat().st_size,
                "note": "File is too large to read whole — request a line window or grep it instead."}}
        result = _read_lines(path, int(params.get("start_line", 1) or 1), int(params.get("end_line", 0) or 0))
    except WorkspaceError as error:
        return {"status": "error", "error": error.message, "code": error.code}
    except (ValueError, TypeError) as error:
        return {"status": "error", "error": f"Invalid parameters: {error}", "code": "CODE_BAD_PARAMS"}
    return {"status": "success", "data": {"file": params.get("file_path"), **result}}


async def code_patch_handler(params: dict[str, Any]) -> dict[str, Any]:
    try:
        root = _workspace_root()
        path = _resolve(str(params.get("file_path", "")), must_exist=True)
        if not path.is_file():
            raise WorkspaceError("CODE_NOT_A_FILE", "code_patch can only edit existing files.")
        try:
            original = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            raise WorkspaceError("CODE_NOT_TEXT", "Refusing to patch a non-UTF-8 file.")
        updated, error_code = _apply_patch_text(
            original,
            str(params.get("target_content", "")),
            str(params.get("replacement_content", "")),
            bool(params.get("replace_all")),
        )
        if error_code:
            hints = {
                "PATCH_TARGET_NOT_FOUND": "Read the file first and copy the exact text (whitespace matters).",
                "PATCH_TARGET_AMBIGUOUS": "Include more surrounding lines to make the target unique, or set replace_all.",
                "EMPTY_SEARCH": "target_content must not be empty.",
            }
            return {"status": "error", "error": f"{error_code.replace('_', ' ').title()}. {hints[error_code]}", "code": error_code}
        backup = _backup(path, root)
        _atomic_write(path, updated)
    except WorkspaceError as error:
        return {"status": "error", "error": error.message, "code": error.code}
    except OSError as error:
        return {"status": "error", "error": f"Could not write the file: {error}", "code": "CODE_WRITE_FAILED"}
    return {"status": "success", "data": {
        "file": params.get("file_path"),
        "diff": _diff(original, updated, str(params.get("file_path"))),
        "bytesChanged": len(updated) - len(original),
        "backup": str(backup) if backup else None,
        "note": None if backup else "Warning: no backup could be written (directory unwritable); change applied without a snapshot.",
    }}


async def code_write_handler(params: dict[str, Any]) -> dict[str, Any]:
    try:
        root = _workspace_root()
        path = _resolve(str(params.get("file_path", "")), must_exist=False)
        content = str(params.get("content", ""))
        if len(content.encode("utf-8")) > MAX_WRITE_BYTES:
            return {"status": "error", "error": f"Refusing to write more than {MAX_WRITE_BYTES:,} bytes in one go.",
                    "code": "CODE_WRITE_TOO_LARGE"}
        existed = path.exists()
        if existed and not bool(params.get("overwrite")):
            return {"status": "error",
                    "error": "File exists — re-request with overwrite=true after showing the user what will be replaced.",
                    "code": "CODE_FILE_EXISTS"}
        if path.is_dir():
            raise WorkspaceError("CODE_NOT_A_FILE", "file_path points at a directory.")
        path.parent.mkdir(parents=True, exist_ok=True)
        original = path.read_text(encoding="utf-8", errors="replace") if existed else ""
        backup = _backup(path, root) if existed else None
        _atomic_write(path, content)
    except WorkspaceError as error:
        return {"status": "error", "error": error.message, "code": error.code}
    except OSError as error:
        return {"status": "error", "error": f"Could not write the file: {error}", "code": "CODE_WRITE_FAILED"}
    return {"status": "success", "data": {
        "file": params.get("file_path"),
        "created": not existed,
        "bytes": len(content),
        "diff": _diff(original, content, str(params.get("file_path"))) if existed else None,
        "backup": str(backup) if backup else None,
    }}


# ── tool contracts ──────────────────────────────────────────────────────────

code_explore_def = ToolDefinition(
    name="code_explore",
    display_name="Explore code",
    description=(
        "Search and map the user's code workspace without dumping whole files. "
        "Actions: tree (directory map), find_files (glob), grep (regex over text, "
        "binary and secret files skipped), view_symbol (Python/TS definitions by name). "
        "Read-only — safe to call proactively before any edit."
    ),
    parameters={
        "action": {"type": "string", "description": "tree | find_files | grep | view_symbol"},
        "path": {"type": "string", "description": "Relative directory to start from (default: workspace root)", "required": False},
        "pattern": {"type": "string", "description": "Glob pattern for find_files (e.g. '*.test.ts')", "required": False},
        "glob": {"type": "string", "description": "Only grep files matching this glob", "required": False},
        "regex": {"type": "string", "description": "Regex for grep", "required": False},
        "symbol": {"type": "string", "description": "Identifier for view_symbol", "required": False},
        "ignore_case": {"type": "boolean", "description": "Case-insensitive grep", "required": False},
        "max_depth": {"type": "number", "description": "Tree depth limit 1-8 (default 3)", "required": False},
    },
    required_parameters=["action"],
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["explore the project", "show the file tree", "search the code for", "find files named"],
)

code_read_def = ToolDefinition(
    name="code_read",
    display_name="Read code",
    description="Read a precise slice of a source file with line numbers. Prefer start_line/end_line windows on big files.",
    parameters={
        "file_path": {"type": "string", "description": "Path relative to the workspace root"},
        "start_line": {"type": "number", "description": "1-based start line", "required": False},
        "end_line": {"type": "number", "description": "1-based end line (inclusive)", "required": False},
    },
    required_parameters=["file_path"],
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["open the file", "read the file", "show me the file"],
)

code_patch_def = ToolDefinition(
    name="code_patch",
    display_name="Patch code",
    description=(
        "Atomic exact-match search-and-replace in one workspace file. Fails closed when the "
        "target is missing or ambiguous — read the file first and quote it exactly. Always "
        "backs the original up outside the repo and returns a unified diff of the change."
    ),
    parameters={
        "file_path": {"type": "string", "description": "File to patch, relative to the workspace root"},
        "target_content": {"type": "string", "description": "Exact text to replace (must appear exactly once)"},
        "replacement_content": {"type": "string", "description": "Replacement text"},
        "replace_all": {"type": "boolean", "description": "Replace every occurrence instead of requiring uniqueness", "required": False},
    },
    required_parameters=["file_path", "target_content", "replacement_content"],
    requires_confirmation=True,
    cancellable=False,
    voice_aliases=["patch the file", "edit the file", "change this code", "fix the file"],
)

code_write_def = ToolDefinition(
    name="code_write",
    display_name="Write file",
    description=(
        "Create a new file in the workspace, or fully overwrite an existing one only when "
        "overwrite=true. Backs up any replaced file outside the repo and reports the diff."
    ),
    parameters={
        "file_path": {"type": "string", "description": "Target path relative to the workspace root"},
        "content": {"type": "string", "description": "Full file body"},
        "overwrite": {"type": "boolean", "description": "Must be true to replace an existing file", "required": False},
    },
    required_parameters=["file_path", "content"],
    requires_confirmation=True,
    cancellable=False,
    voice_aliases=["create a file", "write the file", "save this as a file"],
)

registry.register(code_explore_def, code_explore_handler)
registry.register(code_read_def, code_read_handler)
registry.register(code_patch_def, code_patch_handler)
registry.register(code_write_def, code_write_handler)
