"""
Treg.to Unified Agent Tool Gateway for Hina
Provides server-side authenticated proxy execution across 4,000+ developer and SaaS endpoints
(113 providers: social trend scraping, anti-bot residential proxies, Seedance 2.5 video generation,
SERP/SEO, Slack, cloud compute).
"""

from __future__ import annotations

import logging
import os
from typing import Any
import httpx
from pydantic import BaseModel, Field

from hinaa_api.tools.registry import ToolDefinition, registry

logger = logging.getLogger(__name__)

DEFAULT_TREG_BASE_URL = "https://treg.to"


class TregCallParams(BaseModel):
    endpoint: str = Field(
        ...,
        description=(
            "The Treg catalog endpoint to invoke, e.g. 'instagram.search.reels', "
            "'douyin.search.videos', 'seedance.generate_clip', 'meta.ads_library', "
            "'google.search', 'apify.tiktok-scraper', or 'slack.post_message'."
        ),
    )
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="JSON arguments required by the target catalog endpoint.",
    )
    timeout_seconds: float = Field(
        60.0,
        ge=5.0,
        le=300.0,
        description="Maximum request timeout in seconds.",
    )


async def execute_treg_call(
    endpoint: str,
    payload: dict[str, Any],
    token: str | None = None,
    base_url: str = DEFAULT_TREG_BASE_URL,
    timeout_seconds: float = 60.0,
) -> dict[str, Any]:
    """
    Executes an authenticated server-side POST to Treg's unified tool gateway.
    Injects X-Treg-Token securely without exposing credentials to the client.
    """
    clean_endpoint = endpoint.strip().lstrip("/")
    if not clean_endpoint:
        return {"error": "Missing endpoint. Provide a catalog endpoint such as 'instagram.search.reels'."}

    effective_token = token or os.getenv("TREG_TOKEN") or os.getenv("HINAA_TREG_TOKEN") or os.getenv("TRIG_TOKEN")
    if not effective_token:
        return {
            "error": "Treg token is not configured.",
            "hint": "Set TREG_TOKEN in your .env or environment to unlock 4,000+ catalog tools, or use native fallback tools.",
            "status": "missing_token",
        }

    clean_base = (base_url or DEFAULT_TREG_BASE_URL).rstrip("/")
    # Treg route specification: POST https://treg.to/call/{tool_name}
    url = f"{clean_base}/call/{clean_endpoint}"

    headers = {
        "X-Treg-Token": effective_token,
        "Authorization": f"Bearer {effective_token}",
        "Content-Type": "application/json",
        "User-Agent": "Hinaa-AI-Agent/2.5",
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=True) as client:
            resp = await client.post(url, json=payload, headers=headers)
            
            if resp.status_code == 401 or resp.status_code == 403:
                return {
                    "error": f"Treg authentication failed ({resp.status_code}). Verify your TREG_TOKEN.",
                    "status_code": resp.status_code,
                    "body": resp.text[:500],
                }
            elif resp.status_code == 429:
                return {
                    "error": "Treg rate limit or quota exceeded.",
                    "status_code": resp.status_code,
                    "retry_after": resp.headers.get("Retry-After", "60"),
                }
            
            resp.raise_for_status()
            try:
                data = resp.json()
                return {"success": True, "endpoint": clean_endpoint, "data": data}
            except Exception:
                return {"success": True, "endpoint": clean_endpoint, "raw": resp.text}

    except httpx.TimeoutException:
        logger.warning("Treg gateway request timed out for endpoint %s", clean_endpoint)
        return {
            "error": f"Treg endpoint '{clean_endpoint}' timed out after {timeout_seconds}s.",
            "status": "timeout",
        }
    except Exception as exc:
        logger.error("Treg call failed for endpoint %s: %s", clean_endpoint, exc)
        return {
            "error": f"Treg call failed: {exc}",
            "status": "network_error",
        }


async def treg_call_handler(params: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    settings = context.get("settings")
    token = None
    base_url = DEFAULT_TREG_BASE_URL

    if settings:
        if getattr(settings, "treg_token", None):
            secret = settings.treg_token
            token = secret.get_secret_value() if hasattr(secret, "get_secret_value") else str(secret)
        if getattr(settings, "treg_base_url", None):
            base_url = settings.treg_base_url

    endpoint = str(params.get("endpoint", "")).strip()
    payload = params.get("payload") or {}
    timeout = float(params.get("timeout_seconds", 60.0))

    return await execute_treg_call(
        endpoint=endpoint,
        payload=payload,
        token=token,
        base_url=base_url,
        timeout_seconds=timeout,
    )


registry.register(
    ToolDefinition(
        name="treg_call",
        display_name="Treg.to Tool Gateway",
        description=(
            "Execute tools from the Treg.to catalog (4,000+ endpoints across 113 providers: "
            "TikTok/Instagram trend scrapers, Seedance 2.5 talking-head video generation, Meta Ads Library, "
            "SERP, anti-bot residential proxies, and cloud APIs) using server-side key injection."
        ),
        parameters=TregCallParams.model_json_schema()["properties"],
        required_parameters=["endpoint"],
        requires_confirmation=False,
        risk_level="medium",
        voice_aliases=["call treg", "run treg tool", "treg proxy"],
    ),
    treg_call_handler,
)
