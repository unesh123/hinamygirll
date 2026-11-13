"""Real video generation via fal.ai — the only MP4 path that returns real bytes.

Why this exists: ``GenerativeVideoProvider`` was a stub that failed closed,
and ``VertexVeoAdapter`` faked success by writing a 24-byte MP4 header. Hina
could therefore never return a real video, only refuse or lie about one.

This provider calls fal.ai's queue API and downloads the actual rendered
file. No fake headers, no fake success: every failure raises, and a returned
``bytes`` value is a real MP4 downloaded from fal's storage.

Endpoint choice (verified against fal.ai's own model pages 2026-11-13):
the default is Kling v3 Pro (``fal-ai/kling-video/v3/pro/text-to-video``).
Do NOT point this at ``fal-ai/veo3.1*`` — fal deprecates the whole Veo 3.1
tree on 17 Nov 2026, and Veo 3 is already deprecated. The endpoint is
configurable (``HINAA_FAL_VIDEO_ENDPOINT``) so a future swap is one env line.

Auth: ``FAL_KEY`` env var, server-side only, sent as
``Authorization: Key <key>``. Never in chat, never in the frontend.

Cost: fal.ai is pay-as-you-go prepaid credits, no subscription. Kling v3
Pro is roughly $0.14/s on fal's own pages (re-check live before budgeting;
an 8 s clip is about $1.12 at that rate). There is no free API tier — the
web Sandbox's free generations do not work through the API — so the first
real generation from Hina costs a few dollars of credits.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from ...errors import HinaaError
from ..models import CreativeJobRecord, CreativeOperation
from .base import CreativeProvider

logger = logging.getLogger("hinaa.creative.fal_video")

FAL_QUEUE_BASE = "https://queue.fal.run"
# Kling v3 Pro accepts 3–15 s; clamp the spec into that range.
_MIN_DURATION = 3
_MAX_DURATION = 15
# A real MP4 must at least carry an ftyp box; a 24-byte header is a lie.
_MIN_MP4_BYTES = 1024


class FalVideoProvider(CreativeProvider):
    """Text-to-video via fal.ai's queue API. Fails closed without a key."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        poll_interval_seconds: float = 5.0,
        timeout_seconds: float = 600.0,
    ) -> None:
        if api_key is None or endpoint is None:
            from ...config import get_settings

            settings = get_settings()
            api_key = api_key if api_key is not None else (
                settings.fal_api_key.get_secret_value()
                if settings.fal_api_key
                else None
            )
            endpoint = endpoint or settings.fal_video_endpoint
        self._api_key = (api_key or "").strip()
        self._endpoint = (endpoint or "").strip().strip("/")
        self._transport = transport
        self._poll_interval = poll_interval_seconds
        self._timeout = timeout_seconds
        self._cancel_urls: dict[str, str] = {}

    @property
    def provider_id(self) -> str:
        return "fal_video"

    def is_available(self) -> bool:
        return bool(self._api_key) and bool(self._endpoint)

    def supported_operations(self) -> list[CreativeOperation]:
        # Text-to-video only in v1. Image-to-video needs a different fal
        # endpoint (…/image-to-video) and an uploaded image URL; it stays
        # BLOCKED until that endpoint is wired, rather than pretending.
        return [CreativeOperation.TEXT_TO_VIDEO]

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Key {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _aspect_ratio(spec: Any) -> str:
        ratio = (getattr(spec, "aspect_ratio", "") or "").strip()
        if ratio in ("16:9", "9:16", "1:1"):
            return ratio
        width = getattr(spec, "width", 0) or 0
        height = getattr(spec, "height", 0) or 0
        if width and height:
            if width > height:
                return "16:9"
            if height > width:
                return "9:16"
            return "1:1"
        return "16:9"

    @staticmethod
    def _duration_seconds(spec: Any) -> str:
        try:
            seconds = int(round(float(getattr(spec, "duration_seconds", 5) or 5)))
        except (TypeError, ValueError):
            seconds = 5
        return str(max(_MIN_DURATION, min(_MAX_DURATION, seconds)))

    async def _submit(self, client: httpx.AsyncClient, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{FAL_QUEUE_BASE}/{self._endpoint}"
        try:
            response = await client.post(url, headers=self._headers(), json=payload)
        except httpx.HTTPError as exc:
            raise HinaaError(
                "FAL_REQUEST_FAILED", f"fal.ai request failed: {exc}", 502, True
            ) from exc
        if response.status_code == 401:
            raise HinaaError(
                "FAL_UNAUTHORIZED",
                "fal.ai rejected the configured FAL_KEY. Check the key in the backend env.",
                401,
                True,
            )
        if response.status_code >= 400:
            detail = response.text[:300]
            raise HinaaError("FAL_API_ERROR", f"fal.ai returned HTTP {response.status_code}: {detail}", 502, True)
        return response.json()

    async def _poll_status(self, client: httpx.AsyncClient, status_url: str) -> dict[str, Any]:
        deadline = asyncio.get_event_loop().time() + self._timeout
        while True:
            try:
                response = await client.get(status_url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise HinaaError(
                    "FAL_REQUEST_FAILED", f"fal.ai status check failed: {exc}", 502, True
                ) from exc
            if response.status_code >= 400:
                raise HinaaError(
                    "FAL_API_ERROR",
                    f"fal.ai status check returned HTTP {response.status_code}: {response.text[:300]}",
                    502,
                    True,
                )
            body = response.json()
            status = str(body.get("status", "")).upper()
            if status == "COMPLETED":
                return body
            if status in ("FAILED", "CANCELLED"):
                raise HinaaError(
                    "FAL_JOB_FAILED",
                    f"fal.ai video job ended with status {status}.",
                    502,
                    True,
                )
            if asyncio.get_event_loop().time() > deadline:
                raise HinaaError(
                    "FAL_JOB_TIMEOUT",
                    f"fal.ai video job did not finish within {int(self._timeout)}s.",
                    504,
                    True,
                )
            await asyncio.sleep(self._poll_interval)

    async def execute_job(self, job: CreativeJobRecord) -> bytes:
        """Generate the video and return the real downloaded MP4 bytes."""
        if not self.is_available():
            raise HinaaError(
                "VIDEO_PROVIDER_NOT_CONFIGURED",
                "Video generation is not configured. Set FAL_KEY in the backend env "
                "and buy fal.ai credits; without it Hina cannot generate a video.",
                400,
                True,
            )
        spec = job.spec
        prompt = (spec.prompt or "").strip()
        if not prompt:
            raise HinaaError("VIDEO_PROMPT_REQUIRED", "A video prompt is required.", 400, True)
        payload: dict[str, Any] = {
            "prompt": prompt,
            "duration": self._duration_seconds(spec),
            "aspect_ratio": self._aspect_ratio(spec),
            "generate_audio": True,
        }
        if spec.negative_prompt:
            payload["negative_prompt"] = spec.negative_prompt
        async with httpx.AsyncClient(timeout=60.0, transport=self._transport) as client:
            submitted = await self._submit(client, payload)
            request_id = str(submitted.get("request_id") or "")
            status_url = submitted.get("status_url") or (
                f"{FAL_QUEUE_BASE}/{self._endpoint}/requests/{request_id}/status"
                if request_id
                else ""
            )
            response_url = submitted.get("response_url") or (
                f"{FAL_QUEUE_BASE}/{self._endpoint}/requests/{request_id}"
                if request_id
                else ""
            )
            if submitted.get("cancel_url"):
                self._cancel_urls[request_id] = str(submitted["cancel_url"])
            if not status_url or not response_url:
                raise HinaaError(
                    "FAL_API_ERROR",
                    "fal.ai did not return a status/response URL for the video job.",
                    502,
                    True,
                )
            # NOTE: fal marks failed/cancelled jobs COMPLETED too — the
            # result fetch below must still be checked for an error/video.
            await self._poll_status(client, status_url)
            try:
                result = await client.get(response_url, headers=self._headers())
            except httpx.HTTPError as exc:
                raise HinaaError(
                    "FAL_REQUEST_FAILED", f"fal.ai result fetch failed: {exc}", 502, True
                ) from exc
            if result.status_code >= 400:
                raise HinaaError(
                    "FAL_API_ERROR",
                    f"fal.ai result fetch returned HTTP {result.status_code}: {result.text[:300]}",
                    502,
                    True,
                )
            body = result.json()
            if isinstance(body, dict) and body.get("detail"):
                raise HinaaError("FAL_JOB_FAILED", f"fal.ai video job failed: {body['detail']}", 502, True)
            video = (body or {}).get("video") or {}
            video_url = video.get("url") if isinstance(video, dict) else None
            if not video_url:
                raise HinaaError(
                    "FAL_JOB_FAILED",
                    "fal.ai finished the job but returned no video URL.",
                    502,
                    True,
                )
            try:
                download = await client.get(video_url)
            except httpx.HTTPError as exc:
                raise HinaaError(
                    "FAL_DOWNLOAD_FAILED", f"Downloading the rendered MP4 failed: {exc}", 502, True
                ) from exc
            if download.status_code >= 400:
                raise HinaaError(
                    "FAL_DOWNLOAD_FAILED",
                    f"Downloading the rendered MP4 returned HTTP {download.status_code}.",
                    502,
                    True,
                )
            data = download.content
            if len(data) < _MIN_MP4_BYTES or b"ftyp" not in data[:32]:
                raise HinaaError(
                    "FAL_BAD_VIDEO",
                    "fal.ai returned bytes that are not a real MP4; refusing to pass them on as a video.",
                    502,
                    True,
                )
            return data

    async def cancel_job(self, provider_job_id: str) -> bool:
        url = self._cancel_urls.get(provider_job_id)
        if not url or not self._api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
                response = await client.request("DELETE", url, headers=self._headers())
            return response.status_code < 400
        except httpx.HTTPError:
            return False


def get_video_provider() -> CreativeProvider:
    """The real provider when fal is configured, else the fail-closed stub."""
    from .video_generative_provider import GenerativeVideoProvider

    provider = FalVideoProvider()
    if provider.is_available():
        return provider
    return GenerativeVideoProvider(is_configured=False)
