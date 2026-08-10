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

class BrowserTaskParams(BaseModel):
    goal: str = Field(..., description="The high-level goal you want the browser agent to achieve (e.g., 'Search youtube for lo-fi hip hop and play it').")

async def browser_execute_task(params: BrowserTaskParams) -> str:
    """
    Executes a high-level browser task autonomously by looping with Gemini 2.5 Flash
    and Playwright tools.
    """
    settings = get_settings()
    gemini_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else None
    
    if not gemini_key:
        return "Failed: GEMINI_API_KEY is not configured in the backend."
        
    client = genai.Client(api_key=gemini_key)
    goal = params.goal
    
    system_instruction = f"""You are an autonomous browser agent. Your goal is: {goal}
You have access to browser tools to navigate, read the page, click, and type.
Follow these steps:
1. Always start by navigating to the relevant website if you are not already there.
2. Read the page to see what's on the screen (it returns a numbered list of interactable elements).
3. Use click or type tools on the elements you see.
4. When you have successfully completed the goal, or if you are completely stuck, call the 'finish_task' tool to end the loop and report the outcome.
Never guess selectors. Always read the page first, then use the text or IDs provided in the read_page output to click or type.
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

    max_steps = 10
    step = 0
    final_result = "Task timed out after maximum steps."

    try:
        # Initial prompt to start the loop
        response = await chat.send_message(f"Begin working on the goal: {goal}")
        
        while step < max_steps:
            step += 1
            
            # Check if model wants to call a tool
            if not response.function_calls:
                # If no function call, just prompt it to keep going or finish
                response = await chat.send_message("Please use a tool to continue or call finish_task.")
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
            elif name == "read_page":
                tool_result_str = await browser_extract(BrowserExtractParams())
            elif name == "click":
                tool_result_str = await browser_click(BrowserClickParams(selector=args.get("selector")))
            elif name == "type":
                tool_result_str = await browser_type(BrowserTypeParams(
                    selector=args.get("selector"), 
                    text=args.get("text"), 
                    submit=args.get("submit", False)
                ))
            else:
                tool_result_str = f"Unknown tool {name}"

            # Send tool response back to Gemini
            response = await chat.send_message(
                types.Part.from_function_response(
                    name=name,
                    response={"result": tool_result_str}
                )
            )

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
    requires_confirmation=True
)

registry.register(browser_execute_task_def, browser_execute_task)
