"""CustomGPT AI enterprise knowledge tool for HINAA.

Connects to CustomGPT API (https://app.customgpt.ai/api/v1) to query enterprise
project knowledge bases, uploaded documents, indexing status, and grounded answers.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field

from ..config import get_settings
from ..tools.registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.customgpt")


class CustomGPTQueryParams(BaseModel):
    model_config = {"extra": "ignore"}
    query: str = Field(..., description="The factual question or search query to ask the CustomGPT knowledge base.")
    project_id: Optional[int] = Field(None, description="Optional CustomGPT project ID (defaults to active project if omitted).")


async def query_customgpt(params: CustomGPTQueryParams) -> dict[str, Any]:
    """Query CustomGPT knowledge base for factual answers from indexed projects."""
    settings = get_settings()
    api_key = (
        os.getenv("APP_CUSTOMGPT_AI_API_KEY")
        or os.getenv("APP_COUSTOMGPT_AI_API_KEY")
        or (settings.customgpt_api_key.get_secret_value() if hasattr(settings, "customgpt_api_key") and settings.customgpt_api_key else None)
    )
    base_url = (
        os.getenv("APP_CUSTOMGPT_AI_BASE_URL")
        or os.getenv("APP_COUSTOMGPT_AI_BASE-URL")
        or (settings.customgpt_base_url if hasattr(settings, "customgpt_base_url") and settings.customgpt_base_url else "https://app.customgpt.ai")
    ).rstrip("/")

    if not api_key:
        return {
            "status": "unconfigured",
            "message": "CustomGPT API key is not configured in backend.",
        }

    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        # Step 1: Discover available projects
        try:
            p_resp = await client.get(f"{base_url}/api/v1/projects", headers=headers)
            projects_data = p_resp.json() if p_resp.status_code == 200 else {}
            projects_list = projects_data.get("data", {}).get("data", [])
        except Exception as e:
            logger.warning("CustomGPT project discovery failed: %s", e)
            projects_list = []

        target_project = None
        if params.project_id:
            target_project = next((p for p in projects_list if p.get("id") == params.project_id), None)
        elif projects_list:
            # Default to first active or first project
            target_project = next((p for p in projects_list if p.get("is_chat_active")), projects_list[0])

        if not target_project:
            return {
                "status": "no_projects",
                "message": "No CustomGPT projects found under this account.",
                "query": params.query,
            }

        proj_id = target_project.get("id")
        proj_name = target_project.get("project_name", "Enterprise Project")
        is_active = target_project.get("is_chat_active", False)

        if not is_active:
            # Return project metadata and inform user that the agent needs activation/indexing
            return {
                "status": "agent_inactive",
                "project_id": proj_id,
                "project_name": proj_name,
                "message": (
                    f"Project '{proj_name}' (ID: {proj_id}) is connected to Hina, but chat is currently inactive in CustomGPT. "
                    "To enable live query answering, activate chat or index documents inside your CustomGPT dashboard."
                ),
                "query": params.query,
            }

        # Step 2: Query active project conversation
        try:
            conv_resp = await client.post(
                f"{base_url}/api/v1/projects/{proj_id}/conversations",
                headers=headers,
                json={"name": f"Hina Query: {params.query[:40]}"},
            )
            if conv_resp.status_code not in (200, 201):
                return {
                    "status": "error",
                    "project_id": proj_id,
                    "project_name": proj_name,
                    "message": f"CustomGPT returned status {conv_resp.status_code}: {conv_resp.text[:200]}",
                }

            conv_data = conv_resp.json().get("data", {})
            session_id = conv_data.get("session_id") or conv_data.get("id")

            # Post message to session
            msg_resp = await client.post(
                f"{base_url}/api/v1/projects/{proj_id}/conversations/{session_id}/messages",
                headers=headers,
                json={"prompt": params.query, "stream": False},
            )
            if msg_resp.status_code in (200, 201):
                reply_data = msg_resp.json().get("data", {})
                answer = reply_data.get("openai_response") or reply_data.get("response") or ""
                citations = reply_data.get("citations", [])
                return {
                    "status": "success",
                    "project_id": proj_id,
                    "project_name": proj_name,
                    "answer": answer,
                    "citations": citations,
                }
            else:
                return {
                    "status": "error",
                    "project_id": proj_id,
                    "project_name": proj_name,
                    "message": f"Message dispatch failed [{msg_resp.status_code}]: {msg_resp.text[:200]}",
                }
        except Exception as e:
            logger.exception("Failed to query CustomGPT project %s", proj_id)
            return {
                "status": "exception",
                "project_id": proj_id,
                "project_name": proj_name,
                "error": str(e),
            }


customgpt_def = ToolDefinition(
    name="customgpt_query",
    display_name="Query CustomGPT Enterprise Knowledge",
    description=(
        "Queries enterprise knowledge bases, custom datasets, and document projects hosted on CustomGPT. "
        "Use when the user asks about internal company data, enterprise documents, or custom project knowledge."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "The question to ask the CustomGPT knowledge base.",
        },
        "project_id": {
            "type": "integer",
            "description": "Optional CustomGPT project ID.",
        },
    },
    required_parameters=["query"],
    voice_aliases=[
        "search enterprise knowledge",
        "check customgpt",
        "search project documents",
    ],
    requires_confirmation=False,
)

registry.register(customgpt_def, query_customgpt)
