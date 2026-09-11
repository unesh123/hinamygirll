from __future__ import annotations

import base64
import logging
import time
from typing import Any
import httpx
from ..config import Settings
from .base import ProviderResult

logger = logging.getLogger("hinaa.providers.anthropic_direct")


def build_anthropic_content(text: str, attachments: list[Any] | None = None) -> list[dict[str, Any]] | str:
    if not attachments:
        return text
    blocks: list[dict[str, Any]] = []
    for att in attachments:
        mime = getattr(att, "mime_type", "image/png")
        data = getattr(att, "bytes_data", None)
        if not data:
            continue
        b64 = base64.b64encode(data).decode("utf-8")
        if mime.startswith("image/"):
            blocks.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64,
                },
            })
        elif mime == "application/pdf":
            blocks.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": mime,
                    "data": b64,
                },
            })
    blocks.append({"type": "text", "text": text})
    return blocks


class AnthropicDirectProvider:
    """Direct client for Anthropic's official Messages API (https://api.anthropic.com/v1/messages).

    Bypasses broken intermediary proxies and reverse gateways.
    """

    id = "anthropic-direct"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        self.base_url = "https://api.anthropic.com/v1"
        self.default_model = "claude-3-7-sonnet-20250219"

    def _get_api_key(self) -> str:
        key = self.settings.claude_api_key
        if key:
            return key.get_secret_value()
        return ""

    async def health(self) -> bool:
        """Checks whether Anthropic direct API key is configured."""
        return bool(self._get_api_key())

    async def generate(
        self,
        prompt: str | list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int = 2048,
        attachments: list[Any] | None = None,
    ) -> ProviderResult[str]:
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")

        selected_model = model or self.default_model
        start_time = time.time()

        headers = {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        if isinstance(prompt, str):
            user_content = build_anthropic_content(prompt, attachments)
        else:
            user_content = prompt

        payload: dict[str, Any] = {
            "model": selected_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_content}],
        }
        if system:
            payload["system"] = system

        client = self._client or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.post(f"{self.base_url}/messages", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content_blocks = data.get("content", [])
            text_blocks = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            result_text = "".join(text_blocks)
            latency = int((time.time() - start_time) * 1000)
            return ProviderResult(
                value=result_text,
                provider=self.id,
                latency_ms=latency,
            )
        finally:
            if not self._client:
                await client.aclose()
