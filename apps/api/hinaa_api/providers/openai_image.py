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
        settings_img_key = (
            self.settings.openai_image_api_key.get_secret_value()
            if getattr(self.settings, "openai_image_api_key", None)
            else None
        )
        self._key = (
            os.getenv("OPENAI_IMAGE_API_KEY")
            or os.getenv("IMAGE_PROXY_API_KEY")
            or os.getenv("OPENAI_API_KEY")
            or settings_img_key
            or (self.settings.openai_api_key.get_secret_value() if self.settings.openai_api_key else None)
        )
        if self._key:
            self._key = self._key.strip()

        raw_base = (
            os.getenv("OPENAI_IMAGE_BASE_URL")
            or os.getenv("IMAGE_PROXY_BASE_URL")
            or os.getenv("OPENAI_BASE_URL")
            or getattr(self.settings, "openai_image_base_url", None)
            or "https://api.openai.com/v1"
        )
        self.base_url = str(raw_base).strip().rstrip("/")
        if not self.base_url.endswith("/v1") and "api.openai.com" in self.base_url:
            self.base_url = f"{self.base_url}/v1"

        self.model = (
            os.getenv("OPENAI_IMAGE_MODEL")
            or os.getenv("IMAGE_MODEL")
            or getattr(self.settings, "openai_image_model", None)
            or ("gpt-image-2.5-sunburst" if "api.openai.com" in self.base_url else "")
        ).strip()

    def available(self) -> bool:
        lower_url = self.base_url.lower()
        if any(bad in lower_url for bad in ("testproxy.com", "testproxy.local", "invalid.local")):
            return False
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

        is_gpt_image = self.model.startswith("gpt-image-") or "/gpt-image-" in self.model
        if is_gpt_image:
            size = "1536x1024" if width > height else "1024x1536" if height > width else "1024x1024"

        headers = {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

        full_prompt = prompt
        if negative_prompt:
            full_prompt = f"{prompt} [Negative: {negative_prompt}]"

        is_xkiro = "xkiro.com" in self.base_url.lower()
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": full_prompt,
            "n": 1,
            "size": size,
        }
        if not is_xkiro:
            if is_gpt_image:
                payload["output_format"] = "png"
            else:
                payload["response_format"] = "b64_json"
            if seed is not None and seed > 0 and not is_gpt_image:
                payload["seed"] = seed

        url = f"{self.base_url}/images/generations"
        logger.info("Dispatching image request to OpenAI-compatible provider [%s] at %s...", self.model, url)

        import asyncio

        async def _extract_result(client: httpx.AsyncClient, body: Dict[str, Any], used_model: str) -> OpenAIImageResult:
            items = body.get("data", [])
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
                    provider=f"openai_proxy_{used_model}",
                    model=used_model,
                )
            img_url = first.get("url")
            if img_url:
                img_resp = await client.get(img_url, timeout=30.0)
                if img_resp.status_code == 200 and len(img_resp.content) > 64:
                    raw_bytes = img_resp.content
                    b64_encoded = base64.b64encode(raw_bytes).decode("ascii")
                    return OpenAIImageResult(
                        image_bytes=raw_bytes,
                        base64_data=b64_encoded,
                        seed=seed,
                        provider=f"openai_proxy_{used_model}",
                        model=used_model,
                    )
            raise RuntimeError("Provider returned image record with neither b64_json nor fetchable url.")

        async def _run_single(client: httpx.AsyncClient, req_payload: Dict[str, Any]) -> OpenAIImageResult:
            resp = await client.post(url, headers=headers, json=req_payload)
            if resp.status_code == 200:
                return await _extract_result(client, resp.json(), req_payload["model"])

            if resp.status_code == 202:
                job_data = resp.json()
                job_id = job_data.get("id")
                if not job_id:
                    raise RuntimeError(f"Async image job missing id: {resp.text[:300]}")
                poll_url = f"{url}/{job_id}"
                for _ in range(45):
                    await asyncio.sleep(1.5)
                    poll_resp = await client.get(poll_url, headers=headers, timeout=20.0)
                    if poll_resp.status_code != 200:
                        continue
                    pdata = poll_resp.json()
                    status = str(pdata.get("status") or "").lower()
                    if status in {"succeeded", "completed", "done"}:
                        return await _extract_result(client, pdata, req_payload["model"])
                    if status in {"failed", "error", "cancelled"}:
                        err_detail = pdata.get("error") or pdata
                        raise RuntimeError(f"Async image job {job_id} failed: {err_detail}")
                raise RuntimeError(f"Async image job {job_id} timed out after 67s.")

            if resp.status_code == 400 and "response_format" in resp.text and "response_format" in req_payload:
                retry_payload = {**req_payload, "response_format": "url"}
                resp_retry = await client.post(url, headers=headers, json=retry_payload)
                if resp_retry.status_code == 200:
                    return await _extract_result(client, resp_retry.json(), req_payload["model"])

            err_text = resp.text[:400]
            logger.error("OpenAI-compatible image provider returned [%d]: %s", resp.status_code, err_text)
            raise RuntimeError(f"OpenAI-compatible image generation failed [{resp.status_code}]: {err_text}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                return await _run_single(client, payload)
            except Exception as primary_err:
                if is_xkiro and self.model != "sensenova/sensenova-u1.5-lite":
                    logger.warning(
                        "XKiro image model %s failed (%s); falling back to sensenova/sensenova-u1.5-lite",
                        self.model,
                        primary_err,
                    )
                    fallback_payload = {
                        "model": "sensenova/sensenova-u1.5-lite",
                        "prompt": full_prompt,
                        "n": 1,
                    }
                    return await _run_single(client, fallback_payload)
                raise
