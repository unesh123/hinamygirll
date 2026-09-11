"""Magnific / Freepik FLUX image generation provider.

HINAA's cloud image brain. The primary path is FLUX text-to-image through the
configured Magnific endpoint; optional second-pass upscale sharpens drafts to
presentation quality. Everything is defensive: shape-tolerant response parsing,
bounded timeouts, explicit typed errors, and a clean `available()` probe so
`image_generate` can fall back to the local renderer without hanging a turn.

Endpoint + payload paths are configuration (MAGNIFIC_* env vars) so the exact
vendor contract can be adjusted without code changes.
"""

from __future__ import annotations

import base64
import binascii
import re
from dataclasses import dataclass, field
from typing import Any

import httpx

from ..config import Settings, get_settings


class MagnificError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpe?g|webp));base64,([A-Za-z0-9+/=]+)$")


@dataclass
class MagnificImageResult:
    image_urls: list[str] = field(default_factory=list)
    provider: str = "magnific"
    seed: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _extract_urls(payload: Any) -> list[str]:
    """Collect image URLs from the shapes these APIs are known to return."""
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if isinstance(value, str) and value.startswith(("http://", "https://", "data:image")):
                    if re.search(r"\.(png|jpe?g|webp)(\?|$)", value, re.I) or value.startswith("data:image") or key in {
                        "url", "image", "image_url", "output", "output_url", "result", "image_link", "signed_url", "image_link",
                    }:
                        found.append(value)
                else:
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    # de-dupe, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for url in found:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


class MagnificProvider:
    """Async client for Magnific's FLUX generation + upscale APIs."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    # ── configuration probes ─────────────────────────────────────────────
    @property
    def api_key(self) -> str | None:
        key = self.settings.magnific_api_key
        if key is None:
            key = self.settings.freepik_api_key
        value = key.get_secret_value() if key is not None else ""
        return value.strip() or None

    def available(self) -> bool:
        return self.api_key is not None

    def _headers(self) -> dict[str, str]:
        # The Freepik-side key header and a classic bearer fallback are both
        # sent so one configuration works across either surface of the API.
        key = self.api_key or ""
        return {
            "x-freepik-api-key": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        seconds = float(self.settings.magnific_timeout_seconds or 120)
        return httpx.Timeout(seconds, connect=15.0)

    # ── generation ───────────────────────────────────────────────────────
    async def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        width: int = 1024,
        height: int = 1024,
        seed: int | None = None,
        model: str | None = None,
        reference_image_url: str | None = None,
        reference_image_b64: str | None = None,
        guidance_scale: float = 3.5,
    ) -> MagnificImageResult:
        key = self.api_key
        if key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")

        base = self.settings.magnific_base_url.rstrip("/")
        flux_model = model or (
            self.settings.magnific_model_fast if width <= 768 else self.settings.magnific_model_quality
        )
        path = self.settings.magnific_t2i_path.format(model=flux_model)
        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_images": 1,
            "guidance_scale": guidance_scale,
            "image": {"size": f"{width}x{height}", "width": width, "height": height},
        }
        if seed is not None:
            payload["seed"] = int(seed)
        if reference_image_url:
            payload["reference_image_url"] = reference_image_url
            payload["reference_strength"] = float(self.settings.magnific_reference_strength)
        elif reference_image_b64:
            payload["reference_image_base64"] = reference_image_b64
            payload["reference_strength"] = float(self.settings.magnific_reference_strength)

        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await self._post(client, f"{base}{path}", payload, key)
            body = self._json(response)
            urls = _extract_urls(body)
            if not urls:
                raise MagnificError(
                    "MAGNIFIC_NO_OUTPUT",
                    "Magnific accepted the job but returned no image URL.",
                    retryable=True,
                )
            return MagnificImageResult(image_urls=urls, provider=f"magnific:{flux_model}", seed=seed, raw=body)

    # ── upscale (second pass) ────────────────────────────────────────────
    async def upscale(
        self,
        image_url: str,
        *,
        scale: float = 2.0,
        creativity: float = 0.35,
        hdr: float = 0.5,
        relight: float = 0.2,
    ) -> str:
        key = self.api_key
        if key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")
        base = self.settings.magnific_base_url.rstrip("/")
        payload = {
            "image_url": image_url,
            "scale": scale,
            "creativity": creativity,
            "hdr": hdr,
            "relight": relight,
            "output_format": "png",
        }
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await self._post(client, f"{base}{self.settings.magnific_upscale_path}", payload, key)
            body = self._json(response)
            urls = _extract_urls(body)
            if not urls:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale returned no image URL.", retryable=True)
            return urls[0]

    # ── download ─────────────────────────────────────────────────────────
    async def download(self, url_or_data: str, *, max_bytes: int = 32 * 1024 * 1024) -> bytes:
        data_match = DATA_URL_RE.match(url_or_data)
        if data_match:
            try:
                raw = base64.b64decode(data_match.group(2), validate=False)
            except (binascii.Error, ValueError) as error:
                raise MagnificError("MAGNIFIC_BAD_DATA_URL", "Could not decode the returned data URL.") from error
            if len(raw) > max_bytes:
                raise MagnificError("MAGNIFIC_IMAGE_TOO_LARGE", "The returned image exceeds the size limit.")
            return raw
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(url_or_data)
            if response.status_code >= 400:
                raise MagnificError(
                    "MAGNIFIC_DOWNLOAD_FAILED",
                    f"Could not download the generated image (HTTP {response.status_code}).",
                    retryable=True,
                )
            body = response.content
            if len(body) > max_bytes:
                raise MagnificError("MAGNIFIC_IMAGE_TOO_LARGE", "The returned image exceeds the size limit.")
            return body

    # ── internals ────────────────────────────────────────────────────────
    async def _post(self, client: httpx.AsyncClient, url: str, payload: dict[str, Any], key: str) -> httpx.Response:
        try:
            response = await client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as error:
            raise MagnificError("MAGNIFIC_TIMEOUT", "Magnific did not respond in time.", retryable=True) from error
        except httpx.HTTPError as error:
            raise MagnificError("MAGNIFIC_UNREACHABLE", "Magnific could not be reached.", retryable=True) from error
        if response.status_code == 401 or response.status_code == 403:
            raise MagnificError("MAGNIFIC_KEY_INVALID", "The Magnific/Freepik API key was rejected.")
        if response.status_code == 429:
            raise MagnificError("MAGNIFIC_RATE_LIMIT", "Magnific is rate limiting this key.", retryable=True)
        if response.status_code >= 400:
            detail = ""
            try:
                detail = str(response.json().get("detail") or response.json().get("message") or "")[:300]
            except Exception:  # noqa: BLE001 - error bodies vary; message is best-effort
                detail = response.text[:200]
            raise MagnificError(
                "MAGNIFIC_REJECTED",
                f"Magnific rejected the request (HTTP {response.status_code}). {detail}".strip(),
                retryable=response.status_code >= 500,
            )
        return response

    @staticmethod
    def _json(response: httpx.Response) -> dict[str, Any]:
        try:
            body = response.json()
        except ValueError as error:
            raise MagnificError("MAGNIFIC_BAD_JSON", "Magnific returned a response that is not JSON.", retryable=True) from error
        if isinstance(body, dict) and isinstance(body.get("data"), dict):
            return {**body, **body["data"]}
        return body if isinstance(body, dict) else {"result": body}


magnific_provider = MagnificProvider()
