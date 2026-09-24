"""Tests for C3 Self-Repairing Coding Agent Loop (Directives §16–§22).

Verifies:
1. Base hash verification preventing concurrent edit clobbering.
2. AST syntax validation rejecting malformed code before disk write.
3. Automated self-repair loop: patch -> test -> fail -> parse -> delta patch -> test -> pass.
4. Bounded repair attempts terminating cleanly at budget exhaustion.
"""

import os
import sys
import tempfile
import pytest

from hinaa_api.agent.coding_agent import (
    CodePatch,
    CodingAgentLoop,
    CodingLoopResult,
    PatchResult,
    RepairAttempt,
    apply_code_patch,
    compute_file_hash,
)
from hinaa_api.agent.sandbox import SandboxExecutor
from hinaa_api.agent.verifier_registry import FailureCategory


def test_base_hash_prevents_concurrent_clobber():
    """Applying a patch with a stale base hash is rejected with CONCURRENT_EDIT."""
    with tempfile.TemporaryDirectory() as temp_root:
        file_path = "service.py"
        abs_path = os.path.join(temp_root, file_path)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("def calculate():\n    return 10\n")

        initial_hash = compute_file_hash("def calculate():\n    return 10\n")

        # Concurrent modification (simulating user or another process edit)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write("def calculate():\n    return 20\n")

        # Attempt to patch with initial base_hash
        patch = CodePatch(
            file_path=file_path,
            target_content="return 10",
            replacement_content="return 100",
            base_hash=initial_hash,
        )
        res = apply_code_patch(temp_root, patch)
        assert res.success is False
        assert res.failure_category == FailureCategory.CONCURRENT_EDIT
        assert "Concurrent edit detected" in (res.error or "")


def test_syntax_validation_rejects_broken_python():
    """Patch introducing syntax error is rejected without corrupting the file on disk."""
    with tempfile.TemporaryDirectory() as temp_root:
        file_path = "module.py"
        abs_path = os.path.join(temp_root, file_path)
        original_code = "def valid():\n    return True\n"
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        patch = CodePatch(
            file_path=file_path,
            target_content="def valid():\n    return True\n",
            replacement_content="def valid(:\n    return True\n",  # syntax error
        )
        res = apply_code_patch(temp_root, patch, validate_syntax=True)
        assert res.success is False
        assert res.failure_category == FailureCategory.SYNTAX_ERROR

        # Verify file on disk was NOT touched
        with open(abs_path, "r", encoding="utf-8") as f:
            assert f.read() == original_code


@pytest.mark.asyncio
async def test_self_repair_loop_fixes_math_bug():
    """Self-repairing coding agent fixes a bug through failure parsing and delta patching."""
    with tempfile.TemporaryDirectory() as temp_root:
        # Create buggy calculator.py
        calc_path = os.path.join(temp_root, "calculator.py")
        with open(calc_path, "w", encoding="utf-8") as f:
            f.write("def add(a: int, b: int) -> int:\n    return a - b\n")

        # Create test_calc.py
        test_path = os.path.join(temp_root, "test_calc.py")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(
                "import sys\n"
                "from calculator import add\n"
                "\n"
                "def test_add():\n"
                "    assert add(2, 3) == 5\n"
            )

        sandbox = SandboxExecutor(default_allowed_root=temp_root)
        loop = CodingAgentLoop(
            workspace_root=temp_root,
            sandbox=sandbox,
            max_repair_attempts=3,
        )

        # Mock patch generator simulating an LLM that makes a mistake on attempt 0 and repairs on attempt 1
        async def mock_llm_patch_generator(
            attempt_idx: int,
            error_context: str,
            last_attempt: RepairAttempt | None,
        ) -> CodePatch:
            if attempt_idx == 0:
                # Attempt 0: flawed patch that doesn't fix the bug
                return CodePatch(
                    file_path="calculator.py",
                    target_content="return a - b",
                    replacement_content="return a - b + 0",
                )
            else:
                # Attempt 1: analyzes error and fixes the sign
                assert last_attempt is not None
                assert "assert -1 == 5" in last_attempt.test_output
                return CodePatch(
                    file_path="calculator.py",
                    target_content="return a - b + 0",
                    replacement_content="return a + b",
                )

        test_cmd = [sys.executable, "-m", "pytest", "test_calc.py", "-q"]

        result: CodingLoopResult = await loop.execute_repair_loop(
            patch_generator=mock_llm_patch_generator,
            test_command=test_cmd,
        )

        assert result.success is True
        assert result.status == "resolved"
        assert result.attempts == 2
        assert len(result.applied_patches) == 2
        assert any("Test command succeeded with exit code 0" in e for e in result.evidence)

        # Verify fixed file content on disk
        with open(calc_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "return a + b" in content


@pytest.mark.asyncio
async def test_bounded_repair_attempts_exhaustion():
    """Unfixable test bug terminates after max_repair_attempts without looping forever."""
    with tempfile.TemporaryDirectory() as temp_root:
        calc_path = os.path.join(temp_root, "calculator.py")
        with open(calc_path, "w", encoding="utf-8") as f:
            f.write("def add(a: int, b: int) -> int:\n    return a - b\n")

        test_path = os.path.join(temp_root, "test_calc.py")
        with open(test_path, "w", encoding="utf-8") as f:
            f.write(
                "from calculator import add\n"
                "def test_add():\n"
                "    assert add(2, 3) == 9999\n"
            )

        sandbox = SandboxExecutor(default_allowed_root=temp_root)
        loop = CodingAgentLoop(
            workspace_root=temp_root,
            sandbox=sandbox,
            max_repair_attempts=2,
        )

        # Generator that produces different patches that never satisfy the impossible assertion
        async def stubborn_patch_generator(attempt_idx: int, error_ctx: str, last: RepairAttempt | None) -> CodePatch:
            return CodePatch(
                file_path="calculator.py",
                target_content=f"return a - b" if attempt_idx == 0 else "return a - b + 1",
                replacement_content=f"return a - b + {attempt_idx + 1}",
            )

        test_cmd = [sys.executable, "-m", "pytest", "test_calc.py", "-q"]
        result = await loop.execute_repair_loop(stubborn_patch_generator, test_cmd)

        assert result.success is False
        assert result.status == "budget_exhausted"
        assert result.attempts == 2
