"""Magnific / Freepik FLUX image generation & creative fabric provider.

Unifies HINAA's cloud image brain:
- High-level FLUX text-to-image generation via Magnific (docs.magnific.com) and Freepik APIs
- Task-based asynchronous polling and synchronous fallback extraction
- Creative upscaling & relighting
- Reference-guided generation (flux-kontext-pro / image-to-image)
- Stock image search & asset resolver integration
- Typed MagnificError and MagnificProviderError handling
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from dataclasses import dataclass, field
import logging
from pathlib import Path
import re
from typing import Any, Optional
import uuid

import httpx

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..media import AssetSource, AssetStore, MediaResolver, MediaResult, get_asset_store

logger = logging.getLogger("hinaa.providers.magnific")


class MagnificError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class MagnificProviderError(HinaaError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code=code, message=message, status_code=status_code)


DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpe?g|webp));base64,([A-Za-z0-9+/=]+)$", re.I)

_ASPECT_RATIOS: list[tuple[float, str]] = [
    (1.0, "square_1_1"),
    (4 / 3, "classic_4_3"),
    (3 / 4, "traditional_3_4"),
    (16 / 9, "widescreen_16_9"),
    (9 / 16, "social_story_9_16"),
    (3 / 2, "standard_3_2"),
]


def _aspect_for(width: int, height: int) -> str:
    wanted = (width or 1) / (height or 1)
    return min(_ASPECT_RATIOS, key=lambda pair: abs(pair[0] - wanted))[1]


def _vendor_seed(seed: int | None) -> int | None:
    """Magnific seeds are 1..4,294,967,295 - clamp any Comfy-style value."""
    if seed is None:
        return None
    value = abs(int(seed)) % 4_294_967_295
    return value or 1


def _extract_urls(payload: Any) -> list[str]:
    """Collect image URLs from the shapes these APIs return."""
    found: list[str] = []

    def visit(node: Any, key_hint: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "base64" and isinstance(value, str) and not value.startswith("data:"):
                    mime = "image/png" if value.startswith("iVBORw0KGgo") else "image/jpeg"
                    found.append(f"data:{mime};base64,{value}")
                else:
                    visit(value, key)
        elif isinstance(node, list):
            for item in node:
                visit(item, key_hint)
        elif isinstance(node, str):
            looks_like_image = node.startswith("data:image") or (
                node.startswith(("http://", "https://"))
                and (bool(re.search(r"\\.(png|jpe?g|webp)(\\?|$)", node, re.I)) or key_hint in {
                    "url", "image", "image_url", "output", "output_url", "result",
                    "image_link", "signed_url", "generated",
                })
            )
            if looks_like_image:
                found.append(node)

    visit(payload)
    seen: set[str] = set()
    unique: list[str] = []
    for url in found:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


@dataclass
class MagnificImageResult:
    image_urls: list[str] = field(default_factory=list)
    provider: str = "magnific"
    task_id: str | None = None
    seed: int | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class MagnificProvider:
    """Async client and creative fabric provider for Magnific / Freepik FLUX APIs."""

    def __init__(
        self,
        settings: Settings | None = None,
        asset_store: AssetStore | None = None,
        resolver: MediaResolver | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self._asset_store = asset_store
        self._resolver = resolver

    @property
    def asset_store(self) -> AssetStore:
        if self._asset_store is None:
            self._asset_store = get_asset_store()
        return self._asset_store

    @property
    def resolver(self) -> MediaResolver:
        if self._resolver is None:
            self._resolver = MediaResolver(self.asset_store)
        return self._resolver

    # ── Configuration probes ─────────────────────────────────────────────
    @property
    def api_key(self) -> str | None:
        key = self.settings.magnific_api_key or self.settings.freepik_api_key
        if key is None:
            return None
        value = key.get_secret_value() if hasattr(key, "get_secret_value") else str(key)
        return value.strip() or None

    def available(self) -> bool:
        return self.api_key is not None

    @property
    def is_configured(self) -> bool:
        return self.available()

    def _headers(self) -> dict[str, str]:
        key = self.api_key or ""
        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.settings.freepik_api_key and not self.settings.magnific_api_key:
            headers["x-freepik-api-key"] = key
        else:
            headers["x-magnific-api-key"] = key
        return headers

    def _get_headers(self) -> dict[str, str]:
        if not self.available():
            raise MagnificProviderError(
                "CREDENTIAL_MISSING",
                "Neither MAGNIFIC_API_KEY nor FREEPIK_API_KEY is configured in your environment.",
                status_code=401,
            )
        return self._headers()

    def _timeout(self) -> httpx.Timeout:
        seconds = float(getattr(self.settings, "magnific_timeout_seconds", 240) or 240)
        return httpx.Timeout(seconds, connect=15.0)

    def _base_url(self) -> str:
        if self.settings.freepik_api_key and not self.settings.magnific_api_key:
            return "https://api.freepik.com"
        if getattr(self.settings, "magnific_base_url", None):
            return self.settings.magnific_base_url.rstrip("/")
        if self.settings.magnific_api_key:
            return "https://api.magnific.com"
        return "https://api.freepik.com"

    async def health_check(self) -> bool:
        if not self.is_configured:
            return False
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self._base_url()}/me", headers=headers)
                return res.status_code == 200
        except Exception:
            return False

    # ── Arena FLUX Generation (High Level) ───────────────────────────────
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

        final_prompt = prompt.strip()
        if negative_prompt.strip():
            final_prompt = f"{final_prompt}. Avoid: {negative_prompt.strip().rstrip('.')}."

        base = self._base_url()
        reference = reference_image_url or reference_image_b64 or ""

        # Check if targeting Freepik direct synchronous text-to-image
        if "freepik.com" in base:
            path = "/v1/ai/text-to-image"
            aspect = _aspect_for(width, height)
            payload: dict[str, Any] = {
                "prompt": final_prompt,
                "negative_prompt": negative_prompt,
                "num_images": 1,
                "image": {"size": aspect},
            }
            clamped_seed = _vendor_seed(seed)
            if clamped_seed is not None:
                payload["seed"] = clamped_seed

            flux_model = model or getattr(self.settings, "magnific_model_quality", "flux-dev")
            provider_name = f"freepik:{flux_model}"

            async with httpx.AsyncClient(timeout=self._timeout(), follow_redirects=True) as client:
                response = await self._post(client, f"{base}{path}", payload)
                body = self._json(response)
                urls = _extract_urls(body)
                if not urls:
                    raise MagnificError(
                        "MAGNIFIC_NO_OUTPUT",
                        "Freepik accepted the job but returned no image URL.",
                        retryable=True,
                    )
                return MagnificImageResult(image_urls=urls, provider=provider_name, seed=seed, raw=body)

        # Magnific contract (docs.magnific.com)
        if reference:
            path = getattr(self.settings, "magnific_reference_path", "/v1/ai/text-to-image/flux-kontext-pro")
            payload = {
                "prompt": final_prompt,
                "input_image": reference,
                "aspect_ratio": _aspect_for(width, height),
                "guidance": max(1.0, min(10.0, guidance_scale + 1.0)),
                "steps": 50,
                "prompt_upsampling": False,
            }
            provider_name = "magnific:flux-kontext-pro"
        else:
            flux_model = model or getattr(self.settings, "magnific_model_quality", "flux-dev")
            t2i_template = getattr(self.settings, "magnific_t2i_path", "/v1/ai/text-to-image/{model}")
            path = t2i_template.format(model=flux_model) if "{model}" in t2i_template else t2i_template
            payload = {
                "prompt": final_prompt,
                "aspect_ratio": _aspect_for(width, height),
            }
            provider_name = f"magnific:{flux_model}"

        clamped_seed = _vendor_seed(seed)
        if clamped_seed is not None:
            payload["seed"] = clamped_seed

        async with httpx.AsyncClient(timeout=self._timeout(), follow_redirects=True) as client:
            response = await self._post(client, f"{base}{path}", payload)
            body = self._json(response)
            task_id = str((body.get("data") or {}).get("task_id") or body.get("task_id") or "")
            if not task_id:
                urls = _extract_urls(body)
                if not urls:
                    raise MagnificError(
                        "MAGNIFIC_NO_TASK",
                        "Magnific accepted the request but returned neither a task nor an image.",
                        retryable=True,
                    )
                return MagnificImageResult(image_urls=urls, provider=provider_name, seed=seed, raw=body)

            detail = await self._await_task(client, base, path, task_id, final_prompt)
            urls = _extract_urls(detail)
            if not urls:
                raise MagnificError(
                    "MAGNIFIC_NO_OUTPUT",
                    "Magnific completed the task but returned no image URL.",
                    retryable=True,
                )
            return MagnificImageResult(image_urls=urls, provider=provider_name, task_id=task_id, seed=seed, raw=detail)

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

    # ── Upscale (Unified for URL strings and MediaResult) ─────────────────
    async def upscale(
        self,
        image_url: str | None = None,
        *,
        image_ref: str | None = None,
        scale: float = 2.0,
        factor: int | None = None,
        creativity: float = 0.35,
        hdr: float = 0.5,
        relight: float = 0.2,
        flavor: str = "photo",
        prompt: str | None = None,
        optimized_for: str = "standard",
    ) -> Any:
        # If image_ref is passed from image_fabric, return a MediaResult
        if image_ref is not None:
            eff_factor = factor or int(scale)
            resolved = await self.resolver.resolve(image_ref, role="upscale_source")

            if not self.is_configured:
                stored = self.asset_store.store_bytes(
                    raw_bytes=resolved.bytes_data,
                    filename=f"upscaled_{resolved.asset_id[:8]}.png",
                    mime_type="image/png",
                    source=AssetSource.GENERATED,
                )
                return MediaResult(
                    asset_ref=stored,
                    provider="magnific:mock-upscale",
                    credits_used=10,
                )

            headers = self._get_headers()
            b64_image = base64.b64encode(resolved.bytes_data).decode("ascii")
            payload = {
                "image": f"data:{resolved.mime_type};base64,{b64_image}",
                "scale": eff_factor,
                "flavor": flavor,
                "prompt": prompt or "",
            }

            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{self._base_url()}/upscale",
                    headers=headers,
                    json=payload,
                )
                if resp.status_code not in (200, 201):
                    raise MagnificProviderError(
                        "IMAGE_PROVIDER_ERROR",
                        f"Magnific upscale failed with HTTP {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
                result_json = resp.json()
                out_url = result_json.get("url") or result_json.get("data", {}).get("url")
                if not out_url:
                    raise MagnificProviderError("IMAGE_PROVIDER_ERROR", "Provider did not return an upscaled image URL.")

                out_media = await self.resolver.resolve(out_url, role="output")
                stored = self.asset_store.store_bytes(
                    raw_bytes=out_media.bytes_data,
                    mime_type=out_media.mime_type,
                    source=AssetSource.GENERATED,
                )
                return MediaResult(
                    asset_ref=stored,
                    provider="magnific:upscale",
                    credits_used=result_json.get("costCredits", 10),
                )

        target_url = image_url or ""
        if self.api_key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")

        blob = await self.download(target_url)
        scale_factor = "4x" if scale >= 3.5 else "2x"
        payload = {
            "image": base64.b64encode(blob).decode("ascii"),
            "scale_factor": scale_factor,
            "optimized_for": optimized_for,
            "creativity": max(-10, min(10, round(creativity * 10))),
            "hdr": 1,
            "resemblance": 0,
            "fractality": 0,
        }
        if prompt and prompt.strip():
            payload["prompt"] = prompt.strip()

        base = self._base_url()
        path = getattr(self.settings, "magnific_upscale_path", "/v1/ai/image-upscaler")
        async with httpx.AsyncClient(timeout=self._timeout(), follow_redirects=True) as client:
            response = await self._post(client, f"{base}{path}", payload)
            body = self._json(response)
            task_id = str((body.get("data") or {}).get("task_id") or body.get("task_id") or "")
            urls = _extract_urls(body)
            if not urls and not task_id:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale returned no task or image.", retryable=True)
            if urls:
                return urls[0]
            detail = await self._await_task(client, base, path, task_id, prompt or "")
            urls = _extract_urls(detail)
            if not urls:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale completed with no image URL.", retryable=True)
            return urls[0]

    # ── Stock Search (Creative Fabric) ───────────────────────────────────
    async def stock_search(
        self,
        query: str,
        count: int = 6,
        orientation: str = "all",
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()
        if not clean_query:
            raise MagnificProviderError("VALIDATION_ERROR", "Search query cannot be empty.")
        count = min(max(1, count), 12)

        if not self.is_configured:
            return [
                {
                    "id": f"stock_mock_{i}",
                    "title": f"{clean_query.title()} Result {i+1}",
                    "url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
                    "thumbnailUrl": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=300&q=80",
                    "source": "Stock Catalog",
                }
                for i in range(count)
            ]

        try:
            headers = self._get_headers()
            params = {
                "term": clean_query,
                "limit": count,
                "orientation": orientation if orientation != "all" else None,
            }
            params = {k: v for k, v in params.items() if v is not None}
            async with httpx.AsyncClient(timeout=12.0) as client:
                resp = await client.get(
                    "https://api.freepik.com/v1/resources",
                    headers=headers,
                    params=params,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    items = data.get("data", [])
                    results = []
                    for item in items[:count]:
                        img_info = item.get("image", {})
                        source_url = img_info.get("source", {}).get("url") or item.get("url")
                        preview_url = img_info.get("preview", {}).get("url") or source_url
                        if source_url:
                            results.append({
                                "id": str(item.get("id", "")),
                                "title": item.get("title") or clean_query,
                                "url": source_url,
                                "thumbnailUrl": preview_url,
                                "source": "Freepik Stock",
                            })
                    if results:
                        return results
        except Exception as exc:
            logger.warning("Stock search API error, using safe fallback: %s", exc)

        return [
            {
                "id": f"stock_{i}",
                "title": f"{clean_query.title()} Stock {i+1}",
                "url": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
                "thumbnailUrl": "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=300&q=80",
                "source": "Stock Catalog",
            }
            for i in range(count)
        ]

    # ── Still Image (Creative Fabric) ────────────────────────────────────
    async def generate_still_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int | None = None,
        model: str = "flux-2-flex",
        aspect_ratio: str = "square_1_1",
    ) -> MediaResult:
        if not prompt.strip():
            raise MagnificProviderError("VALIDATION_ERROR", "Prompt is required for still image generation.")

        lowered_model = model.lower()
        if "seedance" in lowered_model:
            model = "flux-2-flex"
            lowered_model = "flux-2-flex"
        elif any(marker in lowered_model for marker in ("video", "animate", "motion", "clip")):
            raise MagnificProviderError(
                "VIDEO_GENERATION_FORBIDDEN",
                "Video generation is strictly forbidden in this environment.",
                status_code=403,
            )

        if not self.is_configured:
            mock_url = "https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=1024&q=80"
            out_media = await self.resolver.resolve(mock_url, role="output")
            stored = self.asset_store.store_bytes(
                raw_bytes=out_media.bytes_data,
                filename="generated_quality_still.png",
                mime_type=out_media.mime_type,
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:mock-still-image",
                credits_used=8,
            )

        headers = self._get_headers()
        submit_path = f"/v1/ai/text-to-image/{model}"
        url = f"{self._base_url()}{submit_path}"
        payload: dict[str, Any] = {
            "prompt": prompt,
            "num_images": 1,
            "image": {"size": aspect_ratio},
        }
        if negative_prompt.strip():
            payload["negative_prompt"] = negative_prompt.strip()
        if seed is not None:
            payload["seed"] = seed

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise MagnificProviderError(
                    "IMAGE_PROVIDER_ERROR",
                    f"Magnific still image generation failed with HTTP {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )
            result_json = resp.json()
            task_id = str((result_json.get("data") or {}).get("task_id") or result_json.get("task_id") or "")
            out_url = None
            out_b64 = None
            if task_id:
                detail = await self._await_task(client, self._base_url(), submit_path, task_id, prompt)
                out_url = detail.get("image_url") or detail.get("url") or (_extract_urls(detail)[0] if _extract_urls(detail) else None)
            else:
                items = result_json.get("data", [])
                if isinstance(items, list) and items:
                    out_url = items[0].get("url")
                    out_b64 = items[0].get("base64")
                if not out_url and not out_b64:
                    out_url = result_json.get("url")

            if out_b64:
                img_bytes = base64.b64decode(out_b64)
                stored = self.asset_store.store_bytes(
                    raw_bytes=img_bytes,
                    filename=f"magnific_{uuid.uuid4().hex[:8]}.png",
                    mime_type="image/png",
                    source=AssetSource.GENERATED,
                )
            elif out_url:
                out_media = await self.resolver.resolve(out_url, role="output")
                stored = self.asset_store.store_bytes(
                    raw_bytes=out_media.bytes_data,
                    mime_type=out_media.mime_type,
                    source=AssetSource.GENERATED,
                )
            else:
                raise MagnificProviderError("IMAGE_PROVIDER_ERROR", "Provider did not return a valid output image.")

            return MediaResult(
                asset_ref=stored,
                provider=f"magnific:{model}",
                task_id=task_id or None,
                credits_used=result_json.get("costCredits", 8),
            )

    # ── Reference Image (Creative Fabric) ────────────────────────────────
    async def reference_generate(
        self,
        prompt: str,
        reference: str,
        strength: float = 0.6,
        style: str = "anime",
    ) -> MediaResult:
        if not prompt.strip():
            raise MagnificProviderError("VALIDATION_ERROR", "Prompt is required for image generation.")

        resolved = await self.resolver.resolve(reference, role="reference")

        if not self.is_configured:
            mock_bytes = resolved.bytes_data
            stored = self.asset_store.store_bytes(
                raw_bytes=mock_bytes,
                filename=f"generated_ref_{resolved.asset_id[:8]}.png",
                mime_type="image/png",
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:mock-reference",
                credits_used=5,
            )

        headers = self._get_headers()
        b64_image = base64.b64encode(resolved.bytes_data).decode("ascii")
        payload = {
            "prompt": prompt,
            "image": f"data:{resolved.mime_type};base64,{b64_image}",
            "strength": max(0.1, min(1.0, strength)),
            "style": style,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self._base_url()}/image-to-image",
                headers=headers,
                json=payload,
            )
            if resp.status_code not in (200, 201):
                raise MagnificProviderError(
                    "IMAGE_PROVIDER_ERROR",
                    f"Magnific reference generation failed with HTTP {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )
            result_json = resp.json()
            out_url = result_json.get("url") or result_json.get("data", {}).get("url")
            if not out_url:
                raise MagnificProviderError("IMAGE_PROVIDER_ERROR", "Provider did not return a valid output image URL.")

            out_media = await self.resolver.resolve(out_url, role="output")
            stored = self.asset_store.store_bytes(
                raw_bytes=out_media.bytes_data,
                mime_type=out_media.mime_type,
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:image-to-image",
                credits_used=result_json.get("costCredits", 8),
            )

    # ── Upscale (Creative Fabric) ────────────────────────────────────────
    async def upscale(
        self,
        image_ref: str,
        scale: float = 2.0,
        factor: int | None = None,
        flavor: str = "photo",
        prompt: str = "",
        **kwargs: Any,
    ) -> MediaResult:
        eff_scale = factor if factor is not None else scale
        resolved = await self.resolver.resolve(image_ref, role="upscale_source")
        if not self.is_configured:
            stored = self.asset_store.store_bytes(
                raw_bytes=resolved.bytes_data,
                filename=f"upscaled_{resolved.asset_id[:8]}.png",
                mime_type=resolved.mime_type or "image/png",
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:mock-upscale",
                credits_used=8,
            )
        headers = self._get_headers()
        b64_image = base64.b64encode(resolved.bytes_data).decode("ascii")
        submit_path = "/v1/ai/image-upscaler"
        scale_val = f"{int(eff_scale)}x" if isinstance(eff_scale, (int, float)) else str(eff_scale)
        payload: dict[str, Any] = {
            "image": f"data:{resolved.mime_type};base64,{b64_image}",
            "scale_factor": scale_val,
        }
        if prompt.strip():
            payload["prompt"] = prompt.strip()

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self._base_url()}{submit_path}", headers=headers, json=payload)
            if resp.status_code not in (200, 201):
                raise MagnificProviderError(
                    "IMAGE_PROVIDER_ERROR",
                    f"Magnific upscale failed with HTTP {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )
            result_json = resp.json()
            task_id = str((result_json.get("data") or {}).get("task_id") or result_json.get("task_id") or "")
            if task_id:
                detail = await self._await_task(client, self._base_url(), submit_path, task_id, prompt)
                out_url = detail.get("image_url") or detail.get("url") or (_extract_urls(detail)[0] if _extract_urls(detail) else None)
            else:
                out_url = result_json.get("url") or (result_json.get("data") or {}).get("url")
            if not out_url:
                raise MagnificProviderError("IMAGE_PROVIDER_ERROR", "Provider did not return an upscaled image URL.")
            out_media = await self.resolver.resolve(out_url, role="output")
            stored = self.asset_store.store_bytes(
                raw_bytes=out_media.bytes_data,
                mime_type=out_media.mime_type,
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:upscale",
                task_id=task_id or None,
                credits_used=result_json.get("costCredits", 8),
            )

    # ── Relight (Creative Fabric) ────────────────────────────────────────
    async def relight(
        self,
        image_ref: str,
        lighting_prompt: str,
    ) -> MediaResult:
        if not lighting_prompt.strip():
            raise MagnificProviderError("VALIDATION_ERROR", "Lighting prompt is required for relight.")

        resolved = await self.resolver.resolve(image_ref, role="relight_source")

        if not self.is_configured:
            stored = self.asset_store.store_bytes(
                raw_bytes=resolved.bytes_data,
                filename=f"relit_{resolved.asset_id[:8]}.png",
                mime_type="image/png",
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:mock-relight",
                credits_used=8,
            )

        headers = self._get_headers()
        b64_image = base64.b64encode(resolved.bytes_data).decode("ascii")
        submit_path = "/v1/ai/image-relight"
        payload = {
            "image": f"data:{resolved.mime_type};base64,{b64_image}",
            "prompt": lighting_prompt,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self._base_url()}{submit_path}",
                headers=headers,
                json=payload,
            )
            if resp.status_code not in (200, 201):
                raise MagnificProviderError(
                    "IMAGE_PROVIDER_ERROR",
                    f"Magnific relight failed with HTTP {resp.status_code}: {resp.text[:200]}",
                    status_code=resp.status_code,
                )
            result_json = resp.json()
            task_id = str((result_json.get("data") or {}).get("task_id") or result_json.get("task_id") or "")
            if task_id:
                detail = await self._await_task(client, self._base_url(), submit_path, task_id, lighting_prompt)
                out_url = detail.get("image_url") or detail.get("url") or (_extract_urls(detail)[0] if _extract_urls(detail) else None)
            else:
                out_url = result_json.get("url") or result_json.get("data", {}).get("url")
            if not out_url:
                raise MagnificProviderError("IMAGE_PROVIDER_ERROR", "Provider did not return a relit image URL.")

            out_media = await self.resolver.resolve(out_url, role="output")
            stored = self.asset_store.store_bytes(
                raw_bytes=out_media.bytes_data,
                mime_type=out_media.mime_type,
                source=AssetSource.GENERATED,
            )
            return MediaResult(
                asset_ref=stored,
                provider="magnific:relight",
                task_id=task_id or None,
                credits_used=result_json.get("costCredits", 8),
            )

    # ── Task Polling Internals ───────────────────────────────────────────
    async def _await_task(
        self,
        client: httpx.AsyncClient,
        base: str,
        submit_path: str,
        task_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        deadline = float(getattr(self.settings, "magnific_timeout_seconds", 240) or 240)
        poll_interval = float(getattr(self.settings, "magnific_poll_seconds", 2.0) or 2.0)
        waited = 0.0
        last: dict[str, Any] = {}
        while waited < deadline:
            response = await client.get(f"{base}{submit_path}/{task_id}", headers=self._headers())
            body = self._json(response)
            data = body.get("data") if isinstance(body.get("data"), dict) else body
            last = data if isinstance(data, dict) else {}
            status = str(last.get("status") or "").upper()
            if status == "COMPLETED":
                return last
            if status == "FAILED":
                reason = str(last.get("message") or last.get("error") or "the task failed without a reason")
                raise MagnificError("MAGNIFIC_TASK_FAILED", f"Magnific could not render the image: {reason[:240]}")
            await asyncio.sleep(poll_interval)
            waited += poll_interval
        raise MagnificError(
            "MAGNIFIC_TIMEOUT",
            f"Magnific is still working on the task after {int(deadline)}s"
            + (f" — re-use seed for the same result if it lands later." if prompt else "."),
            retryable=True,
        )

    async def _post(self, client: httpx.AsyncClient, url: str, payload: dict[str, Any]) -> httpx.Response:
        return await self._send(client, "POST", url, payload)

    async def _get(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
        return await self._send(client, "GET", url, None)

    async def _send(self, client: httpx.AsyncClient, method: str, url: str, payload: dict[str, Any] | None) -> httpx.Response:
        try:
            if payload is None:
                response = await client.request(method, url, headers=self._headers())
            else:
                response = await client.request(method, url, json=payload, headers=self._headers())
        except httpx.TimeoutException as error:
            raise MagnificError("MAGNIFIC_TIMEOUT", "Magnific did not respond in time.", retryable=True) from error
        except httpx.HTTPError as error:
            raise MagnificError("MAGNIFIC_UNREACHABLE", "Magnific could not be reached.", retryable=True) from error
        if response.status_code in (401, 403):
            raise MagnificError(
                "MAGNIFIC_KEY_INVALID",
                "Magnific rejected the API key. Copy a fresh key from your Freepik/Magnific "
                "developer dashboard into MAGNIFIC_API_KEY.",
            )
        if response.status_code == 429:
            raise MagnificError("MAGNIFIC_RATE_LIMIT", "Magnific is rate limiting this key.", retryable=True)
        if response.status_code >= 400:
            detail = ""
            try:
                error_body = response.json()
                detail = str(error_body.get("message") or error_body.get("detail") or "")[:300]
            except Exception:
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
