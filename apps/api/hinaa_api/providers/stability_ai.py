"""Stability AI generative image provider for HINAA.

Leverages Stability AI's Stable Image Core & SD3 APIs for high-resolution,
aesthetic generative diffusion when cloud image generation is requested.
"""

from __future__ import annotations

import base64
import logging
from typing import Optional
import httpx
from pydantic import BaseModel

from ..config import Settings, get_settings

logger = logging.getLogger("hinaa.providers.stability_ai")


class StabilityImageResult(BaseModel):
    image_bytes: bytes
    base64_data: str
    finish_reason: str = "SUCCESS"
    seed: Optional[int] = None
    provider: str = "stabilityai"


class StabilityAIProvider:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._key: Optional[str] = None
        if self.settings.stabilityai_api_key:
            self._key = self.settings.stabilityai_api_key.get_secret_value().strip()
        self.base_url = (self.settings.stabilityai_base_url or "https://api.stability.ai").rstrip("/")
        if "platform.stability.ai" in self.base_url:
            self.base_url = "https://api.stability.ai"

    def available(self) -> bool:
        return bool(self._key and len(self._key) > 8)

    async def generate_image(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        aspect_ratio: str = "1:1",
        seed: Optional[int] = None,
        output_format: str = "png",
        style_preset: Optional[str] = None,
    ) -> StabilityImageResult:
        if not self.available():
            raise RuntimeError("Stability AI API key is not configured.")

        # Map common dimensions or strings to supported aspect ratios
        valid_ratios = {"16:9", "1:1", "21:9", "2:3", "3:2", "4:5", "5:4", "9:16", "9:21"}
        ratio = aspect_ratio if aspect_ratio in valid_ratios else "1:1"

        files: dict[str, tuple[None, str]] = {
            "prompt": (None, prompt[:10000]),
            "output_format": (None, output_format),
            "aspect_ratio": (None, ratio),
        }
        if negative_prompt:
            files["negative_prompt"] = (None, negative_prompt[:10000])
        if seed is not None and seed > 0:
            files["seed"] = (None, str(seed % 4294967295))
        if style_preset and style_preset != "custom":
            preset_map = {
                "anime": "anime",
                "realistic": "photographic",
                "cinematic": "cinematic",
                "3d-art": "3d-model",
                "watercolor": "analog-film",
                "digital": "digital-art",
            }
            if style_preset in preset_map:
                files["style_preset"] = (None, preset_map[style_preset])

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Accept": "application/json",
        }

        url = f"{self.base_url}/v2beta/stable-image/generate/core"
        logger.info("Dispatching image generation to Stability AI Core (%s)...", url)

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, headers=headers, files=files)
            if resp.status_code != 200:
                err_text = resp.text[:400]
                logger.error("Stability AI error [%d]: %s", resp.status_code, err_text)
                raise RuntimeError(f"Stability AI generation failed [{resp.status_code}]: {err_text}")

            data = resp.json()
            b64_image = data.get("image")
            if not b64_image:
                raise RuntimeError("Stability AI returned empty image response.")

            raw_bytes = base64.b64decode(b64_image)
            finish_reason = data.get("finish_reason", "SUCCESS")
            ret_seed = data.get("seed", seed)

            return StabilityImageResult(
                image_bytes=raw_bytes,
                base64_data=b64_image,
                finish_reason=finish_reason,
                seed=ret_seed,
            )
