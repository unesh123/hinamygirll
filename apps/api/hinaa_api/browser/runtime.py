"""Browser Runtime and Process Capacity Manager.

Manages Playwright process lifecycle, browser pooling, concurrency limits,
and memory monitoring to prevent orphaned processes and resource exhaustion.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from typing import Optional
from playwright.async_api import Browser, Playwright, async_playwright

logger = logging.getLogger("hinaa.browser.runtime")


class BrowserRuntimeManager:
    """Singleton process manager for Playwright browser instances."""

    _instance: Optional["BrowserRuntimeManager"] = None
    _lock = asyncio.Lock()

    def __init__(self, max_concurrent_sessions: int = 5, headless: bool = True) -> None:
        self.max_concurrent_sessions = max_concurrent_sessions
        self.headless = headless
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._active_sessions_count = 0
        self._initialized = False

    @classmethod
    async def get_instance(cls, headless: bool = True) -> "BrowserRuntimeManager":
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(headless=headless)
            return cls._instance

    async def get_browser(self) -> Browser:
        """Returns the shared Browser process, launching it lazily if needed."""
        async with self._lock:
            current_loop = asyncio.get_running_loop()
            if self._playwright is None or self._loop != current_loop:
                self._browser = None
                logger.info("Initializing async_playwright runtime on loop %s...", current_loop)
                self._playwright = await async_playwright().start()
                self._loop = current_loop

            if self._browser is None or not self._browser.is_connected():
                # Detect executable if specified
                executable = os.environ.get("HINAA_BROWSER_EXECUTABLE")
                if not executable:
                    for name in ["chromium", "chromium-browser", "google-chrome"]:
                        found = shutil.which(name)
                        if found:
                            executable = found
                            break

                launch_kwargs = {
                    "headless": self.headless,
                    "args": [
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-extensions",
                    ],
                }
                if executable and os.path.exists(executable):
                    launch_kwargs["executable_path"] = executable

                logger.info("Launching Chromium process (headless=%s)...", self.headless)
                self._browser = await self._playwright.chromium.launch(**launch_kwargs)
                self._initialized = True

            return self._browser


    def acquire_session_slot(self) -> bool:
        """Checks concurrency limits before creating a new session."""
        if self._active_sessions_count >= self.max_concurrent_sessions:
            logger.warning(
                "Browser capacity limit reached: %d/%d active sessions",
                self._active_sessions_count,
                self.max_concurrent_sessions,
            )
            return False
        self._active_sessions_count += 1
        return True

    def release_session_slot(self) -> None:
        """Decrements the active session counter."""
        if self._active_sessions_count > 0:
            self._active_sessions_count -= 1

    @property
    def active_sessions_count(self) -> int:
        return self._active_sessions_count

    async def shutdown(self) -> None:
        """Gracefully closes all browser processes and playwright drivers."""
        async with self._lock:
            if self._browser is not None:
                try:
                    await self._browser.close()
                    logger.info("Closed Chromium browser process.")
                except Exception as exc:
                    logger.warning("Error closing browser: %s", exc)
                finally:
                    self._browser = None

            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                    logger.info("Stopped Playwright driver.")
                except Exception as exc:
                    logger.warning("Error stopping Playwright: %s", exc)
                finally:
                    self._playwright = None

            self._active_sessions_count = 0
            self._initialized = False
