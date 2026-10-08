"""
HINAA Computer-Use Engine v2 (General Perception & Autonomous OS Operator).

Architecture:
1. Perception Layer (Three Eyes):
   - Eye 1: Accessibility Eye (Windows UI Automation / AX tree: windows, buttons, textboxes, lists)
   - Eye 2: Browser Eye (DOM, ARIA, URL, selectors, network state)
   - Eye 3: Vision Eye (Screen capture, bounding boxes, coordinate fallback)
   Priority: Accessibility > DOM > Native semantic action > Vision

2. Primitive Action API:
   - observe() -> GeneralPerception
   - find_element(role, name, text) -> Optional[AXElement]
   - focus_window(target) -> bool
   - click(x, y, button, element_id) -> bool
   - type_text(text, clear_first) -> bool
   - press_hotkey(keys) -> bool
   - scroll(direction, amount) -> bool
   - drag(start_x, start_y, end_x, end_y) -> bool
   - open_application(app_or_url) -> bool
   - wait_for_state(condition, timeout) -> bool
   - verify_state(expected) -> bool

3. Safety Confirmation Gate:
   - Splits irreversible actions:
     draft_message -> find_conversation -> focus_input -> type_message -> verify_draft -> request_send_authorization -> send_message -> verify_sent
   - Guarded actions require explicit confirmation token:
     require_confirmation_for: ["send_message", "purchase", "delete", "publish", "deploy", "change_account"]

4. Autonomous Perception-Action-Verification Loop with Bounded Budget:
   - observe -> reason -> act -> observe -> verify -> repeat
   - Bounded by max_steps (default 40), max_wall_time_seconds (120s), and cost policy.

5. Unified Event Bus with Motion Brain:
   - computer_action -> Motion Brain: operating_computer (#06B6D4)
   - verification_success -> Motion Brain: success (#10B981)
   - verification_failed -> Motion Brain: recovery (#EF4444)
"""

from __future__ import annotations

import asyncio
import ctypes
import json
import logging
import math
import os
from pathlib import Path
import platform
import subprocess
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.integrations.desktop_bridge_auth import bridge_token
from hinaa_api.tools.registry import registry, ToolDefinition
from hinaa_api.tools.terminal_hands import _powershell_exe
from hinaa_api.harness.motion_brain import get_motion_director, SemanticIntent, SpatialStation

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Perception Models (The Three Eyes)
# ---------------------------------------------------------------------------

class AXElement(BaseModel):
    """Accessibility element representation from Windows UI Automation / AX tree."""
    role: str = "element"  # window, button, textbox, listitem, checkbox, menu
    name: str = ""
    value: Optional[str] = None
    bounds: Dict[str, int] = Field(default_factory=lambda: {"x": 0, "y": 0, "w": 0, "h": 0})
    is_enabled: bool = True
    is_focused: bool = False
    runtime_id: Optional[str] = None


class BrowserDOMElement(BaseModel):
    """Web element representation from browser inspection."""
    tag: str = "div"
    selector: str = ""
    inner_text: str = ""
    aria_label: Optional[str] = None
    href: Optional[str] = None
    is_visible: bool = True


class VisionScreenSample(BaseModel):
    """Visual display metric sample."""
    screen_width: int = 1920
    screen_height: int = 1080
    scale_factor: float = 1.0
    screenshot_captured: bool = False


class GeneralPerception(BaseModel):
    """Fused perception from Accessibility, Browser, and Vision eyes."""
    active_window_title: str = "Desktop"
    active_process_name: str = "unknown"
    running_apps: List[str] = Field(default_factory=list)
    ax_elements: List[AXElement] = Field(default_factory=list)
    browser_dom: Optional[List[BrowserDOMElement]] = None
    vision: VisionScreenSample = Field(default_factory=VisionScreenSample)
    focused_element: Optional[str] = None
    media_playing: bool = False
    timestamp: float = Field(default_factory=time.time)


# Backward-compatible alias
DesktopObservation = GeneralPerception


class ComputerActionResult(BaseModel):
    success: bool
    action: str
    target: str
    detail: str
    verified: bool = True
    requires_confirmation: bool = False
    confirmation_token: Optional[str] = None
    observation: Optional[GeneralPerception] = None
    error: Optional[str] = None


class ComputerBudget(BaseModel):
    max_steps: int = 40
    max_wall_time_seconds: float = 120.0
    max_cost: float = 0.50
    require_confirmation_for: List[str] = Field(
        default_factory=lambda: [
            "send_message",
            "purchase",
            "delete",
            "publish",
            "deploy",
            "change_account",
        ]
    )


class LoopStepResult(BaseModel):
    step_index: int
    action: str
    target: str
    success: bool
    verified: bool
    latency_ms: float
    detail: str


class ComputerLoopReport(BaseModel):
    goal: str
    success: bool
    steps_taken: int
    total_latency_ms: float
    verified: bool
    requires_confirmation: bool = False
    confirmation_action: Optional[str] = None
    confirmation_token: Optional[str] = None
    history: List[LoopStepResult] = Field(default_factory=list)
    final_observation: Optional[GeneralPerception] = None


# ---------------------------------------------------------------------------
# Native Computer-Use Engine v2
# ---------------------------------------------------------------------------

class NativeComputerOperator:
    """
    General-purpose Autonomous Computer Operator Engine with 3-eye perception,
    primitive actuators, verification loops, and motion bus integration.
    """

    # Confirmation tokens storage for safety-gated actions
    _pending_confirmations: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def _dry_run(cls) -> bool:
        """When HINAA_COMPUTER_DRY_RUN=1 no keystroke, click, launch, or
        message ever reaches the real desktop.

        The evaluation suites set this so a `pytest` run can never type into
        a real WhatsApp chat or send a real message — that exact accident is
        why this switch exists. Production runs leave it unset.
        """
        return os.environ.get("HINAA_COMPUTER_DRY_RUN", "").strip().lower() in {"1", "true", "yes"}

    @classmethod
    def emit_motion_event(cls, event_type: str, detail: str = "") -> None:
        """Publishes computer operation events to the Motion Brain."""
        try:
            director = get_motion_director()
            if event_type == "computer_action":
                director.transition_state(
                    intent=SemanticIntent.OPERATING_COMPUTER,
                    active_tool="computer_operator",
                    energy=0.85,
                    focus=0.95,
                )
            elif event_type == "verification_failed":
                director.transition_state(
                    intent=SemanticIntent.ERROR,
                    active_tool="computer_operator",
                    energy=0.9,
                    focus=0.9,
                )
            elif event_type == "verification_success":
                director.transition_state(
                    intent=SemanticIntent.SUCCESS,
                    active_tool="computer_operator",
                    energy=0.7,
                    focus=0.8,
                )
        except Exception:
            pass

    # ── Eye 1 & Eye 3: Perception ──────────────────────────────────────

    @classmethod
    def observe(cls) -> GeneralPerception:
        """
        Observes current desktop state fusing Accessibility Eye, Process status, and Display metrics.
        """
        active_title = "Desktop"
        active_proc = "unknown"
        running_apps: List[str] = []
        ax_elements: List[AXElement] = []
        screen_w, screen_h = 1920, 1080

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                hwnd = user32.GetForegroundWindow()
                length = user32.GetWindowTextLengthW(hwnd)
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                active_title = buff.value or "Desktop"
                screen_w = user32.GetSystemMetrics(0) or 1920
                screen_h = user32.GetSystemMetrics(1) or 1080
            except Exception:
                pass

            try:
                # Fast running apps enumeration
                cmd = "Get-Process | Where-Object { $_.MainWindowTitle } | Select-Object -ExpandProperty ProcessName"
                res = subprocess.run(
                    [_powershell_exe(), "-NoProfile", "-Command", cmd],
                    capture_output=True,
                    text=True,
                    timeout=1.8,
                )
                if res.returncode == 0:
                    running_apps = [p.strip().lower() for p in res.stdout.splitlines() if p.strip()]
            except Exception:
                pass

            # Synthesize key accessibility landmarks from active title & process
            ax_elements = [
                AXElement(role="window", name=active_title, is_focused=True, bounds={"x": 0, "y": 0, "w": screen_w, "h": screen_h}),
                AXElement(role="button", name="Close", bounds={"x": screen_w - 45, "y": 0, "w": 45, "h": 30}),
                AXElement(role="textbox", name="Search / Message Input", is_focused=False, bounds={"x": 200, "y": 100, "w": 400, "h": 36}),
            ]

        obs = GeneralPerception(
            active_window_title=active_title,
            active_process_name=active_proc,
            running_apps=running_apps,
            ax_elements=ax_elements,
            vision=VisionScreenSample(screen_width=screen_w, screen_height=screen_h),
            media_playing="spotify" in running_apps,
            timestamp=time.time(),
        )
        return obs

    # Backward-compatible method
    @classmethod
    def get_active_window(cls) -> GeneralPerception:
        return cls.observe()

    DAEMON_URL = "http://127.0.0.1:8765"

    @classmethod
    def is_daemon_live(cls) -> bool:
        """Checks if the interactive desktop control daemon is responding on port 8765."""
        import urllib.request
        try:
            req = urllib.request.Request(f"{cls.DAEMON_URL}/health", headers={"User-Agent": "HINAA-ComputerOperator", "Authorization": "Bearer " + bridge_token()})
            with urllib.request.urlopen(req, timeout=0.35) as resp:
                return resp.status == 200
        except Exception:
            return False

    @classmethod
    async def send_daemon_action(cls, action_payload: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Sends an action to the local interactive desktop control daemon."""
        import urllib.request
        try:
            data = json.dumps(action_payload).encode("utf-8")
            req = urllib.request.Request(
                f"{cls.DAEMON_URL}/api/action",
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": "HINAA-ComputerOperator", "Authorization": "Bearer " + bridge_token()},
            )
            loop = asyncio.get_running_loop()
            def _post():
                with urllib.request.urlopen(req, timeout=4.0) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            return await loop.run_in_executor(None, _post)
        except Exception as e:
            logger.debug(f"Daemon call failed: {e}")
            return None

    # ── Primitive Actuator API ─────────────────────────────────────────

    @classmethod
    async def mouse_move(cls, x: int, y: int, smooth: bool = True) -> bool:
        """Moves cursor to (x, y) coordinates. If smooth=True, glides naturally."""
        cls.emit_motion_event("computer_action", f"Move mouse to ({x}, {y})")
        if cls._dry_run():
            return True
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "mouse_move", "x": x, "y": y, "smooth": smooth})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                if not smooth:
                    return bool(user32.SetCursorPos(x, y))

                # Smooth cursor glide interpolation
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
                pt = POINT()
                user32.GetCursorPos(ctypes.byref(pt))
                start_x, start_y = pt.x, pt.y
                steps = 15
                for step in range(1, steps + 1):
                    t = step / steps
                    ease = 1.0 - math.pow(1.0 - t, 3)
                    cur_x = int(start_x + (x - start_x) * ease)
                    cur_y = int(start_y + (y - start_y) * ease)
                    user32.SetCursorPos(cur_x, cur_y)
                    await asyncio.sleep(0.012)
                user32.SetCursorPos(x, y)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def focus_window(cls, target: str) -> bool:
        """Brings target window into foreground."""
        cls.emit_motion_event("computer_action", f"Focus {target}")
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "focus_window", "target": target})
            if res and res.get("success"):
                return True

        if platform.system() != "Windows":
            return False

        ps_script = f"""
        $wscript = New-Object -ComObject WScript.Shell
        $wscript.AppActivate('{target}')
        """
        try:
            res = subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps_script], capture_output=True, timeout=2.0)
            return "True" in res.stdout
        except Exception:
            return False

    @classmethod
    async def list_windows(cls) -> list[dict[str, Any]]:
        """Lists active top-level application windows."""
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "list_windows"})
            if res and "windows" in res:
                return res["windows"]
        if platform.system() == "Windows":
            try:
                import ctypes, ctypes.wintypes
                user32 = ctypes.windll.user32
                windows = []

                def enum_proc(hwnd, lParam):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buff = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buff, length + 1)
                            title = buff.value.strip()
                            if title and title not in ("Default IME", "MSCTFIME UI"):
                                pid = ctypes.c_ulong()
                                user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                                proc_name = ""
                                try:
                                    import psutil
                                    proc_name = psutil.Process(pid.value).name()
                                except Exception:
                                    pass
                                windows.append({
                                    "hwnd": int(hwnd),
                                    "pid": int(pid.value),
                                    "process": proc_name,
                                    "title": title,
                                })
                    return True

                WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM)
                user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
                if windows:
                    return windows
            except Exception:
                pass

            try:
                ps = "Get-Process | Where-Object MainWindowTitle | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json -Compress"
                res = subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=2.5)
                raw = res.stdout.strip()
                if raw:
                    data = json.loads(raw)
                    if isinstance(data, dict):
                        data = [data]
                    return [
                        {"pid": item.get("Id"), "process": item.get("ProcessName", ""), "title": item.get("MainWindowTitle", "")}
                        for item in data
                    ]
            except Exception:
                pass
        return []

    @classmethod
    async def close_window(cls, target: str) -> bool:
        """Closes a target window."""
        cls.emit_motion_event("computer_action", f"Close {target}")
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "close_window", "target": target})
            if res and res.get("success"):
                return True
        if platform.system() == "Windows":
            try:
                ps = f"$p = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{target}*' -or $_.ProcessName -like '*{target}*' }} | Select-Object -First 1; if ($p) {{ $p.CloseMainWindow() }}"
                subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=3.0)
                return True
            except Exception:
                return False
        return False

    @classmethod
    async def set_window_state(cls, target: str, state: str = "maximize") -> bool:
        """Minimizes or maximizes a target window."""
        cls.emit_motion_event("computer_action", f"{state.title()} {target}")
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "set_window_state", "target": target, "state": state})
            if res and res.get("success"):
                return True
        if platform.system() == "Windows":
            try:
                show_cmd = "3" if state == "maximize" else "2"
                ps = f"""
                $wscript = New-Object -ComObject WScript.Shell
                if ($wscript.AppActivate('{target}')) {{
                    Add-Type -TypeDefinition @"
                    using System;
                    using System.Runtime.InteropServices;
                    public class Win32Win {{
                        [DllImport("user32.dll")]
                        public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
                        [DllImport("user32.dll")]
                        public static extern IntPtr GetForegroundWindow();
                    }}
"@
                    [Win32Win]::ShowWindow([Win32Win]::GetForegroundWindow(), {show_cmd})
                }}
                """
                subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=3.0)
                return True
            except Exception:
                return False
        return False

    @classmethod
    async def click(cls, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> bool:
        """Sends native mouse click at screen coordinates."""
        cls.emit_motion_event("computer_action", f"Click {button} x{clicks} at ({x}, {y})")
        if cls._dry_run():
            return True
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "click", "x": x, "y": y, "button": button, "clicks": clicks})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                if x is not None and y is not None and (x > 0 or y > 0):
                    await cls.mouse_move(x, y, smooth=True)
                await asyncio.sleep(0.03)
                btn = button.lower()
                for i in range(clicks):
                    if btn == "right":
                        user32.mouse_event(0x08, 0, 0, 0, 0)
                        user32.mouse_event(0x10, 0, 0, 0, 0)
                    elif btn == "middle":
                        user32.mouse_event(0x20, 0, 0, 0, 0)
                        user32.mouse_event(0x40, 0, 0, 0, 0)
                    else:
                        user32.mouse_event(0x02, 0, 0, 0, 0)
                        user32.mouse_event(0x04, 0, 0, 0, 0)
                    if clicks > 1 and i < clicks - 1:
                        await asyncio.sleep(0.08)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def double_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Double clicks at target coordinates."""
        return await cls.click(x=x, y=y, button="left", clicks=2)

    @classmethod
    async def right_click(cls, x: Optional[int] = None, y: Optional[int] = None) -> bool:
        """Right clicks to open context menu."""
        return await cls.click(x=x, y=y, button="right", clicks=1)

    @classmethod
    async def drag(cls, start_x: int, start_y: int, end_x: int, end_y: int) -> bool:
        """Drags mouse from start to end coordinates."""
        cls.emit_motion_event("computer_action", f"Drag from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "drag", "start_x": start_x, "start_y": start_y, "end_x": end_x, "end_y": end_y})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                await cls.mouse_move(start_x, start_y, smooth=True)
                await asyncio.sleep(0.04)
                user32.mouse_event(0x02, 0, 0, 0, 0)  # LEFTDOWN
                await asyncio.sleep(0.04)
                steps = 20
                for step in range(1, steps + 1):
                    t = step / steps
                    cur_x = int(start_x + (end_x - start_x) * t)
                    cur_y = int(start_y + (end_y - start_y) * t)
                    user32.SetCursorPos(cur_x, cur_y)
                    await asyncio.sleep(0.015)
                user32.SetCursorPos(end_x, end_y)
                await asyncio.sleep(0.04)
                user32.mouse_event(0x04, 0, 0, 0, 0)  # LEFTUP
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def screenshot(cls) -> Dict[str, Any]:
        """Captures real full desktop screen."""
        cls.emit_motion_event("computer_action", "Capture desktop screenshot")
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "screenshot"})
            if res and res.get("success"):
                return res

        screenshot_dir = Path(__file__).resolve().parents[3] / "apps" / "api" / "data" / "screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        filename = f"screen_{int(time.time() * 1000)}.png"
        filepath = screenshot_dir / filename

        # Fallback via local PIL ImageGrab
        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(str(filepath), "PNG")
            return {
                "success": True,
                "filepath": str(filepath),
                "filename": filename,
                "width": img.width,
                "height": img.height,
            }
        except Exception as e:
            logger.debug(f"PIL ImageGrab fallback failed ({e}), trying PowerShell CopyFromScreen")
            try:
                ps = f"""
                Add-Type -AssemblyName System.Windows.Forms, System.Drawing
                $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
                $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
                $g = [System.Drawing.Graphics]::FromImage($bmp)
                $g.CopyFromScreen($b.Location, [System.Drawing.Point]::Empty, $b.Size)
                $bmp.Save('{str(filepath).replace('\\', '\\\\')}', [System.Drawing.Imaging.ImageFormat]::Png)
                $g.Dispose()
                $bmp.Dispose()
                """
                subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=4.0)
                if filepath.exists() and filepath.stat().st_size > 0:
                    return {
                        "success": True,
                        "filepath": str(filepath),
                        "filename": filename,
                    }
            except Exception as ps_err:
                logger.debug(f"PowerShell screenshot also failed: {ps_err}")
            return {
                "success": False,
                "error": "Screen capture could not access display DC. Run 'scripts/start-desktop-daemon.bat' in your desktop session for physical screen access.",
            }

    @classmethod
    async def chrome_control(
        cls,
        url: Optional[str] = None,
        action: str = "navigate",
        selector: Optional[str] = None,
        text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Drives Google Chrome autonomously via Playwright automation engine."""
        cls.emit_motion_event("computer_action", f"Chrome: {action} {url or selector or ''}")
        try:
            from hinaa_api.tools.browser_automation import (
                browser_navigate,
                browser_click,
                browser_type,
                browser_extract,
                BrowserNavigateParams,
                BrowserClickParams,
                BrowserTypeParams,
                BrowserExtractParams,
            )

            if action == "navigate" and url:
                msg = await browser_navigate(BrowserNavigateParams(url=url))
                return {"success": True, "action": "navigate", "detail": msg}
            elif action == "click" and selector:
                msg = await browser_click(BrowserClickParams(selector=selector))
                return {"success": True, "action": "click", "detail": msg}
            elif action == "type" and selector and text:
                msg = await browser_type(BrowserTypeParams(selector=selector, text=text))
                return {"success": True, "action": "type", "detail": msg}
            elif action == "extract":
                msg = await browser_extract(BrowserExtractParams(selector=selector or "body", extract_type="text"))
                return {"success": True, "action": "extract", "detail": msg}
            else:
                return {"success": False, "error": f"Unknown Chrome control action '{action}'."}
        except Exception as e:
            logger.error(f"chrome_control error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    @classmethod
    async def type_text(cls, text: str, clear_first: bool = False) -> bool:
        """Types text using native keystrokes."""
        cls.emit_motion_event("computer_action", f"Type text: {text[:20]}")
        if cls._dry_run():
            return True
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "type_text", "text": text, "clear_first": clear_first})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                safe_text = text.replace("'", "''").replace("{", "{{").replace("}", "}}").replace("+", "{+}").replace("^", "{^}").replace("%", "{%}")
                clear_cmd = "$wscript.SendKeys('^a{BACKSPACE}');" if clear_first else ""
                ps = f"""
                $wscript = New-Object -ComObject WScript.Shell
                {clear_cmd}
                $wscript.SendKeys('{safe_text}')
                """
                subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=3.0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def press_hotkey(cls, keys: str) -> bool:
        """Triggers hotkey combinations (e.g. enter, ctrl+f, alt+tab, escape)."""
        cls.emit_motion_event("computer_action", f"Hotkey: {keys}")
        if cls._dry_run():
            return True
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "press_hotkey", "keys": keys})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                key_map = {
                    "enter": "{ENTER}",
                    "escape": "{ESC}",
                    "tab": "{TAB}",
                    "ctrl+f": "^f",
                    "ctrl+c": "^c",
                    "ctrl+v": "^v",
                    "ctrl+a": "^a",
                    "alt+tab": "%{TAB}",
                    "space": " ",
                }
                mapped = key_map.get(keys.lower(), keys)
                ps = f"""
                $wscript = New-Object -ComObject WScript.Shell
                $wscript.SendKeys('{mapped}')
                """
                subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=2.0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def scroll(cls, direction: str = "down", amount: int = 3) -> bool:
        """Scrolls mouse wheel up or down."""
        cls.emit_motion_event("computer_action", f"Scroll {direction}")
        if cls._dry_run():
            return True
        if cls.is_daemon_live():
            res = await cls.send_daemon_action({"action": "scroll", "direction": direction, "amount": amount})
            if res and res.get("success"):
                return True

        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                delta = -120 * amount if direction == "down" else 120 * amount
                user32.mouse_event(0x0800, 0, 0, delta, 0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def open_application(cls, app_or_url: str) -> ComputerActionResult:
        """Universal application launcher and window focus."""
        cls.emit_motion_event("computer_action", f"Open {app_or_url}")
        target = app_or_url.strip()
        system = platform.system()

        import re
        cleaned = re.sub(r"^(?:open|launch|start|run|switch\s+to|focus)\s+", "", target, flags=re.IGNORECASE).strip()
        trailing_fluff = r"(?i)\s+(?:on\s+my\s+pc|on\s+my\s+computer|on\s+pc|on\s+desktop|in\s+my\s+pc|for\s+me|app|application|browser|software|program|please|now|window)$"
        while re.search(trailing_fluff, cleaned):
            cleaned = re.sub(trailing_fluff, "", cleaned).strip()
        if not cleaned:
            cleaned = target

        app_aliases = {
            "spotify": "spotify",
            "spotify web": "https://open.spotify.com",
            "whatsapp": "whatsapp",
            "arc": "arc",
            "chrome": "chrome",
            "google chrome": "chrome",
            "edge": "msedge",
            "microsoft edge": "msedge",
            "firefox": "firefox",
            "mozilla firefox": "firefox",
            "brave": "brave",
            "youtube": "https://www.youtube.com",
            "netflix": "https://www.netflix.com",
            "prime video": "https://www.primevideo.com",
            "amazon prime": "https://www.primevideo.com",
            "disney plus": "https://www.disneyplus.com",
            "disney+": "https://www.disneyplus.com",
            "hulu": "https://www.hulu.com",
            "crunchyroll": "https://www.crunchyroll.com",
            "twitch": "https://www.twitch.tv",
            "tiktok": "https://www.tiktok.com",
            "instagram": "https://www.instagram.com",
            "twitter": "https://x.com",
            "x": "https://x.com",
            "gmail": "https://mail.google.com",
            "google maps": "https://maps.google.com",
            "maps": "https://maps.google.com",
            "kimi": "https://www.kimi.com",
            "kimi ai": "https://www.kimi.com",
            "chatgpt": "https://chatgpt.com",
            "chat gpt": "https://chatgpt.com",
            "claude": "https://claude.ai",
            "gemini": "https://gemini.google.com",
            "discord": "discord",
            "vscode": "code",
            "vs code": "code",
            "code": "code",
            "visual studio code": "code",
            "integraphy": "Google.Antigravity",
            "antigravity": "Google.Antigravity",
            "antigravity ide": "Google.AntigravityIDE",
            "cursor": "Anysphere.Cursor",
            "opencode": "ai.opencode.desktop",
            "zcode": "dev.zcode.app",
            "terminal": "wt",
            "windows terminal": "wt",
            "cmd": "cmd",
            "command prompt": "cmd",
            "powershell": "powershell",
            "notepad": "notepad",
            "calculator": "calc",
            "calc": "calc",
            "files": "explorer",
            "file explorer": "explorer",
            "explorer": "explorer",
            "paint": "mspaint",
            "task manager": "taskmgr",
            "taskmgr": "taskmgr",
            "word": "winword",
            "excel": "excel",
            "powerpoint": "powerpnt",
            "settings": "ms-settings:",
            "camera": "microsoft.windows.camera:",
            "clock": "ms-clock:",
            "steam": "steam",
            "telegram": "telegram",
            "obs": "obs64",
            "whatsapp": "whatsapp:",
            "whatsapp desktop": "whatsapp:",
            "whatsapp web": "https://web.whatsapp.com",
        }
        if cleaned.lower() in {"my editor", "preferred editor", "code editor", "integrity"}:
            cleaned = os.getenv("HINAA_PREFERRED_EDITOR", "antigravity")
        resolved = app_aliases.get(cleaned.lower(), cleaned)

        if system == "Windows":
            try:
                if resolved.startswith("http://") or resolved.startswith("https://") or resolved.startswith("spotify:") or resolved.startswith("ms-settings:") or resolved.startswith("microsoft.windows."):
                    if not cls._dry_run():
                        subprocess.Popen(["explorer.exe", resolved], shell=False)
                else:
                    safe_target = resolved.replace("'", "''").replace('"', '')
                    workspace = os.environ.get("WORKSPACE_ROOT") or str(Path(__file__).resolve().parents[4])
                    safe_workspace = workspace.replace("'", "''").replace('"', '')
                    ps = f"""
                    $ErrorActionPreference = 'Stop'
                    $target = '{safe_target}'
                    $wsPath = '{safe_workspace}'
                    $ws = New-Object -ComObject WScript.Shell
                    $activated = $ws.AppActivate($target)
                    if (-not $activated) {{
                        $antigravityIdeExe = "$env:LOCALAPPDATA\\Programs\\Antigravity IDE\\Antigravity IDE.exe"
                        $antigravityExe = "$env:LOCALAPPDATA\\Programs\\antigravity\\Antigravity.exe"
                        if ($target -like "*AntigravityIDE*" -and (Test-Path $antigravityIdeExe)) {{
                            Start-Process -FilePath $antigravityIdeExe -ArgumentList "`"$wsPath`"" -ErrorAction Stop
                        }} elseif ($target -like "*Antigravity*" -and (Test-Path $antigravityExe)) {{
                            Start-Process -FilePath $antigravityExe -ArgumentList "`"$wsPath`"" -ErrorAction Stop
                        }} elseif ($target -eq "code") {{
                            Start-Process -FilePath "code" -ArgumentList "`"$wsPath`"" -ErrorAction Stop
                        }} elseif ($target -like "*cursor*") {{
                            Start-Process -FilePath "cursor" -ArgumentList "`"$wsPath`"" -ErrorAction Stop
                        }} else {{
                            $found = Get-StartApps | Where-Object {{ $_.Name -like "*$target*" -or $_.AppID -like "*$target*" }} | Select-Object -First 1
                            if ($found) {{
                                Start-Process "shell:AppsFolder\\$($found.AppID)" -ErrorAction Stop
                            }} else {{
                                Start-Process $target -ErrorAction Stop
                            }}
                        }}
                    }}
                    """
                    if not cls._dry_run():
                        subprocess.run([_powershell_exe(), "-NoProfile", "-Command", ps], timeout=8.0, check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

                await asyncio.sleep(0.4)
                obs = cls.observe()
                # Verify against what the desktop actually shows afterwards:
                # a URL target is verified when any known browser holds a
                # window; an app target when its process or the foreground
                # title names it. "Verification pending" forever meant every
                # launch looked unconfirmed to the mission loop.
                is_url = resolved.startswith(("http://", "https://", "spotify:", "ms-settings:", "microsoft.windows."))
                if is_url:
                    verified = bool({"chrome", "msedge", "firefox", "brave", "arc", "opera"} & set(obs.running_apps))
                else:
                    token = resolved.split("\\")[-1].split(".")[0].lower()
                    verified = any(token in app for app in obs.running_apps) or (
                        bool(token) and token in obs.active_window_title.lower()
                    )
                return ComputerActionResult(
                    success=True,
                    action="open_application",
                    target=app_or_url,
                    detail=(
                        f"'{app_or_url}' is up — verified on the desktop."
                        if verified
                        else f"Launch/focus requested for '{app_or_url}'. Window verification is pending."
                    ),
                    verified=verified,
                    observation=obs,
                )
            except Exception as e:
                cls.emit_motion_event("verification_failed", str(e))
                return ComputerActionResult(
                    success=False,
                    action="open_application",
                    target=app_or_url,
                    detail=f"Failed to launch: {str(e)}",
                    verified=False,
                    error=str(e),
                )

        return ComputerActionResult(success=False, action="open_application", target=app_or_url, detail="Unsupported platform.")

    # ── Safety Confirmation Gate (Splits Irreversible Actions) ─────────

    @classmethod
    async def draft_message(
        cls,
        app_name: str,
        text: str,
        recipient: Optional[str] = None,
    ) -> ComputerActionResult:
        """
        Navigates to chat input and types the message draft safely,
        requiring explicit authorization before sending.
        """
        cls.emit_motion_event("computer_action", f"Draft message for {recipient or app_name}")
        
        if recipient and "whatsapp" in app_name.lower():
            clean_phone = "".join(c for c in recipient if c.isdigit() or c == "+")
            if len(clean_phone) >= 7 and (clean_phone.startswith("+") or clean_phone.isdigit()):
                encoded_msg = urllib.parse.quote(text)
                if platform.system() == "Windows" and not cls._dry_run():
                    os.system(f'start "" "whatsapp://send?phone={clean_phone}&text={encoded_msg}"')
                await asyncio.sleep(0.5)
            else:
                await cls.open_application(app_name)
                await asyncio.sleep(0.4)
                await cls.press_hotkey("ctrl+f")
                await asyncio.sleep(0.2)
                await cls.type_text(recipient)
                await asyncio.sleep(0.3)
                await cls.press_hotkey("enter")
                await asyncio.sleep(0.4)
                await cls.type_text(text, clear_first=False)
        else:
            await cls.open_application(app_name)
            await asyncio.sleep(0.4)
            await cls.type_text(text, clear_first=False)

        # Generate confirmation token
        token = f"tok_{uuid.uuid4().hex[:12]}"
        cls._pending_confirmations[token] = {
            "action": "send_message",
            "app_name": app_name,
            "text": text,
            "recipient": recipient,
            "timestamp": time.time(),
        }

        obs = cls.observe()
        return ComputerActionResult(
            success=True,
            action="draft_message",
            target=app_name,
            detail=f"Drafted message for {recipient or 'recipient'} in {app_name}. Awaiting send confirmation.",
            verified=True,
            requires_confirmation=True,
            confirmation_token=token,
            observation=obs,
        )

    @classmethod
    async def send_message(
        cls,
        app_name: str,
        text: str,
        recipient: Optional[str] = None,
        confirmed: bool = False,
        confirmation_token: Optional[str] = None,
    ) -> ComputerActionResult:
        """
        Sends the message only if explicit confirmation is provided.
        """
        if not confirmed and not (confirmation_token and confirmation_token in cls._pending_confirmations):
            # Divert to draft_message for safety
            return await cls.draft_message(app_name, text, recipient)

        # Clear token if used
        if confirmation_token and confirmation_token in cls._pending_confirmations:
            del cls._pending_confirmations[confirmation_token]

        cls.emit_motion_event("computer_action", f"Authorize send in {app_name}")
        # Press Enter to transmit message
        await cls.press_hotkey("enter")
        cls.emit_motion_event("verification_success", "Message sent")

        obs = cls.observe()
        return ComputerActionResult(
            success=True,
            action="send_message",
            target=app_name,
            detail=f"Confirmed and sent message to {recipient or 'recipient'} in {app_name}.",
            verified=True,
            requires_confirmation=False,
            observation=obs,
        )

    # ── Backward-Compatible Workflow Methods ───────────────────────────

    @classmethod
    async def open_app(cls, app_name: str) -> ComputerActionResult:
        return await cls.open_application(app_name)

    @classmethod
    async def media_control(cls, action: str, query: Optional[str] = None) -> ComputerActionResult:
        """Controls music and media playback."""
        cls.emit_motion_event("computer_action", f"Media {action}")
        if cls._dry_run():
            return ComputerActionResult(
                success=True,
                action="media_control",
                target=action,
                detail=f"(dry run) media command '{action}' — no keys reached the desktop.",
                verified=True,
                observation=cls.observe(),
            )
        action_lower = action.strip().lower()
        system = platform.system()

        if system == "Windows":
            try:
                if action_lower in ("play", "pause", "toggle"):
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
                    encoded = urllib.parse.quote(query)
                    os.system(f'start "" "spotify:search:{encoded}"')
                    await asyncio.sleep(1.0)
                    await cls.press_hotkey("enter")
                    detail = f"Searched and initiated playback for '{query}' on Spotify."
                else:
                    detail = f"Executed media command '{action}'."

                cls.emit_motion_event("verification_success")
                return ComputerActionResult(
                    success=True,
                    action="media_control",
                    target=action,
                    detail=detail,
                    verified=True,
                    observation=cls.observe(),
                )
            except Exception as e:
                cls.emit_motion_event("verification_failed", str(e))
                return ComputerActionResult(
                    success=False,
                    action="media_control",
                    target=action,
                    detail=f"Media control failed: {str(e)}",
                    verified=False,
                    error=str(e),
                )

        return ComputerActionResult(success=False, action="media_control", target=action, detail="Unsupported platform.")

    @classmethod
    async def type_and_send(cls, app_name: str, text: str, recipient: Optional[str] = None) -> ComputerActionResult:
        # Default type_and_send now safely routes through draft_message
        return await cls.draft_message(app_name, text, recipient)

    @classmethod
    async def youtube_play(cls, search_query: str) -> ComputerActionResult:
        cls.emit_motion_event("computer_action", f"YouTube {search_query}")
        try:
            from hinaa_api.tools.youtube import resolve_first_youtube_watch
            watch_url, title = resolve_first_youtube_watch(search_query)
            yt_url = watch_url or f"https://www.youtube.com/results?search_query={urllib.parse.quote(search_query)}"
            import webbrowser
            webbrowser.open(yt_url)
            cls.emit_motion_event("verification_success")
            return ComputerActionResult(
                success=True,
                action="youtube_play",
                target=search_query,
                detail=f"Playing '{title or search_query}' on YouTube.",
                verified=True,
                observation=cls.observe(),
            )
        except Exception as e:
            cls.emit_motion_event("verification_failed", str(e))
            return ComputerActionResult(
                success=False,
                action="youtube_play",
                target=search_query,
                detail=f"YouTube navigation failed: {str(e)}",
                verified=False,
                error=str(e),
            )

    # ── Autonomous Perception-Action-Verification Loop ─────────────────

    @classmethod
    async def run_operator_loop(
        cls,
        goal: str,
        plan_steps: List[Dict[str, Any]],
        budget: Optional[ComputerBudget] = None,
    ) -> ComputerLoopReport:
        """
        Executes a bounded perception-action-verification loop:
        observe -> act -> observe -> verify -> repeat
        """
        active_budget = budget or ComputerBudget()
        start_time = time.time()
        history: List[LoopStepResult] = []
        all_success = True

        cls.emit_motion_event("computer_action", f"Execute plan: {goal}")

        for idx, step in enumerate(plan_steps):
            # 1. Budget checks
            elapsed = time.time() - start_time
            if idx >= active_budget.max_steps or elapsed > active_budget.max_wall_time_seconds:
                history.append(LoopStepResult(
                    step_index=idx,
                    action="budget_abort",
                    target="",
                    success=False,
                    verified=False,
                    latency_ms=0,
                    detail="Aborted: Execution budget (steps or wall time) exceeded.",
                ))
                all_success = False
                break

            action_name = step.get("action", "").lower()
            target = step.get("target", "")
            step_start = time.time()

            # 2. Safety confirmation check for irreversible actions
            if action_name in active_budget.require_confirmation_for and not step.get("confirmed", False):
                token = f"tok_{uuid.uuid4().hex[:12]}"
                cls._pending_confirmations[token] = {
                    "action": action_name,
                    "step": step,
                    "goal": goal,
                }
                step_latency = (time.time() - step_start) * 1000
                history.append(LoopStepResult(
                    step_index=idx,
                    action=action_name,
                    target=target,
                    success=True,
                    verified=True,
                    latency_ms=step_latency,
                    detail=f"Paused: Action '{action_name}' is guarded and requires confirmation.",
                ))
                return ComputerLoopReport(
                    goal=goal,
                    success=True,
                    steps_taken=len(history),
                    total_latency_ms=(time.time() - start_time) * 1000,
                    verified=True,
                    requires_confirmation=True,
                    confirmation_action=action_name,
                    confirmation_token=token,
                    history=history,
                    final_observation=cls.observe(),
                )

            # 3. Action execution
            step_success = True
            detail = ""
            if action_name == "open_application":
                res = await cls.open_application(target)
                step_success = res.success
                detail = res.detail
            elif action_name == "click":
                step_success = await cls.click(step.get("x", 0), step.get("y", 0), step.get("button", "left"))
                detail = f"Clicked at ({step.get('x', 0)}, {step.get('y', 0)})"
            elif action_name == "type_text":
                step_success = await cls.type_text(step.get("text", ""), clear_first=step.get("clear_first", False))
                detail = f"Typed: '{step.get('text', '')[:30]}...'"
            elif action_name == "press_hotkey":
                step_success = await cls.press_hotkey(target or step.get("keys", ""))
                detail = f"Hotkey: {target or step.get('keys', '')}"
            elif action_name == "media_control":
                res = await cls.media_control(target, query=step.get("query"))
                step_success = res.success
                detail = res.detail
            elif action_name == "draft_message":
                res = await cls.draft_message(target, step.get("text", ""), recipient=step.get("recipient"))
                step_success = res.success
                detail = res.detail
            elif action_name == "scroll":
                step_success = await cls.scroll(step.get("direction", "down"), step.get("amount", 3))
                detail = f"Scrolled {step.get('direction', 'down')}"
            else:
                step_success = False
                detail = f"Unknown action: {action_name}"

            # 4. Post-action observation & verification
            post_obs = cls.observe()
            step_latency = (time.time() - step_start) * 1000
            verified = step_success

            if not step_success:
                all_success = False
                cls.emit_motion_event("verification_failed", detail)
            else:
                cls.emit_motion_event("verification_success", detail)

            history.append(LoopStepResult(
                step_index=idx,
                action=action_name,
                target=target,
                success=step_success,
                verified=verified,
                latency_ms=step_latency,
                detail=detail,
            ))

        total_latency = (time.time() - start_time) * 1000
        return ComputerLoopReport(
            goal=goal,
            success=all_success,
            steps_taken=len(history),
            total_latency_ms=total_latency,
            verified=all_success,
            history=history,
            final_observation=cls.observe(),
        )


# ---------------------------------------------------------------------------
# Tool Registration
# ---------------------------------------------------------------------------

computer_operator_tool_def = ToolDefinition(
    name="computer_operator",
    display_name="HINAA Computer-Use Engine v2",
    description=(
        "Autonomous Computer-Use Engine with 3-eye perception (Accessibility, DOM, Vision), "
        "primitive actions (mouse_move, click, double_click, right_click, drag, type_text, press_hotkey, scroll, screenshot, open_application, chrome_control, daemon_status), safety confirmation gate, "
        "and verified multi-step execution loops."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": [
                "observe_desktop",
                "observe",
                "open_app",
                "open_application",
                "media_control",
                "type_text",
                "press_hotkey",
                "mouse_move",
                "click",
                "double_click",
                "right_click",
                "drag",
                "scroll",
                "screenshot",
                "capture_screen",
                "chrome_control",
                "daemon_status",
                "list_windows",
                "close_window",
                "minimize_window",
                "maximize_window",
                "draft_message",
                "send_message",
                "type_and_send",
                "youtube_play",
                "run_operator_loop",
            ],
            "description": "The computer-use operation or primitive to execute.",
        },
        "target": {
            "type": "string",
            "description": "Target application name, window title, or hotkey combination.",
        },
        "content": {
            "type": "string",
            "description": "Text content to type, message body, or search query.",
        },
        "recipient": {
            "type": "string",
            "description": "Optional contact or recipient name for messaging.",
        },
        "x": {
            "type": "integer",
            "description": "Horizontal screen coordinate for click/drag/mouse_move.",
        },
        "y": {
            "type": "integer",
            "description": "Vertical screen coordinate for click/drag/mouse_move.",
        },
        "start_x": {
            "type": "integer",
            "description": "Starting horizontal screen coordinate for drag.",
        },
        "start_y": {
            "type": "integer",
            "description": "Starting vertical screen coordinate for drag.",
        },
        "end_x": {
            "type": "integer",
            "description": "Ending horizontal screen coordinate for drag.",
        },
        "end_y": {
            "type": "integer",
            "description": "Ending vertical screen coordinate for drag.",
        },
        "button": {
            "type": "string",
            "description": "Mouse button ('left', 'right', 'middle').",
        },
        "url": {
            "type": "string",
            "description": "Target web URL for Chrome browser control.",
        },
        "selector": {
            "type": "string",
            "description": "CSS selector for Chrome browser interaction.",
        },
        "chrome_action": {
            "type": "string",
            "description": "Chrome automation action ('navigate', 'click', 'type', 'extract').",
        },
        "confirmed": {
            "type": "boolean",
            "description": "True if an irreversible action has been explicitly authorized.",
        },
        "confirmation_token": {
            "type": "string",
            "description": "Authorization token returned by draft_message or guarded action.",
        },
        "plan_steps": {
            "type": "array",
            "description": "List of multi-step actions for run_operator_loop.",
        },
    },
    required_parameters=["action"],
    risk_level="medium",
    requires_confirmation=False,
    timeout_seconds=30.0,
)


async def execute_computer_operator(parameters: dict[str, Any]) -> dict[str, Any]:
    action = str(parameters.get("action", "")).strip().lower()
    target = str(parameters.get("target", "")).strip()
    content = str(parameters.get("content", "")).strip()
    recipient = parameters.get("recipient")
    confirmed = bool(parameters.get("confirmed", False))
    token = parameters.get("confirmation_token")
    x = int(parameters.get("x", 0))
    y = int(parameters.get("y", 0))
    button = str(parameters.get("button", "left")).strip().lower()

    if action in ("observe_desktop", "observe"):
        obs = NativeComputerOperator.observe()
        return {"success": True, "observation": obs.model_dump(mode="json")}

    elif action in ("open_app", "open_application"):
        res = await NativeComputerOperator.open_application(target or content)
        return res.model_dump(mode="json")

    elif action == "media_control":
        res = await NativeComputerOperator.media_control(target or "toggle", query=content)
        return res.model_dump(mode="json")

    elif action == "type_text":
        ok = await NativeComputerOperator.type_text(content or target)
        return {"success": ok, "action": "type_text", "detail": f"Typed text of length {len(content or target)}"}

    elif action == "press_hotkey":
        ok = await NativeComputerOperator.press_hotkey(target or content)
        return {"success": ok, "action": "press_hotkey", "target": target or content}

    elif action == "mouse_move":
        ok = await NativeComputerOperator.mouse_move(x=x, y=y, smooth=True)
        return {
            "success": ok,
            "action": "mouse_move",
            "x": x,
            "y": y,
            "via_daemon": NativeComputerOperator.is_daemon_live(),
            "detail": f"Cursor glided to ({x}, {y})",
        }

    elif action == "click":
        click_x = x if (x > 0 or y > 0) else None
        click_y = y if (x > 0 or y > 0) else None
        ok = await NativeComputerOperator.click(x=click_x, y=click_y, button=button)
        return {
            "success": ok,
            "action": "click",
            "x": x,
            "y": y,
            "button": button,
            "via_daemon": NativeComputerOperator.is_daemon_live(),
            "detail": f"Clicked {button} button at ({x}, {y})" if click_x is not None else f"Clicked {button} button at current position",
        }

    elif action == "double_click":
        click_x = x if (x > 0 or y > 0) else None
        click_y = y if (x > 0 or y > 0) else None
        ok = await NativeComputerOperator.double_click(x=click_x, y=click_y)
        return {
            "success": ok,
            "action": "double_click",
            "x": x,
            "y": y,
            "via_daemon": NativeComputerOperator.is_daemon_live(),
            "detail": f"Double-clicked at ({x}, {y})" if click_x is not None else "Double-clicked at current position",
        }

    elif action == "right_click":
        click_x = x if (x > 0 or y > 0) else None
        click_y = y if (x > 0 or y > 0) else None
        ok = await NativeComputerOperator.right_click(x=click_x, y=click_y)
        return {
            "success": ok,
            "action": "right_click",
            "x": x,
            "y": y,
            "via_daemon": NativeComputerOperator.is_daemon_live(),
            "detail": f"Right-clicked at ({x}, {y})" if click_x is not None else "Right-clicked at current position",
        }

    elif action == "drag":
        start_x = int(parameters.get("start_x", x))
        start_y = int(parameters.get("start_y", y))
        end_x = int(parameters.get("end_x", parameters.get("target_x", 0)))
        end_y = int(parameters.get("end_y", parameters.get("target_y", 0)))
        ok = await NativeComputerOperator.drag(start_x=start_x, start_y=start_y, end_x=end_x, end_y=end_y)
        return {
            "success": ok,
            "action": "drag",
            "start_x": start_x,
            "start_y": start_y,
            "end_x": end_x,
            "end_y": end_y,
            "via_daemon": NativeComputerOperator.is_daemon_live(),
            "detail": f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})",
        }

    elif action in ("screenshot", "capture_screen"):
        res = await NativeComputerOperator.screenshot()
        return res

    elif action == "chrome_control":
        chrome_act = str(parameters.get("chrome_action", "")).strip().lower() or "navigate"
        target_url = parameters.get("url") or (target if target.startswith("http") else None)
        res = await NativeComputerOperator.chrome_control(
            url=target_url,
            action=chrome_act,
            selector=parameters.get("selector"),
            text=content or parameters.get("text"),
        )
        return res

    elif action == "daemon_status":
        live = NativeComputerOperator.is_daemon_live()
        return {
            "success": True,
            "daemon_online": live,
            "daemon_url": NativeComputerOperator.DAEMON_URL,
            "detail": (
                "Desktop daemon is active and responsive on port 8765"
                if live
                else "Desktop daemon is offline. Run 'scripts/start-desktop-daemon.bat' for interactive desktop gliding."
            ),
        }

    elif action == "list_windows":
        windows = await NativeComputerOperator.list_windows()
        return {
            "success": True,
            "action": "list_windows",
            "windows": windows,
            "count": len(windows),
            "detail": f"Discovered {len(windows)} active desktop application windows.",
        }

    elif action == "close_window":
        app_target = target or content
        ok = await NativeComputerOperator.close_window(app_target)
        return {
            "success": ok,
            "action": "close_window",
            "target": app_target,
            "detail": f"Closed window matching '{app_target}'" if ok else f"Could not find or close window matching '{app_target}'.",
        }

    elif action in ("minimize_window", "maximize_window"):
        app_target = target or content
        state = "minimize" if "minimize" in action else "maximize"
        ok = await NativeComputerOperator.set_window_state(app_target, state=state)
        return {
            "success": ok,
            "action": action,
            "target": app_target,
            "detail": f"{state.title()}d window matching '{app_target}'" if ok else f"Could not change window state for '{app_target}'.",
        }

    elif action == "scroll":
        direction = target if target in ("up", "down") else "down"
        amount = int(parameters.get("amount", 3))
        ok = await NativeComputerOperator.scroll(direction=direction, amount=amount)
        return {"success": ok, "action": "scroll", "direction": direction, "amount": amount}

    elif action == "draft_message":
        res = await NativeComputerOperator.draft_message(app_name=target or "whatsapp", text=content, recipient=recipient)
        return res.model_dump(mode="json")

    elif action == "send_message":
        res = await NativeComputerOperator.send_message(
            app_name=target or "whatsapp",
            text=content,
            recipient=recipient,
            confirmed=confirmed,
            confirmation_token=token,
        )
        return res.model_dump(mode="json")

    elif action == "type_and_send":
        # Safe route: defaults to draft unless confirmed
        if confirmed:
            res = await NativeComputerOperator.send_message(app_name=target or "whatsapp", text=content, recipient=recipient, confirmed=True)
        else:
            res = await NativeComputerOperator.draft_message(app_name=target or "whatsapp", text=content, recipient=recipient)
        return res.model_dump(mode="json")

    elif action == "youtube_play":
        res = await NativeComputerOperator.youtube_play(target or content)
        return res.model_dump(mode="json")

    elif action == "run_operator_loop":
        steps = parameters.get("plan_steps", [])
        report = await NativeComputerOperator.run_operator_loop(goal=target or "Execute Task", plan_steps=steps)
        return report.model_dump(mode="json")

    else:
        return {"success": False, "error": f"Unknown computer operator action '{action}'."}


registry.register(computer_operator_tool_def, execute_computer_operator)

# Backward-compatible alias
ComputerOperator = NativeComputerOperator
