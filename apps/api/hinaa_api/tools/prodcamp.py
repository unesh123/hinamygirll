import asyncio
import logging
import os
from typing import Any, Literal
import httpx
from pydantic import BaseModel, Field

from hinaa_api.config import get_settings
from hinaa_api.tools.registry import registry, ToolDefinition

logger = logging.getLogger("hinaa.tools.prodcamp")


def _get_api_key_and_base_url() -> tuple[str | None, str]:
    settings = get_settings()
    api_key: str | None = None
    if settings.prodcamp_api_key:
        api_key = settings.prodcamp_api_key.get_secret_value()
    if not api_key:
        api_key = os.getenv("PRODCAMP_API_KEY") or os.getenv("ProdCamp_API_KEY")

    raw_base_url = (
        getattr(settings, "prodcamp_base_url", None)
        or os.getenv("PRODCAMP_BASE_URL")
        or "https://app.prodcamp.com/api/v1"
    )
    # Normalize: if the user passes their dashboard URL (e.g. https://app.prodcamp.com/GYUSVWIVH/dashboard),
    # point to the standard REST API root.
    if "app.prodcamp.com" in raw_base_url:
        base_url = "https://app.prodcamp.com/api/v1"
    else:
        base_url = raw_base_url.rstrip("/")

    return api_key, base_url


# ---------------------------------------------------------
# Tool 1: List ProdCamp Features / Roadmap
# ---------------------------------------------------------

class ListFeaturesParams(BaseModel):
    model_config = {"extra": "ignore"}
    status: str | None = Field(None, description="Optional status filter (e.g. 'Backlog', 'Soon', 'Future').")
    search: str | None = Field(None, description="Optional search term to filter features.")
    limit: int = Field(10, description="Maximum number of features to retrieve (default 10).")


async def prodcamp_list_features(params: ListFeaturesParams) -> str | dict[str, Any]:
    """Retrieve active product roadmap features from ProdCamp."""
    api_key, base_url = _get_api_key_and_base_url()
    if not api_key:
        return "ProdCamp API key is not configured. Please set PRODCAMP_API_KEY in your environment."

    url = f"{base_url}/features?apiKey={api_key}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers={"User-Agent": "HINAA-AI/1.0", "Accept": "application/json"})
            if resp.status_code != 200:
                return f"Failed to retrieve ProdCamp features (HTTP {resp.status_code}): {resp.text[:200]}"
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return "No features found in your ProdCamp roadmap."

            # Filter if needed
            filtered = items
            if params.status:
                filtered = [
                    f for f in filtered
                    if (f.get("status") or {}).get("caption", "").lower() == params.status.lower()
                ]
            if params.search:
                s = params.search.lower()
                filtered = [
                    f for f in filtered
                    if s in (f.get("name") or "").lower()
                ]

            filtered = filtered[:params.limit]
            
            summary = [f"### 🚀 ProdCamp Product Roadmap ({len(filtered)} features shown)\n"]
            for f in filtered:
                fid = f.get("id")
                name = f.get("name")
                status = (f.get("status") or {}).get("caption", "Unknown")
                priority = (f.get("priority") or {}).get("caption", "Normal")
                upvotes = f.get("upvotesCount", 0)
                summary.append(f"- **#{fid} {name}** | Status: `{status}` | Priority: `{priority}` | Upvotes: `{upvotes}`")

            return "\n".join(summary)
    except Exception as e:
        logger.exception("Error querying ProdCamp features")
        return f"Error connecting to ProdCamp: {e}"


# ---------------------------------------------------------
# Tool 2: Submit Customer Feedback / Idea to ProdCamp
# ---------------------------------------------------------

class SubmitFeedbackParams(BaseModel):
    model_config = {"extra": "ignore"}
    content: str = Field(..., description="The user feedback, suggestion, feature request, or bug report.")
    account_name: str | None = Field(None, description="Optional account name (defaults to 'HINAA Workspace').")
    source_url: str | None = Field(None, description="Optional source URL where the feedback was collected.")


async def prodcamp_submit_feedback(params: SubmitFeedbackParams) -> str | dict[str, Any]:
    """Submit a user feedback item, suggestion, or request into ProdCamp."""
    api_key, base_url = _get_api_key_and_base_url()
    if not api_key:
        return "ProdCamp API key is not configured. Please set PRODCAMP_API_KEY in your environment."

    url = f"{base_url}/feedback?apiKey={api_key}"
    payload = {
        "content": params.content.strip(),
        "customerAccount": {
            "id": 81117,
            "accountName": params.account_name or "HINAA Workspace",
        },
        "sourceUrl": params.source_url or "https://hinaa-workspace.vercel.app",
        "sentVia": 2,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers={"User-Agent": "HINAA-AI/1.0", "Accept": "application/json"})
            if resp.status_code in (200, 201):
                res_data = resp.json()
                fb_id = res_data.get("id")
                return (
                    f"✅ **Feedback successfully logged to ProdCamp!**\n"
                    f"- Feedback ID: `#{fb_id}`\n"
                    f"- Content: *\"{params.content}\"*\n"
                    f"- View and manage in your [ProdCamp Dashboard](https://app.prodcamp.com)."
                )
            return f"Failed to submit feedback to ProdCamp (HTTP {resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        logger.exception("Error submitting ProdCamp feedback")
        return f"Error submitting feedback to ProdCamp: {e}"


# ---------------------------------------------------------
# Tool 3: Create Roadmap Feature in ProdCamp
# ---------------------------------------------------------

class CreateFeatureParams(BaseModel):
    model_config = {"extra": "ignore"}
    name: str = Field(..., description="Title of the feature or epic.")
    status_caption: Literal["Backlog", "Soon", "Future", "Under consideration"] = Field(
        "Backlog", description="Roadmap column status."
    )
    priority_caption: Literal["Low", "Normal", "High", "Critical"] = Field(
        "Normal", description="Priority level."
    )
    is_public: bool = Field(True, description="Whether the feature is visible on the public roadmap.")


async def prodcamp_create_feature(params: CreateFeatureParams) -> str | dict[str, Any]:
    """Create a new product feature card directly on the ProdCamp roadmap."""
    api_key, base_url = _get_api_key_and_base_url()
    if not api_key:
        return "ProdCamp API key is not configured. Please set PRODCAMP_API_KEY in your environment."

    status_map = {"Backlog": 1, "Under consideration": 2, "Soon": 3, "Future": 4}
    priority_map = {"Low": 1, "Normal": 2, "High": 3, "Critical": 4}

    status_id = status_map.get(params.status_caption, 1)
    priority_id = priority_map.get(params.priority_caption, 2)

    url = f"{base_url}/features?apiKey={api_key}"
    payload = {
        "name": params.name.strip(),
        "status": {"id": status_id, "caption": params.status_caption},
        "priority": {"id": priority_id, "caption": params.priority_caption},
        "isPublic": params.is_public,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers={"User-Agent": "HINAA-AI/1.0", "Accept": "application/json"})
            if resp.status_code in (200, 201):
                data = resp.json()
                feat_id = data.get("id")
                return (
                    f"🎉 **Roadmap Feature Created in ProdCamp!**\n"
                    f"- Feature: **{params.name}**\n"
                    f"- ID: `#{feat_id}`\n"
                    f"- Column: `{params.status_caption}`\n"
                    f"- Priority: `{params.priority_caption}`\n"
                    f"- Track in your [ProdCamp Roadmap](https://app.prodcamp.com)."
                )
            return f"Failed to create feature in ProdCamp (HTTP {resp.status_code}): {resp.text[:200]}"
    except Exception as e:
        logger.exception("Error creating ProdCamp feature")
        return f"Error creating feature in ProdCamp: {e}"


# ---------------------------------------------------------
# Tool Definitions & Registry Binding
# ---------------------------------------------------------

prodcamp_list_features_def = ToolDefinition(
    name="prodcamp_list_features",
    display_name="List ProdCamp Roadmap",
    description="List active product roadmap features, statuses ('Backlog', 'Soon', 'Future'), and priorities from ProdCamp.",
    parameters={
        "status": {
            "type": "string",
            "description": "Optional filter by status ('Backlog', 'Soon', 'Future').",
        },
        "search": {
            "type": "string",
            "description": "Optional keyword search term.",
        },
        "limit": {
            "type": "integer",
            "description": "Max features to return (default 10).",
        },
    },
    required_parameters=[],
    voice_aliases=["list roadmap", "check prodcamp roadmap", "show product roadmap", "what features are planned"],
    requires_confirmation=False,
)

prodcamp_submit_feedback_def = ToolDefinition(
    name="prodcamp_submit_feedback",
    display_name="Submit ProdCamp Feedback",
    description="Submit user feedback, feature ideas, or bug reports directly into ProdCamp for product tracking.",
    parameters={
        "content": {
            "type": "string",
            "description": "The feedback, suggestion, or bug report description.",
        },
        "account_name": {
            "type": "string",
            "description": "Optional account name (defaults to 'HINAA Workspace').",
        },
    },
    required_parameters=["content"],
    voice_aliases=["submit feedback", "log feedback to prodcamp", "save feature request"],
    requires_confirmation=False,
)

prodcamp_create_feature_def = ToolDefinition(
    name="prodcamp_create_feature",
    display_name="Create ProdCamp Feature",
    description="Create a new roadmap feature or epic on the ProdCamp board with priority and status.",
    parameters={
        "name": {
            "type": "string",
            "description": "The title of the feature or epic.",
        },
        "status_caption": {
            "type": "string",
            "enum": ["Backlog", "Soon", "Future", "Under consideration"],
            "description": "Roadmap column.",
        },
        "priority_caption": {
            "type": "string",
            "enum": ["Low", "Normal", "High", "Critical"],
            "description": "Feature priority level.",
        },
    },
    required_parameters=["name"],
    voice_aliases=["create roadmap feature", "add feature to prodcamp", "plan new feature"],
    requires_confirmation=True,
)

registry.register(prodcamp_list_features_def, prodcamp_list_features)
registry.register(prodcamp_submit_feedback_def, prodcamp_submit_feedback)
registry.register(prodcamp_create_feature_def, prodcamp_create_feature)
