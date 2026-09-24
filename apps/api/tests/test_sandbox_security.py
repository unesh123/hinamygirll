"""Tests for C2 Sandboxed Command Execution Engine (Directives §10–§15).

Verifies:
1. Path boundary enforcement and path escape rejection (cwd outside allowed_root).
2. Ambient environment secret stripping (API keys, tokens, credentials).
3. Stdout/stderr credential masking.
4. Execution timeout enforcement.
5. Framework-aware output parsers (Pytest, TypeScript, SyntaxError).
"""

import os
import sys
import tempfile
import pytest

from hinaa_api.agent.sandbox import (
    CommandRequest,
    PytestOutputParser,
    PythonSyntaxOutputParser,
    SandboxExecutor,
    SandboxSecurityViolation,
    TypeScriptOutputParser,
    sanitize_output,
)


@pytest.mark.asyncio
async def test_path_escape_blocked_cwd():
    """Attempting to execute commands with cwd outside allowed_root is rejected."""
    with tempfile.TemporaryDirectory() as temp_root:
        outside_path = os.path.dirname(temp_root)
        executor = SandboxExecutor(default_allowed_root=temp_root)

        req = CommandRequest(
            command=[sys.executable, "-c", "print('hello')"],
            cwd=outside_path,
            allowed_root=temp_root,
        )
        res = await executor.run_command(req)
        assert res.exit_code == 126
        assert res.violation is not None
        assert "Path escape rejected" in res.violation


def test_secret_environment_filtering():
    """Host ambient secrets (API keys, tokens, passwords) are stripped from child process environment."""
    os.environ["HINAA_TEST_API_KEY"] = "sk-test-secret-123456"
    os.environ["GITHUB_TOKEN"] = "ghp_mocktoken12345678901234567890"
    os.environ["DATABASE_PASSWORD"] = "supersecretpass"
    os.environ["SAFE_SYSTEM_VAR"] = "normal_value"

    try:
        executor = SandboxExecutor()
        clean_env = executor.build_clean_environment()

        # Sensitive variables MUST be stripped
        assert "HINAA_TEST_API_KEY" not in clean_env
        assert "GITHUB_TOKEN" not in clean_env
        assert "DATABASE_PASSWORD" not in clean_env

        # Safe system variables MUST be preserved
        assert "PATH" in clean_env
    finally:
        os.environ.pop("HINAA_TEST_API_KEY", None)
        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("DATABASE_PASSWORD", None)
        os.environ.pop("SAFE_SYSTEM_VAR", None)


def test_output_credential_redaction():
    """Stdout/stderr leaking credentials is scrubbed with [REDACTED]."""
    raw_leak = (
        "Connected with Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.secret\n"
        "Config: api_key=sk-proj-12345678901234567890\n"
        "GitHub remote: ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890"
    )
    sanitized = sanitize_output(raw_leak)

    assert "eyJhbGci" not in sanitized
    assert "sk-proj-12345678901234567890" not in sanitized
    assert "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890" not in sanitized
    assert "[REDACTED]" in sanitized


@pytest.mark.asyncio
async def test_timeout_enforcement():
    """Commands running past timeout_seconds are killed and return exit code 124."""
    with tempfile.TemporaryDirectory() as temp_root:
        executor = SandboxExecutor(default_allowed_root=temp_root)
        req = CommandRequest(
            command=[sys.executable, "-c", "import time; time.sleep(5)"],
            cwd=temp_root,
            allowed_root=temp_root,
            timeout_seconds=0.2,
        )
        res = await executor.run_command(req)
        assert res.timed_out is True
        assert res.exit_code == 124


def test_pytest_output_parser():
    """Parses pytest failure outputs into structured failure evidence."""
    mock_output = """
============================= test session starts =============================
rootdir: /app
collected 3 items

tests/test_math.py .F.                                                   [100%]

================================== FAILURES ===================================
__________________________________ test_add ___________________________________

    def test_add():
>       assert add(2, 3) == 5
E       assert -1 == 5
E        +  where -1 = add(2, 3)

tests/test_math.py:12: AssertionError
FAILED tests/test_math.py::test_add - assert -1 == 5
=========================== 1 failed, 2 passed in 0.05s ===========================
"""
    parsed = PytestOutputParser.parse(mock_output)
    assert parsed.framework == "pytest"
    assert parsed.passed == 2
    assert parsed.failed == 1
    assert len(parsed.failures) == 1
    assert parsed.failures[0].location == "tests/test_math.py::test_add"
    assert parsed.failures[0].error_type == "AssertionError"
    assert "assert -1 == 5" in parsed.failures[0].message


def test_typescript_output_parser():
    """Parses TypeScript compiler error messages."""
    mock_tsc = """
src/services/auth.ts(45,12): error TS2322: Type 'string' is not assignable to type 'number'.
src/components/Button.tsx(12,5): error TS2741: Property 'onClick' is missing in type.
"""
    parsed = TypeScriptOutputParser.parse(mock_tsc)
    assert parsed.framework == "typescript"
    assert parsed.failed == 2
    assert parsed.failures[0].location == "src/services/auth.ts:45"
    assert parsed.failures[0].error_type == "TS2322"


def test_python_syntax_output_parser():
    """Parses Python SyntaxError tracebacks."""
    mock_syntax = '''
  File "calculator.py", line 4
    def add(a, b)
                 ^
SyntaxError: expected ':'
'''
    parsed = PythonSyntaxOutputParser.parse(mock_syntax)
    assert parsed.framework == "python_syntax"
    assert parsed.failed == 1
    assert parsed.failures[0].location == "calculator.py:4"
    assert parsed.failures[0].error_type == "SyntaxError"
    assert "expected ':'" in parsed.failures[0].message
