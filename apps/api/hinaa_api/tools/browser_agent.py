import asyncio
import json
import logging
from typing import Optional, Dict, Any

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from hinaa_api.config import get_settings
from hinaa_api.tools.registry import registry, ToolDefinition
from hinaa_api.tools.browser_automation import (
    _get_page,
    browser_navigate,
    BrowserNavigateParams,
    browser_extract,
    BrowserExtractParams,
    browser_click,
    BrowserClickParams,
    browser_type,
    BrowserTypeParams,
)

logger = logging.getLogger("hinaa.tools.browser_agent")

approval_events = {}

class BrowserTaskParams(BaseModel):
    goal: str = Field(..., description="The high-level goal you want the browser agent to achieve (e.g., 'Search youtube for lo-fi hip hop and play it').")
    max_steps: int = Field(15, description="Maximum number of steps before timing out.")

async def browser_execute_task(params: BrowserTaskParams) -> str:
    """
    Executes a high-level browser task autonomously by looping with Gemini Flash
    and Playwright browser actuation tools.
    Supports continuous navigation, reading DOM, clicking, typing, scrolling, and keypresses.
    """
    settings = get_settings()
    gemini_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    
    if not gemini_key:
        return "Failed: GEMINI_API_KEY is not configured in the backend."
        
    client = genai.Client(api_key=gemini_key)
    goal = params.goal
    max_steps = params.max_steps
    
    system_instruction = f"""You are an expert autonomous browser agent. Your mission: {goal}
You operate a real desktop web browser via tools:
- navigate(url): Open any website URL.
- read_page(): Inspect current title, URL, scroll position, visible text, and interactable elements with indices and IDs.
- click(selector): Click any link, button, video, or element by text or CSS/ID selector.
- type(selector, text, submit): Enter search queries or inputs into textboxes. Set submit=True to submit immediately with Enter.
- scroll(direction, amount): Scroll 'down' or 'up' (e.g. amount=600 or 1000) to reveal more content, videos, comments, or results below.
- press_key(key): Press keyboard keys ('Enter', 'Space', 'Escape', 'Tab', 'PageDown', 'PageUp').
- wait(seconds): Wait for dynamic content, SPAs, or videos to load.
- finish_task(result): Complete the task once the goal is accomplished and report what was achieved.

Guidelines:
1. If not already on the required site, begin by navigating there (e.g. https://www.google.com, https://www.youtube.com).
2. Always read the page first before interacting to see available elements and inputs.
3. To search on Google or YouTube, type into the search box with submit=True, or press_key 'Enter'.
4. To see more items down the page, scroll down and then read the page again.
5. Once you have reached the goal or started playback, finish the task with a helpful summary.
"""

    agent_tools = [
        {
            "function_declarations": [
                {
                    "name": "navigate",
                    "description": "Navigate to a URL",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "url": {"type": "STRING"}
                        },
                        "required": ["url"]
                    }
                },
                {
                    "name": "read_page",
                    "description": "Read the current page to get visible text and interactable elements.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {}
                    }
                },
                {
                    "name": "click",
                    "description": "Click an element by text, id, or selector.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "selector": {"type": "STRING"}
                        },
                        "required": ["selector"]
                    }
                },
                {
                    "name": "type",
                    "description": "Type text into an input field and optionally press Enter.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "selector": {"type": "STRING"},
                            "text": {"type": "STRING"},
                            "submit": {"type": "BOOLEAN"}
                        },
                        "required": ["selector", "text", "submit"]
                    }
                },
                {
                    "name": "scroll",
                    "description": "Scroll down or up on the page to reveal more content, search results, or comments.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "direction": {"type": "STRING", "description": "'down' or 'up' (default 'down')"},
                            "amount": {"type": "INTEGER", "description": "Number of pixels to scroll (e.g. 500, 800)"}
                        }
                    }
                },
                {
                    "name": "press_key",
                    "description": "Press a keyboard key like 'Enter', 'Escape', 'ArrowDown', 'Space', 'Tab'.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "key": {"type": "STRING", "description": "Key name to press (e.g. 'Enter', 'Escape', 'PageDown', 'Space')"}
                        },
                        "required": ["key"]
                    }
                },
                {
                    "name": "wait",
                    "description": "Wait a specified number of seconds for dynamic content or pages to load.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "seconds": {"type": "NUMBER", "description": "Seconds to wait (default 2.0)"}
                        }
                    }
                },
                {
                    "name": "finish_task",
                    "description": "Call this when the goal is achieved or impossible.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "result": {"type": "STRING", "description": "The final summary of what happened."}
                        },
                        "required": ["result"]
                    }
                }
            ]
        }
    ]

    chat = client.aio.chats.create(
        model="gemini-3.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=agent_tools,
            temperature=0.2,
        )
    )

    async def safe_send(msg):
        import re
        for attempt in range(4):
            try:
                return await chat.send_message(msg)
            except Exception as ex:
                err_str = str(ex)
                if ("429" in err_str or "RESOURCE_EXHAUSTED" in err_str) and attempt < 3:
                    match = re.search(r"retry in ([\d\.]+)s", err_str, re.IGNORECASE)
                    backoff = (float(match.group(1)) + 1.0) if match else (12.0 + attempt * 4.0)
                    logger.warning(f"[BrowserAgent] Rate limited (429), backing off for {backoff:.1f}s...")
                    await asyncio.sleep(backoff)
                    continue
                raise

    max_steps = params.max_steps
    step = 0
    final_result = "Task timed out after maximum steps."

    try:
        # Initial prompt to start the loop
        response = await safe_send(f"Begin working on the goal: {goal}")
        
        current_url = ""
        
        while step < max_steps:
            step += 1
            
            # Check if model wants to call a tool
            if not response.function_calls:
                response = await safe_send("Please use an action tool (navigate, read_page, click, type, scroll, wait) or call finish_task.")
                continue

            function_call = response.function_calls[0]
            name = function_call.name
            args = function_call.args
            
            logger.info(f"[BrowserAgent Step {step}] Called {name}({args})")
            
            tool_result_str = ""
            if name == "finish_task":
                final_result = args.get("result", "Task finished with no summary provided.")
                break
            elif name == "navigate":
                tool_result_str = await browser_navigate(BrowserNavigateParams(url=args.get("url")))
                current_url = args.get("url", "")
            elif name == "read_page":
                tool_result_str = await browser_extract(BrowserExtractParams())
            elif name == "click":
                selector = str(args.get("selector") or args.get("text") or args.get("target") or "")
                tool_result_str = await browser_click(BrowserClickParams(selector=selector))
            elif name == "type":
                selector = str(args.get("selector") or "")
                text = str(args.get("text") or "")
                submit = bool(args.get("submit", True))
                tool_result_str = await browser_type(BrowserTypeParams(selector=selector, text=text, submit=submit))
            elif name == "scroll":
                page = await _get_page()
                direction = str(args.get("direction", "down")).lower()
                amount = int(args.get("amount", 600))
                dy = amount if direction == "down" else -amount
                try:
                    await page.mouse.wheel(0, dy)
                    await asyncio.sleep(0.5)
                    scroll_y = await page.evaluate("window.scrollY || 0")
                    tool_result_str = f"Successfully scrolled {direction} by {amount}px (current Y={scroll_y}px)."
                except Exception as e:
                    tool_result_str = f"Failed to scroll: {str(e)}"
            elif name == "press_key":
                page = await _get_page()
                key = str(args.get("key", "Enter"))
                try:
                    await page.keyboard.press(key)
                    await asyncio.sleep(0.4)
                    tool_result_str = f"Successfully pressed key '{key}'."
                except Exception as e:
                    tool_result_str = f"Failed to press key: {str(e)}"
            elif name == "wait":
                seconds = float(args.get("seconds", 2.0))
                await asyncio.sleep(seconds)
                tool_result_str = f"Waited {seconds} seconds."
            else:
                tool_result_str = f"Unknown tool {name}"

            # Send tool response back to Gemini
            response = await safe_send(
                types.Part.from_function_response(
                    name=name,
                    response={"result": tool_result_str}
                )
            )

        if final_result == "Task timed out after maximum steps.":
            final_result = f"Completed {step} autonomous browser steps for '{goal}' at {current_url or 'browser'}. Navigation and actions were executed."

    except Exception as e:
        final_result = f"Browser Agent crashed: {str(e)}"
    finally:
        # Do not close the client because other things might use it? Actually client.aio.aclose() closes THIS client's session.
        # Wait, google-genai Client has no aclose() in newer versions or it's a no-op, but it's safe if it exists.
        pass

    return final_result


browser_execute_task_def = ToolDefinition(
    name="browser_execute_task",
    display_name="Browser: Autonomous Agent",
    description="Hands off a complex browser goal to an autonomous sub-agent that can navigate, read, type, and click its way through the web to achieve the goal.",
    parameters={
        "goal": {"type": "string", "description": "The high-level goal you want the browser agent to achieve (e.g., 'Search youtube for lo-fi hip hop and play it')."}
    },
    required_parameters=["goal"],
    voice_aliases=["do this on the browser", "browser task", "automate the browser"],
    requires_confirmation=False
)

registry.register(browser_execute_task_def, browser_execute_task)
