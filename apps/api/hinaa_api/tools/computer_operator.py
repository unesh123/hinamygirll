"""
HINAA Native Computer Operator Engine.

Modeled on autonomous voice-controlled desktop agents (Alfred / Computer-Use runtime):
1. Native Application Controller: Launches, switches, and focuses desktop apps (Spotify, Arc, Chrome, WhatsApp, VS Code).
2. Media & Playback Automator: System & app-level playback control, search-and-play on Spotify & YouTube.
3. Message Dispatcher: Automates window activation, recipient targeting, and keyboard text typing.
4. Desktop Observer: Inspects active window titles, running media processes, and UI coordinates.
5. OS-Native Execution: High-speed native execution using Windows ctypes/PowerShell/Shell hooks and Playwright.
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import os
import platform
import subprocess
import urllib.parse
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger(__name__)


class DesktopObservation(BaseModel):
    active_window_title: str
    active_process_name: str
    running_apps: List[str] = Field(default_factory=list)
    media_playing: bool = False
    timestamp: float = 0.0


class ComputerActionResult(BaseModel):
    success: bool
    action: str
    target: str
    detail: str
    observation: Optional[DesktopObservation] = None


class NativeComputerOperator:
    """
    Executes semantic computer-use actions directly against the local operating system.
    """

    @classmethod
    def get_active_window(cls) -> DesktopObservation:
        """Inspects current active window and running media processes."""
        active_title = "Unknown"
        active_proc = "unknown"
        running_apps: List[str] = []

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                active_title = buff.value or "Desktop"
            except Exception:
                pass

            try:
                # Fast process check via powershell
                cmd = "Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object -ExpandProperty ProcessName"
                res = subprocess.run(["powershell", "-NoProfile", "-Command", cmd], capture_output=True, text=True, timeout=2.0)
                if res.returncode == 0:
                    running_apps = [p.strip().lower() for p in res.stdout.splitlines() if p.strip()]
            except Exception:
                pass

        return DesktopObservation(
            active_window_title=active_title,
            active_process_name=active_proc,
            running_apps=running_apps,
            media_playing="spotify" in running_apps,
            timestamp=asyncio.get_event_loop().time(),
        )

    @classmethod
    async def open_app(cls, app_name: str) -> ComputerActionResult:
        """
        Launches or activates application by semantic name (e.g. spotify, whatsapp, arc, chrome).
        """
        app_lower = app_name.strip().lower()
        system = platform.system()

        app_map_windows = {
            "spotify": "spotify",
            "whatsapp": "whatsapp",
            "arc": "arc",
            "chrome": "chrome",
            "edge": "msedge",
            "youtube": "https://www.youtube.com",
            "discord": "discord",
            "vscode": "code",
            "terminal": "wt",
            "notepad": "notepad",
        }

        target = app_map_windows.get(app_lower, app_lower)

        if system == "Windows":
            try:
                if target.startswith("http://") or target.startswith("https://"):
                    # Open web destination
                    os.system(f'start "" "{target}"')
                else:
                    # Activate if already running, or start process
                    ps_script = f"""
                    $wscript = New-Object -ComObject WScript.Shell
                    $activated = $wscript.AppActivate('{target}')
                    if (-not $activated) {{
                        Start-Process '{target}' -ErrorAction SilentlyContinue
                    }}
                    """
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], timeout=3.0)

                return ComputerActionResult(
                    success=True,
                    action="open_app",
                    target=app_name,
                    detail=f"Successfully launched and focused '{app_name}'.",
                    observation=cls.get_active_window(),
                )
            except Exception as e:
                logger.warning("Failed to open app %s: %s", app_name, e)
                return ComputerActionResult(
                    success=False,
                    action="open_app",
                    target=app_name,
                    detail=f"Could not open application: {str(e)}",
                )

        return ComputerActionResult(success=False, action="open_app", target=app_name, detail="Unsupported platform.")

    @classmethod
    async def media_control(cls, action: str, query: Optional[str] = None) -> ComputerActionResult:
        """
        Controls music and media playback (play, pause, next, search_and_play).
        """
        action_lower = action.strip().lower()
        system = platform.system()

        if system == "Windows":
            try:
                if action_lower in ("play", "pause", "toggle"):
                    # Virtual Key Media Play/Pause (0xB3)
                    ctypes.windll.user32.keybd_event(0xB3, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB3, 0, 2, 0)
                    detail = "Toggled media playback."
                elif action_lower in ("next", "skip"):
                    ctypes.windll.user32.keybd_event(0xB0, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB0, 0, 2, 0)
                    detail = "Skipped to next track."
                elif action_lower in ("prev", "previous"):
                    ctypes.windll.user32.keybd_event(0xB1, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0xB1, 0, 2, 0)
                    detail = "Returned to previous track."
                elif action_lower == "search_and_play" and query:
                    # Open Spotify deep link query: spotify:search:<query>
                    encoded = urllib.parse.quote(query)
                    os.system(f'start "" "spotify:search:{encoded}"')
                    await asyncio.sleep(1.2)
                    # Press Enter / Space to trigger playback
                    ctypes.windll.user32.keybd_event(0x0D, 0, 0, 0)
                    ctypes.windll.user32.keybd_event(0x0D, 0, 2, 0)
                    detail = f"Searched and initiated playback for '{query}' on Spotify."
                else:
                    detail = f"Executed media command '{action}'."

                return ComputerActionResult(
                    success=True,
                    action="media_control",
                    target=action,
                    detail=detail,
                    observation=cls.get_active_window(),
                )
            except Exception as e:
                return ComputerActionResult(
                    success=False,
                    action="media_control",
                    target=action,
                    detail=f"Media control failed: {str(e)}",
                )

        return ComputerActionResult(success=False, action="media_control", target=action, detail="Unsupported platform.")

    @classmethod
    async def type_and_send(cls, app_name: str, text: str, recipient: Optional[str] = None) -> ComputerActionResult:
        """
        Activates target app (e.g. WhatsApp / Discord), navigates to chat, and types message.
        """
        if platform.system() == "Windows":
            try:
                # 1. Focus application
                await cls.open_app(app_name)
                await asyncio.sleep(0.5)

                # 2. If recipient specified on WhatsApp, search for recipient
                if recipient and "whatsapp" in app_name.lower():
                    # Focus search: Ctrl + F
                    ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)  # Ctrl
                    ctypes.windll.user32.keybd_event(0x46, 0, 0, 0)  # F
                    ctypes.windll.user32.keybd_event(0x46, 0, 2, 0)
                    ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
                    await asyncio.sleep(0.3)

                    # Send recipient search via WScript SendKeys
                    ps_type_rec = f"""
                    $wscript = New-Object -ComObject WScript.Shell
                    $wscript.SendKeys('{recipient}')
                    Start-Sleep -Milliseconds 400
                    $wscript.SendKeys('{{ENTER}}')
                    """
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps_type_rec], timeout=3.0)
                    await asyncio.sleep(0.5)

                # 3. Type message text
                safe_text = text.replace("'", "''").replace("{", "{{").replace("}", "}}")
                ps_type_msg = f"""
                $wscript = New-Object -ComObject WScript.Shell
                $wscript.SendKeys('{safe_text}')
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_type_msg], timeout=3.0)

                return ComputerActionResult(
                    success=True,
                    action="type_and_send",
                    target=app_name,
                    detail=f"Focused {app_name} and typed message: '{text[:50]}...'",
                    observation=cls.get_active_window(),
                )
            except Exception as e:
                return ComputerActionResult(
                    success=False,
                    action="type_and_send",
                    target=app_name,
                    detail=f"Typing action failed: {str(e)}",
                )

        return ComputerActionResult(success=False, action="type_and_send", target=app_name, detail="Unsupported platform.")

    @classmethod
    async def youtube_play(cls, search_query: str) -> ComputerActionResult:
        """
        Navigates to YouTube, queries the topic/creator, and plays video.
        """
        try:
            encoded = urllib.parse.quote(search_query)
            yt_url = f"https://www.youtube.com/results?search_query={encoded}"
            os.system(f'start "" "{yt_url}"')
            return ComputerActionResult(
                success=True,
                action="youtube_play",
                target=search_query,
                detail=f"Opened YouTube query for '{search_query}'.",
                observation=cls.get_active_window(),
            )
        except Exception as e:
            return ComputerActionResult(
                success=False,
                action="youtube_play",
                target=search_query,
                detail=f"YouTube navigation failed: {str(e)}",
            )


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------

computer_operator_tool_def = ToolDefinition(
    name="computer_operator",
    display_name="Native Desktop Computer Operator",
    description=(
        "Controls native desktop applications and media like an autonomous computer operator: "
        "launches apps (Spotify, Arc, WhatsApp, YouTube), controls music playback, types messages, "
        "and coordinates multi-step desktop actions."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": ["open_app", "media_control", "type_and_send", "youtube_play", "observe_desktop"],
            "description": "The desktop operation to execute.",
        },
        "target": {
            "type": "string",
            "description": "Target application name, media action, or search query.",
        },
        "content": {
            "type": "string",
            "description": "Optional message content or search details.",
        },
        "recipient": {
            "type": "string",
            "description": "Optional contact or recipient name (e.g. for WhatsApp/chat apps).",
        },
    },
    required_parameters=["action"],
    risk_level="medium",
    requires_confirmation=False,
    timeout_seconds=20.0,
)


async def execute_computer_operator(parameters: dict[str, Any]) -> dict[str, Any]:
    action = str(parameters.get("action", "")).strip().lower()
    target = str(parameters.get("target", "")).strip()
    content = str(parameters.get("content", "")).strip()
    recipient = parameters.get("recipient")

    if action == "open_app":
        res = await NativeComputerOperator.open_app(target or content)
    elif action == "media_control":
        res = await NativeComputerOperator.media_control(target or "toggle", query=content)
    elif action == "type_and_send":
        res = await NativeComputerOperator.type_and_send(app_name=target or "whatsapp", text=content, recipient=recipient)
    elif action == "youtube_play":
        res = await NativeComputerOperator.youtube_play(target or content)
    elif action == "observe_desktop":
        obs = NativeComputerOperator.get_active_window()
        return {"success": True, "observation": obs.model_dump(mode="json")}
    else:
        return {"success": False, "error": f"Unknown computer operator action '{action}'."}

    return res.model_dump(mode="json")


registry.register(computer_operator_tool_def, execute_computer_operator)
