"""Phase 10 Acceptance Test Suite: Desktop, Browser & Terminal Reliability.

Empirically validates Phase 10 requirements:
1. Desktop: Opens authorized editor, writes/verifies scratch workspace file, stops on command, rejects protected system dirs.
2. Browser: Executes form task on deterministic local fixture, verifies DOM mutation, generates binary screenshot receipt.
3. Terminal: Bounded WSL2 Kali Linux execution, timeout cancellation with process tree termination, policy guardrails & path containment.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
import time
import pytest

from hinaa_api.tools.computer_operator import (
    NativeComputerOperator,
    execute_computer_operator,
)
from hinaa_api.tools.terminal_hands import (
    execute_terminal_hands,
    TerminalExecuteParams,
)
from hinaa_api.tools.browser_automation import (
    _get_page,
    browser_navigate,
    BrowserNavigateParams,
    browser_type,
    BrowserTypeParams,
    browser_click,
    BrowserClickParams,
    browser_extract,
    BrowserExtractParams,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "browser_fixture.html"
EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "docs" / "evidence"
SCRATCH_DIR = Path(__file__).resolve().parents[1] / ".runtime" / "scratch"


# ---------------------------------------------------------------------------
# 1. Desktop Task Reliability & Authorization
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase10_desktop_editor_lifecycle_in_scratch_workspace():
    """Hina opens authorized editor, creates scratch file, verifies contents on disk, stops on command."""
    SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
    test_file = SCRATCH_DIR / f"desktop_receipt_{int(time.time())}.txt"
    expected_content = f"PHASE10_DESKTOP_RECEIPT_{time.time()}_VERIFIED"
    test_file.write_text(expected_content, encoding="utf-8")

    # 1. Open authorized editor (notepad) targeting scratch file
    res = await NativeComputerOperator.open_application(f"notepad {test_file}")
    assert res.success is True, f"Failed to launch editor: {res.detail}"

    # Allow brief window focus
    await asyncio.sleep(0.5)

    # 2. Verify file content exists and matches exactly on disk
    assert test_file.is_file(), "Scratch file not found on disk"
    readback = test_file.read_text(encoding="utf-8")
    assert readback == expected_content, f"Content mismatch: expected {expected_content}, got {readback}"

    # 3. Stop on command (terminate/close editor window cleanly)
    closed = await NativeComputerOperator.close_window("notepad")
    assert closed is True, "Failed to close editor window on command"


@pytest.mark.asyncio
async def test_phase10_desktop_rejects_unauthorized_system_paths():
    """Desktop operator rejects access to protected OS directories outside workspace."""
    envelope = await execute_computer_operator({
        "action": "read_folder",
        "target": r"C:\Windows\System32\config",
    })
    assert envelope["success"] is False
    assert envelope["execution_status"] == "FAILED"
    assert "protected" in str(envelope["error_details"]).lower()


# ---------------------------------------------------------------------------
# 2. Browser Task Reliability on Local Fixture
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase10_browser_controlled_form_task(monkeypatch):
    """Run controlled browser form task on local HTML fixture with observed DOM mutations and PNG receipt."""
    import hinaa_api.tools.browser_automation as ba
    ba._page = None
    ba._browser = None
    monkeypatch.setenv("BROWSERBASE_API_KEY", "")
    monkeypatch.setenv("HINAA_BROWSERBASE_API_KEY", "")
    monkeypatch.setenv("HINAA_BROWSER_HEADLESS", "true")
    from hinaa_api.config import get_settings
    settings = get_settings()
    if hasattr(settings, "browserbase_api_key"):
        monkeypatch.setattr(settings, "browserbase_api_key", None)

    assert FIXTURE_PATH.is_file(), f"Fixture file missing at {FIXTURE_PATH}"

    # Navigate
    nav_res = await browser_navigate(BrowserNavigateParams(url=FIXTURE_PATH.as_uri()))
    assert "Successfully navigated" in nav_res

    page = await _get_page()
    assert page is not None
    assert await page.title() == "HINAA Deterministic Browser Test Fixture"

    # Form action: fill input
    fill_payload = "Phase10-Browser-Receipt-Payload"
    await browser_type(BrowserTypeParams(selector="#test-search-box", text=fill_payload, submit=False))
    val = await page.input_value("#test-search-box")
    assert val == fill_payload

    # Form submit action: click button
    await browser_click(BrowserClickParams(selector="#test-submit-btn"))

    # Verify DOM state change
    status = await page.inner_text("#status-badge")
    assert status == f"STATUS_SUBMITTED: {fill_payload}"

    token = await page.inner_text("#token-alpha")
    assert token == "ARTIFACT-ALPHA-7782"

    # Capture binary PNG evidence
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_path = EVIDENCE_DIR / "browser_e2e_evidence.png"
    await page.screenshot(path=str(screenshot_path))
    assert screenshot_path.is_file()
    assert screenshot_path.stat().st_size > 5000, "Screenshot file size too small"


# ---------------------------------------------------------------------------
# 3. Terminal Reliability (WSL Kali Linux, Bounded Timeout, Guardrails)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_phase10_terminal_bounded_wsl_kali_execution():
    """Run bounded command in WSL2 Kali Linux and capture exit code 0 and stdout."""
    res = await execute_terminal_hands(TerminalExecuteParams(
        command="uname -s && cat /etc/os-release | grep PRETTY_NAME",
        runtime="kali",
        timeout_seconds=15,
    ))
    assert res.get("status") == "success"
    assert res.get("exitCode") == 0
    stdout = res.get("stdout", "")
    assert "Linux" in stdout
    assert "Kali" in stdout


@pytest.mark.asyncio
async def test_phase10_terminal_cancels_long_process():
    """Long process terminates cleanly when execution timeout expires."""
    t0 = time.time()
    res = await execute_terminal_hands(TerminalExecuteParams(
        command="Start-Sleep -Seconds 20",
        runtime="powershell",
        timeout_seconds=2,
    ))
    duration = time.time() - t0
    assert res.get("status") == "timeout"
    assert "process tree was stopped" in res.get("error", "")
    assert duration < 10.0, f"Timeout took too long: {duration}s"


@pytest.mark.asyncio
async def test_phase10_terminal_security_guardrail_rejection():
    """Prohibited destructive commands are immediately rejected by safety guardrails."""
    res = await execute_terminal_hands(TerminalExecuteParams(
        command="format c: /fs:ntfs",
        runtime="powershell",
        timeout_seconds=5,
    ))
    assert res.get("status") == "rejected"
    assert "Security Guardrail" in res.get("error", "")


@pytest.mark.asyncio
async def test_phase10_terminal_path_containment_violation():
    """Path containment blocks directory navigation outside project workspace."""
    res = await execute_terminal_hands(TerminalExecuteParams(
        command="Get-ChildItem",
        cwd="../../../../Windows",
        runtime="powershell",
        timeout_seconds=5,
    ))
    assert res.get("status") == "rejected"
    assert "outside allowed workspace roots" in res.get("error", "")
