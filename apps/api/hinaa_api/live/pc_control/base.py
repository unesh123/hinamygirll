"""Cross-platform PC control contract with risk classification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

READ_ACTIONS = frozenset({"screenshot", "active_window"})
WRITE_ACTIONS = frozenset({"click", "type", "hotkey", "open_app"})


class ConfirmationRequiredError(PermissionError):
    """Raised when a desktop write action is attempted without explicit confirmation."""


def is_write_action(action: str) -> bool:
    clean = str(action or "").removeprefix("pc.").strip().lower()
    if clean in READ_ACTIONS:
        return False
    # Fail closed: unknown or write actions require explicit confirmation.
    return True


@dataclass(frozen=True)
class ScreenPoint:
    x: int
    y: int
    confidence: float = 1.0
    label: str = ""


class DesktopDriver(Protocol):
    platform_name: str

    def screenshot(self) -> dict[str, Any]: ...
    def active_window(self) -> dict[str, Any]: ...
    def click(self, x: int, y: int) -> dict[str, Any]: ...
    def type_text(self, text: str) -> dict[str, Any]: ...
    def hotkey(self, keys: list[str]) -> dict[str, Any]: ...
    def open_app(self, app: str) -> dict[str, Any]: ...
