"""
HINAA Autonomous UI Director & Interface Actuation Tool.

Allows HINAA to programmatically orchestrate the client workspace:
- Navigation across modes (Work, Showroom 3D, Operate Core, Vault)
- Switching sections (Images, Library, Projects, Terminal, Settings, Memory)
- Actuating 3D avatar presence (Full 3D, PIP, Hidden) and companion switching
- Toggling tool drawers (Terminal Hands, Music, Settings, Memory Panel)
- Desktop window states (Standard, Floating Companion, Compact Bar)
- Guiding visual highlights on the UI
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import ToolDefinition, registry
from hinaa_api.harness.canonical_event_bus import get_canonical_event_bus, HinaCanonicalEvent

logger = logging.getLogger(__name__)


class UIControlRequest(BaseModel):
    action: str = Field(
        ...,
        description=(
            "UI action to perform: 'navigate', 'switch_mode', 'switch_section', "
            "'switch_operate_tab', 'set_avatar_mode', 'set_companion', 'toggle_drawer', "
            "'set_theme', 'desktop_window_mode', 'highlight_element', 'trigger_voice'"
        ),
    )
    mode: Optional[str] = Field(None, description="Workspace mode: 'work', 'showroom', 'operate', 'vault'")
    section: Optional[str] = Field(
        None,
        description="Navigation section: 'chat', 'talk', 'showroom', 'operate', 'vault', 'images', 'library', 'projects', 'creations', 'settings', 'terminal', 'memory'",
    )
    tab: Optional[str] = Field(
        None,
        description="Operate tab or subtab: 'tasks', 'capabilities', 'reports', 'orion', 'graph', 'policy', 'memory', 'verifier', 'rag', 'fleet', 'replay'",
    )
    avatar_mode: Optional[str] = Field(None, description="Avatar presentation mode: '3d', 'pip', 'hidden'")
    companion_id: Optional[str] = Field(None, description="Companion persona ID: 'hinaa', 'sakura', 'nova'")
    drawer: Optional[str] = Field(None, description="Drawer to open/close: 'terminal', 'settings', 'memory', 'music'")
    open: Optional[bool] = Field(True, description="Whether drawer should be open or closed")
    theme: Optional[str] = Field(None, description="Interface theme: 'dark', 'light'")
    window_mode: Optional[str] = Field(
        None,
        description="Desktop window mode: 'standard', 'floating_companion', 'compact_bar', 'full_screen'",
    )
    selector: Optional[str] = Field(None, description="CSS selector for UI element to highlight")
    label: Optional[str] = Field(None, description="Explanation tooltip for highlighted element")
    command: Optional[str] = Field(None, description="Initial command if opening terminal")


async def execute_ui_control(parameters: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Executes a UI control actuation, broadcasting to the Canonical Event Bus and returning instructions to client."""
    action = parameters.get("action", "navigate")
    mode = parameters.get("mode")
    section = parameters.get("section")
    tab = parameters.get("tab")
    avatar_mode = parameters.get("avatar_mode")
    companion_id = parameters.get("companion_id")
    drawer = parameters.get("drawer")
    is_open = parameters.get("open", True)
    theme = parameters.get("theme")
    window_mode = parameters.get("window_mode")
    selector = parameters.get("selector")
    label = parameters.get("label")
    command = parameters.get("command")

    # Record event on Canonical Event Bus
    bus = get_canonical_event_bus()
    run_id = (context or {}).get("run_id", "ui_run_direct")
    bus.publish_event(
        HinaCanonicalEvent(
            run_id=run_id,
            agent_name="AutonomousUIDirector",
            capability="ui_control",
            action=f"ui_{action}",
            resource=mode or section or tab or drawer or window_mode or "workspace",
            policy_decision="allow",
            result=parameters,
        )
    )

    logger.info("Autonomous UI Director executed: action=%s, target=%s", action, parameters)

    return {
        "success": True,
        "action": action,
        "ui_action": {
            "action": action,
            "mode": mode,
            "section": section,
            "tab": tab,
            "avatar_mode": avatar_mode,
            "companion_id": companion_id,
            "drawer": drawer,
            "open": is_open,
            "theme": theme,
            "window_mode": window_mode,
            "selector": selector,
            "label": label,
            "command": command,
        },
        "message": f"UI action '{action}' executed successfully.",
    }


ui_control_tool_def = ToolDefinition(
    name="ui_control",
    display_name="Autonomous UI Director",
    description=(
        "Directly controls HINAA's user interface. Use this when the user asks to switch views, "
        "show 3D showroom/orion visualizer, open terminal hands, change avatar mode, inspect fleet or replay, "
        "or change desktop window modes."
    ),
    parameters={
        "action": {
            "type": "string",
            "description": "The UI action: 'navigate', 'switch_mode', 'switch_section', 'switch_operate_tab', 'set_avatar_mode', 'set_companion', 'toggle_drawer', 'set_theme', 'desktop_window_mode', 'highlight_element'",
        },
        "mode": {
            "type": "string",
            "description": "Workspace mode: 'work', 'showroom', 'operate', 'vault'",
        },
        "section": {
            "type": "string",
            "description": "Navigation section: 'chat', 'talk', 'showroom', 'operate', 'vault', 'images', 'library', 'projects', 'creations', 'settings', 'terminal', 'memory'",
        },
        "tab": {
            "type": "string",
            "description": "Operate tab or subtab: 'tasks', 'capabilities', 'reports', 'orion', 'graph', 'policy', 'memory', 'verifier', 'rag', 'fleet', 'replay'",
        },
        "avatar_mode": {
            "type": "string",
            "description": "Avatar mode: '3d', 'pip', 'hidden'",
        },
        "companion_id": {
            "type": "string",
            "description": "Companion persona ID: 'hinaa', 'sakura', 'nova'",
        },
        "drawer": {
            "type": "string",
            "description": "Drawer: 'terminal', 'settings', 'memory', 'music'",
        },
        "open": {
            "type": "boolean",
            "description": "Whether drawer is open",
        },
        "window_mode": {
            "type": "string",
            "description": "Desktop window mode: 'standard', 'floating_companion', 'compact_bar', 'full_screen'",
        },
    },
    required_parameters=["action"],
    permission_level="default",
    risk_level="low",
)

registry.register(ui_control_tool_def, execute_ui_control)
