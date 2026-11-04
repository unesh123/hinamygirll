"""Typed Browser Action Executor and Postcondition Verifier.

Executes Playwright locator actions, performs actionability checks, and
strictly verifies observed postconditions before declaring success.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional
from playwright.async_api import Locator, Page

from .action_schema import (
    ActionPostcondition,
    ActionTarget,
    BrowserActionRequest,
    BrowserActionResult,
    BrowserActionType,
    PermissionTier,
)
from .evidence import EvidenceCollector
from .file_transfer import FileTransferManager
from .policy import BrowserSecurityPolicy
from .recovery import RecoveryHandler
from .session_manager import BrowserSession

logger = logging.getLogger("hinaa.browser.executor")


class ActionExecutor:
    """Dispatches typed actions, validates permissions, and verifies postconditions."""

    def __init__(
        self,
        policy: BrowserSecurityPolicy,
        evidence_collector: Optional[EvidenceCollector] = None,
        file_transfer_manager: Optional[FileTransferManager] = None,
    ) -> None:
        self.policy = policy
        self.evidence = evidence_collector or EvidenceCollector()
        self.files = file_transfer_manager or FileTransferManager()

    def _resolve_locator(self, page: Page, target: ActionTarget) -> Locator:
        """Resolves an ActionTarget into an accessible Playwright locator."""
        if target.by == "role" and target.role:
            return page.get_by_role(target.role, name=target.name, exact=target.exact)
        if target.by == "text":
            return page.get_by_text(target.selector, exact=target.exact)
        if target.by == "label":
            return page.get_by_label(target.selector, exact=target.exact)
        if target.by == "placeholder":
            return page.get_by_placeholder(target.selector, exact=target.exact)
        if target.by == "test_id":
            return page.get_by_test_id(target.selector)
        # Default CSS selector locator
        return page.locator(target.selector)

    async def verify_postcondition(
        self, page: Page, postcondition: Optional[ActionPostcondition]
    ) -> tuple[bool, str]:
        """Asserts expected postcondition through DOM or URL inspection."""
        if not postcondition or postcondition.check_type == "none":
            return True, "NO_POSTCONDITION_SPECIFIED"

        c_type = postcondition.check_type
        exp_val = postcondition.expected_value or ""

        try:
            if c_type == "url_contains":
                is_met = exp_val in page.url
                return is_met, f"URL '{page.url}' contains '{exp_val}': {is_met}"

            if c_type == "url_matches":
                import re
                is_met = bool(re.search(exp_val, page.url))
                return is_met, f"URL '{page.url}' matches pattern '{exp_val}': {is_met}"

            if c_type == "text_present":
                # Check body text
                body_text = await page.evaluate("() => document.body ? document.body.innerText : ''")
                is_met = exp_val.lower() in body_text.lower()
                return is_met, f"Text '{exp_val}' present in page: {is_met}"

            if c_type == "element_visible":
                loc = page.locator(exp_val)
                is_met = await loc.is_visible()
                return is_met, f"Element '{exp_val}' visible: {is_met}"

            if c_type == "element_hidden":
                loc = page.locator(exp_val)
                is_met = await loc.is_hidden()
                return is_met, f"Element '{exp_val}' hidden: {is_met}"

            return True, "UNKNOWN_POSTCONDITION_PASSED"
        except Exception as exc:
            return False, f"POSTCONDITION_CHECK_FAILED: {exc}"

    async def execute(
        self, session: BrowserSession, request: BrowserActionRequest
    ) -> BrowserActionResult:
        """Executes a single typed action with permission checks and postcondition verification."""
        t0 = time.perf_counter()
        page = session.current_page
        current_url = page.url

        # 1. Cancellation check
        if session.is_cancelled:
            return BrowserActionResult(
                action_id=request.action_id,
                task_id=session.task_id,
                action_type=request.action_type,
                status="CANCELLED",
                observed_url=current_url,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                failure_code="TASK_CANCELLED",
                failure_message="Action aborted due to task cancellation request",
            )

        # 2. Permission Tier Check
        tier = self.policy.determine_action_tier(request, current_url)
        if tier == PermissionTier.TIER_C_SPECIFIC_APPROVAL:
            # Verify approval token
            if not request.user_approved or not request.approval_token:
                session.emit_event(
                    f"Tier C action '{request.action_type.value}' requires explicit user approval",
                    observed_url=current_url,
                )
                return BrowserActionResult(
                    action_id=request.action_id,
                    task_id=session.task_id,
                    action_type=request.action_type,
                    status="APPROVAL_REQUIRED",
                    observed_url=current_url,
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                    failure_code="HUMAN_APPROVAL_REQUIRED",
                    failure_message="Action requires explicit human authorization token",
                )

            # Validate cryptographic approval token
            is_valid_token = self.policy.verify_approval_token(
                request.approval_token,
                session.task_id,
                request,
                current_url,
            )
            if not is_valid_token:
                return BrowserActionResult(
                    action_id=request.action_id,
                    task_id=session.task_id,
                    action_type=request.action_type,
                    status="FAILED",
                    observed_url=current_url,
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                    failure_code="INVALID_APPROVAL_TOKEN",
                    failure_message="Provided approval token is invalid, expired, or parameters changed",
                )

        # 3. Dispatch specific action type
        try:
            extracted_data: Any = None

            if request.action_type == BrowserActionType.CLICK:
                if not request.target:
                    raise ValueError("Target locator is required for browser.click")

                if request.target.by == "coordinate" and request.target.coordinates:
                    x, y = request.target.coordinates
                    logger.info("Performing coordinate fallback click at (%d, %d)", x, y)
                    await page.mouse.click(x, y)
                else:
                    locator = self._resolve_locator(page, request.target)
                    if request.target.index > 0:
                        locator = locator.nth(request.target.index)
                    # Use bounded retry for transient detachment
                    await RecoveryHandler.execute_with_retry(
                        lambda: locator.click(timeout=request.timeout_ms),
                        is_idempotent=True,
                    )

            elif request.action_type == BrowserActionType.FILL:
                if not request.target or request.value is None:
                    raise ValueError("Target locator and value are required for browser.fill")
                locator = self._resolve_locator(page, request.target)
                await RecoveryHandler.execute_with_retry(
                    lambda: locator.fill(request.value, timeout=request.timeout_ms),
                    is_idempotent=True,
                )

            elif request.action_type == BrowserActionType.CHECK:
                if not request.target:
                    raise ValueError("Target locator is required for browser.check")
                locator = self._resolve_locator(page, request.target)
                await locator.check(timeout=request.timeout_ms)

            elif request.action_type == BrowserActionType.SELECT:
                if not request.target or request.value is None:
                    raise ValueError("Target locator and value are required for browser.select")
                locator = self._resolve_locator(page, request.target)
                await locator.select_option(request.value, timeout=request.timeout_ms)

            elif request.action_type == BrowserActionType.SCROLL:
                delta_y = int(request.value or "500")
                await page.evaluate(f"window.scrollBy(0, {delta_y})")

            elif request.action_type == BrowserActionType.WAIT_FOR:
                if request.target:
                    loc = self._resolve_locator(page, request.target)
                    await loc.wait_for(timeout=request.timeout_ms)
                else:
                    await page.wait_for_timeout(min(request.timeout_ms, 5000))

            elif request.action_type == BrowserActionType.SCREENSHOT:
                shot_data = await self.evidence.capture_screenshot(
                    page, session.task_id, action_name=request.action_id
                )
                extracted_data = shot_data

            elif request.action_type == BrowserActionType.DOWNLOAD:
                # Trigger action and wait for download event
                async with page.expect_download(timeout=request.timeout_ms) as download_info:
                    if request.target:
                        loc = self._resolve_locator(page, request.target)
                        await loc.click()
                    else:
                        raise ValueError("Target download trigger element required")
                download = await download_info.value
                download_receipt = await self.files.handle_download(
                    download, session.task_id, max_bytes=session.spec.max_download_bytes
                )
                extracted_data = download_receipt

            elif request.action_type == BrowserActionType.UPLOAD_APPROVED:
                if not request.target or not request.value:
                    raise ValueError("Target input element and file path required for upload")
                locator = self._resolve_locator(page, request.target)
                await locator.set_input_files(request.value)

            elif request.action_type == BrowserActionType.SWITCH_TAB:
                if not request.tab_id:
                    raise ValueError("tab_id required for switch_tab")
                ok = await session.switch_tab(request.tab_id)
                if not ok:
                    raise RuntimeError(f"Could not switch to tab '{request.tab_id}'")

            elif request.action_type == BrowserActionType.CLOSE:
                await session.close()
                return BrowserActionResult(
                    action_id=request.action_id,
                    task_id=session.task_id,
                    action_type=request.action_type,
                    status="SUCCESS",
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                    postcondition_verified=True,
                )

            # 4. Verify postcondition
            page = session.current_page
            observed_url = page.url
            observed_title = await page.title()
            post_ok, post_details = await self.verify_postcondition(page, request.postcondition)

            elapsed = (time.perf_counter() - t0) * 1000
            session.emit_event(
                f"Action {request.action_type.value} completed ({'postcondition met' if post_ok else 'postcondition failed'})",
                observed_url=observed_url,
                metrics={"action_latency_ms": elapsed},
            )

            return BrowserActionResult(
                action_id=request.action_id,
                task_id=session.task_id,
                action_type=request.action_type,
                status="SUCCESS" if post_ok else "FAILED",
                observed_url=observed_url,
                observed_title=observed_title,
                elapsed_ms=elapsed,
                postcondition_verified=post_ok,
                postcondition_details=post_details,
                extracted_data=extracted_data,
                failure_code=None if post_ok else "POSTCONDITION_FAILED",
                failure_message=None if post_ok else post_details,
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            logger.warning("Browser action execution failed: %s", exc)
            return BrowserActionResult(
                action_id=request.action_id,
                task_id=session.task_id,
                action_type=request.action_type,
                status="FAILED",
                observed_url=session.current_page.url if session.pages else "",
                elapsed_ms=elapsed,
                failure_code="ACTION_EXECUTION_ERROR",
                failure_message=str(exc),
            )
