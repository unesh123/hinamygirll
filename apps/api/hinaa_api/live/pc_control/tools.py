"""Risk-gated PC control executor and tool-registry definitions."""

from __future__ import annotations

import sys
from typing import Any

from ...tools.registry import RiskTier, ToolDefinition, ToolEffect, registry
from .base import ConfirmationRequiredError, DesktopDriver, is_write_action
from .linux import LinuxDesktopDriver
from .macos import MacOSDesktopDriver
from .vision import locate_target
from .windows import WindowsDesktopDriver


def get_desktop_driver(platform_override: str | None = None) -> DesktopDriver:
    plat = (platform_override or sys.platform).lower()
    if plat.startswith("win"):
        return WindowsDesktopDriver()
    if plat.startswith("darwin") or plat == "macos":
        return MacOSDesktopDriver()
    return LinuxDesktopDriver()


def execute_pc_action(
    action: str,
    params: dict[str, Any] | None = None,
    *,
    confirmed: bool = False,
    driver: DesktopDriver | None = None,
) -> dict[str, Any]:
    """Execute a PC control action with strict confirmation gating for writes."""
    args = dict(params or {})
    clean = str(action or "").removeprefix("pc.").strip().lower()
    write = is_write_action(clean)

    if write and not confirmed:
        raise ConfirmationRequiredError(
            f"PC action 'pc.{clean}' modifies desktop state and requires confirmed=True."
        )

    drv = driver or get_desktop_driver()
    if clean == "screenshot":
        return drv.screenshot()
    if clean == "active_window":
        return drv.active_window()
    if clean == "click":
        if "x" in args and "y" in args:
            return drv.click(int(args["x"]), int(args["y"]))
        pt = locate_target(str(args.get("label") or ""), ocr_tokens=args.get("ocr_tokens"))
        if pt is None:
            return {"status": "error", "error": "Target element coordinates or label match required"}
        return drv.click(pt.x, pt.y)
    if clean == "type":
        return drv.type_text(str(args.get("text") or ""))
    if clean == "hotkey":
        keys = [str(k) for k in (args.get("keys") or [])]
        return drv.hotkey(keys)
    if clean == "open_app":
        return drv.open_app(str(args.get("app") or ""))
    return {"status": "error", "error": f"Unsupported PC action: {clean}"}


PC_TOOL_SPECS: tuple[tuple[str, str, bool, RiskTier, ToolEffect, dict[str, Any]], ...] = (
    (
        "pc.screenshot",
        "Capture desktop screenshot",
        False,
        RiskTier.TIER_0_READ_ONLY,
        ToolEffect.READ,
        {},
    ),
    (
        "pc.active_window",
        "Read active desktop window title",
        False,
        RiskTier.TIER_0_READ_ONLY,
        ToolEffect.READ,
        {},
    ),
    (
        "pc.click",
        "Click desktop UI target",
        True,
        RiskTier.TIER_3_PROCESS,
        ToolEffect.EXECUTE_PROCESS,
        {"label": {"type": "string"}, "x": {"type": "integer"}, "y": {"type": "integer"}},
    ),
    (
        "pc.type",
        "Type text into active desktop window",
        True,
        RiskTier.TIER_3_PROCESS,
        ToolEffect.EXECUTE_PROCESS,
        {"text": {"type": "string"}},
    ),
    (
        "pc.hotkey",
        "Send keyboard shortcut",
        True,
        RiskTier.TIER_3_PROCESS,
        ToolEffect.EXECUTE_PROCESS,
        {"keys": {"type": "array"}},
    ),
    (
        "pc.open_app",
        "Launch desktop application",
        True,
        RiskTier.TIER_3_PROCESS,
        ToolEffect.EXECUTE_PROCESS,
        {"app": {"type": "string"}},
    ),
)


def register_pc_control_tools(target_registry=registry) -> list[str]:
    registered: list[str] = []
    for name, display, needs_confirm, risk, effect, params in PC_TOOL_SPECS:
        if target_registry.get(name) is None:
            async def _handler(payload: dict[str, Any], *, _action=name, _confirm=needs_confirm) -> dict[str, Any]:
                confirmed = bool(payload.get("confirmed", False)) if _confirm else True
                return execute_pc_action(_action, payload, confirmed=confirmed)

            target_registry.register(
                ToolDefinition(
                    name=name,
                    display_name=display,
                    description=f"Jarvis live desktop control: {display}",
                    parameters=params,
                    required_parameters=list(params.keys()) if name in {"pc.type", "pc.hotkey", "pc.open_app"} else [],
                    is_read_only=not needs_confirm,
                    requires_confirmation=needs_confirm,
                    risk_tier=risk,
                    risk_level="high" if needs_confirm else "low",
                    effect=effect,
                    timeout_seconds=15,
                ),
                _handler,
            )
        registered.append(name)
    return registered
