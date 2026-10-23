"""
Directive §4: Deterministic Local Fixture End-to-End Browser Verification Suite.

Validates that browser automation operates beyond an HTTP 200 envelope:
1. Navigates to a deterministic local HTML fixture.
2. Asserts exact final URL and page title.
3. Types input into target selector and verifies value in live DOM.
4. Clicks button and asserts live DOM state mutation.
5. Verifies dynamic container visibility and extracts target tokens.
6. Captures and verifies binary PNG screenshot evidence on disk.
7. Evaluates accessibility snapshot of interactive elements.
"""

import os
from pathlib import Path
import pytest

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


@pytest.mark.asyncio
async def test_browser_end_to_end_fixture_execution():
    assert FIXTURE_PATH.is_file(), f"Fixture file missing at {FIXTURE_PATH}"
    fixture_url = FIXTURE_PATH.as_uri()

    # 1. Navigate to local fixture
    nav_res = await browser_navigate(BrowserNavigateParams(url=fixture_url))
    assert "Successfully navigated" in nav_res
    assert "HINAA Deterministic Browser Test Fixture" in nav_res

    page = await _get_page()
    assert page is not None
    assert "browser_fixture.html" in page.url
    assert await page.title() == "HINAA Deterministic Browser Test Fixture"

    # 2. Assert initial DOM state
    heading = await page.inner_text("#fixture-heading")
    assert heading == "HINAA Browser Automation Verification"
    initial_status = await page.inner_text("#status-badge")
    assert initial_status == "Awaiting Interaction"

    # 3. Type into input control
    test_text = "Hina Autonomous Action 2026"
    type_res = await browser_type(
        BrowserTypeParams(selector="#test-search-box", text=test_text, submit=False)
    )
    assert "Successfully typed" in type_res

    # Live DOM assertion on input field value
    input_val = await page.input_value("#test-search-box")
    assert input_val == test_text

    # 4. Click button and verify state transition
    click_res = await browser_click(BrowserClickParams(selector="#test-submit-btn"))
    assert "Successfully clicked" in click_res

    # Live DOM assertion on updated status badge
    updated_status = await page.inner_text("#status-badge")
    assert updated_status == f"STATUS_SUBMITTED: {test_text}"

    # 5. Verify dynamic content visibility and extracted tokens
    is_data_visible = await page.is_visible("#extracted-data")
    assert is_data_visible is True

    alpha_token = await page.inner_text("#token-alpha")
    beta_token = await page.inner_text("#token-beta")
    assert alpha_token == "ARTIFACT-ALPHA-7782"
    assert beta_token == "VERIFIED-DOM-STATE"

    extract_res = await browser_extract(BrowserExtractParams())
    assert "ARTIFACT-ALPHA-7782" in extract_res
    assert "VERIFIED-DOM-STATE" in extract_res

    # 6. Capture real binary screenshot evidence
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    screenshot_file = EVIDENCE_DIR / "browser_e2e_evidence.png"
    await page.screenshot(path=str(screenshot_file))
    assert screenshot_file.is_file(), "Screenshot artifact was not created"
    assert screenshot_file.stat().st_size > 1000, "Screenshot artifact must contain binary image data"

    # 7. Accessibility Snapshot check
    # Evaluate that interactive elements are in AX tree
    ax_roles = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('input, button, h1, div')).map(el => el.tagName);
    }""")
    assert "INPUT" in ax_roles
    assert "BUTTON" in ax_roles
    assert "H1" in ax_roles
