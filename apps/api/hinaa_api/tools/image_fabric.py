from __future__ import annotations

import logging
from typing import Any, Optional
from pydantic import BaseModel, Field

from ..config import get_settings
from ..errors import HinaaError
from ..media import AssetStore, get_asset_store, MediaResolver
from ..providers.magnific import MagnificProvider
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.tools.image_fabric")


class ImageSearchFabricParams(BaseModel):
    model_config = {"extra": "ignore"}
    query: str
    count: int = 6
    orientation: str = "all"
    source: str = "all"  # "stock", "web", or "all"
    userId: Optional[str] = None
    conversationId: Optional[str] = None


class ImageUpscaleParams(BaseModel):
    model_config = {"extra": "ignore"}
    image: Optional[str] = None
    attachment_ids: list[str] = []
    reference_images: list[str] = []
    imageUrl: Optional[str] = None
    scale: int = 2
    flavor: str = "photo"
    prompt: str = ""
    userId: Optional[str] = None
    conversationId: Optional[str] = None


class ImageRelightParams(BaseModel):
    model_config = {"extra": "ignore"}
    image: Optional[str] = None
    attachment_ids: list[str] = []
    reference_images: list[str] = []
    imageUrl: Optional[str] = None
    lighting_prompt: str
    userId: Optional[str] = None
    conversationId: Optional[str] = None


class ImageFabric:
    """Provider-neutral creative fabric coordinating stock search, reference-guided generation,

    upscaling, and relighting.
    """

    def __init__(self) -> None:
        self.settings = get_settings()
        self.asset_store = get_asset_store()
        self.resolver = MediaResolver(self.asset_store)
        self.magnific = MagnificProvider(self.settings, self.asset_store, self.resolver)

    def _resolve_target_ref(
        self,
        direct: Optional[str],
        attachment_ids: list[str],
        reference_images: list[str],
        imageUrl: Optional[str],
    ) -> str:
        """Picks the first valid reference from available parameters."""
        if direct and direct.strip():
            return direct.strip()
        if attachment_ids:
            return attachment_ids[0]
        if reference_images:
            return reference_images[0]
        if imageUrl and imageUrl.strip():
            return imageUrl.strip()
        raise HinaaError(
            "IMAGE_REFERENCE_MISSING",
            "An image attachment, asset ID, or URL is required for this operation.",
            status_code=400,
        )

    async def handle_search(self, params: ImageSearchFabricParams) -> dict[str, Any]:
        """Unified stock and web image search."""
        clean_q = params.query.strip()
        if not clean_q:
            raise HinaaError("VALIDATION_ERROR", "Search query cannot be empty.", status_code=400)

        # 1. First search via Magnific / Freepik stock
        stock_results = await self.magnific.stock_search(clean_q, count=params.count, orientation=params.orientation)
        if stock_results:
            return {
                "status": "success",
                "query": clean_q,
                "count": len(stock_results),
                "images": stock_results,
                "results": stock_results,
            }

        # 2. Fallback to existing browser image search if stock fails
        from .browser import image_search
        return await image_search({"query": clean_q, "count": params.count})

    async def handle_upscale(self, params: ImageUpscaleParams) -> dict[str, Any]:
        """Micro-texture 2x/4x image upscaler."""
        target_ref = self._resolve_target_ref(
            params.image,
            params.attachment_ids,
            params.reference_images,
            params.imageUrl,
        )
        result = await self.magnific.upscale(
            image_ref=target_ref,
            factor=params.scale,
            flavor=params.flavor,
            prompt=params.prompt,
        )
        return {
            "status": "success",
            "asset_id": result.asset_ref.id,
            "url": result.asset_ref.public_url,
            "public_url": result.asset_ref.public_url,
            "imageUrl": result.asset_ref.public_url,
            "provider": result.provider,
            "credits_used": result.credits_used,
        }

    async def handle_relight(self, params: ImageRelightParams) -> dict[str, Any]:
        """Studio and dynamic ambiance relighter."""
        target_ref = self._resolve_target_ref(
            params.image,
            params.attachment_ids,
            params.reference_images,
            params.imageUrl,
        )
        result = await self.magnific.relight(
            image_ref=target_ref,
            lighting_prompt=params.lighting_prompt,
        )
        return {
            "status": "success",
            "asset_id": result.asset_ref.id,
            "url": result.asset_ref.public_url,
            "public_url": result.asset_ref.public_url,
            "imageUrl": result.asset_ref.public_url,
            "provider": result.provider,
            "credits_used": result.credits_used,
        }


image_fabric = ImageFabric()

# Register new tools into the global registry
image_upscale_def = ToolDefinition(
    name="image_upscale",
    display_name="Upscale Image",
    description="Upscale an image by 2x or 4x with micro-texture enhancement.",
    parameters={
        "image": {"type": "string", "description": "Asset ID, public URL, or data URI of the image to upscale."},
        "scale": {"type": "integer", "description": "Scale factor: 2 or 4."},
        "flavor": {"type": "string", "description": "Upscale flavor: 'photo', 'anime', or 'art'."},
    },
    required_parameters=[],
    requires_confirmation=False,
    cancellable=True,
)

image_relight_def = ToolDefinition(
    name="image_relight",
    display_name="Relight Image",
    description="Relight an image with dynamic lighting direction and studio ambiance.",
    parameters={
        "image": {"type": "string", "description": "Asset ID, public URL, or data URI of the image to relight."},
        "lighting_prompt": {"type": "string", "description": "Lighting description (e.g. 'golden hour studio light', 'neon cyberpunk')."},
    },
    required_parameters=["lighting_prompt"],
    requires_confirmation=False,
    cancellable=True,
)

registry.register(image_upscale_def, image_fabric.handle_upscale)
registry.register(image_relight_def, image_fabric.handle_relight)
