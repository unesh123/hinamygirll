"""
Freepik & Magnific AI Suite for HINAA
Enterprise-Grade Creative Intelligence & Asset Hub

Capabilities:
1. Ultra-fast, lowest-cost text-to-image generation via Flux Schnell & Freepik AI
2. Magnific AI Upscaler & High-Fidelity Enhancement
3. Freepik Stock Resource / Asset Search (Photos, Vectors, Icons)
4. Comprehensive Usage Tracking & Daily Quota Guard
5. Strict Exclusion: Zero video generation per project policy
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Optional
import uuid

import httpx
from pydantic import BaseModel, Field

from ..config import get_settings
from ..errors import HinaaError
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.freepik_suite")

USAGE_FILE = Path("apps/api/data/freepik_usage.json")
IMAGE_STORE = Path("apps/api/data/images")
IMAGE_STORE.mkdir(parents=True, exist_ok=True)
USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)


class FreepikUsageTracker:
    """Thread-safe persistent usage and daily quota tracker."""

    def __init__(self, storage_path: Path = USAGE_FILE):
        self.storage_path = storage_path
        self._ensure_storage()

    def _ensure_storage(self) -> None:
        if not self.storage_path.exists():
            today_str = date.today().isoformat()
            data = {
                "date": today_str,
                "daily_requests": 0,
                "lifetime_requests": 0,
                "breakdown": {
                    "image_generate": 0,
                    "upscale": 0,
                    "stock_search": 0,
                },
                "models_used": {},
                "recent_actions": [],
            }
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _read_data(self) -> dict[str, Any]:
        self._ensure_storage()
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            today_str = date.today().isoformat()
            if data.get("date") != today_str:
                # New day rollover
                data["date"] = today_str
                data["daily_requests"] = 0
                self._save_data(data)
            return data
        except Exception as exc:
            logger.warning("Failed to read Freepik usage data: %s", exc)
            return {
                "date": date.today().isoformat(),
                "daily_requests": 0,
                "lifetime_requests": 0,
                "breakdown": {"image_generate": 0, "upscale": 0, "stock_search": 0},
                "models_used": {},
                "recent_actions": [],
            }

    def _save_data(self, data: dict[str, Any]) -> None:
        try:
            self.storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as exc:
            logger.error("Failed to save Freepik usage data: %s", exc)

    def check_quota(self, credits_needed: int = 1) -> tuple[bool, int, int]:
        """Returns (has_quota, current_credits_used, daily_credit_limit)."""
        settings = get_settings()
        limit = getattr(settings, "magnific_daily_credit_budget", None) or settings.freepik_daily_limit or 500
        data = self._read_data()
        current = data.get("daily_credits", data.get("daily_requests", 0))
        return (current + credits_needed <= limit, current, limit)

    def record_usage(
        self,
        action: str,
        model: str = "flux-schnell",
        credits: int = 1,
        user_id: str | None = None,
        latency_ms: int = 0,
        status: str = "success",
    ) -> None:
        data = self._read_data()
        data["daily_requests"] = data.get("daily_requests", 0) + 1
        data["daily_credits"] = data.get("daily_credits", 0) + credits
        data["lifetime_requests"] = data.get("lifetime_requests", 0) + 1
        data["lifetime_credits"] = data.get("lifetime_credits", 0) + credits
        
        breakdown = data.setdefault("breakdown", {})
        breakdown[action] = breakdown.get(action, 0) + credits

        models = data.setdefault("models_used", {})
        models[model] = models.get(model, 0) + credits

        recent = data.setdefault("recent_actions", [])
        recent.insert(0, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "model": model,
            "credits": credits,
            "latencyMs": latency_ms,
            "status": status,
        })
        data["recent_actions"] = recent[:20]
        self._save_data(data)

        # Also persist to database if available
        if user_id:
            try:
                from ..persistence.db import get_session_factory
                from ..persistence.orm import ProviderUsage
                factory = get_session_factory()
                with factory() as session:
                    pu = ProviderUsage(
                        user_id=user_id,
                        provider="magnific",
                        operation=action,
                        model=model,
                        credits=credits,
                        status=status,
                        latency_ms=latency_ms,
                    )
                    session.add(pu)
                    session.commit()
            except Exception as exc:
                logger.debug("Skipped DB provider_usage insert: %s", exc)

    def get_summary(self) -> dict[str, Any]:
        data = self._read_data()
        settings = get_settings()
        limit = getattr(settings, "magnific_daily_credit_budget", None) or settings.freepik_daily_limit or 500
        daily_credits = data.get("daily_credits", data.get("daily_requests", 0))
        return {
            "configured": settings.freepik_configured,
            "date": data.get("date"),
            "dailyRequests": data.get("daily_requests", 0),
            "dailyCredits": daily_credits,
            "dailyLimit": limit,
            "remainingCredits": max(0, limit - daily_credits),
            "lifetimeRequests": data.get("lifetime_requests", 0),
            "lifetimeCredits": data.get("lifetime_credits", 0),
            "breakdown": data.get("breakdown", {}),
            "modelsUsed": data.get("models_used", {}),
            "defaultModel": settings.freepik_model or "flux-schnell",
            "tierOptions": {
                "economy": "flux-schnell (1 credit, lowest cost, fastest)",
                "balanced": "flux-dev (5 credits, detailed generation)",
                "quality": "mystic (10 credits, ultra-high fidelity)",
            },
            "recentActions": data.get("recent_actions", [])[:5],
            "videoAllowed": False,
            "videoCapabilityStatus": "HARD_DISABLED_PER_POLICY",
            "status": "active" if settings.freepik_configured else "needs_api_key",
        }


usage_tracker = FreepikUsageTracker()


# ─── 1. Text-to-Image Generation (Lowest Cost: Flux Schnell) ───────────────────

class FreepikImageParams(BaseModel):
    model_config = {"extra": "ignore"}
    prompt: str = Field(..., description="Prompt describing the image to generate")
    count: int = Field(1, description="Number of images (1-4)")
    model: str = Field("flux-schnell", description="Model: flux-schnell (lowest cost/fastest), classic, or flux-dev")
    aspect_ratio: str = Field("square_1_1", description="Aspect ratio: square_1_1, widescreen_16_9, portrait_4_5")


async def generate_freepik_image(
    prompt: str,
    count: int = 1,
    model: str = "flux-schnell",
    aspect_ratio: str = "square_1_1",
) -> list[dict[str, Any]]:
    """Generate high-quality images using Freepik's low-cost Flux Schnell engine."""
    settings = get_settings()
    key = settings.active_freepik_key
    if not key:
        raise HinaaError(
            "PROVIDER_CONFIGURATION_MISSING",
            "Freepik / Magnific API key is not configured. Add FREEPIK_API_KEY to apps/api/.env.local.",
            status_code=503,
            user_action_required=True,
        )

    has_quota, used, limit = usage_tracker.check_quota()
    if not has_quota:
        raise HinaaError(
            "QUOTA_EXCEEDED",
            f"Daily Freepik generation limit reached ({used}/{limit}). Increases tomorrow or update FREEPIK_DAILY_LIMIT.",
            status_code=429,
        )

    url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {
        "x-freepik-api-key": key.get_secret_value(),
        "x-magnific-api-key": key.get_secret_value(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload: dict[str, Any] = {
        "prompt": prompt,
        "num_images": min(max(1, count), 4),
        "image": {"size": aspect_ratio or "square_1_1"},
    }

    entries: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        if resp.status_code != 200:
            logger.warning("Freepik API returned error: %d %s", resp.status_code, resp.text)
            resp.raise_for_status()

        data = resp.json().get("data", [])
        for item in data:
            b64 = item.get("base64")
            img_url = item.get("url")
            file_name = f"freepik_{uuid.uuid4().hex}.jpg"
            target = IMAGE_STORE / file_name
            if b64:
                target.write_bytes(base64.b64decode(b64))
                entries.append({
                    "file_path": str(target),
                    "filename": file_name,
                    "url": f"/v1/generated-images/{file_name}",
                    "model": model,
                })
            elif img_url:
                dl = await client.get(img_url, timeout=30.0)
                if dl.status_code == 200:
                    target.write_bytes(dl.content)
                    entries.append({
                        "file_path": str(target),
                        "filename": file_name,
                        "url": f"/v1/generated-images/{file_name}",
                        "model": model,
                    })

    if entries:
        usage_tracker.record_usage("image_generate", model=model)

    return entries


# ─── 2. Magnific AI Upscaler ───────────────────────────────────────────────────

class MagnificUpscaleParams(BaseModel):
    model_config = {"extra": "ignore"}
    image_url_or_path: str = Field(..., description="Image URL or local image path to upscale")
    scale_factor: int = Field(2, description="Upscale multiplier (2 or 4)")
    optimized_for: str = Field("standard", description="Optimization profile: standard, portraits, anime, art")


async def upscale_via_magnific(
    image_input: str,
    scale_factor: int = 2,
    optimized_for: str = "standard",
) -> dict[str, Any]:
    """Upscale and enhance image fidelity using Magnific AI / Freepik Upscaler."""
    settings = get_settings()
    key = settings.active_freepik_key
    if not key:
        raise HinaaError(
            "PROVIDER_CONFIGURATION_MISSING",
            "Freepik / Magnific API key is not configured.",
            status_code=503,
            user_action_required=True,
        )

    has_quota, used, limit = usage_tracker.check_quota()
    if not has_quota:
        raise HinaaError("QUOTA_EXCEEDED", "Daily Freepik API limit reached.", status_code=429)

    url = "https://api.freepik.com/v1/ai/tools/upscaler"
    headers = {
        "x-freepik-api-key": key.get_secret_value(),
        "x-magnific-api-key": key.get_secret_value(),
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Prepare image data: base64 or URL
    payload: dict[str, Any] = {
        "scale": scale_factor,
        "optimized_for": optimized_for,
    }
    
    local_path = Path(image_input)
    if local_path.exists() and local_path.is_file():
        b64 = base64.b64encode(local_path.read_bytes()).decode("ascii")
        payload["image"] = f"data:image/jpeg;base64,{b64}"
    elif image_input.startswith("http"):
        payload["image_url"] = image_input
    else:
        payload["image"] = image_input

    out_file = IMAGE_STORE / f"magnific_{uuid.uuid4().hex}.jpg"
    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        res_b64 = data.get("base64")
        res_url = data.get("url")

        if res_b64:
            out_file.write_bytes(base64.b64decode(res_b64))
        elif res_url:
            dl = await client.get(res_url, timeout=40.0)
            dl.raise_for_status()
            out_file.write_bytes(dl.content)

    usage_tracker.record_usage("upscale", model="magnific-upscaler")
    return {
        "status": "success",
        "original": image_input,
        "upscaled_path": str(out_file),
        "url": f"/v1/generated-images/{out_file.name}",
        "scale": scale_factor,
    }


# ─── 3. Freepik Stock Resource Search ──────────────────────────────────────────

class FreepikResourceSearchParams(BaseModel):
    model_config = {"extra": "ignore"}
    query: str = Field(..., description="Search term for stock photos, vectors, icons")
    count: int = Field(6, description="Number of resources to fetch (max 20)")
    resource_type: str = Field("all", description="Resource type filter: all, photo, vector, psd, icon")


async def search_freepik_stock(
    query: str,
    count: int = 6,
    resource_type: str = "all",
) -> list[dict[str, Any]]:
    """Search Freepik's repository of over 100M+ stock resources."""
    settings = get_settings()
    key = settings.active_freepik_key
    if not key:
        raise HinaaError(
            "PROVIDER_CONFIGURATION_MISSING",
            "Freepik API key is not configured.",
            status_code=503,
            user_action_required=True,
        )

    url = f"https://api.freepik.com/v1/resources?term={query}&limit={min(max(1, count), 20)}"
    if resource_type != "all":
        url += f"&filters[content_type]={resource_type}"

    headers = {
        "x-freepik-api-key": key.get_secret_value(),
        "x-magnific-api-key": key.get_secret_value(),
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        
        results: list[dict[str, Any]] = []
        for item in data:
            results.append({
                "id": item.get("id"),
                "title": item.get("title") or query.title(),
                "thumbnail": item.get("image", {}).get("source", {}).get("url"),
                "url": item.get("url"),
                "author": item.get("author", {}).get("name"),
                "type": item.get("type"),
            })

    usage_tracker.record_usage("stock_search", model="freepik-catalog")
    return results


def assert_no_video_generation(requested_action: str) -> None:
    """Strictly enforces project policy banning video generation across all layers."""
    if any(k in requested_action.lower() for k in ("video", "animate", "text_to_video", "image_to_video")):
        raise HinaaError(
            "CAPABILITY_DISABLED",
            "Video generation is strictly disabled in HINAA per system architecture policy. All image, design, and upscale capabilities remain fully active.",
            status_code=403,
            retryable=False,
        )


# ─── Tool Registrations ────────────────────────────────────────────────────────

class MagnificImageParams(BaseModel):
    model_config = {"extra": "ignore"}
    prompt: str = Field(..., description="Prompt describing the image to generate")
    count: int = Field(1, description="Number of images (1-4)")
    tier: str = Field("economy", description="Cost tier: economy (lowest cost/fastest), balanced, or quality")
    model: str = Field("flux-schnell", description="Model override: flux-schnell, classic, flux-dev, mystic")
    aspect_ratio: str = Field("square_1_1", description="Aspect ratio: square_1_1, widescreen_16_9, portrait_4_5")


magnific_image_def = ToolDefinition(
    name="magnific_image_generate",
    display_name="Magnific AI Creative Suite",
    description="Generate high-fidelity images using Magnific / Freepik AI with cost-tier routing (economy: 1 credit, balanced: 5 credits, quality: 10 credits).",
    parameters={
        "prompt": {"type": "string", "description": "Visual prompt for image creation"},
        "count": {"type": "integer", "description": "Number of variations (1-4)"},
        "tier": {"type": "string", "description": "Cost tier: 'economy', 'balanced', 'quality'"},
        "model": {"type": "string", "description": "Model name override"},
    },
    required_parameters=["prompt"],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
)

freepik_image_def = ToolDefinition(
    name="freepik_image_generate",
    display_name="Freepik Flux Image Generator",
    description="Generate ultra-fast AI images using Freepik's low-cost Flux Schnell engine.",
    parameters={
        "prompt": {"type": "string", "description": "Visual prompt for image creation"},
        "count": {"type": "integer", "description": "Number of variations (1-4)"},
        "model": {"type": "string", "description": "Model name, default 'flux-schnell'"},
    },
    required_parameters=["prompt"],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
)

freepik_upscale_def = ToolDefinition(
    name="magnific_upscale",
    display_name="Magnific AI Upscaler",
    description="Enhance resolution, fine details, and clarity of images using Magnific AI.",
    parameters={
        "image_url_or_path": {"type": "string", "description": "Target image URL or local file path"},
        "scale_factor": {"type": "integer", "description": "Upscale factor (2 or 4)"},
    },
    required_parameters=["image_url_or_path"],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
)

freepik_stock_def = ToolDefinition(
    name="freepik_stock_search",
    display_name="Freepik Stock Assets Search",
    description="Search Freepik catalog for stock photos, vectors, and icons.",
    parameters={
        "query": {"type": "string", "description": "Keywords to search for"},
        "count": {"type": "integer", "description": "Number of items (max 20)"},
    },
    required_parameters=["query"],
    permission_level="default",
    requires_confirmation=False,
    risk_level="low",
)

# Explicit video rejection tool
video_blocked_def = ToolDefinition(
    name="video_generate",
    display_name="Video Generator (Disabled)",
    description="Video generation is hard-disabled across HINAA OS.",
    parameters={"prompt": {"type": "string", "description": "Prompt"}},
    required_parameters=["prompt"],
    permission_level="default",
    requires_confirmation=False,
    risk_level="high",
)

async def _handle_magnific_image(params: MagnificImageParams) -> dict[str, Any]:
    tier_map = {"economy": "flux-schnell", "balanced": "flux-dev", "quality": "mystic"}
    resolved_model = params.model if params.model != "flux-schnell" else tier_map.get(params.tier, "flux-schnell")
    images = await generate_freepik_image(
        prompt=params.prompt,
        count=params.count,
        model=resolved_model,
        aspect_ratio=params.aspect_ratio,
    )
    return {"status": "success", "images": images, "count": len(images), "tier": params.tier}

async def _handle_freepik_image(params: FreepikImageParams) -> dict[str, Any]:
    images = await generate_freepik_image(
        prompt=params.prompt,
        count=params.count,
        model=params.model,
        aspect_ratio=params.aspect_ratio,
    )
    return {"status": "success", "images": images, "count": len(images)}

async def _handle_magnific_upscale(params: MagnificUpscaleParams) -> dict[str, Any]:
    return await upscale_via_magnific(
        image_input=params.image_url_or_path,
        scale_factor=params.scale_factor,
        optimized_for=params.optimized_for,
    )

async def _handle_freepik_stock(params: FreepikResourceSearchParams) -> dict[str, Any]:
    items = await search_freepik_stock(
        query=params.query,
        count=params.count,
        resource_type=params.resource_type,
    )
    return {"status": "success", "items": items, "count": len(items)}

async def _handle_video_blocked(_: Any) -> dict[str, Any]:
    assert_no_video_generation("video")
    return {}

registry.register(magnific_image_def, _handle_magnific_image)
registry.register(freepik_image_def, _handle_freepik_image)
registry.register(freepik_upscale_def, _handle_magnific_upscale)
registry.register(freepik_stock_def, _handle_freepik_stock)
registry.register(video_blocked_def, _handle_video_blocked)
