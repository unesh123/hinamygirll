import asyncio
import logging
import os
import shutil
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Browser, Page

from hinaa_api.tools.registry import registry, ToolDefinition
from hinaa_api.errors import HinaaError

logger = logging.getLogger(__name__)

# Global browser state
_playwright = None
_browser: Optional[Browser] = None
_page: Optional[Page] = None

async def _get_page() -> Page:
    global _playwright, _browser, _page
    if _page is None or _page.is_closed():
        if _playwright is None:
            _playwright = await async_playwright().start()
        if _browser is None or not _browser.is_connected():
            executable = os.environ.get("HINAA_BROWSER_EXECUTABLE") or shutil.which("chromium") or shutil.which("chromium-browser") or shutil.which("google-chrome")
            launch_options: dict[str, Any] = {"headless": False}
            if executable:
                launch_options["executable_path"] = executable
            _browser = await _playwright.chromium.launch(**launch_options)
        context = await _browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        _page = await context.new_page()
    return _page

# -----------------
# 1. Navigate
# -----------------
class BrowserNavigateParams(BaseModel):
    url: str = Field(..., description="URL to navigate to.")

async def browser_navigate(params: BrowserNavigateParams) -> str:
    try:
        url = params.url
        if not url.startswith("http"):
            url = "https://" + url
        page = await _get_page()
        await page.goto(url, wait_until="networkidle")
        title = await page.title()
        owned_page_count = len(page.context.pages)
        return f"Successfully navigated to {url}. Page title: '{title}'. Owned browser pages: {owned_page_count}."
    except Exception as e:
        return f"Failed to navigate: {str(e)}"

browser_navigate_def = ToolDefinition(
    name="browser_navigate",
    display_name="Browser: Navigate",
    description="Navigate the automated browser to a specific URL.",
    parameters={
        "url": {"type": "string", "description": "URL to navigate to."}
    },
    required_parameters=["url"],
    voice_aliases=["go to", "open the website", "navigate to"],
    requires_confirmation=False,
    risk_level="low"
)

# -----------------
# 2. Extract
# -----------------
class BrowserExtractParams(BaseModel):
    pass

async def browser_extract(params: BrowserExtractParams) -> str:
    try:
        page = await _get_page()
        title = await page.title()
        url = page.url
        
        # Extract main text
        text_content = await page.evaluate('''() => {
            return document.body.innerText.substring(0, 3000);
        }''')
        
        # Extract interactable elements
        elements = await page.evaluate('''() => {
            const els = Array.from(document.querySelectorAll('a, button, input'));
            return els.slice(0, 30).map(e => ({
                tag: e.tagName,
                text: e.innerText || e.value || e.placeholder || '',
                id: e.id || ''
            })).filter(e => e.text.trim().length > 0);
        }''')
        
        summary = f"Current URL: {url}\nTitle: {title}\n\nVisible Text:\n{text_content}\n\nInteractable Elements:\n"
        for i, el in enumerate(elements):
            summary += f"[{i}] {el['tag']}: {el['text']} (ID: {el['id']})\n"
            
        return summary
    except Exception as e:
        return f"Failed to extract page content: {str(e)}"

browser_extract_def = ToolDefinition(
    name="browser_extract",
    display_name="Browser: Read Page",
    description="Reads the current page in the automated browser, returning visible text and interactable elements.",
    parameters={},
    required_parameters=[],
    voice_aliases=["read the page", "what's on the screen", "scan the page"],
    requires_confirmation=False,
    risk_level="low"
)

# -----------------
# 3. Click
# -----------------
class BrowserClickParams(BaseModel):
    selector: str = Field(..., description="The text, role, or CSS selector of the element to click. If it's visible text, you can use 'text=Your Text'.")

async def browser_click(params: BrowserClickParams) -> str:
    try:
        page = await _get_page()
        # Try finding by text first if no special characters
        if "=" not in params.selector and not params.selector.startswith(".") and not params.selector.startswith("#"):
            locator = page.get_by_text(params.selector, exact=False).first
            if await locator.count() == 0:
                 locator = page.locator(f"text={params.selector}").first
        else:
            locator = page.locator(params.selector).first
            
        await locator.click(timeout=5000)
        await page.wait_for_load_state("networkidle", timeout=3000)
        return f"Successfully clicked element matching '{params.selector}'."
    except Exception as e:
        return f"Failed to click element '{params.selector}': {str(e)}"

browser_click_def = ToolDefinition(
    name="browser_click",
    display_name="Browser: Click Element",
    description="Click an element on the current page using text or a CSS selector.",
    parameters={
        "selector": {"type": "string", "description": "Text or CSS selector of the element."}
    },
    required_parameters=["selector"],
    voice_aliases=["click on", "press the button", "click"],
    requires_confirmation=True,
    risk_level="medium"
)

# -----------------
# 4. Type
# -----------------
class BrowserTypeParams(BaseModel):
    selector: str = Field(..., description="The selector or text identifying the input field.")
    text: str = Field(..., description="The text to type into the field.")
    submit: bool = Field(False, description="Whether to press Enter after typing.")

async def browser_type(params: BrowserTypeParams) -> str:
    try:
        page = await _get_page()
        if "=" not in params.selector and not params.selector.startswith(".") and not params.selector.startswith("#"):
            locator = page.get_by_role("textbox", name=params.selector).first
            if await locator.count() == 0:
                 locator = page.locator(f"text={params.selector}").first
        else:
            locator = page.locator(params.selector).first
            
        await locator.fill(params.text)
        if params.submit:
            await locator.press("Enter")
            await page.wait_for_load_state("networkidle", timeout=3000)
            
        return f"Successfully typed '{params.text}' into '{params.selector}'."
    except Exception as e:
        return f"Failed to type: {str(e)}"

browser_type_def = ToolDefinition(
    name="browser_type",
    display_name="Browser: Type Text",
    description="Type text into an input field on the current page.",
    parameters={
        "selector": {"type": "string", "description": "Text or CSS selector of the input field."},
        "text": {"type": "string", "description": "Text to type."},
        "submit": {"type": "boolean", "description": "Press Enter after typing."}
    },
    required_parameters=["selector", "text"],
    voice_aliases=["type", "enter", "search for"],
    requires_confirmation=True,
    risk_level="medium"
)


registry.register(browser_navigate_def, browser_navigate)
registry.register(browser_extract_def, browser_extract)
registry.register(browser_click_def, browser_click)
registry.register(browser_type_def, browser_type)

# =====================================================
# NEW: System Control Tools
# =====================================================

import json
import os
import subprocess
import sys
import threading
import datetime
from pathlib import Path

from hinaa_api.config import DATA_DIR


class FileReadParams(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to read.")


FILE_TOOL_ROOT = Path(__file__).resolve().parents[2] / "data"


def resolve_tool_file(file_path: str) -> Path:
    root = FILE_TOOL_ROOT.resolve()
    candidate = Path(file_path)
    resolved = (candidate if candidate.is_absolute() else root / candidate).resolve()
    if not resolved.is_relative_to(root) or resolved == root:
        raise HinaaError("FILE_ACCESS_DENIED", "Choose a file inside HINAA's data folder.", 403)
    return resolved


async def file_read(params: FileReadParams) -> str:
    try:
        file_path = params.file_path
        resolved = resolve_tool_file(file_path)
        if not resolved.is_file():
            return f"File not found: '{file_path}'"
        if resolved.stat().st_size > 1_048_576:
            raise HinaaError("FILE_TOO_LARGE", "Text file reads are limited to 1 MiB.", 413)
        content = resolved.read_text(encoding="utf-8", errors="replace")
        return f"=== File: {file_path} ===\n{content}"
    except HinaaError:
        raise
    except OSError as error:
        raise HinaaError("FILE_READ_FAILED", "The file could not be read.", 422) from error


file_read_def = ToolDefinition(
    name="file_read",
    display_name="System: Read File",
    description="Read the contents of a text file on the computer.",
    parameters={
        "file_path": {"type": "string", "description": "Absolute path to the file to read."}
    },
    required_parameters=["file_path"],
    voice_aliases=["read file", "open file", "show me"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(file_read_def, file_read)


class FileWriteParams(BaseModel):
    file_path: str = Field(..., description="Absolute path to the file to write.")
    content: str = Field(..., description="Content to write to the file.")


async def file_write(params: FileWriteParams) -> str:
    try:
        file_path = params.file_path
        resolved = resolve_tool_file(file_path)
        if len(params.content.encode("utf-8")) > 1_048_576:
            raise HinaaError("FILE_TOO_LARGE", "Text file writes are limited to 1 MiB.", 413)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        with resolved.open("x", encoding="utf-8") as target:
            target.write(params.content)
        return f"Successfully wrote to '{file_path}' ({len(params.content)} chars)."
    except FileExistsError as error:
        raise HinaaError("FILE_EXISTS", "That file already exists. Choose a new filename to preserve the original.", 409) from error
    except HinaaError:
        raise
    except OSError as error:
        raise HinaaError("FILE_WRITE_FAILED", "The file could not be created.", 422) from error


file_write_def = ToolDefinition(
    name="file_write",
    display_name="System: Write File",
    description="Write content to a text file on the computer.",
    parameters={
        "file_path": {"type": "string", "description": "Absolute path to the file to write."},
        "content": {"type": "string", "description": "Content to write."}
    },
    required_parameters=["file_path", "content"],
    voice_aliases=["write file", "save this", "save to"],
    requires_confirmation=False,
    risk_level="medium"
)
registry.register(file_write_def, file_write)


class SystemInfoParams(BaseModel):
    pass


async def system_info(params: SystemInfoParams) -> str:
    try:
        import psutil
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")
        cpu_percent = psutil.cpu_percent(interval=0.1)
        return (
            f"System Information:\n"
            f"  CPU Usage: {cpu_percent}%\n"
            f"  Total Memory: {mem.total / (1024**3):.2f} GB\n"
            f"  Available Memory: {mem.available / (1024**3):.2f} GB\n"
            f"  Memory Usage: {mem.percent}%\n"
            f"  Total Disk: {disk.total / (1024**3):.2f} GB\n"
            f"  Free Disk: {disk.free / (1024**3):.2f} GB\n"
            f"  Disk Usage: {disk.percent}%\n"
            f"  Platform: {sys.platform}\n"
            f"  Python Version: {sys.version.split(' ')[0]}"
        )
    except ImportError:
        return "psutil not installed; cannot retrieve system info."
    except Exception as e:
        return f"Failed to get system info: {str(e)}"


system_info_def = ToolDefinition(
    name="system_info",
    display_name="System: Info",
    description="Get computer system statistics (CPU, memory, disk).",
    parameters={},
    required_parameters=[],
    voice_aliases=["system info", "computer status", "how am i doing"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(system_info_def, system_info)


class AppLaunchParams(BaseModel):
    app_name: str = Field(..., description="Name of the application to launch.")


async def app_launch(params: AppLaunchParams) -> str:
    try:
        app_name = params.app_name.strip().lower()
        if sys.platform.startswith("win"):
            allowed = {"notepad": "notepad.exe", "calculator": "calc.exe", "calc": "calc.exe", "paint": "mspaint.exe"}
            executable = allowed.get(app_name)
            if executable is None:
                raise HinaaError("APP_NOT_ALLOWED", "This local launcher supports Notepad, Calculator, and Paint.", 403)
            system_dir = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32"
            subprocess.Popen([str(system_dir / executable)], shell=False)
        else:
            raise HinaaError("APP_PLATFORM_UNSUPPORTED", "Application launch is currently available on Windows only.", 422)
        return f"Launching '{params.app_name}'..."
    except HinaaError:
        raise
    except OSError as error:
        raise HinaaError("APP_LAUNCH_FAILED", "The application could not be launched.", 422) from error


app_launch_def = ToolDefinition(
    name="app_launch",
    display_name="System: Launch App",
    description="Launch an application on the computer.",
    parameters={
        "app_name": {"type": "string", "description": "Name of the application to launch."}
    },
    required_parameters=["app_name"],
    voice_aliases=["open", "run", "launch"],
    requires_confirmation=False,
    risk_level="medium"
)
registry.register(app_launch_def, app_launch)


class ClipboardGetParams(BaseModel):
    pass


async def clipboard_get(params: ClipboardGetParams) -> str:
    try:
        import pyperclip
        content = pyperclip.paste()
        return f"Clipboard content:\n{content}" if content else "(clipboard is empty)"
    except ImportError:
        return "pyperclip not installed; cannot read clipboard."
    except Exception as e:
        return f"Failed to read clipboard: {str(e)}"


clipboard_get_def = ToolDefinition(
    name="clipboard_get",
    display_name="System: Clipboard Get",
    description="Read the current clipboard content.",
    parameters={},
    required_parameters=[],
    voice_aliases=["clipboard", "copy this", "what's copied"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(clipboard_get_def, clipboard_get)


class ClipboardSetParams(BaseModel):
    text: str = Field(..., description="Text to copy to the clipboard.")


async def clipboard_set(params: ClipboardSetParams) -> str:
    try:
        import pyperclip
        pyperclip.copy(params.text)
        return f"Copied '{params.text[:50]}{'...' if len(params.text) > 50 else ''}' to clipboard."
    except ImportError:
        return "pyperclip not installed; cannot write clipboard."
    except Exception as e:
        return f"Failed to write clipboard: {str(e)}"


clipboard_set_def = ToolDefinition(
    name="clipboard_set",
    display_name="System: Clipboard Set",
    description="Write text to the clipboard.",
    parameters={
        "text": {"type": "string", "description": "Text to copy to the clipboard."}
    },
    required_parameters=["text"],
    voice_aliases=["copy", "set clipboard", "copy this"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(clipboard_set_def, clipboard_set)


class ScreenshotParams(BaseModel):
    region: str = Field("full", description="Region to capture: 'full', 'screen', or 'rectangle:x:y:w:h'")


async def screenshot(params: ScreenshotParams) -> str:
    try:
        import mss
        with mss.mss() as sct:
            if params.region == "full":
                monitor = sct.monitors[1]
            elif params.region == "screen":
                monitor = sct.monitors[0]
            else:
                parts = params.region.split(":")
                x, y, w, h = int(parts[0]), int(parts[1]), int(parts[2]), int(parts[3])
                monitor = {"top": y, "left": x, "width": w, "height": h}
            sct_img = sct.grab(monitor)
            img_path = DATA_DIR / "screenshot.png"
            img_path.parent.mkdir(parents=True, exist_ok=True)
            mss.tools.to_png(sct.rgb, sct.size, output=str(img_path))
            return f"Screenshot saved to '{img_path}'. Region: {params.region}"
    except ImportError:
        return "mss not installed; cannot take screenshot."
    except Exception as e:
        return f"Failed to take screenshot: {str(e)}"


screenshot_def = ToolDefinition(
    name="screenshot",
    display_name="System: Screenshot",
    description="Capture a screenshot of the screen or a region.",
    parameters={
        "region": {"type": "string", "description": "Region to capture: 'full', 'screen', or 'rectangle:x:y:w:h'"}
    },
    required_parameters=["region"],
    voice_aliases=["screenshot", "screen capture", "capture screen"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(screenshot_def, screenshot)


# =====================================================
# Memory: User Preferences Persistence
# =====================================================

_user_preferences_file = DATA_DIR / "user_preferences.json"
_user_preferences: Dict[str, Any] = {}

# Ensure data directory exists
_user_preferences_file.parent.mkdir(parents=True, exist_ok=True)

# Load existing preferences on startup
if _user_preferences_file.exists():
    try:
        with open(_user_preferences_file, "r", encoding="utf-8") as f:
            _user_preferences = json.load(f)
    except Exception:
        _user_preferences = {}


def _save_preferences():
    """Save user preferences to disk."""
    try:
        with open(_user_preferences_file, "w", encoding="utf-8") as f:
            json.dump(_user_preferences, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"Failed to save user preferences: {e}")


class UserPreferenceUpdateParams(BaseModel):
    key: str = Field(..., description="Preference key (e.g., 'favorite_site_Youtube', 'default_search_engine').")
    value: Any = Field(..., description="Preference value to store.")


async def user_preference_update(params: UserPreferenceUpdateParams) -> str:
    """Update a user preference value. The agent can learn from interactions."""
    try:
        _user_preferences[params.key] = params.value
        _save_preferences()
        return f"Updated preference '{params.key}' = '{str(params.value)[:100]}'"
    except Exception as e:
        return f"Failed to update preference: {str(e)}"


user_preference_update_def = ToolDefinition(
    name="user_preference_update",
    display_name="Memory: Update Preference",
    description="Update a user preference that the agent will remember across sessions.",
    parameters={
        "key": {"type": "string", "description": "Preference key (e.g., 'favorite_site_Youtube', 'default_search_engine')."},
        "value": {"type": "any", "description": "Preference value to store."}
    },
    required_parameters=["key", "value"],
    voice_aliases=["remember this", "learn this", "save this"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(user_preference_update_def, user_preference_update)


class UserPreferenceGetParams(BaseModel):
    key: str = Field(..., description="Preference key to retrieve.")


async def user_preference_get(params: UserPreferenceGetParams) -> str:
    """Retrieve a user preference value."""
    try:
        value = _user_preferences.get(params.key, "not_set")
        return f"Preference '{params.key}': {value}"
    except Exception as e:
        return f"Failed to get preference: {str(e)}"


user_preference_get_def = ToolDefinition(
    name="user_preference_get",
    display_name="Memory: Get Preference",
    description="Retrieve a previously stored user preference.",
    parameters={
        "key": {"type": "string", "description": "Preference key to retrieve."}
    },
    required_parameters=["key"],
    voice_aliases=["what do you remember", "do you know", "recall"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(user_preference_get_def, user_preference_get)


class UserPreferencesListParams(BaseModel):
    pass


async def user_preferences_list(params: UserPreferencesListParams) -> str:
    """List all stored user preferences (keys only)."""
    try:
        keys = list(_user_preferences.keys())
        if not keys:
            return "No user preferences stored yet."
        lines = [f"  - {key}: {str(_user_preferences[key])[:80]}" for key in keys]
        return "Stored user preferences:\n" + "\n".join(lines)
    except Exception as e:
        return f"Failed to list preferences: {str(e)}"


user_preferences_list_def = ToolDefinition(
    name="user_preferences_list",
    display_name="Memory: List Preferences",
    description="List all stored user preference keys.",
    parameters={},
    required_parameters=[],
    voice_aliases=["show memories", "what have you learned", "my preferences"],
    requires_confirmation=False,
    risk_level="low"
)
registry.register(user_preferences_list_def, user_preferences_list)

# These operations inspect private local/browser data or change external state.
# The HTTP dispatcher and canonical runtime both consume these same definitions.
for _gated_definition in (
    browser_navigate_def, browser_extract_def, file_read_def, file_write_def,
    app_launch_def, clipboard_get_def, clipboard_set_def, screenshot_def,
    user_preference_update_def,
):
    _gated_definition.requires_confirmation = True


# Keep existing registry registrations at the bottom
# (they're already registered above, but ensuring they're included)
