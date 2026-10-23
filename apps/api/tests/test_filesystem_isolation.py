"""
Tests for HINAA Filesystem Isolation & Terminal Sandbox Subsystem.
Verifies GHSA-w5fx-fh39-j5rw / CVE-2025-59532 path containment,
directory traversal rejection, credential redaction, and environment secret stripping.
"""

import os
import pytest
from pathlib import Path

from hinaa_api.harness.sandbox_policy import (
    SandboxPolicyEngine,
    SandboxSecurityViolation,
)
from hinaa_api.runtime_paths import project_root
from hinaa_api.tools.terminal_hands import execute_terminal_hands


def test_sandbox_path_containment_inside_and_outside(tmp_path: Path):
    """Verifies that SandboxPolicyEngine allows inside paths and blocks directory traversal escapes."""
    root = str(tmp_path)
    inside_dir = tmp_path / "src" / "modules"
    inside_dir.mkdir(parents=True)
    inside_file = inside_dir / "app.py"
    inside_file.write_text("print('safe')", encoding="utf-8")

    # Inside passes
    validated = SandboxPolicyEngine.validate_path_containment(str(inside_file), [root])
    assert validated == os.path.realpath(str(inside_file))

    # Path traversal outside fails
    outside_file = tmp_path.parent / "escape.txt"
    with pytest.raises(SandboxSecurityViolation):
        SandboxPolicyEngine.validate_path_containment(str(outside_file), [root])


def test_sandbox_output_credential_sanitization():
    """Verifies that secrets, API keys, and Bearer tokens are redacted from output."""
    raw_leak = (
        "Execution output:\n"
        "OPENAI_API_KEY=sk-abcdef1234567890abcdef1234567890\n"
        "Authorization: Bearer my_secret_jwt_token_12345\n"
        "GITHUB_TOKEN=ghp_1234567890abcdef1234567890abcdef1234\n"
        "Normal log line."
    )
    sanitized = SandboxPolicyEngine.sanitize_output(raw_leak)
    assert "sk-abcdef" not in sanitized
    assert "my_secret_jwt_token_12345" not in sanitized
    assert "ghp_1234567890" not in sanitized
    assert "[REDACTED_SECRET]" in sanitized
    assert "Normal log line." in sanitized


def test_sandbox_strip_environment_secrets():
    """Verifies that secret environment variables are stripped from subprocess environment."""
    dirty_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/home/user",
        "DATABASE_URL": "postgres://user:pass@localhost/db",
        "OPENAI_API_KEY": "sk-123456789",
        "GITHUB_PAT": "ghp_secret",
        "JWT_SECRET": "topsecret",
        "PUBLIC_VAR": "hello_world",
    }
    clean = SandboxPolicyEngine.strip_environment_secrets(dirty_env)
    assert "PATH" in clean
    assert "HOME" in clean
    assert "PUBLIC_VAR" in clean
    assert "OPENAI_API_KEY" not in clean
    assert "GITHUB_PAT" not in clean
    assert "JWT_SECRET" not in clean


@pytest.mark.asyncio
async def test_terminal_hands_cwd_traversal_rejection():
    """Verifies that terminal_hands strictly rejects cwd outside the workspace root."""
    res = await execute_terminal_hands({
        "command": "git status",
        "cwd": "../../Windows/System32",
    })
    assert res["status"] == "rejected"
    assert "Security boundary breach" in res.get("error", "") or "outside" in res.get("error", "")


@pytest.mark.asyncio
async def test_terminal_hands_output_secret_redaction():
    """Verifies that terminal_hands automatically redacts echoed secret tokens."""
    res = await execute_terminal_hands({
        "command": "echo 'api_key=sk-secrettoken1234567890abcdef'",
    })
    assert res["status"] == "success"
    assert "sk-secrettoken" not in res.get("stdout", "")
    assert "[REDACTED_SECRET]" in res.get("stdout", "")
