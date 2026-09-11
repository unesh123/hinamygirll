from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from ..errors import HinaaError

CreativeCategory = Literal["image", "upscale", "relight"]
CreativeTier = Literal["economy", "balanced", "quality", "premium"]


CostType = Literal["fixed", "dynamic", "range", "provider_reported"]


@dataclass(frozen=True, slots=True)
class CreativeModel:
    id: str
    name: str
    cost_credits: int
    category: CreativeCategory
    tier: CreativeTier
    description: str
    recommended_for: tuple[str, ...] = field(default_factory=tuple)
    is_video: bool = False
    cost_type: CostType = "fixed"
    estimated_credits: int | None = None
    requires_cost_calculation: bool = False


# Canonical verified Magnific pricing & creative model registry
CANONICAL_MODELS: dict[str, CreativeModel] = {
    "classic-fast": CreativeModel(
        id="classic-fast",
        name="Classic Fast",
        cost_credits=1,
        category="image",
        tier="economy",
        description="Ultra-fast 1-credit draft model for rapid prompt testing and storyboards.",
        recommended_for=("rapid_iteration", "storyboarding", "thumbnails"),
        cost_type="fixed",
    ),
    "classic": CreativeModel(
        id="classic",
        name="Classic",
        cost_credits=5,
        category="image",
        tier="balanced",
        description="Standard Classic model delivering balanced composition and lighting.",
        recommended_for=("concept_art", "standard_illustration"),
        cost_type="fixed",
    ),
    "flux-fast": CreativeModel(
        id="flux-fast",
        name="Flux.1 Fast",
        cost_credits=5,
        category="image",
        tier="balanced",
        description="Fast Flux-1 inference with strong prompt fidelity.",
        recommended_for=("fast_flux", "poster_layout"),
        cost_type="fixed",
    ),
    "flux-1": CreativeModel(
        id="flux-1",
        name="Flux.1 Standard",
        cost_credits=10,
        category="image",
        tier="quality",
        description="High-fidelity Flux.1 model for detailed character and environment work.",
        recommended_for=("detailed_character", "avatar_texture", "wallpaper"),
        cost_type="fixed",
    ),
    "mystic-1": CreativeModel(
        id="mystic-1",
        name="Mystic 1.0",
        cost_credits=45,
        category="image",
        tier="premium",
        description="Photorealistic rendering engine v1 for finished studio visuals.",
        recommended_for=("final_portfolio", "photorealism"),
        cost_type="fixed",
    ),
    "mystic-2.5": CreativeModel(
        id="mystic-2.5",
        name="Mystic 2.5",
        cost_credits=50,
        category="image",
        tier="premium",
        description="Flagship state-of-the-art Mystic engine with exceptional anatomical precision.",
        recommended_for=("masterpiece_render", "hero_key_visual"),
        cost_type="fixed",
    ),
    "upscale-2x": CreativeModel(
        id="upscale-2x",
        name="Magnific Upscale Precision",
        cost_credits=0,
        category="upscale",
        tier="quality",
        description="High-detail creative upscaler with output-size dependent dynamic credit deduction.",
        recommended_for=("upscaling", "print_prep"),
        cost_type="dynamic",
        estimated_credits=None,
        requires_cost_calculation=True,
    ),
    "relight": CreativeModel(
        id="relight",
        name="Magnific Relight",
        cost_credits=0,
        category="relight",
        tier="quality",
        description="Directional portrait and environment relighting with provider-reported operation pricing.",
        recommended_for=("lighting_correction", "mood_adaptation"),
        cost_type="dynamic",
        estimated_credits=None,
        requires_cost_calculation=True,
    ),
}


class CreativeModelRegistry:
    """Model registry enforcing canonical pricing, pacing recommendations, and a strict video ban."""

    @staticmethod
    def get_model(model_id: str) -> CreativeModel:
        clean = (model_id or "").strip().lower()
        if "video" in clean:
            raise HinaaError(
                "VIDEO_GENERATION_FORBIDDEN",
                "Video generation is strictly disabled on HINAA OS to preserve credits and prevent unauthorized video compute.",
                status_code=403,
            )
        if clean in CANONICAL_MODELS:
            return CANONICAL_MODELS[clean]

        alias_map = {
            "flux-schnell": "flux-fast",
            "flux-dev": "flux-1",
            "mystic": "mystic-2.5",
            "upscale": "upscale-2x",
        }
        target = alias_map.get(clean)
        if target and target in CANONICAL_MODELS:
            return CANONICAL_MODELS[target]

        return CANONICAL_MODELS["flux-fast"]

    @staticmethod
    def list_models(category: str | None = None) -> list[CreativeModel]:
        models = list(CANONICAL_MODELS.values())
        if category:
            models = [m for m in models if m.category == category]
        return models

    @staticmethod
    def recommend_model(task: str, pacing_mode: str = "balanced") -> CreativeModel:
        task_lower = (task or "").lower()
        if "video" in task_lower:
            raise HinaaError(
                "VIDEO_GENERATION_FORBIDDEN",
                "Video generation is strictly disabled on HINAA OS.",
                status_code=403,
            )

        if "upscale" in task_lower:
            return CANONICAL_MODELS["upscale-2x"]
        if "relight" in task_lower or "light" in task_lower:
            return CANONICAL_MODELS["relight"]

        if pacing_mode == "economy":
            if "draft" in task_lower or "quick" in task_lower or "preview" in task_lower:
                return CANONICAL_MODELS["classic-fast"]
            return CANONICAL_MODELS["flux-fast"]

        if pacing_mode == "use-it-wisely":
            return CANONICAL_MODELS["mystic-2.5"]

        if pacing_mode == "quality":
            if "masterpiece" in task_lower or "final" in task_lower:
                return CANONICAL_MODELS["mystic-2.5"]
            return CANONICAL_MODELS["flux-1"]

        if "draft" in task_lower or "fast" in task_lower:
            return CANONICAL_MODELS["classic-fast"]
        return CANONICAL_MODELS["flux-fast"]

    @staticmethod
    def calculate_upscale_credits(
        width: int,
        height: int,
        scale_factor: float = 2.0,
    ) -> int:
        """Estimate dynamic upscale credits based on output megapixel resolution."""
        output_pixels = (width * scale_factor) * (height * scale_factor)
        megapixels = output_pixels / 1_000_000.0
        return max(5, int(megapixels * 5.0))