"""Magnific / Freepik FLUX image generation provider.

HINAA's cloud image brain, wired to the real Magnific API contract
(docs.magnific.com): base URL ``https://api.magnific.com``, header
``x-magnific-api-key``, and an asynchronous task pattern on every endpoint —

* ``POST /v1/ai/text-to-image/flux-dev``          → ``{data:{task_id,status}}``
* ``GET  /v1/ai/text-to-image/flux-dev/{task-id}`` → ``{data:{status,generated[]}}``
* ``POST /v1/ai/text-to-image/flux-kontext-pro``  (reference-guided, ``input_image`` URL)
* ``POST /v1/ai/image-upscaler`` (creative upscale; base64 image, scale 2x/4x/…)

This module owns submission + polling + tolerant result extraction so the
``image_generate`` tool stays declarative. Errors are typed (``MagnificError``
with ``code``) and every failure path resolves quickly enough for the tool to
fall back to the local renderer without hanging a turn.
"""

from __future__ import annotations

import asyncio
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


DATA_URL_RE = re.compile(r"^data:(image/(?:png|jpe?g|webp));base64,([A-Za-z0-9+/=]+)$", re.I)

# Aspect ratios the vendor accepts, mapped from the box we asked for.
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
    """Magnific seeds are 1..4,294,967,295 — clamp any Comfy-style value."""
    if seed is None:
        return None
    value = abs(int(seed)) % 4_294_967_295
    return value or 1


def _extract_urls(payload: Any) -> list[str]:
    """Collect image URLs from the shapes these APIs return (and future ones).

    The task detail puts finals under ``data.generated[]``; older/alternative
    vendor surfaces have used ``urls``/``image.url``/artifact lists, so the walk
    is generic and key-aware rather than path-specific.
    """
    found: list[str] = []

    def visit(node: Any, key_hint: str = "") -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                visit(value, key)
        elif isinstance(node, list):
            for item in node:
                visit(item, key_hint)
        elif isinstance(node, str):
            looks_like_image = node.startswith("data:image") or (
                node.startswith(("http://", "https://"))
                and (bool(re.search(r"\.(png|jpe?g|webp)(\?|$)", node, re.I)) or key_hint in {
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
    """Async client for Magnific's FLUX generation + creative upscaler."""

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
        key = self.api_key or ""
        # The Magnific header is authoritative; the Freepik-era header is sent
        # too so one key works across both surfaces of the same account.
        return {
            "x-magnific-api-key": key,
            "x-freepik-api-key": key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _timeout(self) -> httpx.Timeout:
        seconds = float(self.settings.magnific_timeout_seconds or 180)
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
        if self.api_key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")

        # The vendor has no negative field — bake the constraints into the
        # prompt so the user's "no text, no watermark" intent survives.
        final_prompt = prompt.strip()
        if negative_prompt.strip():
            final_prompt = f"{final_prompt}. Avoid: {negative_prompt.strip().rstrip('.')}."

        reference = reference_image_url or reference_image_b64 or ""
        if reference:
            # Kontext Pro is the reference-aware endpoint; it takes the image
            # as a URL (data URLs included) and exposes guidance/steps.
            path = self.settings.magnific_reference_path
            payload: dict[str, Any] = {
                "prompt": final_prompt,
                "input_image": reference,
                "aspect_ratio": _aspect_for(width, height),
                "guidance": max(1.0, min(10.0, guidance_scale + 1.0)),
                "steps": 50,
                "prompt_upsampling": False,
            }
            provider_name = "magnific:flux-kontext-pro"
        else:
            flux_model = model or self.settings.magnific_model_quality
            path = self.settings.magnific_t2i_path.format(model=flux_model)
            payload = {
                "prompt": final_prompt,
                "aspect_ratio": _aspect_for(width, height),
            }
            provider_name = f"magnific:{flux_model}"

        clamped_seed = _vendor_seed(seed)
        if clamped_seed is not None:
            payload["seed"] = clamped_seed

        base = self.settings.magnific_base_url.rstrip("/")
        async with httpx.AsyncClient(timeout=self._timeout(), follow_redirects=True) as client:
            response = await self._post(client, f"{base}{path}", payload)
            body = self._json(response)
            task_id = str((body.get("data") or {}).get("task_id") or body.get("task_id") or "")
            if not task_id:
                # A synchronous vendor shape that already carries images is
                # still accepted — forward compatibility is cheap here.
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

    # ── upscale (second pass) ────────────────────────────────────────────
    async def upscale(
        self,
        image_url: str,
        *,
        scale: float = 2.0,
        creativity: float = 0.35,
        prompt: str = "",
        optimized_for: str = "standard",
    ) -> str:
        """Creative upscale. The vendor takes the image as raw base64, so the
        draft is fetched first; URL inputs from HINAA's own gallery resolve
        through the local filesystem transparently."""
        if self.api_key is None:
            raise MagnificError("MAGNIFIC_NOT_CONFIGURED", "No Magnific/Freepik API key is configured.")

        blob = await self.download(image_url)
        scale_factor = "4x" if scale >= 3.5 else "2x"
        payload: dict[str, Any] = {
            "image": base64.b64encode(blob).decode("ascii"),
            "scale_factor": scale_factor,
            "optimized_for": optimized_for,
            "creativity": max(-10, min(10, round(creativity * 10))),
            "hdr": 1,
            "resemblance": 0,
            "fractality": 0,
        }
        if prompt.strip():
            # Reusing the generation prompt on the upscale pass is the
            # vendor-documented trick for keeping detail coherent.
            payload["prompt"] = prompt.strip()

        base = self.settings.magnific_base_url.rstrip("/")
        path = self.settings.magnific_upscale_path
        async with httpx.AsyncClient(timeout=self._timeout(), follow_redirects=True) as client:
            response = await self._post(client, f"{base}{path}", payload)
            body = self._json(response)
            task_id = str((body.get("data") or {}).get("task_id") or body.get("task_id") or "")
            urls = _extract_urls(body)
            if not urls and not task_id:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale returned no task or image.", retryable=True)
            if urls:
                return urls[0]
            detail = await self._await_task(client, base, path, task_id, prompt)
            urls = _extract_urls(detail)
            if not urls:
                raise MagnificError("MAGNIFIC_UPSCALE_NO_OUTPUT", "Magnific upscale completed with no image URL.", retryable=True)
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
    async def _await_task(
        self,
        client: httpx.AsyncClient,
        base: str,
        submit_path: str,
        task_id: str,
        prompt: str,
    ) -> dict[str, Any]:
        """Poll ``{submit_path}/{task_id}`` to COMPLETED within the budget.

        The vendor's own timeout is generous; ours bounds the whole turn, so a
        wedged task degrades into a typed retryable error (and possibly the
        local fallback) instead of an eternal spinner.
        """
        deadline = float(self.settings.magnific_timeout_seconds or 180)
        poll_interval = float(self.settings.magnific_poll_seconds or 2.0)
        waited = 0.0
        last: dict[str, Any] = {}
        while waited < deadline:
            response = await self._get(client, f"{base}{submit_path}/{task_id}")
            body = self._json(response)
            data = body.get("data") if isinstance(body.get("data"), dict) else body
            last = data if isinstance(data, dict) else {}
            status = str(last.get("status") or "").upper()
            if status == "COMPLETED" or _extract_urls(last):
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
        return body if isinstance(body, dict) else {"result": body}


magnific_provider = MagnificProvider()
