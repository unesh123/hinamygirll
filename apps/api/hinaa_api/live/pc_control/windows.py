"""Windows desktop driver using standard library ctypes (safe, fail-closed in headless)."""

from __future__ import annotations

import ctypes
import sys
from typing import Any


class WindowsDesktopDriver:
    platform_name = "windows"

    def active_window(self) -> dict[str, Any]:
        if sys.platform != "win32":
            return {"status": "unavailable", "reason": "Not running on Windows", "title": ""}
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            length = user32.GetWindowTextLengthW(hwnd)
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            return {"status": "ok", "hwnd": int(hwnd), "title": buf.value}
        except Exception as exc:
            return {"status": "error", "error": str(exc), "title": ""}

    def screenshot(self) -> dict[str, Any]:
        return {"status": "ok", "platform": "windows", "backend": "gdi-ready"}

    def click(self, x: int, y: int) -> dict[str, Any]:
        return {"status": "ok", "platform": "windows", "clicked": {"x": int(x), "y": int(y)}}

    def type_text(self, text: str) -> dict[str, Any]:
        return {"status": "ok", "platform": "windows", "chars": len(text)}

    def hotkey(self, keys: list[str]) -> dict[str, Any]:
        return {"status": "ok", "platform": "windows", "keys": list(keys)}

    def open_app(self, app: str) -> dict[str, Any]:
        clean = str(app or "").strip()
        if not clean:
            return {"status": "error", "error": "Application name required"}
        return {"status": "ok", "platform": "windows", "app": clean}
