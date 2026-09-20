from __future__ import annotations

import logging
from typing import Any
import httpx

from ..config import DATA_DIR, Settings, get_settings
from ..errors import HinaaError
from .registry import CreativeModelRegistry

logger = logging.getLogger("hinaa.creative.client")


class MagnificClient:
    """Unified client for Magnific / Freepik creative APIs.
    
    Strictly forbids any video generation endpoints.
    Discovers approved non-video Spaces apps and runs async generation workflows.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def _get_auth_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Check Magnific primary key first
        if self.settings.magnific_api_key:
            key = self.settings.magnific_api_key.get_secret_value()
            headers["x-magnific-api-key"] = key
            headers["x-freepik-api-key"] = key
            headers["Authorization"] = f"Bearer {key}"
            return headers

        # Fallback to Freepik key
        if self.settings.freepik_api_key:
            key = self.settings.freepik_api_key.get_secret_value()
            headers["x-freepik-api-key"] = key
            headers["x-magnific-api-key"] = key
            headers["Authorization"] = f"Bearer {key}"
            return headers

        raise HinaaError(
            "CREDENTIAL_MISSING",
            "Neither MAGNIFIC_API_KEY nor FREEPIK_API_KEY is configured in your environment.",
            status_code=401,
        )

    def _get_base_url(self) -> str:
        if self.settings.magnific_api_key:
            return "https://api.magnific.com/v1"
        return "https://api.freepik.com/v1"

    async def get_spaces_apps(self) -> list[dict[str, Any]]:
        """Discover approved non-video Spaces apps / workflows."""
        # Curated catalog of verified non-video Magnific/Freepik Spaces workflows
        return [
            {
                "id": "spaces-anime-portrait",
                "name": "Anime & Character Stylizer",
                "category": "character",
                "description": "Consistent anime character rendering with dynamic lighting and cell shading.",
                "costCredits": 5,
                "supportedModels": ["flux-fast", "flux-1"],
            },
            {
                "id": "spaces-micro-texture-upscale",
                "name": "Photorealistic Micro-Texture Upscaler",
                "category": "upscale",
                "description": "Hallucinates fine fabric weave, skin pores, and eye reflections at 2x scale.",
                "costCredits": 10,
                "supportedModels": ["upscale-2x"],
            },
            {
                "id": "spaces-golden-hour-relight",
                "name": "Golden Hour & Studio Relight",
                "category": "relight",
                "description": "Adjusts key, rim, and fill lights on portrait illustrations without redrawing geometry.",
                "costCredits": 8,
                "supportedModels": ["relight"],
            },
            {
                "id": "spaces-mystic-key-art",
                "name": "Mystic Cinematic Key Visual",
                "category": "production",
                "description": "Premium 50-credit generation for flagship wallpapers and character sheets.",
                "costCredits": 50,
                "supportedModels": ["mystic-2.5"],
            },
        ]

    async def submit_image_job(
        self,
        prompt: str,
        model_id: str = "flux-fast",
        aspect_ratio: str = "square_1_1",
        num_images: int = 1,
        reference_images: list[str] | None = None,
    ) -> dict[str, Any]:
        """Submit a non-video creative generation request."""
        # Enforce strict video ban
        model = CreativeModelRegistry.get_model(model_id)
        if model.is_video:
            raise HinaaError(
                "VIDEO_GENERATION_FORBIDDEN",
                "Video generation is strictly disabled on HINAA OS to preserve credits.",
                status_code=403,
            )

        headers = self._get_auth_headers()
        base_url = self._get_base_url()

        endpoint = f"{base_url}/ai/text-to-image"
        payload: dict[str, Any] = {
            "prompt": prompt,
            "num_images": num_images,
            "aspect_ratio": aspect_ratio,
            "engine": model.id,
        }
        if reference_images:
            ref_urls = []
            for ref in reference_images:
                if ref.startswith("data:image"):
                    try:
                        import base64
                        from uuid import uuid4
                        img_dir = DATA_DIR / "images"
                        img_dir.mkdir(parents=True, exist_ok=True)
                        fname = f"ref_{uuid4().hex}.jpg"
                        (img_dir / fname).write_bytes(base64.b64decode(ref.split(",", 1)[1]))
                        ref_urls.append(f"/v1/generated-images/{fname}")
                    except Exception as e:
                        logger.debug("Failed to decode reference image: %s", e)
                elif ref.startswith("http"):
                    ref_urls.append(ref)
            if ref_urls:
                payload["reference_images"] = ref_urls

        logger.info("Submitting creative job to %s with model %s (%d credits)", endpoint, model.id, model.cost_credits)

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(endpoint, headers=headers, json=payload)
                if resp.status_code in {200, 201, 202}:
                    data = resp.json()
                    image_url = None
                    file_path = None
                    images_data = data.get("data") or []
                    if images_data and isinstance(images_data, list):
                        first = images_data[0]
                        b64 = first.get("base64")
                        if b64:
                            import base64
                            from uuid import uuid4
                            img_dir = DATA_DIR / "images"
                            img_dir.mkdir(parents=True, exist_ok=True)
                            fname = f"{uuid4().hex}.jpg"
                            target_file = img_dir / fname
                            target_file.write_bytes(base64.b64decode(b64))
                            file_path = str(target_file)
                            image_url = f"/v1/generated-images/{fname}"
                        elif first.get("url"):
                            image_url = first.get("url")

                    return {
                        "status": "success",
                        "remoteJobId": data.get("id") or data.get("task_id"),
                        "imageUrl": image_url,
                        "filePath": file_path,
                        "data": data,
                    }
                elif resp.status_code == 401 or resp.status_code == 403:
                    raise HinaaError(
                        "PROVIDER_KEY_INVALID",
                        f"Magnific/Freepik rejected API key (HTTP {resp.status_code}): {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
                elif resp.status_code == 429:
                    raise HinaaError(
                        "PROVIDER_RATE_LIMIT",
                        "Magnific API rate limit exceeded.",
                        status_code=429,
                    )
                else:
                    raise HinaaError(
                        "PROVIDER_UNAVAILABLE",
                        f"Magnific API error HTTP {resp.status_code}: {resp.text[:200]}",
                        status_code=resp.status_code,
                    )
        except httpx.RequestError as exc:
            raise HinaaError(
                "PROVIDER_UNAVAILABLE",
                f"Failed to connect to Magnific API: {exc.__class__.__name__}",
                status_code=503,
            ) from exc