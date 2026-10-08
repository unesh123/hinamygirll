"""OpenAI-compatible generative image provider for HINAA.

Enables seamless integration with any OpenAI-compatible image endpoint:
- Custom Gemini 3.1 Flash Image (Nano Banana 2) proxies
- OpenRouter, Together AI, Fal.ai, DeepInfra, Replicate proxies
- Official OpenAI DALL-E 3
"""

from __future__ import annotations

import base64
import logging
import os
from typing import Optional, Any, Dict
import httpx
from pydantic import BaseModel

from ..config import Settings, get_settings

logger = logging.getLogger("hinaa.providers.openai_image")


class OpenAIImageResult(BaseModel):
    image_bytes: bytes
    base64_data: str
    finish_reason: str = "SUCCESS"
    seed: Optional[int] = None
    provider: str = "openai_image_proxy"
    model: str = "gemini-3.1-flash-image"


class OpenAIImageProvider:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._key = (
            os.getenv("OPENAI_IMAGE_API_KEY")
            or os.getenv("IMAGE_PROXY_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or (self.settings.openai_api_key.get_secret_value() if self.settings.openai_api_key else None)
        )
        if self._key:
            self._key = self._key.strip()

        raw_base = (
            os.getenv("OPENAI_IMAGE_BASE_URL")
            or os.getenv("IMAGE_PROXY_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        self.base_url = str(raw_base).strip().rstrip("/")
        if not self.base_url.endswith("/v1") and "api.openai.com" in self.base_url:
            self.base_url = f"{self.base_url}/v1"

        self.model = (
            os.getenv("OPENAI_IMAGE_MODEL")
            or os.getenv("IMAGE_MODEL")
            or ("gpt-image-2.5-sunburst" if "api.openai.com" in self.base_url else "")
        ).strip()

    def available(self) -> bool:
        return bool(self._key and len(self._key) >= 6 and self.model)

    async def generate_image(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        style_preset: Optional[str] = None,
    ) -> OpenAIImageResult:
        if not self.available():
            raise RuntimeError("OpenAI image provider API key is not configured.")

        # Match dimensions to closest supported OpenAI size
        if width > height:
            size = "1792x1024" if width >= 1400 else "1024x1024"
        elif height > width:
            size = "1024x1792" if height >= 1400 else "1024x1024"
        else:
            size = "1024x1024"

        is_gpt_image = self.model.startswith("gpt-image-")
        if is_gpt_image:
            size = "1536x1024" if width > height else "1024x1536" if height > width else "1024x1024"

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt} [Negative: {negative_prompt}]"

        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": full_prompt,
            "n": 1,
            "size": size,
        }
        if is_gpt_image:
            payload["output_format"] = "png"
        else:
            payload["response_format"] = "b64_json"
        if seed is not None and seed > 0 and not is_gpt_image:
            payload["seed"] = seed

        url = f"{self.base_url}/images/generations"
        logger.info("Dispatching image request to OpenAI-compatible provider [%s] at %s...", self.model, url)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                if not items:
                    raise RuntimeError("Provider returned empty data list.")
                first = items[0]
                b64_str = first.get("b64_json")
                if b64_str:
                    raw_bytes = base64.b64decode(b64_str)
                    return OpenAIImageResult(
                        image_bytes=raw_bytes,
                        base64_data=b64_str,
                        seed=seed,
                        provider=f"openai_proxy_{self.model}",
                        model=self.model,
                    )
                img_url = first.get("url")
                if img_url:
                    img_resp = await client.get(img_url, timeout=30.0)
                    if img_resp.status_code == 200:
                        raw_bytes = img_resp.content
                        b64_encoded = base64.b64encode(raw_bytes).decode("ascii")
                        return OpenAIImageResult(
                            image_bytes=raw_bytes,
                            base64_data=b64_encoded,
                            seed=seed,
                            provider=f"openai_proxy_{self.model}",
                            model=self.model,
                        )

            # If standard endpoint failed or returned non-200, check if error was response format related
            if resp.status_code == 400 and "response_format" in resp.text:
                # Retry with standard url response format
                payload["response_format"] = "url"
                resp_retry = await client.post(url, headers=headers, json=payload)
                if resp_retry.status_code == 200:
                    data = resp_retry.json()
                    first = data.get("data", [{}])[0]
                    img_url = first.get("url")
                    if img_url:
                        img_resp = await client.get(img_url, timeout=30.0)
                        if img_resp.status_code == 200:
                            raw_bytes = img_resp.content
                            b64_encoded = base64.b64encode(raw_bytes).decode("ascii")
                            return OpenAIImageResult(
                                image_bytes=raw_bytes,
                                base64_data=b64_encoded,
                                seed=seed,
                                provider=f"openai_proxy_{self.model}",
                                model=self.model,
                            )

            err_text = resp.text[:400]
            logger.error("OpenAI-compatible image provider returned [%d]: %s", resp.status_code, err_text)
            raise RuntimeError(f"OpenAI-compatible image generation failed [{resp.status_code}]: {err_text}")
