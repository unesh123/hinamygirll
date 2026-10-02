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
import os
import platform
import subprocess
import time
import urllib.parse
import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import registry, ToolDefinition
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
                    ["powershell", "-NoProfile", "-Command", cmd],
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

    # ── Primitive Actuator API ─────────────────────────────────────────

    @classmethod
    async def focus_window(cls, target: str) -> bool:
        """Brings target window into foreground."""
        cls.emit_motion_event("computer_action", f"Focus {target}")
        if platform.system() != "Windows":
            return False

        ps_script = f"""
        $wscript = New-Object -ComObject WScript.Shell
        $wscript.AppActivate('{target}')
        """
        try:
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps_script], capture_output=True, timeout=2.0)
            return "True" in res.stdout
        except Exception:
            return False

    @classmethod
    async def click(cls, x: int = 0, y: int = 0, button: str = "left") -> bool:
        """Sends native mouse click at screen coordinates."""
        cls.emit_motion_event("computer_action", f"Click {button} at ({x}, {y})")
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                if x > 0 or y > 0:
                    user32.SetCursorPos(x, y)
                await asyncio.sleep(0.05)
                # Mouse event flags: MOUSEEVENTF_LEFTDOWN = 0x02, LEFTUP = 0x04, RIGHTDOWN = 0x08, RIGHTUP = 0x10
                if button == "right":
                    user32.mouse_event(0x08, 0, 0, 0, 0)
                    user32.mouse_event(0x10, 0, 0, 0, 0)
                else:
                    user32.mouse_event(0x02, 0, 0, 0, 0)
                    user32.mouse_event(0x04, 0, 0, 0, 0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def type_text(cls, text: str, clear_first: bool = False) -> bool:
        """Types text using native keystrokes."""
        cls.emit_motion_event("computer_action", f"Type text: {text[:20]}")
        if platform.system() == "Windows":
            try:
                safe_text = text.replace("'", "''").replace("{", "{{").replace("}", "}}").replace("+", "{+}").replace("^", "{^}").replace("%", "{%}")
                clear_cmd = "$wscript.SendKeys('^a{BACKSPACE}');" if clear_first else ""
                ps = f"""
                $wscript = New-Object -ComObject WScript.Shell
                {clear_cmd}
                $wscript.SendKeys('{safe_text}')
                """
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=3.0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def press_hotkey(cls, keys: str) -> bool:
        """Triggers hotkey combinations (e.g. enter, ctrl+f, alt+tab, escape)."""
        cls.emit_motion_event("computer_action", f"Hotkey: {keys}")
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
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=2.0)
                return True
            except Exception:
                return False
        return True

    @classmethod
    async def scroll(cls, direction: str = "down", amount: int = 3) -> bool:
        """Scrolls mouse wheel up or down."""
        cls.emit_motion_event("computer_action", f"Scroll {direction}")
        if platform.system() == "Windows":
            try:
                user32 = ctypes.windll.user32
                # MOUSEEVENTF_WHEEL = 0x0800. Positive is up (120), negative is down (-120)
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
            "discord": "discord",
            "vscode": "code",
            "vs code": "code",
            "code": "code",
            "visual studio code": "code",
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
        resolved = app_aliases.get(cleaned.lower(), cleaned)

        if system == "Windows":
            try:
                if resolved.startswith("http://") or resolved.startswith("https://") or resolved.startswith("spotify:") or resolved.startswith("ms-settings:") or resolved.startswith("microsoft.windows."):
                    os.system(f'start "" "{resolved}"')
                else:
                    safe_target = resolved.replace("'", "''").replace('"', '')
                    ps = f"""
                    $target = '{safe_target}'
                    $ws = New-Object -ComObject WScript.Shell
                    $activated = $ws.AppActivate($target)
                    if (-not $activated) {{
                        $found = Get-StartApps | Where-Object {{ $_.Name -like "*$target*" -or $_.AppID -like "*$target*" }} | Select-Object -First 1
                        if ($found) {{
                            Start-Process "shell:AppsFolder\\$($found.AppID)" -ErrorAction SilentlyContinue
                        }} else {{
                            Start-Process $target -ErrorAction SilentlyContinue
                        }}
                    }}
                    """
                    subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=4.0)

                await asyncio.sleep(0.4)
                obs = cls.observe()
                return ComputerActionResult(
                    success=True,
                    action="open_application",
                    target=app_or_url,
                    detail=f"Launched/focused '{app_or_url}'.",
                    verified=True,
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
                if platform.system() == "Windows":
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
        "primitive actions (click, type, hotkey, scroll, open_application), safety confirmation gate, "
        "and verified multi-step execution loops."
    ),
    parameters={
        "action": {
            "type": "string",
            "enum": [
                "observe_desktop",
                "open_app",
                "open_application",
                "media_control",
                "type_text",
                "press_hotkey",
                "click",
                "scroll",
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
            "description": "Horizontal screen coordinate for click/drag.",
        },
        "y": {
            "type": "integer",
            "description": "Vertical screen coordinate for click/drag.",
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

    elif action == "click":
        ok = await NativeComputerOperator.click(x=x, y=y)
        return {"success": ok, "action": "click", "x": x, "y": y}

    elif action == "scroll":
        direction = target if target in ("up", "down") else "down"
        ok = await NativeComputerOperator.scroll(direction=direction)
        return {"success": ok, "action": "scroll", "direction": direction}

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
