"""Navigation, Redirect Auditing, and Tab Management.

Handles page navigation with pre- and post-redirect SSRF checks,
SPA hydration stabilization, and popup/tab control.
"""

from __future__ import annotations

import logging
import time
from typing import Optional, Tuple
from playwright.async_api import Page, Response

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

        # 2. Redirect auditor listener
        async def on_response(response: Response) -> None:
            nonlocal redirect_blocked
            if 300 <= response.status < 400:
                redirect_url = response.headers.get("location")
                if redirect_url:
                    # Resolve relative redirect if needed
                    if not redirect_url.startswith(("http://", "https://")):
                        from urllib.parse import urljoin
                        redirect_url = urljoin(response.url, redirect_url)
                    
                    is_ok, err = self.policy.validate_url(redirect_url)
                    if not is_ok:
                        logger.warning("SSRF Pivot blocked in redirect: %s -> %s (%s)", response.url, redirect_url, err)
                        redirect_blocked = f"REDIRECT_SSRF_BLOCKED: {redirect_url} ({err})"

        page.on("response", on_response)

        try:
            session.emit_event(f"Navigating to {url}...", observed_url=url)
            resp = await page.goto(url, wait_until=wait_until, timeout=timeout_ms)
            
            if redirect_blocked:
                # If a redirect to a forbidden target was detected, immediately navigate away or close
                await page.goto("about:blank")
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
                await page.wait_for_load_state("networkidle", timeout=2000)
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
            page.remove_listener("response", on_response)
