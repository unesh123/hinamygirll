"""Cross-platform PC control package."""

from .base import ConfirmationRequiredError, DesktopDriver, ScreenPoint, is_write_action
from .tools import PC_TOOL_SPECS, execute_pc_action, get_desktop_driver, register_pc_control_tools
from .vision import locate_target

__all__ = [
    "ConfirmationRequiredError",
    "DesktopDriver",
    "PC_TOOL_SPECS",
    "ScreenPoint",
    "execute_pc_action",
    "get_desktop_driver",
    "is_write_action",
    "locate_target",
    "register_pc_control_tools",
]
