"""WhatsApp Web driver for Hina's own persistent Playwright profile.

The send flow is deliberately narrow: search for an allow-listed chat, open the
exact-title result, read the open chat's header from the DOM, and refuse to type
or send unless that header equals the allowed name. It never creates chats,
never touches media, and never clicks anything but the exact-title result row
and the send control.

The page is behind the small `WhatsAppPage` protocol so tests inject a fake.
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Protocol

from ..errors import HinaaError
from . import whatsapp_selectors as sel
from .whatsapp_guard import (
    WhatsAppPolicyError,
    normalize_chat_name,
    validate_message,
    validate_recipient,
)

PROFILE_DIR_ENV = "HINAA_WHATSAPP_PROFILE_DIR"


def default_profile_dir() -> Path:
    override = os.environ.get(PROFILE_DIR_ENV, "").strip()
    if override:
        return Path(override).expanduser()
    return Path(__file__).resolve().parents[4] / ".runtime" / "whatsapp-profile"


class WhatsAppPage(Protocol):
    async def is_logged_in(self) -> bool: ...
    async def open_chat_via_search(self, name: str) -> None: ...
    async def read_open_chat_title(self) -> str | None: ...
    async def type_message(self, text: str) -> None: ...
    async def press_send(self) -> None: ...
    async def clear_search(self) -> None: ...


PageProvider = Callable[[], Awaitable[WhatsAppPage]]


def _driver_error(code: str, message: str, status: int = 502) -> HinaaError:
    return HinaaError(code, message, status, True, False)


async def send_to_allowed_chat(
    page: WhatsAppPage,
    recipient: str,
    text: str,
    *,
    allowed: tuple[str, ...] | None = None,
) -> dict[str, object]:
    """Layer 3: re-validate, then verify the DOM header before typing and at send time."""
    name = validate_recipient(recipient, allowed)
    validate_message(text)
    if not await page.is_logged_in():
        raise _driver_error(
            "WHATSAPP_NOT_LOGGED_IN", "WhatsApp Web is not linked; scan the QR code once.", 409
        )

    async def _assert_header() -> None:
        title = await page.read_open_chat_title()
        if title is None or normalize_chat_name(title) != name:
            raise WhatsAppPolicyError(
                "WHATSAPP_HEADER_MISMATCH",
                "The open chat is not the requested allow-listed chat; nothing was sent.",
            )

    try:
        await page.open_chat_via_search(name)
        await _assert_header()
        await page.type_message(text)
        # The conversation could have switched while typing; check again at the last moment.
        await _assert_header()
        await page.press_send()
    except WhatsAppPolicyError:
        await _best_effort_clear(page)
        raise
    return {"recipient": name, "length": len(text), "sent_at": time.time()}


async def _best_effort_clear(page: WhatsAppPage) -> None:
    try:
        await page.clear_search()
    except Exception:  # noqa: BLE001, S110 - cleanup must not mask the policy error
        pass


class PlaywrightWhatsAppPage:
    """Selector-driven implementation over a Playwright page."""

    def __init__(self, page) -> None:  # noqa: ANN001 - playwright Page
        self._page = page

    async def _first(self, selectors: tuple[str, ...], *, timeout_ms: int = 4000, **fmt: str):
        for template in selectors:
            locator = self._page.locator(template.format(**fmt) if fmt else template).first
            try:
                await locator.wait_for(state="visible", timeout=timeout_ms)
                return locator
            except Exception:  # noqa: BLE001, S112
                continue
        return None

    async def is_logged_in(self) -> bool:
        return await self._first(sel.CHAT_LIST, timeout_ms=3000) is not None

    async def open_chat_via_search(self, name: str) -> None:
        box = await self._first(sel.SEARCH_BOX)
        if box is None:
            raise _driver_error(
                "WHATSAPP_SELECTOR_MISSING",
                "Search box not found; WhatsApp Web markup may have changed.",
            )
        await box.click()
        await self._page.keyboard.press("Control+A")
        await self._page.keyboard.press("Backspace")
        await self._page.keyboard.insert_text(name)
        result = await self._first(
            sel.SEARCH_RESULT_TITLE, timeout_ms=6000, name=sel.css_attr_escape(name)
        )
        if result is None:
            raise WhatsAppPolicyError(
                "WHATSAPP_CHAT_NOT_FOUND",
                "No existing chat with that exact name; new chats are never created.",
            )
        await result.click()

    async def read_open_chat_title(self) -> str | None:
        locator = await self._first(sel.OPEN_CHAT_TITLE, timeout_ms=3000)
        if locator is None:
            return None
        title = await locator.get_attribute("title")
        return title if title else await locator.inner_text()

    async def type_message(self, text: str) -> None:
        box = await self._first(sel.COMPOSER)
        if box is None:
            raise _driver_error(
                "WHATSAPP_SELECTOR_MISSING",
                "Message box not found; WhatsApp Web markup may have changed.",
            )
        await box.click()
        for index, line in enumerate(text.split("\n")):
            if index:
                await self._page.keyboard.press("Shift+Enter")
            if line:
                await self._page.keyboard.insert_text(line)

    async def press_send(self) -> None:
        button = await self._first(sel.SEND_BUTTON)
        if button is None:
            raise _driver_error(
                "WHATSAPP_SELECTOR_MISSING",
                "Send button not found; WhatsApp Web markup may have changed.",
            )
        await button.click()

    async def clear_search(self) -> None:
        await self._page.keyboard.press("Escape")


class WhatsAppBrowser:
    """Owns the single persistent context (Chromium locks the profile dir)."""

    def __init__(self, profile_dir: Path | None = None, headless: bool | None = None) -> None:
        self.profile_dir = profile_dir or default_profile_dir()
        self.headless = (
            os.environ.get("HINAA_WHATSAPP_HEADLESS", "").strip().lower() in {"1", "true", "yes"}
            if headless is None
            else headless
        )
        self._playwright = None
        self._context = None
        self._page: PlaywrightWhatsAppPage | None = None
        self._lock = asyncio.Lock()

    def profile_present(self) -> bool:
        return self.profile_dir.is_dir() and any(self.profile_dir.iterdir())

    async def page(self) -> WhatsAppPage:
        async with self._lock:
            if self._page is not None and self._context is not None:
                try:
                    _ = self._context.pages
                    return self._page
                except Exception:  # noqa: BLE001
                    self._page = None
            from playwright.async_api import async_playwright

            self.profile_dir.mkdir(parents=True, exist_ok=True)
            if self._playwright is None:
                self._playwright = await async_playwright().start()
            self._context = await self._playwright.chromium.launch_persistent_context(
                str(self.profile_dir),
                headless=self.headless,
                viewport={"width": 1280, "height": 860},
            )
            raw = self._context.pages[0] if self._context.pages else await self._context.new_page()
            if not raw.url.startswith(sel.WEB_URL):
                await raw.goto(sel.WEB_URL, wait_until="domcontentloaded")
            self._page = PlaywrightWhatsAppPage(raw)
            return self._page


_BROWSER: WhatsAppBrowser | None = None


def get_browser() -> WhatsAppBrowser:
    global _BROWSER
    if _BROWSER is None:
        _BROWSER = WhatsAppBrowser()
    return _BROWSER
