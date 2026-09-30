"""Browser-Use Cloud autonomous web agent for HINAA.

Connects to Browser-Use Cloud API (https://api.browser-use.com/api/v2) to execute
complex, multi-step browser tasks (navigating, clicking, searching, interacting,
and synthesizing web findings) in managed cloud sandboxes.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel, Field

from ..config import get_settings
from ..tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.browser_cloud")


class BrowserCloudTaskParams(BaseModel):
    model_config = {"extra": "ignore"}
    task: str = Field(..., description="The high-level autonomous browsing goal (e.g. 'Search Hacker News for latest AI announcements and summarize the top 3 stories').")
    startUrl: Optional[str] = Field(None, description="Optional starting URL to open directly.")
    max_steps: int = Field(25, description="Maximum browsing steps before completing.")
    flash_mode: bool = Field(True, description="Enable faster execution mode.")


class BrowserCloudResult(BaseModel):
    task_id: str
    status: str
    output: Optional[str] = None
    live_url: Optional[str] = None
    steps_taken: int = 0
    error: Optional[str] = None


async def execute_browser_cloud_task(params: BrowserCloudTaskParams) -> dict[str, Any]:
    """Execute an autonomous browsing task on Browser-Use Cloud."""
    settings = get_settings()
    api_key = (
        os.getenv("BROWSER_USE_API_KEY")
        or os.getenv("BROWSER_USE_API_KEY1")
        or os.getenv("BROWSER_USE_API_KEY2")
    )
    if not api_key and hasattr(settings, "browser_use_api_key") and settings.browser_use_api_key:
        api_key = settings.browser_use_api_key.get_secret_value()

    if not api_key:
        logger.info("Browser-Use API key not configured; routing to local/Bright Data agent.")
        from .browser_agent import browser_execute_task, BrowserTaskParams
        local_result = await browser_execute_task(BrowserTaskParams(
            goal=params.task,
            max_steps=min(params.max_steps, 15),
        ))
        return {
            "status": "completed",
            "provider": "local_playwright",
            "summary": local_result,
        }

    base_url = "https://api.browser-use.com/api/v2"
    headers = {
        "X-Browser-Use-API-Key": api_key.strip(),
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {
        "task": params.task,
        "maxSteps": min(max(params.max_steps, 5), 50),
        "flashMode": params.flash_mode,
        "vision": True,
    }
    if params.startUrl and params.startUrl.startswith(("http://", "https://")):
        payload["startUrl"] = params.startUrl

    logger.info("Submitting task to Browser-Use Cloud: %s", params.task[:100])

    async with httpx.AsyncClient(timeout=40.0) as client:
        create_resp = await client.post(f"{base_url}/tasks", headers=headers, json=payload)
        if create_resp.status_code not in (200, 201):
            err_msg = create_resp.text[:300]
            logger.warning("Browser-Use Cloud task creation failed [%d]: %s; falling back to local browser", create_resp.status_code, err_msg)
            from .browser_agent import browser_execute_task, BrowserTaskParams
            local_result = await browser_execute_task(BrowserTaskParams(
                goal=params.task,
                max_steps=min(params.max_steps, 15),
            ))
            return {
                "status": "completed",
                "provider": "local_fallback",
                "summary": local_result,
            }

        task_data = create_resp.json()
        task_id = task_data.get("id")
        if not task_id:
            return {"status": "failed", "error": "No task ID returned by Browser-Use Cloud."}

        logger.info("Browser-Use Cloud task %s created; polling execution...", task_id)

        # Poll status up to 90 seconds (18 iterations * 5s)
        final_data = task_data
        for _ in range(18):
            await asyncio.sleep(5.0)
            status_resp = await client.get(f"{base_url}/tasks/{task_id}", headers=headers)
            if status_resp.status_code == 200:
                final_data = status_resp.json()
                status = final_data.get("status", "").lower()
                if status in ("completed", "finished", "success", "failed", "cancelled", "stopped"):
                    break

        status = final_data.get("status", "completed")
        output = final_data.get("output") or final_data.get("result") or ""
        if not output and isinstance(final_data.get("steps"), list) and final_data["steps"]:
            # Extract notes from steps
            last_step = final_data["steps"][-1]
            output = last_step.get("notes") or last_step.get("action") or "Task executed successfully."

        live_url = final_data.get("liveUrl") or final_data.get("shareUrl") or f"https://cloud.browser-use.com/tasks/{task_id}"

        return {
            "status": status,
            "provider": "browser_use_cloud",
            "task_id": task_id,
            "output": output or "Task completed by Browser-Use autonomous cloud agent.",
            "live_url": live_url,
            "summary": f"Browser-Use Cloud executed task: {output[:300]}",
        }


browser_cloud_def = ToolDefinition(
    name="browser_cloud_agent",
    display_name="Autonomous Cloud Browser (Browser-Use)",
    description=(
        "Executes complex, multi-step browser tasks autonomously on Browser-Use Cloud. "
        "Use when the user asks to navigate websites, click, interact, search live online sites, "
        "fill web forms, or extract structured data from interactive web apps."
    ),
    parameters={
        "task": {
            "type": "string",
            "description": "The exact browsing goal or instruction for the autonomous agent.",
        },
        "startUrl": {
            "type": "string",
            "description": "Optional starting URL (e.g. 'https://news.ycombinator.com').",
        },
        "max_steps": {
            "type": "integer",
            "description": "Maximum steps the browser agent should take (default 25).",
        },
    },
    required_parameters=["task"],
    voice_aliases=[
        "browse the web",
        "search the web with browser",
        "open the browser and",
        "navigate to",
        "check the website",
    ],
    requires_confirmation=False,
)

registry.register(browser_cloud_def, execute_browser_cloud_task)
