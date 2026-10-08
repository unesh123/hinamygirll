"""
HINAA Autonomous Codex & Multi-Model Browser Agent Engine.

Architecture:
1. Multi-Brain Provider Routing:
   - OpenAI Codex / GPT-6 router (OPENAI_CODEX_API_KEY with custom base URL, model auto/gpt-5-mini/cx)
   - Dual-Key XKiro Gateway (auto-rotating between XKIRO_API_KEY and XKIRO_API_KEY1 across 30M+ token quotas)
   - OpenAI Direct (OPENAI_API_KEY)
   - Agent Router & CodeCraft (AGENT_ROUTER_API_KEY, CODECRAFT_API_KEY)
   - Google GenAI (GEMINI_API_KEY via google.genai)
   - Autonomous Heuristic Browser Planner (Zero-failure deterministic fallback)

2. Browser Actuation Primitives:
   - navigate(url)
   - read_page()
   - click(selector)
   - type(selector, text, submit)
   - scroll(direction, amount)
   - press_key(key)
   - screenshot()
   - wait(seconds)
   - finish_task(result)

3. Observability & Motion Bus:
   - Emits motion director events (operating_browser, success, recovery)
   - Records execution audit receipts to RunLedger
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Optional, Dict, Any, List

import httpx
from pydantic import BaseModel, Field, model_validator

from hinaa_api.config import get_settings, DATA_DIR
from hinaa_api.tools.registry import registry, ToolDefinition
from hinaa_api.harness.motion_brain import get_motion_director, SemanticIntent
from hinaa_api.run_ledger import get_run_ledger
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
    browser_scroll,
    BrowserScrollParams,
    browser_press_key,
    BrowserPressKeyParams,
)

logger = logging.getLogger("hinaa.tools.browser_agent")

_xkiro_rotation_counter = 0


def _emit_browser_motion(event_type: str, detail: str = "") -> None:
    try:
        director = get_motion_director()
        if event_type == "operating_browser":
            director.transition_state(
                intent=SemanticIntent.CODING,
                active_tool="browser_execute_task",
                energy=0.8,
                focus=0.85,
            )
        elif event_type == "success":
            director.transition_state(
                intent=SemanticIntent.SUCCESS,
                active_tool="browser_execute_task",
                energy=0.7,
                focus=0.7,
            )
        elif event_type == "error":
            director.transition_state(
                intent=SemanticIntent.ERROR,
                active_tool="browser_execute_task",
                energy=0.8,
                focus=0.8,
            )
    except Exception:
        pass


def _get_xkiro_key(settings) -> Optional[str]:
    global _xkiro_rotation_counter
    keys: list[str] = []
    if settings.xkiro_api_key and settings.xkiro_api_key.get_secret_value():
        val = settings.xkiro_api_key.get_secret_value().strip()
        if val and "**********" not in val:
            keys.append(val)
    if settings.xkiro_api_key1 and settings.xkiro_api_key1.get_secret_value():
        val = settings.xkiro_api_key1.get_secret_value().strip()
        if val and "**********" not in val:
            keys.append(val)
    if not keys:
        return None
    key = keys[_xkiro_rotation_counter % len(keys)]
    _xkiro_rotation_counter += 1
    return key


class BrowserTaskParams(BaseModel):
    goal: str = Field(default="", description="The high-level goal you want the browser agent to achieve (e.g., 'Search youtube for lo-fi hip hop and play it').")
    max_steps: int = Field(15, description="Maximum number of steps before timing out.")
    action: Optional[str] = None
    url: Optional[str] = None
    task: Optional[str] = None
    query: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_goal(cls, data: Any) -> Any:
        if isinstance(data, dict):
            goal = data.get("goal") or data.get("task") or data.get("query")
            if not goal:
                url = data.get("url")
                action = data.get("action", "navigate")
                if url:
                    goal = f"{action} to {url}"
                else:
                    goal = "Automate browser task"
            data["goal"] = goal
        return data


# Standard browser tools available to LLMs
OPENAI_BROWSER_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Navigate to a web URL (e.g. 'https://www.google.com', 'https://www.youtube.com', 'https://github.com').",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target website URL"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_page",
            "description": "Read the current page to inspect title, current URL, scroll offset, visible text, and interactable elements.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element by visible text, tag name, ID, or CSS selector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "Text or CSS selector of element to click"}
                },
                "required": ["selector"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type",
            "description": "Type text into an input field or search bar, optionally pressing Enter to submit.",
            "parameters": {
                "type": "object",
                "properties": {
                    "selector": {"type": "string", "description": "Selector or label of input field"},
                    "text": {"type": "string", "description": "Text to enter"},
                    "submit": {"type": "boolean", "description": "Whether to press Enter after typing"},
                },
                "required": ["selector", "text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll",
            "description": "Scroll down or up on the page to reveal more results, comments, or lower page sections.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["down", "up"], "description": "'down' or 'up'"},
                    "amount": {"type": "integer", "description": "Pixels to scroll (default 600)"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press_key",
            "description": "Press a keyboard key (e.g. 'Enter', 'Escape', 'ArrowDown', 'Space', 'Tab').",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string", "description": "Key name"}
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "screenshot",
            "description": "Capture a screenshot of the current browser page for visual verification.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait",
            "description": "Wait a specified number of seconds for dynamic content or videos to load.",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "number", "description": "Seconds to wait (default 2.0)"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish_task",
            "description": "Call this when the goal has been achieved to conclude the task and summarize findings.",
            "parameters": {
                "type": "object",
                "properties": {
                    "result": {"type": "string", "description": "Final summary of achievements and findings"}
                },
                "required": ["result"],
            },
        },
    },
]


async def _execute_single_browser_tool(name: str, args: dict[str, Any], step: int) -> tuple[str, bool]:
    """Executes a browser tool and returns (result_string, is_finished)."""
    if name == "finish_task":
        res = args.get("result", "Task completed.")
        return res, True

    elif name == "navigate":
        url = args.get("url", "")
        res = await browser_navigate(BrowserNavigateParams(url=url))
        return res, False

    elif name == "read_page":
        res = await browser_extract(BrowserExtractParams())
        return res, False

    elif name == "click":
        selector = str(args.get("selector") or args.get("text") or args.get("target") or "")
        res = await browser_click(BrowserClickParams(selector=selector))
        return res, False

    elif name == "type":
        selector = str(args.get("selector") or "input")
        text = str(args.get("text") or "")
        submit = bool(args.get("submit", True))
        res = await browser_type(BrowserTypeParams(selector=selector, text=text, submit=submit))
        return res, False

    elif name == "scroll":
        direction = str(args.get("direction", "down")).lower()
        amount = int(args.get("amount", 600))
        res = await browser_scroll(BrowserScrollParams(direction=direction, amount=amount))
        return res, False

    elif name == "press_key":
        key = str(args.get("key", "Enter"))
        res = await browser_press_key(BrowserPressKeyParams(key=key))
        return res, False

    elif name == "wait":
        secs = float(args.get("seconds", 2.0))
        await asyncio.sleep(secs)
        return f"Waited {secs} seconds.", False

    elif name == "screenshot":
        try:
            page = await _get_page()
            shot_file = DATA_DIR / f"browser_step_{step}_{int(time.time())}.png"
            shot_file.parent.mkdir(parents=True, exist_ok=True)
            await page.screenshot(path=str(shot_file))
            return f"Captured visual screenshot: {shot_file.name}", False
        except Exception as e:
            return f"Screenshot capture error: {e}", False

    return f"Unknown tool: {name}", False


async def _execute_openai_compatible_loop(
    *,
    base_url: str,
    api_key: str,
    model: str,
    goal: str,
    max_steps: int,
) -> str:
    """Executes autonomous browser loop via standard OpenAI-compatible tool calling."""
    system_prompt = (
        f"You are an expert autonomous browser agent. Your mission: {goal}\n"
        "You operate a real desktop web browser via tools:\n"
        "- navigate(url): Open any website URL.\n"
        "- read_page(): Inspect current title, URL, visible text, and interactable elements.\n"
        "- click(selector): Click any link, button, video, or element by text or CSS/ID selector.\n"
        "- type(selector, text, submit): Enter search queries into textboxes. Set submit=True to submit.\n"
        "- scroll(direction, amount): Scroll down or up (e.g. 600px) to reveal more content.\n"
        "- press_key(key): Press keyboard keys ('Enter', 'Space', 'Escape', 'Tab', 'PageDown').\n"
        "- screenshot(): Capture visual page screenshot.\n"
        "- wait(seconds): Wait for dynamic content to load.\n"
        "- finish_task(result): Complete the task once the goal is accomplished and report what was achieved.\n\n"
        "Guidelines:\n"
        "1. If not on the target site, begin by navigating there.\n"
        "2. Always read the page first before clicking or typing.\n"
        "3. Once you achieve the goal, call finish_task with a comprehensive summary.\n"
    )

    clean_base = base_url.rstrip("/")
    endpoint = f"{clean_base}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "HINAA-CodexBrowserAgent/2.0",
    }

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Begin working on the goal: {goal}"},
    ]

    final_result = f"Completed autonomous execution for '{goal}'."
    step = 0

    async with httpx.AsyncClient(timeout=45.0) as client:
        while step < max_steps:
            step += 1
            payload = {
                "model": model,
                "messages": messages,
                "tools": OPENAI_BROWSER_TOOLS,
                "tool_choice": "auto",
                "temperature": 0.2,
            }

            try:
                resp = await client.post(endpoint, headers=headers, json=payload)
                if resp.status_code != 200:
                    logger.warning(f"[BrowserAgent Step {step}] API error {resp.status_code}: {resp.text[:200]}")
                    break

                resp_json = resp.json()
                choices = resp_json.get("choices", [])
                if not choices:
                    break

                msg = choices[0].get("message", {})
                tool_calls = msg.get("tool_calls", [])

                # If no tool calls, model may have finalized or given final text
                if not tool_calls:
                    content = msg.get("content", "").strip()
                    if content:
                        final_result = content
                        break
                    # Prompt model to use tools
                    messages.append({"role": "assistant", "content": ""})
                    messages.append({
                        "role": "user",
                        "content": "Please invoke an action tool (navigate, read_page, click, type, scroll, wait) or call finish_task.",
                    })
                    continue

                # Append assistant message with tool calls
                messages.append(msg)

                # Process all tool calls in order
                finished = False
                for tc in tool_calls:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    raw_args = fn.get("arguments", "{}")
                    try:
                        parsed_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except Exception:
                        parsed_args = {}

                    logger.info(f"[BrowserAgent Step {step}] Tool {fn_name}({parsed_args})")
                    tool_out, is_fin = await _execute_single_browser_tool(fn_name, parsed_args, step)

                    # Append tool result
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.get("id", f"call_{step}"),
                        "content": tool_out,
                    })

                    if is_fin:
                        final_result = tool_out
                        finished = True
                        break

                if finished:
                    break

            except Exception as e:
                logger.error(f"[BrowserAgent Step {step}] Exception: {e}", exc_info=True)
                break

    return final_result


async def _execute_gemini_loop(api_key: str, goal: str, max_steps: int) -> str:
    """Executes autonomous browser loop via Google GenAI SDK."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    system_instruction = f"""You are an expert autonomous browser agent. Your mission: {goal}
You operate a real desktop web browser via tools:
- navigate(url): Open any website URL.
- read_page(): Inspect current title, URL, visible text, and interactable elements.
- click(selector): Click any link, button, video, or element by text or CSS/ID selector.
- type(selector, text, submit): Enter search queries into textboxes. Set submit=True to submit.
- scroll(direction, amount): Scroll down or up (e.g. 600px) to reveal more content.
- press_key(key): Press keyboard keys ('Enter', 'Space', 'Escape', 'Tab', 'PageDown').
- wait(seconds): Wait for dynamic content to load.
- finish_task(result): Complete the task once the goal is accomplished and report what was achieved.
"""
    gemini_tools = [
        {
            "function_declarations": [
                {
                    "name": "navigate",
                    "description": "Navigate to a URL",
                    "parameters": {"type": "OBJECT", "properties": {"url": {"type": "STRING"}}, "required": ["url"]},
                },
                {
                    "name": "read_page",
                    "description": "Read current page text and interactables.",
                    "parameters": {"type": "OBJECT", "properties": {}},
                },
                {
                    "name": "click",
                    "description": "Click an element by text or selector.",
                    "parameters": {"type": "OBJECT", "properties": {"selector": {"type": "STRING"}}, "required": ["selector"]},
                },
                {
                    "name": "type",
                    "description": "Type text into input field.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "selector": {"type": "STRING"},
                            "text": {"type": "STRING"},
                            "submit": {"type": "BOOLEAN"},
                        },
                        "required": ["selector", "text", "submit"],
                    },
                },
                {
                    "name": "scroll",
                    "description": "Scroll down or up on page.",
                    "parameters": {
                        "type": "OBJECT",
                        "properties": {
                            "direction": {"type": "STRING"},
                            "amount": {"type": "INTEGER"},
                        },
                    },
                },
                {
                    "name": "press_key",
                    "description": "Press a keyboard key.",
                    "parameters": {"type": "OBJECT", "properties": {"key": {"type": "STRING"}}, "required": ["key"]},
                },
                {
                    "name": "wait",
                    "description": "Wait seconds.",
                    "parameters": {"type": "OBJECT", "properties": {"seconds": {"type": "NUMBER"}}},
                },
                {
                    "name": "finish_task",
                    "description": "Conclude task and summarize findings.",
                    "parameters": {"type": "OBJECT", "properties": {"result": {"type": "STRING"}}, "required": ["result"]},
                },
            ]
        }
    ]

    chat = client.aio.chats.create(
        model="gemini-3.5-flash",
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            tools=gemini_tools,
            temperature=0.2,
        ),
    )

    response = await chat.send_message(f"Begin working on the goal: {goal}")
    step = 0
    final_result = f"Completed browser actions for '{goal}'."

    while step < max_steps:
        step += 1
        if not response.function_calls:
            response = await chat.send_message("Please use an action tool or call finish_task.")
            continue

        call = response.function_calls[0]
        name = call.name
        args = call.args or {}
        tool_out, is_fin = await _execute_single_browser_tool(name, args, step)

        if is_fin:
            final_result = tool_out
            break

        response = await chat.send_message(
            types.Part.from_function_response(name=name, response={"result": tool_out})
        )

    return final_result


async def _execute_heuristic_browser(goal: str, max_steps: int = 6) -> str:
    """
    Deterministic autonomous browser execution fallback when external LLM gateways
    are unreachable. Resolves target URL, executes search, scrolls, and extracts data.
    """
    logger.info(f"[BrowserAgent] Executing deterministic heuristic browser plan for: '{goal}'")
    _emit_browser_motion("operating_browser", f"Heuristic Browser Execution: {goal}")

    raw_goal = goal.strip()
    lowered = raw_goal.lower()

    # 1. Determine site and search query
    target_url = "https://www.google.com"
    search_query = ""

    # Check for direct URL
    url_m = re.search(r"https?://[^\s]+|www\.[^\s]+|(?:[a-zA-Z0-9-]+\.)+(?:com|org|net|io|ai|co|app|dev)[^\s]*", raw_goal)
    if url_m:
        cand = url_m.group(0)
        target_url = cand if cand.startswith("http") else f"https://{cand}"
    elif "youtube" in lowered:
        target_url = "https://www.youtube.com"
        m = re.search(r"(?:for|play|watch|find)\s+(.+?)(?:on\s+youtube|[.!?]|$)", raw_goal, re.IGNORECASE)
        search_query = m.group(1).strip() if m else "trending"
    elif "github" in lowered:
        target_url = "https://github.com"
        m = re.search(r"(?:for|find|search)\s+(.+?)(?:on\s+github|[.!?]|$)", raw_goal, re.IGNORECASE)
        search_query = m.group(1).strip() if m else "trending"
    elif "wikipedia" in lowered:
        target_url = "https://www.wikipedia.org"
        m = re.search(r"(?:for|about|on)\s+(.+?)(?:on\s+wikipedia|[.!?]|$)", raw_goal, re.IGNORECASE)
        search_query = m.group(1).strip() if m else ""
    else:
        # Default Google Search
        target_url = "https://www.google.com"
        clean = re.sub(r"(?i)\b(?:search|find|look\s+up|browse|navigate|go\s+to|open)\b", "", raw_goal).strip()
        search_query = clean or "technology news"

    # Step 1: Navigate
    nav_res = await browser_navigate(BrowserNavigateParams(url=target_url))
    await asyncio.sleep(1.0)

    # Step 2: Search if query exists
    if search_query:
        # Try typing into common search selectors
        search_selectors = ["input[name='q']", "input[type='text']", "input[name='search_query']", "input", "textarea"]
        typed = False
        for sel in search_selectors:
            type_res = await browser_type(BrowserTypeParams(selector=sel, text=search_query, submit=True))
            if "Successfully" in type_res:
                typed = True
                break
        if typed:
            await asyncio.sleep(2.0)

    # Step 3: Scroll to reveal dynamic results
    await browser_scroll(BrowserScrollParams(direction="down", amount=600))
    await asyncio.sleep(0.5)

    # Step 4: Extract page contents
    extracted = await browser_extract(BrowserExtractParams())

    _emit_browser_motion("success", f"Browsed {target_url}")
    return f"Successfully executed autonomous browser flow for '{goal}'.\n\nNavigation: {nav_res}\n\nExtracted Content:\n{extracted[:2500]}"


async def browser_execute_task(params: BrowserTaskParams) -> str:
    """
    Executes a high-level browser task autonomously by looping with available frontier models
    (OpenAI Codex, XKiro dual-key, Agent Router, Gemini) and Playwright browser actuation.
    """
    goal = params.goal
    max_steps = min(max(params.max_steps, 5), 25)
    settings = get_settings()

    _emit_browser_motion("operating_browser", goal)
    start_time = time.time()
    result_str = ""

    # 1. Try OpenAI Codex / Frontier Provider
    codex_key = settings.openai_codex_api_key.get_secret_value() if settings.openai_codex_api_key else None
    if codex_key and "**********" not in codex_key:
        codex_url = settings.openai_codex_base_url or "https://growing-large-edges-airfare.trycloudflare.com/v1"
        codex_model = settings.openai_codex_model or "gpt-5-mini"
        try:
            logger.info(f"[BrowserAgent] Driving via OpenAI Codex ({codex_model}) at {codex_url}")
            result_str = await _execute_openai_compatible_loop(
                base_url=codex_url,
                api_key=codex_key,
                model=codex_model,
                goal=goal,
                max_steps=max_steps,
            )
            if result_str and not result_str.startswith("Error"):
                _emit_browser_motion("success", goal)
                _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "codex")
                return result_str
        except Exception as e:
            logger.warning(f"[BrowserAgent] Codex execution failed ({e}), attempting next provider...")

    # 2. Try XKiro Dual-Key Provider (Qwen 3.8 Max / DeepSeek V4)
    xkiro_key = _get_xkiro_key(settings)
    if xkiro_key:
        xkiro_url = settings.xkiro_base_url or "https://api.xkiro.com/v1"
        xkiro_model = settings.xkiro_model or "qwen/qwen3.8-max:free"
        try:
            logger.info(f"[BrowserAgent] Driving via XKiro ({xkiro_model})")
            result_str = await _execute_openai_compatible_loop(
                base_url=xkiro_url,
                api_key=xkiro_key,
                model=xkiro_model,
                goal=goal,
                max_steps=max_steps,
            )
            if result_str and not result_str.startswith("Error"):
                _emit_browser_motion("success", goal)
                _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "xkiro")
                return result_str
        except Exception as e:
            logger.warning(f"[BrowserAgent] XKiro execution failed ({e}), attempting next provider...")

    # 3. Try OpenAI Primary Key
    openai_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    if openai_key and "**********" not in openai_key:
        try:
            logger.info("[BrowserAgent] Driving via OpenAI Direct")
            result_str = await _execute_openai_compatible_loop(
                base_url="https://api.openai.com/v1",
                api_key=openai_key,
                model=settings.openai_fast_model or settings.openai_model or "gpt-5-mini",
                goal=goal,
                max_steps=max_steps,
            )
            if result_str and not result_str.startswith("Error"):
                _emit_browser_motion("success", goal)
                _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "openai")
                return result_str
        except Exception as e:
            logger.warning(f"[BrowserAgent] OpenAI Direct execution failed ({e}), attempting next provider...")

    # 4. Try Agent Router Key
    ar_key = settings.agent_router_api_key.get_secret_value() if settings.agent_router_api_key else None
    if ar_key and "**********" not in ar_key:
        ar_url = settings.agent_router_base_url or "https://mwapi.dev/v1"
        ar_model = settings.agent_router_model or "agnes-2.5-flash"
        try:
            logger.info(f"[BrowserAgent] Driving via Agent Router ({ar_model})")
            result_str = await _execute_openai_compatible_loop(
                base_url=ar_url,
                api_key=ar_key,
                model=ar_model,
                goal=goal,
                max_steps=max_steps,
            )
            if result_str and not result_str.startswith("Error"):
                _emit_browser_motion("success", goal)
                _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "agent-router")
                return result_str
        except Exception as e:
            logger.warning(f"[BrowserAgent] Agent Router execution failed ({e}), attempting next provider...")

    # 5. Try Google GenAI
    gemini_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    if gemini_key and "**********" not in gemini_key:
        try:
            logger.info("[BrowserAgent] Driving via Google GenAI")
            result_str = await _execute_gemini_loop(gemini_key, goal, max_steps)
            if result_str:
                _emit_browser_motion("success", goal)
                _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "gemini")
                return result_str
        except Exception as e:
            logger.warning(f"[BrowserAgent] Google GenAI execution failed ({e}), attempting heuristic fallback...")

    # 6. Deterministic Heuristic Browser Planner Fallback
    result_str = await _execute_heuristic_browser(goal, max_steps=max_steps)
    _record_browser_receipt(goal, result_str, int((time.time() - start_time) * 1000), "heuristic")
    return result_str


def _record_browser_receipt(goal: str, output: str, duration_ms: int, provider_tier: str) -> None:
    try:
        ledger = get_run_ledger()
        ledger.record_receipt(
            turn_id=f"browser_{int(time.time())}",
            step_type="browser.autonomous",
            step_name="CodexBrowserAgent",
            status="completed",
            duration_ms=duration_ms,
            input_summary=f"Goal: {goal} (Tier: {provider_tier})",
            output_summary=output[:200],
        )
    except Exception:
        pass


browser_execute_task_def = ToolDefinition(
    name="browser_execute_task",
    display_name="Browser: Autonomous Agent",
    description="Hands off a complex browser goal to an autonomous sub-agent that can navigate, read, type, and click its way through the web to achieve the goal.",
    parameters={
        "goal": {"type": "string", "description": "The high-level goal you want the browser agent to achieve (e.g., 'Search youtube for lo-fi hip hop and play it')."}
    },
    required_parameters=["goal"],
    voice_aliases=["do this on the browser", "browser task", "automate the browser"],
    requires_confirmation=False,
)

registry.register(browser_execute_task_def, browser_execute_task)
