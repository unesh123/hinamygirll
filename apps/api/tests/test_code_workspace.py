"""Behaviour tests for the workspace-confined coding tools.

Covers the security promises (traversal, symlink escape, secret blindness)
and the exactness contract of code_patch — the parts that must never regress.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
import types
from pathlib import Path

import pytest

# This suite exercises pure filesystem logic — nothing needs the FastAPI app.
# Register lightweight package stubs first so the module loads even on a
# Python that cannot parse the (unrelated) PEP 695 syntax elsewhere in the
# package. On a fully-imported tree (conftest already loaded hinaa_api) the
# guard leaves the real package untouched.
if "hinaa_api" not in sys.modules:
    _api_root = pathlib.Path(__file__).resolve().parents[1]
    _pkg = types.ModuleType("hinaa_api")
    _pkg.__path__ = [str(_api_root / "hinaa_api")]
    sys.modules["hinaa_api"] = _pkg
    _tools = types.ModuleType("hinaa_api.tools")
    _tools.__path__ = [str(_api_root / "hinaa_api" / "tools")]
    sys.modules["hinaa_api.tools"] = _tools

from hinaa_api.config import get_settings
import hinaa_api.tools.code_workspace as cw


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "app.py").write_text(
        "import os\n\n\ndef load_env(name):\n    value = os.environ.get(name)\n    return value\n\n\n"
        "def helper():\n    return 1\n",
        encoding="utf-8",
    )
    (root / "notes.md").write_text("keep secret: hunter2 in here", encoding="utf-8")
    (root / ".env").write_text("MAGNIFIC_API_KEY=super-secret-value\n", encoding="utf-8")
    sub = root / "src" / "deep"
    sub.mkdir(parents=True)
    (sub / "config.ts").write_text("export const SECRET_TOKEN = 'nope';\n", encoding="utf-8")
    (sub / "big.bin").write_bytes(b"\x00\x01" * 5000)
    monkeypatch.setenv("HINAA_CODE_ROOT", str(root))
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path / "hinaa-home"))
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def run(handler, params: dict):
    return asyncio.run(handler(params))


class TestPathJail:
    def test_absolute_paths_refused(self, workspace):
        out = run(cw.code_read_handler, {"file_path": "/etc/passwd"})
        assert out["status"] == "error"
        assert out["code"] == "CODE_PATH_OUTSIDE_WORKSPACE"

    def test_traversal_refused(self, workspace):
        out = run(cw.code_read_handler, {"file_path": "../../etc/passwd"})
        assert out["code"] == "CODE_PATH_OUTSIDE_WORKSPACE"

    def test_symlink_escape_refused(self, workspace):
        if os.name == "nt":
            pytest.skip("symlinks need privileges on Windows")
        os.symlink("/etc", workspace / "escape")
        out = run(cw.code_read_handler, {"file_path": "escape/passwd"})
        assert out["code"] == "CODE_PATH_OUTSIDE_WORKSPACE"

    def test_secret_files_invisible(self, workspace):
        out = run(cw.code_read_handler, {"file_path": ".env"})
        assert out["code"] == "CODE_PATH_REFUSED"
        grep = run(cw.code_explore_handler, {"action": "grep", "pattern": "super-secret"})
        assert grep["status"] == "success"
        assert grep["data"]["matches"] == []
        tree = run(cw.code_explore_handler, {"action": "tree"})
        assert not any(".env" in line for line in tree["data"]["entries"])


class TestExplore:
    def test_tree_lists_and_hides_ignored(self, workspace):
        (workspace / "node_modules").mkdir()
        (workspace / "node_modules" / "junk.js").write_text("// junk", encoding="utf-8")
        data = run(cw.code_explore_handler, {"action": "tree"})["data"]
        joined = "\n".join(data["entries"])
        assert "app.py" in joined and "src/" in joined
        assert "node_modules" not in joined

    def test_grep_finds_with_line_numbers(self, workspace):
        data = run(cw.code_explore_handler, {"action": "grep", "pattern": "load_env", "glob": "*.py"})["data"]
        hits = [m for m in data["matches"] if m["file"] == "app.py"]
        assert hits and hits[0]["line"] == 4

    def test_binary_skipped(self, workspace):
        data = run(cw.code_explore_handler, {"action": "grep", "pattern": "\\\\x01"})["data"]
        assert all(m["file"] != "src/deep/big.bin" for m in data["matches"])

    def test_view_symbol_returns_body_preview(self, workspace):
        data = run(cw.code_explore_handler, {"action": "view_symbol", "symbol": "load_env"})["data"]
        assert data["definitions"][0]["file"] == "app.py"
        assert "os.environ.get" in data["definitions"][0]["preview"]

    def test_bad_regex_is_typed_error(self, workspace):
        out = run(cw.code_explore_handler, {"action": "grep", "pattern": "([unclosed"})
        assert out["code"] == "CODE_BAD_REGEX"


class TestPatchAndWrite:
    def test_missing_target_fails_closed(self, workspace):
        out = run(cw.code_patch_handler, {"file_path": "app.py", "target_content": "def nope():", "replacement_content": "x"})
        assert out["code"] == "PATCH_TARGET_NOT_FOUND"
        assert "Read the file first" in out["error"]

    def test_ambiguous_target_fails_closed(self, workspace):
        out = run(cw.code_patch_handler, {"file_path": "app.py", "target_content": "    return ", "replacement_content": "    return "})
        assert out["code"] == "PATCH_TARGET_AMBIGUOUS"

    def test_unique_patch_applies_with_backup_and_diff(self, workspace):
        out = run(cw.code_patch_handler, {
            "file_path": "app.py",
            "target_content": "def helper():\n    return 1",
            "replacement_content": "def helper():\n    return 2",
        })
        assert out["status"] == "success"
        updated = (workspace / "app.py").read_text(encoding="utf-8")
        assert "return 2" in updated
        assert "+    return 2" in out["data"]["diff"]
        backup = Path(out["data"]["backup"])
        assert backup.exists() and "return 1" in backup.read_text(encoding="utf-8")
        assert str(workspace) not in str(backup)  # backups live OUTSIDE the repo

    def test_overwrite_guard_then_create(self, workspace):
        blocked = run(cw.code_write_handler, {"file_path": "notes.md", "content": "boom"})
        assert blocked["code"] == "CODE_FILE_EXISTS"
        made = run(cw.code_write_handler, {"file_path": "src/new/mod.py", "content": "VALUE = 1\n"})
        assert made["status"] == "success" and made["data"]["created"] is True
        assert (workspace / "src" / "new" / "mod.py").read_text(encoding="utf-8") == "VALUE = 1\n"

    def test_write_refuses_secrets(self, workspace):
        out = run(cw.code_write_handler, {"file_path": ".env", "content": "X=1", "overwrite": True})
        assert out["code"] == "CODE_PATH_REFUSED"

    def test_patch_rejects_secret_files(self, workspace):
        out = run(cw.code_patch_handler, {"file_path": "src/deep/config.ts", "target_content": "SECRET_TOKEN", "replacement_content": "X"})
        # config.ts is NOT a secret-name (no .env pattern) — allowed; but .env.local is refused
        env_local = run(cw.code_patch_handler, {"file_path": ".env.local", "target_content": "a", "replacement_content": "b"})
        assert out["status"] == "success" or out["code"] != "CODE_PATH_REFUSED"
        assert env_local["code"] == "CODE_PATH_REFUSED"


class TestRead:
    def test_line_window_and_numbering(self, workspace):
        data = run(cw.code_read_handler, {"file_path": "app.py", "start_line": 4, "end_line": 6})["data"]
        assert data["content"].splitlines()[0].startswith("    4 |")
        assert data["from"] == 4 and data["to"] == 6 and data["totalLines"] == 10
