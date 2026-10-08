"""
HINAA Autonomous Desktop Control Daemon (Universal OS & Mouse Bridge).
Runs in the user's interactive Windows desktop session to provide:
1. Physical mouse movement with smooth Bezier gliding
2. Left, right, middle, and double clicking
3. Drag-and-drop
4. Keystroke typing and hotkey dispatch
5. Real-time desktop screenshot capture
6. Window focus and application launching
7. Chrome / Browser driving bridge

Default port: 8765 (http://127.0.0.1:8765)
"""

from __future__ import annotations

import asyncio
import base64
import ctypes
from ctypes import wintypes
import io
import json
import logging
import math
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any, Dict, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("HinaaDesktopDaemon")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "api"))
from hinaa_api.integrations.desktop_bridge_auth import bridge_token, authorized
BRIDGE_TOKEN = bridge_token(create=True)
PORT = int(os.environ.get("HINAA_DAEMON_PORT", 8765))
HOST = "127.0.0.1"

# Windows API Setup
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

# Mouse event constants
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

# Screenshot output folder
SCREENSHOT_DIR = Path(__file__).resolve().parents[1] / "apps" / "api" / "data" / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class WindowsDesktopActuator:
    """Native Windows actuator running inside interactive desktop session."""

    @staticmethod
    def get_screen_resolution() -> tuple[int, int]:
        w = user32.GetSystemMetrics(0) or 1920
        h = user32.GetSystemMetrics(1) or 1080
        return w, h

    @staticmethod
    def get_cursor_position() -> tuple[int, int]:
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y

    @classmethod
    def mouse_move(cls, target_x: int, target_y: int, smooth: bool = True, steps: int = 15) -> bool:
        """Moves cursor to (target_x, target_y). If smooth=True, glides naturally."""
        try:
            start_x, start_y = cls.get_cursor_position()
            if not smooth or (start_x == target_x and start_y == target_y):
                user32.SetCursorPos(target_x, target_y)
                return True

            for step in range(1, steps + 1):
                t = step / steps
                # Ease-out cubic curve: 1 - (1 - t)^3
                ease = 1.0 - math.pow(1.0 - t, 3)
                cur_x = int(start_x + (target_x - start_x) * ease)
                cur_y = int(start_y + (target_y - start_y) * ease)
                user32.SetCursorPos(cur_x, cur_y)
                time.sleep(0.012)  # ~80 FPS smooth cursor glide

            user32.SetCursorPos(target_x, target_y)
            return True
        except Exception as e:
            logger.error(f"mouse_move failed: {e}")
            return False

    @classmethod
    def click(cls, x: Optional[int] = None, y: Optional[int] = None, button: str = "left", clicks: int = 1) -> bool:
        """Clicks at (x, y) or current position."""
        try:
            if x is not None and y is not None and (x > 0 or y > 0):
                cls.mouse_move(x, y, smooth=True)

            btn = button.lower()
            for i in range(clicks):
                if btn == "right":
                    user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
                    time.sleep(0.03)
                    user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
                elif btn == "middle":
                    user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
                    time.sleep(0.03)
                    user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
                else:  # left
                    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
                    time.sleep(0.03)
                    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

                if clicks > 1 and i < clicks - 1:
                    time.sleep(0.08)  # Double-click spacing

            return True
        except Exception as e:
            logger.error(f"click failed: {e}")
            return False

    @classmethod
    def drag(cls, start_x: int, start_y: int, end_x: int, end_y: int, steps: int = 20) -> bool:
        """Drags mouse from (start_x, start_y) to (end_x, end_y)."""
        try:
            cls.mouse_move(start_x, start_y, smooth=True)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
            time.sleep(0.05)

            for step in range(1, steps + 1):
                t = step / steps
                cur_x = int(start_x + (end_x - start_x) * t)
                cur_y = int(start_y + (end_y - start_y) * t)
                user32.SetCursorPos(cur_x, cur_y)
                time.sleep(0.015)

            user32.SetCursorPos(end_x, end_y)
            time.sleep(0.05)
            user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
            return True
        except Exception as e:
            logger.error(f"drag failed: {e}")
            return False

    @classmethod
    def scroll(cls, direction: str = "down", amount: int = 3) -> bool:
        """Scrolls the mouse wheel."""
        try:
            delta = -120 * amount if direction.lower() == "down" else 120 * amount
            user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, delta, 0)
            return True
        except Exception as e:
            logger.error(f"scroll failed: {e}")
            return False

    @classmethod
    def type_text(cls, text: str, clear_first: bool = False) -> bool:
        """Types string into currently focused application."""
        try:
            safe_text = (
                text.replace("'", "''")
                .replace("{", "{{")
                .replace("}", "}}")
                .replace("+", "{+}")
                .replace("^", "{^}")
                .replace("%", "{%}")
            )
            clear_cmd = "$ws.SendKeys('^a{BACKSPACE}');" if clear_first else ""
            ps = f"""
            $ws = New-Object -ComObject WScript.Shell
            {clear_cmd}
            $ws.SendKeys('{safe_text}')
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=4.0)
            return True
        except Exception as e:
            logger.error(f"type_text failed: {e}")
            return False

    @classmethod
    def press_hotkey(cls, keys: str) -> bool:
        """Sends hotkey combinations (enter, ctrl+c, alt+tab, etc.)."""
        key_map = {
            "enter": "{ENTER}",
            "return": "{ENTER}",
            "esc": "{ESC}",
            "escape": "{ESC}",
            "tab": "{TAB}",
            "space": " ",
            "backspace": "{BACKSPACE}",
            "up": "{UP}",
            "down": "{DOWN}",
            "left": "{LEFT}",
            "right": "{RIGHT}",
            "ctrl+a": "^a",
            "ctrl+c": "^c",
            "ctrl+v": "^v",
            "ctrl+f": "^f",
            "ctrl+s": "^s",
            "ctrl+z": "^z",
            "ctrl+y": "^y",
            "alt+tab": "%{TAB}",
            "alt+f4": "%{F4}",
            "win+d": "^{ESC}d",
        }
        mapped = key_map.get(keys.lower().strip(), keys)
        try:
            ps = f"""
            $ws = New-Object -ComObject WScript.Shell
            $ws.SendKeys('{mapped}')
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=3.0)
            return True
        except Exception as e:
            logger.error(f"press_hotkey failed: {e}")
            return False

    @classmethod
    def focus_window(cls, target: str) -> bool:
        """Brings the window with matching title to the foreground."""
        try:
            ps = f"""
            $ws = New-Object -ComObject WScript.Shell
            $ws.AppActivate('{target}')
            """
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=3.0)
            return "True" in res.stdout
        except Exception as e:
            logger.error(f"focus_window failed: {e}")
            return False

    @classmethod
    def list_windows(cls) -> list[dict[str, Any]]:
        """Lists active top-level windows with title, pid, and process name."""
        windows = []
        try:
            import ctypes.wintypes
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
        except Exception as e:
            logger.debug(f"EnumWindows failed: {e}")

        try:
            ps = "Get-Process | Where-Object MainWindowTitle | Select-Object Id, ProcessName, MainWindowTitle | ConvertTo-Json -Compress"
            res = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=3.0)
            raw = res.stdout.strip()
            if raw:
                data = json.loads(raw)
                if isinstance(data, dict):
                    data = [data]
                for item in data:
                    windows.append({
                        "pid": item.get("Id"),
                        "process": item.get("ProcessName", ""),
                        "title": item.get("MainWindowTitle", ""),
                    })
        except Exception as e:
            logger.error(f"list_windows failed: {e}")
        return windows

    @classmethod
    def close_window(cls, target: str) -> bool:
        """Closes a window matching title or process name."""
        try:
            ps = f"""
            $p = Get-Process | Where-Object {{ $_.MainWindowTitle -like '*{target}*' -or $_.ProcessName -like '*{target}*' }} | Select-Object -First 1
            if ($p) {{ $p.CloseMainWindow() }}
            """
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=3.0)
            return True
        except Exception as e:
            logger.error(f"close_window failed: {e}")
            return False

    @classmethod
    def set_window_state(cls, target: str, state: str = "maximize") -> bool:
        """Minimizes or maximizes a window."""
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
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=3.0)
            return True
        except Exception as e:
            logger.error(f"set_window_state failed: {e}")
            return False

    @classmethod
    def capture_screenshot(cls) -> Dict[str, Any]:
        """Captures full desktop screen, saves PNG, and returns file path & dimensions."""
        filename = f"screen_{int(time.time() * 1000)}.png"
        filepath = SCREENSHOT_DIR / filename
        w, h = cls.get_screen_resolution()

        try:
            from PIL import ImageGrab
            img = ImageGrab.grab()
            img.save(str(filepath), "PNG")
            
            # Generate small base64 thumbnail for quick client preview
            thumb = img.copy()
            thumb.thumbnail((320, 180))
            buf = io.BytesIO()
            thumb.save(buf, format="JPEG", quality=70)
            b64_thumb = base64.b64encode(buf.getvalue()).decode("utf-8")

            return {
                "success": True,
                "filepath": str(filepath),
                "filename": filename,
                "width": img.width,
                "height": img.height,
                "thumbnail_b64": f"data:image/jpeg;base64,{b64_thumb}",
            }
        except Exception as e:
            logger.warning(f"PIL ImageGrab failed, trying PowerShell CopyFromScreen: {e}")
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
                subprocess.run(["powershell", "-NoProfile", "-Command", ps], timeout=4.0)
                if filepath.exists():
                    return {
                        "success": True,
                        "filepath": str(filepath),
                        "filename": filename,
                        "width": w,
                        "height": h,
                    }
            except Exception as ps_err:
                logger.error(f"PowerShell screenshot also failed: {ps_err}")

        return {"success": False, "error": "Screen capture could not access display DC."}


class DaemonRequestHandler(BaseHTTPRequestHandler):
    """HTTP API handling incoming desktop automation requests."""

    def _send_json(self, data: Dict[str, Any], status: int = 200) -> None:
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_OPTIONS(self) -> None:
        # The private API calls this bridge server-to-server. Websites cannot pair it.
        self._send_json({"error": "Browser requests are not supported by the desktop bridge."}, status=403)

    def _authorized(self) -> bool:
        return not self.headers.get("Origin") and authorized(self.headers.get("Authorization"), BRIDGE_TOKEN)

    def do_GET(self) -> None:
        if not self._authorized():
            self._send_json({"error": "Desktop pairing required"}, status=401)
            return
        if self.path == "/health" or self.path == "/api/status":
            w, h = WindowsDesktopActuator.get_screen_resolution()
            mx, my = WindowsDesktopActuator.get_cursor_position()
            self._send_json({
                "status": "ready",
                "daemon": "HINAA Autonomous Desktop Operator Bridge v2",
                "os": sys.platform,
                "resolution": f"{w}x{h}",
                "cursor": {"x": mx, "y": my},
                "port": PORT,
            })
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def do_POST(self) -> None:
        if not self._authorized():
            # Consume bounded requests before closing so Windows does not reset
            # the socket and hide the authorization error from the API client.
            try:
                length = int(self.headers.get("Content-Length", 0))
                if 0 < length <= 65536:
                    self.connection.settimeout(2)
                    self.rfile.read(length)
            except (ValueError, OSError):
                pass
            self._send_json({"error": "Desktop pairing required"}, status=401)
            return
        if self.path in ("/api/action", "/action", "/api/execute"):
            try:
                length = int(self.headers.get("Content-Length", 0))
                if length <= 0 or length > 65536:
                    self._send_json({"error": "Action payload must be between 1 and 65536 bytes"}, status=413)
                    return
                body = json.loads(self.rfile.read(length).decode("utf-8")) if length > 0 else {}
                action = str(body.get("action", "")).lower().strip()
                result: Dict[str, Any] = {"success": True, "action": action}

                if action == "mouse_move":
                    x = int(body.get("x", 0))
                    y = int(body.get("y", 0))
                    smooth = bool(body.get("smooth", True))
                    ok = WindowsDesktopActuator.mouse_move(x, y, smooth=smooth)
                    result = {"success": ok, "action": "mouse_move", "x": x, "y": y}

                elif action == "click":
                    x = body.get("x")
                    y = body.get("y")
                    button = str(body.get("button", "left"))
                    clicks = int(body.get("clicks", 1))
                    ok = WindowsDesktopActuator.click(
                        x=int(x) if x is not None else None,
                        y=int(y) if y is not None else None,
                        button=button,
                        clicks=clicks,
                    )
                    result = {"success": ok, "action": "click", "button": button, "clicks": clicks}

                elif action == "double_click":
                    x = body.get("x")
                    y = body.get("y")
                    ok = WindowsDesktopActuator.click(
                        x=int(x) if x is not None else None,
                        y=int(y) if y is not None else None,
                        button="left",
                        clicks=2,
                    )
                    result = {"success": ok, "action": "double_click"}

                elif action == "right_click":
                    x = body.get("x")
                    y = body.get("y")
                    ok = WindowsDesktopActuator.click(
                        x=int(x) if x is not None else None,
                        y=int(y) if y is not None else None,
                        button="right",
                        clicks=1,
                    )
                    result = {"success": ok, "action": "right_click"}

                elif action == "drag":
                    sx = int(body.get("start_x", 0))
                    sy = int(body.get("start_y", 0))
                    ex = int(body.get("end_x", 0))
                    ey = int(body.get("end_y", 0))
                    ok = WindowsDesktopActuator.drag(sx, sy, ex, ey)
                    result = {"success": ok, "action": "drag", "from": [sx, sy], "to": [ex, ey]}

                elif action == "scroll":
                    direction = str(body.get("direction", "down"))
                    amount = int(body.get("amount", 3))
                    ok = WindowsDesktopActuator.scroll(direction=direction, amount=amount)
                    result = {"success": ok, "action": "scroll", "direction": direction}

                elif action == "type_text":
                    text = str(body.get("text", body.get("content", "")))
                    clear_first = bool(body.get("clear_first", False))
                    ok = WindowsDesktopActuator.type_text(text, clear_first=clear_first)
                    result = {"success": ok, "action": "type_text", "length": len(text)}

                elif action == "press_hotkey":
                    keys = str(body.get("keys", body.get("target", "enter")))
                    ok = WindowsDesktopActuator.press_hotkey(keys)
                    result = {"success": ok, "action": "press_hotkey", "keys": keys}

                elif action == "focus_window":
                    target = str(body.get("target", ""))
                    ok = WindowsDesktopActuator.focus_window(target)
                    result = {"success": ok, "action": "focus_window", "target": target}

                elif action == "list_windows":
                    wins = WindowsDesktopActuator.list_windows()
                    result = {"success": True, "action": "list_windows", "windows": wins, "count": len(wins)}

                elif action == "close_window":
                    target = str(body.get("target", ""))
                    ok = WindowsDesktopActuator.close_window(target)
                    result = {"success": ok, "action": "close_window", "target": target}

                elif action in ("minimize_window", "maximize_window", "set_window_state"):
                    target = str(body.get("target", ""))
                    state = str(body.get("state", "maximize")) if action == "set_window_state" else ("minimize" if "minimize" in action else "maximize")
                    ok = WindowsDesktopActuator.set_window_state(target, state=state)
                    result = {"success": ok, "action": action, "target": target}

                elif action in ("screenshot", "capture_screen"):
                    result = WindowsDesktopActuator.capture_screenshot()

                else:
                    result = {"success": False, "error": f"Unknown daemon action '{action}'."}

                self._send_json(result)
            except Exception as e:
                logger.error(f"Error handling POST action: {e}", exc_info=True)
                self._send_json({"success": False, "error": str(e)}, status=500)
        else:
            self._send_json({"error": "Not Found"}, status=404)

    def log_message(self, format, *args):
        # Quiet standard HTTP access logging to prevent console spam
        pass


def run_daemon():
    server = HTTPServer((HOST, PORT), DaemonRequestHandler)
    w, h = WindowsDesktopActuator.get_screen_resolution()
    mx, my = WindowsDesktopActuator.get_cursor_position()
    logger.info(f"===========================================================")
    logger.info(f"  HINAA Autonomous Desktop Control Daemon v2 Active")
    logger.info(f"  Listening on: http://{HOST}:{PORT}")
    logger.info(f"  Display Resolution: {w}x{h} | Cursor Pos: ({mx}, {my})")
    logger.info(f"  Controls: Mouse Glide, Clicks, Drag, Type, Hotkeys, Screen")
    logger.info(f"===========================================================")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Daemon shutting down.")
        server.server_close()


if __name__ == "__main__":
    run_daemon()
