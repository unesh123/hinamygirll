"""Dynamic xKiro AI Model Catalog Manager & Live Discovery Service.

Retrieves and validates model identifiers directly from xKiro's official
GET /v1/models endpoint (https://docs.xkiro.com), classifies them by capability
and latency tier, and enforces server-side model validation without unsafe wildcards.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

# Verified benchmarked models on xKiro (proven 200 OK with measured latencies)
VERIFIED_XKIRO_MODELS: list[dict[str, Any]] = [
    {
        "id": "mistralai/codestral-2508",
        "name": "Codestral 2508",
        "tier": "fast_free",
        "description": "Fastest coding & conversational model on xKiro (~1.8-2.5s)",
        "is_default": True,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "mistralai/ministral-14b",
        "name": "Ministral 14B",
        "tier": "fast_free",
        "description": "Fast multilingual & conversational reasoning model (~2.2s)",
        "is_default": False,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "mistralai/mistral-large-2512",
        "name": "Mistral Large 2512",
        "tier": "large_free",
        "description": "Frontier open-weights model for complex code & reasoning (~2.8s)",
        "is_default": False,
        "context_window": 128000,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "mistralai/ministral-8b",
        "name": "Ministral 8B",
        "tier": "fast_free",
        "description": "Ultra-lightweight conversational model (~2.3s)",
        "is_default": False,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "qwen/qwen3.8-max:free",
        "name": "Qwen 3.8 Max (Free)",
        "tier": "large_free",
        "description": "High-capacity reasoning brain (traffic-variable ~5-17s)",
        "is_default": False,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "qwen/qwen3.7-max:free",
        "name": "Qwen 3.7 Max (Free)",
        "tier": "large_free",
        "description": "Qwen frontier model for multi-turn planning (~8.5s)",
        "is_default": False,
        "context_window": 32768,
        "supports_streaming": True,
        "supports_tools": True,
    },
    {
        "id": "cohere/command-a-reasoning",
        "name": "Cohere Command A",
        "tier": "reasoning_free",
        "description": "Chain-of-thought enterprise reasoning model (~7.5s)",
        "is_default": False,
        "context_window": 64000,
        "supports_streaming": True,
        "supports_tools": True,
    },
]


class XKiroCatalogManager:
    """Manages dynamic retrieval, caching, and server-side validation of xKiro models."""

    def __init__(self, base_url: str = "https://api.xkiro.com/v1", ttl_seconds: int = 3600) -> None:
        self.base_url = base_url.rstrip("/")
        self.ttl_seconds = ttl_seconds
        self._cached_catalog: list[dict[str, Any]] = list(VERIFIED_XKIRO_MODELS)
        self._raw_model_ids: set[str] = {m["id"] for m in VERIFIED_XKIRO_MODELS}
        self._last_fetched: float = 0.0
        self._lock = asyncio.Lock()

    async def get_models(self, api_key: Optional[str] = None, force_refresh: bool = False) -> list[dict[str, Any]]:
        """Return the list of models, refreshing from the remote catalog if expired."""
        now = time.time()
        if not force_refresh and (now - self._last_fetched < self.ttl_seconds) and self._cached_catalog:
            return self._cached_catalog

        if not api_key:
            return self._cached_catalog

        async with self._lock:
            if not force_refresh and (time.time() - self._last_fetched < self.ttl_seconds):
                return self._cached_catalog

            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.get(
                        f"{self.base_url}/models",
                        headers={"Authorization": f"Bearer {api_key}"},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_list = data.get("data", [])
                        new_ids = {item["id"] for item in raw_list if isinstance(item, dict) and "id" in item}
                        if new_ids:
                            self._raw_model_ids.update(new_ids)
                            
                            # Merge remote models with our metadata
                            merged: list[dict[str, Any]] = []
                            verified_map = {m["id"]: m for m in VERIFIED_XKIRO_MODELS}
                            
                            # Add verified models first (preserving priority order)
                            for v in VERIFIED_XKIRO_MODELS:
                                merged.append(v)

                            # Add any new free / mistral / qwen models discovered remotely
                            for item in raw_list:
                                mid = item.get("id")
                                if mid and mid not in verified_map:
                                    is_free = ":free" in mid or "free" in mid or "mistral" in mid
                                    merged.append({
                                        "id": mid,
                                        "name": mid.split("/")[-1].replace("-", " ").title(),
                                        "tier": "discovered_free" if is_free else "payg",
                                        "description": f"Discovered xKiro model ({item.get('owned_by', 'xkiro')})",
                                        "is_default": False,
                                        "context_window": item.get("context_window", 32768),
                                        "supports_streaming": True,
                                        "supports_tools": True,
                                    })
                            self._cached_catalog = merged
                            self._last_fetched = time.time()
                            logger.info("Successfully refreshed xKiro catalog: %d models total", len(merged))
            except Exception as exc:
                logger.warning("Failed to refresh xKiro catalog remotely (%s); using verified baseline", exc)

        return self._cached_catalog

    def is_model_valid(self, model_id: str) -> bool:
        """Server-side check: verify if model_id is known to the xKiro catalog."""
        clean = model_id.strip()
        if not clean:
            return False
        if clean in self._raw_model_ids:
            return True
        for m in self._cached_catalog:
            if m["id"] == clean:
                return True
        return False

    def default_model(self) -> str:
        """Return the default recommended fast free model."""
        return "mistralai/codestral-2508"


_GLOBAL_CATALOG_MANAGER: Optional[XKiroCatalogManager] = None


def get_xkiro_catalog_manager(base_url: str = "https://api.xkiro.com/v1") -> XKiroCatalogManager:
    global _GLOBAL_CATALOG_MANAGER
    if _GLOBAL_CATALOG_MANAGER is None:
        _GLOBAL_CATALOG_MANAGER = XKiroCatalogManager(base_url=base_url)
    return _GLOBAL_CATALOG_MANAGER
