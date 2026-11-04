"""Isolated Task and Tenant Browser Session Manager.

Creates dedicated ephemeral BrowserContext instances per task, ensuring strict
isolation of cookies, storage, tabs, and permissions across tenants and tasks.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4
from playwright.async_api import Browser, BrowserContext, Page

from .action_schema import (
    BrowserTaskApprovalRequest,
    BrowserTaskEvent,
    BrowserTaskSpec,
    BrowserTaskState,
    TabInfo,
)
from .runtime import BrowserRuntimeManager

logger = logging.getLogger("hinaa.browser.session")


class BrowserSession:
    """Encapsulates an isolated browser context for a specific task and tenant."""

    def __init__(
        self,
        spec: BrowserTaskSpec,
        context: BrowserContext,
        initial_page: Page,
        runtime: BrowserRuntimeManager,
    ) -> None:
        self.spec = spec
        self.task_id = spec.task_id
        self.tenant_id = spec.tenant_id
        self.user_id = spec.user_id
        self.context = context
        self.runtime = runtime
        self.state = BrowserTaskState.STARTING
        self.trace_id = spec.trace_id or f"trace-{uuid4().hex[:12]}"

        # Tab registry: tab_id -> Page
        self.pages: Dict[str, Page] = {}
        self.active_tab_id: Optional[str] = None
        self._max_tabs = 5

        # Event stream subscribers
        self._event_subscribers: List[asyncio.Queue[BrowserTaskEvent]] = []
        self._events_history: List[BrowserTaskEvent] = []

        # Cancellation event
        self._cancellation_requested = False

        # Pending approval request for Tier C actions
        self.pending_approval: Optional[BrowserTaskApprovalRequest] = None

        # Register initial page
        self._register_page(initial_page)

        # Wire popup interception
        self.context.on("page", self._on_popup_created)

    def _register_page(self, page: Page) -> str:
        tab_id = f"tab-{uuid4().hex[:8]}"
        self.pages[tab_id] = page
        self.active_tab_id = tab_id
        return tab_id

    def _on_popup_created(self, page: Page) -> None:
        if len(self.pages) >= self._max_tabs:
            logger.warning("Max tabs reached in session %s; closing popup", self.task_id)
            asyncio.create_task(page.close())
            return
        tab_id = self._register_page(page)
        logger.info("New popup intercepted and registered in session %s: %s", self.task_id, tab_id)

    @property
    def current_page(self) -> Page:
        if self.active_tab_id and self.active_tab_id in self.pages:
            p = self.pages[self.active_tab_id]
            if not p.is_closed():
                return p
        # Fallback to first non-closed page
        for tid, p in self.pages.items():
            if not p.is_closed():
                self.active_tab_id = tid
                return p
        raise RuntimeError("No open pages available in session")

    async def list_tabs(self) -> List[TabInfo]:
        tabs = []
        for tab_id, page in list(self.pages.items()):
            if page.is_closed():
                continue
            url = page.url
            try:
                title = await page.title()
            except Exception:
                title = "Unknown"
            tabs.append(
                TabInfo(
                    tab_id=tab_id,
                    url=url,
                    title=title,
                    origin=page.url.split("/")[2] if "://" in page.url else page.url,
                    is_active=(tab_id == self.active_tab_id),
                )
            )
        return tabs

    async def switch_tab(self, tab_id: str) -> bool:
        if tab_id in self.pages and not self.pages[tab_id].is_closed():
            self.active_tab_id = tab_id
            await self.pages[tab_id].bring_to_front()
            return True
        return False

    async def close_tab(self, tab_id: str) -> bool:
        if tab_id in self.pages:
            p = self.pages.pop(tab_id)
            if not p.is_closed():
                await p.close()
            if self.active_tab_id == tab_id:
                self.active_tab_id = next(iter(self.pages.keys()), None)
            return True
        return False

    def emit_event(
        self,
        message: str,
        state: Optional[BrowserTaskState] = None,
        observed_url: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> BrowserTaskEvent:
        if state:
            self.state = state
        evt = BrowserTaskEvent(
            event_id=f"evt-{uuid4().hex[:8]}",
            task_id=self.task_id,
            state=self.state,
            message=message,
            observed_url=observed_url or (self.current_page.url if self.pages else None),
            screenshot_path=screenshot_path,
            approval_request=self.pending_approval,
            metrics=metrics or {},
        )
        self._events_history.append(evt)
        for q in self._event_subscribers:
            q.put_nowait(evt)
        return evt

    def subscribe_events(self) -> asyncio.Queue[BrowserTaskEvent]:
        q: asyncio.Queue[BrowserTaskEvent] = asyncio.Queue()
        # Backfill history
        for evt in self._events_history:
            q.put_nowait(evt)
        self._event_subscribers.append(q)
        return q

    def unsubscribe_events(self, q: asyncio.Queue[BrowserTaskEvent]) -> None:
        if q in self._event_subscribers:
            self._event_subscribers.remove(q)

    def request_cancellation(self) -> None:
        self._cancellation_requested = True
        self.state = BrowserTaskState.CANCELLING
        self.emit_event("Task cancellation requested by user", state=BrowserTaskState.CANCELLING)

    @property
    def is_cancelled(self) -> bool:
        return self._cancellation_requested

    async def close(self) -> None:
        """Closes all pages and the context, releasing runtime capacity."""
        logger.info("Closing browser session for task %s (tenant %s)", self.task_id, self.tenant_id)
        try:
            await self.context.close()
        except Exception as exc:
            logger.warning("Error closing context for session %s: %s", self.task_id, exc)
        finally:
            self.runtime.release_session_slot()
            self.pages.clear()


class BrowserSessionManager:
    """Manages active browser sessions across tasks and tenants."""

    def __init__(self, runtime: BrowserRuntimeManager) -> None:
        self.runtime = runtime
        self._sessions: Dict[str, BrowserSession] = {}
        self._lock = asyncio.Lock()

    async def create_session(self, spec: BrowserTaskSpec) -> BrowserSession:
        async with self._lock:
            # 1. Enforce capacity limit
            if not self.runtime.acquire_session_slot():
                raise RuntimeError("MAX_CONCURRENT_BROWSER_SESSIONS_EXCEEDED")

            try:
                browser = await self.runtime.get_browser()

                # 2. Create isolated ephemeral context
                context = await browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36 HINAA-Agent/2.0",
                    permissions=[],  # Deny all permissions (geo, mic, camera, notifications)
                    ignore_https_errors=False,
                )

                # 3. Create initial page
                initial_page = await context.new_page()

                session = BrowserSession(spec, context, initial_page, self.runtime)
                session.emit_event("Browser session initialized with isolated context", state=BrowserTaskState.RUNNING)
                self._sessions[spec.task_id] = session
                return session
            except Exception:
                self.runtime.release_session_slot()
                raise


    def get_session(self, task_id: str) -> Optional[BrowserSession]:
        return self._sessions.get(task_id)

    async def close_session(self, task_id: str) -> None:
        async with self._lock:
            session = self._sessions.pop(task_id, None)
            if session:
                await session.close()

    async def close_all(self) -> None:
        async with self._lock:
            for session in list(self._sessions.values()):
                await session.close()
            self._sessions.clear()
