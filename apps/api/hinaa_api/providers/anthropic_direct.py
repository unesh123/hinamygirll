from __future__ import annotations

import base64
import logging
import time
from typing import Any
import httpx

from ..ops import genai
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


_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


class AnthropicDirectProvider:
    """Direct client for Anthropic's official Messages API (https://api.anthropic.com/v1/messages).

    Bypasses broken intermediary proxies and reverse gateways.
    """

    id = "anthropic-direct"

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self._client = client
        base = (settings.active_claude_base_url or "https://api.anthropic.com").rstrip("/")
        self.base_url = base if base.endswith("/v1") else f"{base}/v1"
        self.default_model = settings.active_claude_model

    def _get_api_key(self) -> str:
        key = self.settings.claude_api_key
        if key:
            return key.get_secret_value()
        return ""

    def request_headers(self, api_key: str) -> dict[str, str]:
        headers = {
            "x-api-key": api_key,
            "anthropic-version": self.settings.claude_api_version,
            "content-type": "application/json",
            # Cloudflare-guarded gateways reject the default httpx UA (error
            # 1010); api.anthropic.com itself ignores it.
            "User-Agent": _BROWSER_UA,
        }
        if self.settings.is_mwapi_claude_gateway:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    async def health(self) -> bool:
        """Checks whether Anthropic direct API key is configured."""
        return bool(self._get_api_key())

    async def create_message(
        self, payload: dict[str, Any], *, timeout_s: float = 120.0
    ) -> dict[str, Any]:
        """POST a prepared Messages payload and return the decoded JSON body."""
        api_key = self._get_api_key()
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        client = self._client or httpx.AsyncClient(timeout=timeout_s)
        try:
            with genai.llm_call(
                provider=genai.PROVIDER_ANTHROPIC,
                model=payload.get("model"),
                max_tokens=payload.get("max_tokens"),
            ) as call:
                call.set_input(payload.get("messages"), payload.get("system"))
                resp = await client.post(
                    f"{self.base_url}/messages", headers=self.request_headers(api_key), json=payload
                )
                resp.raise_for_status()
                data = resp.json()
                call.record_anthropic_response(data)
                return data
        finally:
            if not self._client:
                await client.aclose()

    async def generate(
        self,
        prompt: str | list[dict[str, Any]],
        system: str | None = None,
        model: str | None = None,
        max_tokens: int | None = None,
        attachments: list[Any] | None = None,
    ) -> ProviderResult[str]:
        if not self._get_api_key():
            raise ValueError("ANTHROPIC_API_KEY is not configured.")
        if max_tokens is None:
            try:
                max_tokens = int(self.settings.llm_max_output_tokens)
            except Exception:  # pragma: no cover
                max_tokens = 16_384

        start_time = time.time()
        user_content = (
            build_anthropic_content(prompt, attachments) if isinstance(prompt, str) else prompt
        )
        payload: dict[str, Any] = {
            "model": model or self.default_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": user_content}],
        }
        if system:
            payload["system"] = system

        data = await self.create_message(payload, timeout_s=30.0)
        result_text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        return ProviderResult(
            value=result_text,
            provider=self.id,
            latency_ms=int((time.time() - start_time) * 1000),
        )
