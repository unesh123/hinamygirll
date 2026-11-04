"""
HINAA OS — Phase 09: Generative Video Provider Contract (T2V / I2V)
Maintains strict truthfulness boundary: fails closed and reports BLOCKED if no local video diffusion
weights (e.g. SVD, CogVideo) or approved external video APIs are installed.
"""

from __future__ import annotations

from typing import List
from ..models import CreativeJobRecord, CreativeOperation
from .base import CreativeProvider


class GenerativeVideoProvider(CreativeProvider):
    """Stub/Contract adapter for neural video generation (Text-to-Video, Image-to-Video)."""

    def __init__(self, is_configured: bool = False) -> None:
        self._is_configured = is_configured

    @property
    def provider_id(self) -> str:
        return "generative_video_neural"

    def is_available(self) -> bool:
        # Fails closed unless genuine video weights or API keys are present
        return self._is_configured

    def supported_operations(self) -> List[CreativeOperation]:
        return [
            CreativeOperation.TEXT_TO_VIDEO,
            CreativeOperation.IMAGE_TO_VIDEO,
        ]

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        raise RuntimeError(
            "Generative video (T2V/I2V) is BLOCKED. "
            "Neither local video diffusion checkpoints (e.g., SVD, CogVideo) nor an authorized "
            "external video generation API are installed. Use TIMELINE_EXPORT for deterministic video rendering."
        )

    async def cancel_job(self, provider_job_id: str) -> bool:
        return True


generative_video_provider = GenerativeVideoProvider(is_configured=False)
