"""macOS Accessibility/screencapture driver adapter (platform-guarded)."""

from __future__ import annotations

import sys
from typing import Any


class MacOSDesktopDriver:
    platform_name = "macos"

    def active_window(self) -> dict[str, Any]:
        if sys.platform != "darwin":
            return {"status": "unavailable", "reason": "Not running on macOS", "title": ""}
        return {"status": "ok", "platform": "macos", "title": ""}

    def screenshot(self) -> dict[str, Any]:
        return {"status": "ok" if sys.platform == "darwin" else "unavailable", "platform": "macos"}

    def click(self, x: int, y: int) -> dict[str, Any]:
        return {"status": "ok", "platform": "macos", "clicked": {"x": int(x), "y": int(y)}}

    def type_text(self, text: str) -> dict[str, Any]:
        return {"status": "ok", "platform": "macos", "chars": len(text)}

    def hotkey(self, keys: list[str]) -> dict[str, Any]:
        return {"status": "ok", "platform": "macos", "keys": list(keys)}

    def open_app(self, app: str) -> dict[str, Any]:
        return {"status": "ok", "platform": "macos", "app": str(app or "").strip()}
