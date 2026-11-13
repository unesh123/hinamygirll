"""Free video generation via Hugging Face Inference Providers — the $0 path.

Why this exists: every major video API bills from the first call (fal.ai,
Gemini API Veo, Kling, Runway — no free tier for video in 2026, verified
2026-11-13). The one real $0 route is Hugging Face: every HF account gets
a small monthly Inference Provider credit pool that auto-applies, and a
free personal token (huggingface.co/settings/tokens, needs the "Inference
Providers" permission) is enough to call it. A 5 s clip from an open video
model typically lands in the $0.05–$0.30 range against that pool — so this
covers a handful of clips a month, not unlimited production. It is slow
(shared pool, queues of minutes) and rate-limited, and the pool can run
out — when it does, the provider fails honestly instead of pretending.

How it works (HF's own docs, text-to-video task page): the
``huggingface_hub`` InferenceClient with a provider (default ``fal-ai``)
and a model (default ``Wan-AI/Wan2.2-TI2V-5B``); ``client.text_to_video``
returns the video bytes. The provider and model are configurable
(``HINAA_HF_VIDEO_PROVIDER`` / ``HINAA_HF_VIDEO_MODEL``) so a future swap
is one env line. fal.ai stays the paid upgrade: see
``fal_video_provider.py`` — when FAL_KEY is set, the paid provider wins.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ...errors import HinaaError
from ..models import CreativeJobRecord, CreativeOperation
from .base import CreativeProvider

logger = logging.getLogger("hinaa.creative.hf_video")

# A real MP4 must at least carry an ftyp box; a 24-byte header is a lie.
_MIN_MP4_BYTES = 1024
_DEFAULT_PROVIDER = "fal-ai"
_DEFAULT_MODEL = "Wan-AI/Wan2.2-TI2V-5B"


class HfVideoProvider(CreativeProvider):
    """Text-to-video via HF Inference Providers. Free token, free credit pool."""

    def __init__(
        self,
        api_key: str | None = None,
        provider: str | None = None,
        model: str | None = None,
        *,
        client_factory: Any = None,
    ) -> None:
        if api_key is None or provider is None or model is None:
            from ...config import get_settings

            settings = get_settings()
            api_key = api_key if api_key is not None else (
                settings.hf_api_key.get_secret_value()
                if settings.hf_api_key
                else None
            )
            provider = provider or settings.hf_video_provider
            model = model or settings.hf_video_model
        self._api_key = (api_key or "").strip()
        self._provider = (provider or _DEFAULT_PROVIDER).strip()
        self._model = (model or _DEFAULT_MODEL).strip()
        self._client_factory = client_factory

    @property
    def provider_id(self) -> str:
        return "hf_video"

    def is_available(self) -> bool:
        return bool(self._api_key) and bool(self._model)

    def supported_operations(self) -> list[CreativeOperation]:
        return [CreativeOperation.TEXT_TO_VIDEO]

    def _make_client(self) -> Any:
        if self._client_factory is not None:
            return self._client_factory()
        try:
            from huggingface_hub import InferenceClient
        except ImportError as exc:
            raise HinaaError(
                "HF_CLIENT_MISSING",
                "huggingface_hub is not installed; add it to requirements.txt.",
                500,
                True,
            ) from exc
        return InferenceClient(provider=self._provider, api_key=self._api_key)

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        """Generate the video and return the real MP4 bytes (or fail honestly)."""
        if not self.is_available():
            raise HinaaError(
                "VIDEO_PROVIDER_NOT_CONFIGURED",
                "Video generation is not configured. Set HF_TOKEN in the backend env "
                "(free at huggingface.co/settings/tokens, with Inference Providers "
                "permission) for the free Hugging Face route, or FAL_KEY for paid fal.ai.",
                400,
                True,
            )
        spec = job.spec
        prompt = (spec.prompt or "").strip()
        if not prompt:
            raise HinaaError("VIDEO_PROMPT_REQUIRED", "A video prompt is required.", 400, True)
        client = self._make_client()

        def _generate() -> Any:
            # InferenceClient.text_to_video is synchronous; run it off the loop.
            kwargs: dict[str, Any] = {"model": self._model}
            if spec.negative_prompt:
                kwargs["negative_prompt"] = [spec.negative_prompt]
            return client.text_to_video(prompt, **kwargs)

        try:
            result = await asyncio.to_thread(_generate)
        except Exception as exc:
            raise HinaaError(
                "HF_VIDEO_FAILED",
                f"Hugging Face video generation failed: {exc}",
                502,
                True,
            ) from exc
        data = result if isinstance(result, (bytes, bytearray)) else None
        if data is None and hasattr(result, "read"):
            data = result.read()
        if not isinstance(data, (bytes, bytearray)) or len(data) < _MIN_MP4_BYTES or b"ftyp" not in bytes(data)[:32]:
            raise HinaaError(
                "HF_BAD_VIDEO",
                "Hugging Face returned bytes that are not a real MP4; refusing to pass them on as a video.",
                502,
                True,
            )
        return bytes(data)

    async def cancel_job(self, provider_job_id: str) -> bool:
        # The HF InferenceClient text_to_video call is a single blocking call
        # with no job handle, so there is nothing to cancel remotely.
        return False
