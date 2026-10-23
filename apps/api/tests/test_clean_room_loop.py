"""Tests for the clean_room_loop tool (REA-inspired Clean-Room Rebuild).

Verifies:
1. Path escape rejection (dest, oracle, spec).
2. Honest failure reporting when backends are unavailable.
3. Full 6-stage pipeline execution: Spec -> Oracle -> Rebuild -> Test -> Pass.
4. Self-repair loop when the initial implementation fails an oracle test.
"""
from __future__ import annotations

import sys
import pytest

from hinaa_api.tools import clean_room_loop
from hinaa_api.tools.clean_room_loop import (
    CleanRoomRebuildParams,
    clean_room_loop_handler,
)


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setenv("HINAA_LOCAL_WORKSPACE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def fake_backends(monkeypatch):
    monkeypatch.setattr(
        clean_room_loop, "_configured_code_backends", lambda settings: [{"name": "fake_brain"}]
    )


def _mock_llm(monkeypatch, replies: list[str]):
    queue = list(replies)

    async def fake_llm(backends, system, user):
        val = queue.pop(0) if queue else "{}"
        return val, "fake:clean_room_brain"

    monkeypatch.setattr(clean_room_loop, "_llm_text", fake_llm)


@pytest.mark.asyncio
async def test_clean_room_escape_rejected(workspace, fake_backends, monkeypatch):
    _mock_llm(monkeypatch, ['{"spec_markdown": "test"}'])
    params = CleanRoomRebuildParams(
        task="reverse engineer rate limiter",
        target_evidence="class RateLimiter: pass",
        destination_file="../../evil.py",
        oracle_test_file="tests/test_oracle.py",
    )
    result = await clean_room_loop_handler(params)
    assert result["status"] == "error"
    assert result["code"] == "WORKSPACE_ESCAPE"


@pytest.mark.asyncio
async def test_clean_room_no_backends_handled(workspace, monkeypatch):
    monkeypatch.setattr(clean_room_loop, "_configured_code_backends", lambda settings: [])
    params = CleanRoomRebuildParams(
        task="rebuild feature",
        target_evidence="evidence data",
        destination_file="services/calc.py",
        oracle_test_file="tests/test_oracle_calc.py",
    )
    result = await clean_room_loop_handler(params)
    assert result["status"] == "error"
    assert result["code"] == "CODING_BRAIN_UNAVAILABLE"


@pytest.mark.asyncio
async def test_clean_room_full_pipeline_success(workspace, fake_backends, monkeypatch):
    # Step 1: Spec response
    spec_json = (
        '{"spec_markdown": "# Math Token Bucket\\n\\nContract: compute_sum(a: int, b: int) -> int", '
        '"summary": "Simple sum computation", "interfaces": ["compute_sum"], "invariants": ["a+b==sum"]}'
    )
    # Step 2: Oracle response (pytest)
    oracle_code = (
        "import pytest\\n"
        "from calc import compute_sum\\n\\n"
        "def test_compute_sum_positive():\\n"
        "    assert compute_sum(2, 3) == 5\\n\\n"
        "def test_compute_sum_negative():\\n"
        "    assert compute_sum(-1, 1) == 0\\n"
    )
    oracle_json = f'{{"file_path": "test_oracle.py", "full_content": "{oracle_code}", "summary": "test suite"}}'
    
    # Step 3: Clean-room implementation
    impl_code = (
        "def compute_sum(a: int, b: int) -> int:\\n"
        "    return a + b\\n"
    )
    impl_json = f'{{"file_path": "calc.py", "full_content": "{impl_code}", "summary": "calc implementation"}}'

    _mock_llm(monkeypatch, [spec_json, oracle_json, impl_json])

    params = CleanRoomRebuildParams(
        task="Rebuild compute_sum function",
        target_evidence="API returns sum of two integers",
        destination_file="calc.py",
        oracle_test_file="test_oracle.py",
        spec_file="SPEC.md",
        test_command=f"{sys.executable} -m pytest test_oracle.py -q",
    )

    result = await clean_room_loop_handler(params)
    assert result["status"] == "success"
    assert result["verified"] is True
    assert (workspace / "calc.py").exists()
    assert (workspace / "test_oracle.py").exists()
    assert (workspace / "SPEC.md").exists()
    assert "compute_sum" in (workspace / "calc.py").read_text()


@pytest.mark.asyncio
async def test_clean_room_self_repair_on_failing_oracle(workspace, fake_backends, monkeypatch):
    # Step 1: Spec response
    spec_json = '{"spec_markdown": "# Math Sub\\n\\nContract: sub(a, b) -> a - b", "summary": "Subtraction"}'
    
    # Step 2: Oracle response
    oracle_code = (
        "from sub_module import sub\\n\\n"
        "def test_sub():\\n"
        "    assert sub(10, 4) == 6\\n"
    )
    oracle_json = f'{{"file_path": "test_oracle_sub.py", "full_content": "{oracle_code}", "summary": "sub test"}}'
    
    # Step 3: Broken initial implementation (bug: adds instead of subtracts)
    broken_impl_code = (
        "def sub(a: int, b: int) -> int:\\n"
        "    return a + b\\n"
    )
    broken_impl_json = f'{{"file_path": "sub_module.py", "full_content": "{broken_impl_code}", "summary": "broken sub"}}'

    # Step 4: Repair patch proposal
    repair_patch_json = (
        '{"file_path": "sub_module.py", '
        '"target_content": "    return a + b", '
        '"replacement_content": "    return a - b", '
        '"summary": "fix addition to subtraction"}'
    )

    _mock_llm(monkeypatch, [spec_json, oracle_json, broken_impl_json, repair_patch_json])

    params = CleanRoomRebuildParams(
        task="Rebuild subtraction logic",
        target_evidence="def sub(a, b): return a - b",
        destination_file="sub_module.py",
        oracle_test_file="test_oracle_sub.py",
        test_command=f"{sys.executable} -m pytest test_oracle_sub.py -q",
        max_attempts=3,
    )

    result = await clean_room_loop_handler(params)
    assert result["status"] == "success"
    assert result["verified"] is True
    assert result["attempts"] == 2  # Passed on attempt 2 after surgical patch!
    assert "return a - b" in (workspace / "sub_module.py").read_text()
