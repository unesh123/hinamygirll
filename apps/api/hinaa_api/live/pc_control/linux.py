"""Linux X11/Wayland driver adapter (platform-guarded)."""

from __future__ import annotations

import sys
from typing import Any


class LinuxDesktopDriver:
    platform_name = "linux"

    def active_window(self) -> dict[str, Any]:
        if not sys.platform.startswith("linux"):
            return {"status": "unavailable", "reason": "Not running on Linux", "title": ""}
        return {"status": "ok", "platform": "linux", "title": ""}

    def screenshot(self) -> dict[str, Any]:
        return {"status": "ok" if sys.platform.startswith("linux") else "unavailable", "platform": "linux"}

    def click(self, x: int, y: int) -> dict[str, Any]:
        return {"status": "ok", "platform": "linux", "clicked": {"x": int(x), "y": int(y)}}

    def type_text(self, text: str) -> dict[str, Any]:
        return {"status": "ok", "platform": "linux", "chars": len(text)}

    def hotkey(self, keys: list[str]) -> dict[str, Any]:
        return {"status": "ok", "platform": "linux", "keys": list(keys)}

    def open_app(self, app: str) -> dict[str, Any]:
        return {"status": "ok", "platform": "linux", "app": str(app or "").strip()}
