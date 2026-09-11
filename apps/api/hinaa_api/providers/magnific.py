from __future__ import annotations

import base64
import logging
import uuid
from typing import Any, Optional
import httpx

from ..config import Settings, get_settings
from ..errors import HinaaError
from ..media import MediaResolver, AssetStore, get_asset_store, AssetSource, MediaResult
from ..media.resolver import ResolvedMedia

logger = logging.getLogger("hinaa.providers.magnific")


class MagnificProviderError(HinaaError):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(code=code, message=message, status_code=status_code)


class MagnificProvider:
    """Provider for Magnific Creative Fabric operations:
    - stock search
    - reference-guided generation
    - micro-texture 2x/4x upscaling
    - relighting and ambiance transfer
    """

    def __init__(
        self,
        settings: Settings | None = None,
        asset_store: AssetStore | None = None,
        resolver: MediaResolver | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.asset_store = asset_store or get_asset_store()
        self.resolver = resolver or MediaResolver(self.asset_store)

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.magnific_api_key or self.settings.freepik_api_key)

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.settings.magnific_api_key:
            key = self.settings.magnific_api_key.get_secret_value()
            headers["x-magnific-api-key"] = key
            headers["Authorization"] = f"Bearer {key}"
            return headers
        if self.settings.freepik_api_key:
            key = self.settings.freepik_api_key.get_secret_value()
            headers["x-freepik-api-key"] = key
            headers["Authorization"] = f"Bearer {key}"
            return headers
        raise MagnificProviderError(
            "CREDENTIAL_MISSING",
            "Neither MAGNIFIC_API_KEY nor FREEPIK_API_KEY is configured in your environment.",
            status_code=401,
        )

    def _base_url(self) -> str:
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

    async def stock_search(
        self,
        query: str,
        count: int = 6,
        orientation: str = "all",
    ) -> list[dict[str, Any]]:
        """Search stock image catalog."""
        clean_query = query.strip()
        if not clean_query:
            raise MagnificProviderError("VALIDATION_ERROR", "Search query cannot be empty.")

        count = min(max(1, count), 12)

        if not self.is_configured:
            return [
                {
                    "id": f"stock_mock_{i}",
                    "title": f"{clean_query.title()} Result {i+1}",
                    "url": f"https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
                    "thumbnailUrl": f"https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=300&q=80",
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
                "url": f"https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=800&q=80",
                "thumbnailUrl": f"https://images.unsplash.com/photo-1579783902614-a3fb3927b675?auto=format&fit=crop&w=300&q=80",
                "source": "Stock Catalog",
            }
            for i in range(count)
        ]

    async def generate_still_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int | None = None,
        model: str = "flux-2-flex",
        aspect_ratio: str = "square_1_1",
    ) -> MediaResult:
        """Generate a pristine still image using FLUX.2 Flex or Mystic."""
        if not prompt.strip():
            raise MagnificProviderError("VALIDATION_ERROR", "Prompt is required for still image generation.")

        # Guard: Video operations strictly forbidden
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

    async def reference_generate(
        self,
        prompt: str,
        reference: str,
        strength: float = 0.6,
        style: str = "anime",
    ) -> MediaResult:
        """Generate a new image guided by a reference image (ID, URL, or data URI)."""
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

    async def upscale(
        self,
        image_ref: str,
        factor: int = 2,
        flavor: str = "photo",
        prompt: str = "",
    ) -> MediaResult:
        """Upscale an image by 2x or 4x preserving micro-textures."""
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
            "scale": factor,
            "flavor": flavor,
            "prompt": prompt,
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

    async def relight(
        self,
        image_ref: str,
        lighting_prompt: str,
    ) -> MediaResult:
        """Relight an image with dynamic lighting direction and ambiance."""
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
