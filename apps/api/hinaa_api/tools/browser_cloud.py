"""Browser-Use Cloud v4 autonomous web agent for HINAA.

Connects to Browser-Use Cloud API v4 (https://api.browser-use.com/api/v4)
supporting `/runs`, `/sessions/{session_id}/queue`, `allowed_domains` domain
confinement, yellow/red confirmation gating, and HTML-free diagnostics.
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
from typing import Any, Optional
import httpx
from pydantic import BaseModel, Field

from ..config import get_settings
from ..tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.browser_cloud")

_RED_RISK_RE = re.compile(
    r"(?i)\b(?:buy|purchase|checkout|place\s+order|pay\s+now|complete\s+payment|transfer\s+money|delete\s+account|wire\s+funds|confirm\s+purchase)\b"
)
_YELLOW_RISK_RE = re.compile(
    r"(?i)\b(?:log\s*in|sign\s*in|submit\s+form|send\s+(?:email|message|dm)|post\s+(?:comment|reply|tweet)|apply\s+for|upload\s+file|book\s+ticket)\b"
)


def _sanitize_cloud_error(status_code: int, raw_text: str) -> str:
    txt = str(raw_text or "").strip()
    if "<html" in txt.lower() or "<!doctype" in txt.lower() or "<head" in txt.lower():
        clean = html.unescape(re.sub(r"<[^>]+>", " ", txt))
        clean = re.sub(r"\s+", " ", clean).strip()[:160]
        return f"Browser-Use Cloud returned HTTP {status_code} HTML gateway error ({clean or 'Bad Gateway'})."
    return f"Browser-Use Cloud returned HTTP {status_code}: {txt[:220]}"


def classify_browser_risk(task: str) -> str:
    if _RED_RISK_RE.search(task or ""):
        return "red"
    if _YELLOW_RISK_RE.search(task or ""):
        return "yellow"
    return "green"


def _resolve_browser_use_credentials() -> tuple[str | None, str]:
    settings = get_settings()
    api_key = (
        os.getenv("BROWSER_USE_API_KEY")
        or os.getenv("BROWSER_USE_API_KEY1")
        or os.getenv("BROWSER_USE_API_KEY2")
    )
    if not api_key and hasattr(settings, "browser_use_api_key") and settings.browser_use_api_key:
        api_key = settings.browser_use_api_key.get_secret_value()
    base_url = getattr(settings, "active_browser_use_base_url", None) or "https://api.browser-use.com/api/v4"
    return (api_key.strip() if api_key else None), base_url.rstrip("/")


class BrowserCloudTaskParams(BaseModel):
    model_config = {"extra": "ignore"}
    task: str = Field(..., description="The high-level autonomous browsing goal.")
    startUrl: Optional[str] = Field(None, description="Optional starting URL to open directly.")
    max_steps: int = Field(25, description="Maximum browsing steps before completing.")
    flash_mode: bool = Field(True, description="Enable faster execution mode.")
    session_id: Optional[str] = Field(None, description="Existing Browser-Use v4 session id to queue into.")
    allowed_domains: list[str] = Field(default_factory=list, description="Optional domain allowlist (e.g. ['amazon.com', 'github.com']).")
    confirmed: bool = Field(False, description="Set true after user confirms yellow/red state-changing browser actions.")


class BrowserCloudResult(BaseModel):
    task_id: str
    status: str
    output: Optional[str] = None
    live_url: Optional[str] = None
    steps_taken: int = 0
    error: Optional[str] = None


async def execute_browser_cloud_task(params: BrowserCloudTaskParams) -> dict[str, Any]:
    """Execute an autonomous browsing run on Browser-Use Cloud v4 (or queue into a session)."""
    risk_tier = classify_browser_risk(params.task)
    if risk_tier in ("yellow", "red") and not params.confirmed:
        return {
            "status": "confirmation_required",
            "requires_confirmation": True,
            "risk_tier": risk_tier,
            "provider": "browser_use_v4",
            "allowed_domains": list(params.allowed_domains),
            "summary": (
                f"Browser action classified as `{risk_tier.upper()}` risk "
                "(login, form submission, or checkout). Explicit user confirmation is required before running."
            ),
        }

    api_key, base_url = _resolve_browser_use_credentials()
    if not api_key:
        logger.info("Browser-Use API key not configured; routing to local Playwright browser agent.")
        from .browser_agent import browser_execute_task, BrowserTaskParams
        local_result = await browser_execute_task(BrowserTaskParams(
            goal=params.task,
            max_steps=min(params.max_steps, 15),
        ))
        return {
            "status": "completed",
            "provider": "local_playwright",
            "risk_tier": risk_tier,
            "summary": local_result,
        }

    headers = {
        "X-Browser-Use-API-Key": api_key,
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
    if params.allowed_domains:
        clean_domains = [str(d).strip().lower() for d in params.allowed_domains if str(d).strip()]
        if clean_domains:
            payload["allowedDomains"] = clean_domains

    is_queued = bool(params.session_id and params.session_id.strip())
    submit_url = (
        f"{base_url}/sessions/{params.session_id.strip()}/queue"
        if is_queued
        else f"{base_url}/runs"
    )
    logger.info("Submitting Browser-Use v4 %s request: %s", "queue" if is_queued else "run", params.task[:100])

    async with httpx.AsyncClient(timeout=40.0) as client:
        create_resp = await client.post(submit_url, headers=headers, json=payload)
        if create_resp.status_code not in (200, 201, 202):
            clean_err = _sanitize_cloud_error(create_resp.status_code, create_resp.text)
            logger.warning("%s; falling back to local browser for read-only tasks", clean_err)
            if risk_tier == "green":
                from .browser_agent import browser_execute_task, BrowserTaskParams
                local_result = await browser_execute_task(BrowserTaskParams(
                    goal=params.task,
                    max_steps=min(params.max_steps, 15),
                ))
                return {
                    "status": "completed",
                    "provider": "local_fallback",
                    "risk_tier": risk_tier,
                    "cloud_error": clean_err,
                    "summary": local_result,
                }
            return {
                "status": "failed",
                "provider": "browser_use_v4",
                "risk_tier": risk_tier,
                "error": clean_err,
            }

        task_data = create_resp.json()
        run_id = task_data.get("runId") or task_data.get("run_id") or task_data.get("id")
        session_id = task_data.get("sessionId") or task_data.get("session_id") or params.session_id
        if not run_id:
            if is_queued:
                return {
                    "status": str(task_data.get("status") or "queued"),
                    "provider": "browser_use_v4",
                    "session_id": session_id,
                    "risk_tier": risk_tier,
                    "output": task_data,
                    "summary": f"Queued task into Browser-Use v4 session `{session_id}`.",
                }
            return {"status": "failed", "provider": "browser_use_v4", "error": "No run id returned by Browser-Use Cloud v4."}

        logger.info("Browser-Use v4 run %s created; checking status...", run_id)
        final_data = task_data
        poll_path = f"{base_url}/runs/{run_id}"
        initial_status = str(final_data.get("status") or "").lower()
        if initial_status not in ("completed", "finished", "success", "failed", "cancelled", "stopped"):
            for _ in range(18):
                await asyncio.sleep(5.0)
                status_resp = await client.get(poll_path, headers=headers)
                if status_resp.status_code == 200:
                    final_data = status_resp.json()
                    status = str(final_data.get("status") or "").lower()
                    if status in ("completed", "finished", "success", "failed", "cancelled", "stopped"):
                        break

        status = str(final_data.get("status") or "completed")
        output = final_data.get("output") or final_data.get("result") or ""
        if not output and isinstance(final_data.get("steps"), list) and final_data["steps"]:
            last_step = final_data["steps"][-1]
            output = last_step.get("notes") or last_step.get("action") or "Task executed successfully."

        live_url = final_data.get("liveUrl") or final_data.get("shareUrl") or f"https://cloud.browser-use.com/runs/{run_id}"

        return {
            "status": status,
            "provider": "browser_use_v4",
            "run_id": run_id,
            "task_id": run_id,
            "session_id": final_data.get("sessionId") or session_id,
            "risk_tier": risk_tier,
            "allowed_domains": list(params.allowed_domains),
            "output": output or "Task completed by Browser-Use v4 autonomous cloud agent.",
            "live_url": live_url,
            "summary": f"Browser-Use v4 executed run `{run_id}`: {str(output)[:300]}",
        }


browser_cloud_def = ToolDefinition(
    name="browser_cloud_agent",
    display_name="Autonomous Cloud Browser (Browser-Use v4)",
    description=(
        "Executes multi-step browser tasks autonomously on Browser-Use Cloud v4 "
        "(`/api/v4/runs` and `/api/v4/sessions/{id}/queue`) with allowed_domains safety "
        "and yellow/red confirmation gating for logins or purchases."
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
        "session_id": {
            "type": "string",
            "description": "Optional Browser-Use v4 session id to queue another follow-up step.",
        },
        "allowed_domains": {
            "type": "array",
            "description": "Optional domain allowlist (e.g. ['github.com', 'docs.python.org']).",
        },
        "confirmed": {
            "type": "boolean",
            "description": "Set true after explicit user confirmation for yellow/red actions.",
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
