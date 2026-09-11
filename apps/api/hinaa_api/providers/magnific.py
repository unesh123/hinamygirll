"""Magnific / Freepik FLUX image generation & creative fabric provider.

Unifies HINAA's cloud image brain:
- High-level FLUX text-to-image generation via Magnific/Freepik
- Micro-texture upscaling & relighting
- Reference-guided generation
- Stock image search
- Asset resolver & store integration
- Local ComfyUI fallback compatibility
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
import logging
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
                        "url", "image", "image_url", "output", "output_url", "result", "image_link", "signed_url",
                    }:
                        found.append(value)
                else:
                    visit(value)
        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(payload)
    seen: set[str] = set()
    unique: list[str] = []
    for url in found:
        if url not in seen:
            seen.add(url)
            unique.append(url)
    return unique


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
        return {
            "x-freepik-api-key": key,
            "Authorization": f"Bearer {key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _get_headers(self) -> dict[str, str]:
        if not self.available():
            raise MagnificProviderError(
                "CREDENTIAL_MISSING",
                "Neither MAGNIFIC_API_KEY nor FREEPIK_API_KEY is configured in your environment.",
                status_code=401,
            )
        return self._headers()

    def _timeout(self) -> httpx.Timeout:
        seconds = float(getattr(self.settings, "magnific_timeout_seconds", 120) or 120)
        return httpx.Timeout(seconds, connect=15.0)

    def _base_url(self) -> str:
        if getattr(self.settings, "magnific_base_url", None):
            return self.settings.magnific_base_url.rstrip("/")
        if self.settings.magnific_api_key:
            return "https://api.magnific.com/v1"
        return "https://api.freepik.com/v1"

    async def health_check(self) -> bool:
        if not self.is_configured:
            return False
        try:
            headers = self._get_headers()
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(f"{self._base_url()}/me", headers=headers)
                return res.status_code in (200, 401, 403)
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

        base = self.settings.magnific_base_url.rstrip("/") if getattr(self.settings, "magnific_base_url", None) else "https://api.freepik.com"
        fast_model = getattr(self.settings, "magnific_model_fast", "flux-schnell")
        quality_model = getattr(self.settings, "magnific_model_quality", "flux-dev")
        flux_model = model or (fast_model if width <= 768 else quality_model)
        t2i_template = getattr(self.settings, "magnific_t2i_path", "/v1/ai/text-to-image/{model}")
        path = t2i_template.format(model=flux_model)

        payload: dict[str, Any] = {
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "num_images": 1,
            "guidance_scale": guidance_scale,
            "image": {"size": f"{width}x{height}", "width": width, "height": height},
        }
        if seed is not None:
            payload["seed"] = int(seed)
        ref_strength = float(getattr(self.settings, "magnific_reference_strength", 0.6) or 0.6)
        if reference_image_url:
            payload["reference_image_url"] = reference_image_url
            payload["reference_strength"] = ref_strength
        elif reference_image_b64:
            payload["reference_image_base64"] = reference_image_b64
            payload["reference_strength"] = ref_strength

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

        # Arena URL string upscale
        target_url = image_url or ""
        key = self.api_key
        if key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")
        base = getattr(self.settings, "magnific_base_url", "https://api.freepik.com").rstrip("/")
        upscale_path = getattr(self.settings, "magnific_upscale_path", "/v1/ai/upscale")
        payload = {
            "image_url": target_url,
            "scale": scale,
            "creativity": creativity,
            "hdr": hdr,
            "relight": relight,
            "output_format": "png",
        }
        async with httpx.AsyncClient(timeout=self._timeout()) as client:
            response = await self._post(client, f"{base}{upscale_path}", payload, key)
            body = self._json(response)
            urls = _extract_urls(body)
            if not urls:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale returned no image URL.", retryable=True)
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
        if any(marker in lowered_model for marker in ("video", "seedance", "animate", "motion", "clip")):
            raise MagnificProviderError(
                "VIDEO_GENERATION_FORBIDDEN",
                "Video generation (including Seedance) is strictly forbidden in this environment.",
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
        url = f"{self._base_url()}/ai/text-to-image"
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
            items = result_json.get("data", [])
            out_url = None
            out_b64 = None
            if items:
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
        payload = {
            "image": f"data:{resolved.mime_type};base64,{b64_image}",
            "lighting_prompt": lighting_prompt,
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(
                f"{self._base_url()}/relight",
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
                credits_used=result_json.get("costCredits", 8),
            )

    # ── Download ─────────────────────────────────────────────────────────
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

    # ── HTTP Internals ───────────────────────────────────────────────────
    async def _post(self, client: httpx.AsyncClient, url: str, payload: dict[str, Any], key: str) -> httpx.Response:
        try:
            response = await client.post(url, json=payload, headers=self._headers())
        except httpx.TimeoutException as error:
            raise MagnificError("MAGNIFIC_TIMEOUT", "Magnific did not respond in time.", retryable=True) from error
        except httpx.HTTPError as error:
            raise MagnificError("MAGNIFIC_UNREACHABLE", "Magnific could not be reached.", retryable=True) from error
        if response.status_code in (401, 403):
            raise MagnificError("MAGNIFIC_KEY_INVALID", "The Magnific/Freepik API key was rejected.")
        if response.status_code == 429:
            raise MagnificError("MAGNIFIC_RATE_LIMIT", "Magnific is rate limiting this key.", retryable=True)
        if response.status_code >= 400:
            detail = ""
            try:
                detail = str(response.json().get("detail") or response.json().get("message") or "")[:300]
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
