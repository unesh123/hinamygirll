"""Security-wall tests for terminal_run.

Each test pins one of the four guarantees: shell-free parsing, refusal lists,
environment scrubbing, and workspace confinement — plus the happy paths so a
legit `pytest`-style command stays usable.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import pytest

if "hinaa_api" not in sys.modules:
    import types
    _root = Path(__file__).resolve().parents[1]
    _pkg = types.ModuleType("hinaa_api"); _pkg.__path__ = [str(_root / "hinaa_api")]
    sys.modules["hinaa_api"] = _pkg
    _tools = types.ModuleType("hinaa_api.tools"); _tools.__path__ = [str(_root / "hinaa_api" / "tools")]
    sys.modules["hinaa_api.tools"] = _tools

from hinaa_api.config import get_settings
import hinaa_api.tools.terminal_runner as tr


@pytest.fixture()
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "project"
    root.mkdir()
    (root / "hello.txt").write_text("hi", encoding="utf-8")
    monkeypatch.setenv("HINAA_CODE_ROOT", str(root))
    monkeypatch.setenv("HINAA_TERMINAL_ENABLED", "true")
    monkeypatch.setenv("MAGNIFIC_API_KEY", "LEAK-TEST-KEY-9000")  # must never reach the child
    get_settings.cache_clear()
    yield root
    get_settings.cache_clear()


def run(params: dict):
    return asyncio.run(tr.terminal_run_handler(params))


@pytest.mark.skipif(os.name == "nt", reason="posix coreutils")
class TestHappyPath:
    def test_echo_runs_in_workspace(self, workspace):
        out = run({"command": "echo hello from jail"})
        assert out["status"] == "success"
        assert out["data"]["exitCode"] == 0
        assert "hello from jail" in out["data"]["stdout"]

    def test_nonzero_exit_is_data_not_error(self, workspace):
        out = run({"command": "false"})
        assert out["status"] == "success"
        assert out["data"]["exitCode"] != 0

    def test_env_is_scrubbed_of_secrets(self, workspace):
        out = run({"command": "env"})
        assert "LEAK-TEST-KEY-9000" not in out["data"]["stdout"]

    def test_output_tails_when_huge(self, workspace, monkeypatch):
        monkeypatch.setenv("HINAA_TERMINAL_MAX_OUTPUT_BYTES", "200")
        get_settings.cache_clear()
        out = run({"command": "seq 1 500"})
        assert out["status"] == "success"
        assert out["data"]["truncated"] is True
        assert len(out["data"]["stdout"]) < 300

    def test_timeout_kills_and_reports(self, workspace):
        out = run({"command": "sleep 10", "timeout_seconds": 0.4})
        assert out["status"] == "success"
        assert out["data"]["timedOut"] is True

@pytest.mark.skipif(os.name == "nt", reason="argv rules are identical; posix examples")
class TestWalls:
    def test_pipes_and_operators_refused(self, workspace):
        for cmd in ["echo hi | tee pwn", "ls > out.txt", "true && rm -rf /", "echo $(whoami)"]:
            out = run({"command": cmd})
            assert out["code"] == "TERMINAL_SHELL_SYNTAX", cmd

    def test_destructive_binaries_refused(self, workspace):
        for cmd in ["rm -rf .", "sudo ls", "shutdown -h now", "powershell -Command x"]:
            out = run({"command": cmd})
            assert out["code"] in {"TERMINAL_COMMAND_REFUSED", "TERMINAL_COMMAND_NOT_FOUND"}, cmd

    def test_inline_interpreter_code_refused(self, workspace):
        out = run({"command": "python -c 'import os; os.system(\'rm -rf /\')'"})
        assert out["code"] == "TERMINAL_COMMAND_REFUSED"

    def test_unknown_command_fails_typed(self, workspace):
        out = run({"command": "definitely-not-a-real-binary-42 --version"})
        assert out["code"] == "TERMINAL_COMMAND_NOT_FOUND"

    def test_working_dir_escape_refused(self, workspace):
        out = run({"command": "ls", "working_dir": "../../etc"})
        assert out["code"] == "CODE_PATH_OUTSIDE_WORKSPACE"

    def test_disabled_flag_hard_off(self, workspace, monkeypatch):
        monkeypatch.setenv("HINAA_TERMINAL_ENABLED", "false")
        get_settings.cache_clear()
        out = run({"command": "echo hi"})
        assert out["code"] == "TERMINAL_DISABLED"


class TestProjectVenv:
    def test_venv_bin_is_prepended_to_path(self, workspace):
        venv_bin = workspace / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        marker = venv_bin / "hinaa-probe"
        marker.write_text("#!/bin/sh\necho venv-first\n", encoding="utf-8")
        marker.chmod(0o755)
        if os.name != "nt":
            out = run({"command": "hinaa-probe"})
            assert out["status"] == "success" and "venv-first" in out["data"]["stdout"]
