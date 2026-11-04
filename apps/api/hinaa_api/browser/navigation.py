"""Navigation, Redirect Auditing, and Tab Management.

Handles page navigation with pre- and post-redirect SSRF checks,
SPA hydration stabilization, and popup/tab control.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple
from playwright.async_api import Page, Route

from .action_schema import BrowserActionResult, BrowserActionType
from .policy import BrowserSecurityPolicy
from .session_manager import BrowserSession

logger = logging.getLogger("hinaa.browser.navigation")


class NavigationHandler:
    """Controls safe browser navigation and redirect validation."""

    def __init__(self, policy: BrowserSecurityPolicy) -> None:
        self.policy = policy

    async def navigate(
        self,
        session: BrowserSession,
        url: str,
        timeout_ms: int = 15000,
        wait_until: str = "domcontentloaded",
    ) -> BrowserActionResult:
        """Navigates to URL, auditing initial URL and all subsequent redirect hops."""
        action_id = f"act-nav-{int(time.time()*1000)}"
        t0 = time.perf_counter()

        # 0. Check task cancellation
        if session.is_cancelled:
            return BrowserActionResult(
                action_id=action_id,
                task_id=session.task_id,
                action_type=BrowserActionType.OPEN,
                status="CANCELLED",
                observed_url=session.current_page.url if session.pages else "",
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                failure_code="TASK_CANCELLED",
                failure_message="Action aborted due to task cancellation request",
            )

        # 1. Pre-navigation URL policy validation
        valid, reason = self.policy.validate_url(url)
        if not valid:
            session.emit_event(f"Navigation blocked by security policy: {reason}", observed_url=url)
            return BrowserActionResult(
                action_id=action_id,
                task_id=session.task_id,
                action_type=BrowserActionType.OPEN,
                status="FAILED",
                observed_url=url,
                elapsed_ms=(time.perf_counter() - t0) * 1000,
                failure_code="SECURITY_POLICY_VIOLATION",
                failure_message=f"URL validation failed: {reason}",
            )

        page = session.current_page
        redirect_blocked: Optional[str] = None

        # 2. Response listener for 3xx redirect headers
        def on_response(response):
            nonlocal redirect_blocked
            if 300 <= response.status < 400:
                loc = response.headers.get("location")
                if loc:
                    is_ok, err = self.policy.validate_url(loc)
                    if not is_ok:
                        logger.warning("SSRF blocked in redirect: %s -> %s (%s)", response.url, loc, err)
                        redirect_blocked = f"REDIRECT_SSRF_BLOCKED: {loc} ({err})"

        page.on("response", on_response)

        # 3. Instantaneous route-level SSRF defense on all requests & redirects
        async def handle_route(route: Route) -> None:
            nonlocal redirect_blocked
            req_url = route.request.url
            if req_url.startswith(("about:", "chrome-error:")):
                await route.continue_()
                return

            is_ok, err = self.policy.validate_url(req_url)
            if not is_ok:
                logger.warning("SSRF blocked before network request: %s (%s)", req_url, err)
                redirect_blocked = f"REDIRECT_SSRF_BLOCKED: {req_url} ({err})"
                await route.abort("blockedbyclient")
                return

            await route.continue_()

        await page.route("**/*", handle_route)


        try:
            session.emit_event(f"Navigating to {url}...", observed_url=url)
            try:
                await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            except Exception as nav_exc:
                if redirect_blocked:
                    # Expected abort due to SSRF block
                    pass
                else:
                    raise nav_exc

            if redirect_blocked:
                return BrowserActionResult(
                    action_id=action_id,
                    task_id=session.task_id,
                    action_type=BrowserActionType.OPEN,
                    status="FAILED",
                    observed_url="about:blank",
                    elapsed_ms=(time.perf_counter() - t0) * 1000,
                    failure_code="SSRF_REDIRECT_DETECTED",
                    failure_message=redirect_blocked,
                )

            # Wait briefly for client hydration / dynamic rendering
            try:
                await page.wait_for_load_state("networkidle", timeout=1000)
            except Exception:
                pass  # Networkidle timeout is expected on pages with streaming sockets

            observed_url = page.url
            title = await page.title()
            elapsed = (time.perf_counter() - t0) * 1000

            session.emit_event(
                f"Successfully opened {observed_url} ('{title}') in {elapsed:.1f}ms",
                observed_url=observed_url,
                metrics={"navigation_latency_ms": elapsed},
            )

            return BrowserActionResult(
                action_id=action_id,
                task_id=session.task_id,
                action_type=BrowserActionType.OPEN,
                status="SUCCESS",
                observed_url=observed_url,
                observed_title=title,
                elapsed_ms=elapsed,
                postcondition_verified=True,
                postcondition_details=f"Arrived at {observed_url}",
            )

        except Exception as exc:
            elapsed = (time.perf_counter() - t0) * 1000
            if redirect_blocked:
                return BrowserActionResult(
                    action_id=action_id,
                    task_id=session.task_id,
                    action_type=BrowserActionType.OPEN,
                    status="FAILED",
                    observed_url="about:blank",
                    elapsed_ms=elapsed,
                    failure_code="SSRF_REDIRECT_DETECTED",
                    failure_message=redirect_blocked,
                )
            session.emit_event(f"Navigation failed: {exc}", observed_url=url)
            return BrowserActionResult(
                action_id=action_id,
                task_id=session.task_id,
                action_type=BrowserActionType.OPEN,
                status="FAILED",
                observed_url=page.url if not page.is_closed() else url,
                elapsed_ms=elapsed,
                failure_code="NAVIGATION_ERROR",
                failure_message=str(exc),
            )
        finally:
            try:
                page.remove_listener("response", on_response)
            except Exception:
                pass
            try:
                await page.unroute("**/*", handle_route)
            except Exception:
                pass

