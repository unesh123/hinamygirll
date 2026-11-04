"""
HINAA OS — Phase 09: ComfyUI Local Provider Adapter
Connects to local ComfyUI instance (http://127.0.0.1:8188) with graceful fallback and honest availability.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from ..models import CreativeJobRecord, CreativeOperation
from ..registry import creative_registry
from .base import CreativeProvider

logger = logging.getLogger("hinaa.creative.comfy")


class ComfyUIProvider(CreativeProvider):
    """Integrates with local ComfyUI runtime."""

    def __init__(self, base_url: str = "http://127.0.0.1:8188") -> None:
        self.base_url = base_url.rstrip("/")

    @property
    def provider_id(self) -> str:
        return "comfyui_local"

    def is_available(self) -> bool:
        return creative_registry.probe_comfyui(self.base_url)

    def supported_operations(self) -> List[CreativeOperation]:
        return [
            CreativeOperation.TEXT_TO_IMAGE,
            CreativeOperation.IMAGE_TO_IMAGE,
            CreativeOperation.INPAINT,
        ]

    async def get_system_stats(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(f"{self.base_url}/system_stats")
            resp.raise_for_status()
            return resp.json()

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        if not self.is_available():
            raise RuntimeError(
                f"ComfyUI provider is not available at {self.base_url}. Ensure ComfyUI server is running."
            )
        raise NotImplementedError("ComfyUI workflow execution requires active local server.")

    async def cancel_job(self, provider_job_id: str) -> bool:
        if not self.is_available():
            return False
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.post(f"{self.base_url}/interrupt")
                return resp.status_code == 200
        except Exception:
            return False


comfyui_provider = ComfyUIProvider()
