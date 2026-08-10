import asyncio
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from playwright.async_api import async_playwright, Browser, Page

from hinaa_api.tools.registry import registry, ToolDefinition

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
            _browser = await _playwright.chromium.launch(headless=False)
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
        return f"Successfully navigated to {url}. Page title: '{title}'"
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
    requires_confirmation=True
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
    requires_confirmation=False
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
    requires_confirmation=True
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
    requires_confirmation=True
)


registry.register(browser_navigate_def, browser_navigate)
registry.register(browser_extract_def, browser_extract)
registry.register(browser_click_def, browser_click)
registry.register(browser_type_def, browser_type)
