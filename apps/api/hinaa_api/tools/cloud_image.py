"""
hinaa_api/tools/cloud_image.py
Multi-tier cloud image generation provider.

When local ComfyUI is offline, image_generate routes here and stores the images
under apps/api/data/images so the existing /v1/generated-images serve path and
tool-poll flow work unchanged.

Tier 1: Freepik API (if FREEPIK_API_KEY is configured)
Tier 2: Active Custom Gateway / OpenAI /images/generations
Tier 3: Pollinations.ai (zero-cost cloud fallback, requires no key)
"""
from __future__ import annotations

import asyncio
import base64
import logging
import random
import urllib.parse
import uuid
from pathlib import Path

import httpx

from ..config import DATA_DIR, get_settings

logger = logging.getLogger("hinaa.cloud_image")

_IMAGE_STORE = DATA_DIR / "images"


def cloud_image_available() -> bool:
    """Cloud generation is always available via configured keys or free cloud fallback."""
    return True


def _image_store_dir() -> Path:
    store = _IMAGE_STORE.resolve()
    store.mkdir(parents=True, exist_ok=True)
    return store


async def _generate_via_freepik(prompt: str, count: int, key: str, store: Path) -> list[dict]:
    url = "https://api.freepik.com/v1/ai/text-to-image"
    headers = {
        "x-freepik-api-key": key,
        "x-magnific-api-key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    payload = {
        "prompt": prompt,
        "num_images": min(max(1, count), 4),
        "image": {"size": "square_1_1"},
    }
    entries: list[dict] = []
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for item in data:
            b64 = item.get("base64")
            img_url = item.get("url")
            file_name = f"{uuid.uuid4().hex}.jpg"
            target = store / file_name
            if b64:
                target.write_bytes(base64.b64decode(b64))
                entries.append({"file_path": str(target)})
            elif img_url:
                dl = await client.get(img_url, timeout=30.0)
                if dl.status_code == 200:
                    target.write_bytes(dl.content)
                    entries.append({"file_path": str(target)})
    return entries


async def _generate_via_openai_compat(
    prompt: str, count: int, key: str, base_url: str, store: Path, model: str | None = None
) -> list[dict]:
    url = f"{base_url.rstrip('/')}/images/generations"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    chosen_model = model or ("dall-e-3" if "openai.com" in base_url else "step-image-edit-2")
    payload = {
        "model": chosen_model,
        "prompt": prompt,
        "n": 1 if chosen_model == "dall-e-3" else min(max(1, count), 4),
        "size": "1024x1024",
    }
    entries: list[dict] = []
    async with httpx.AsyncClient(timeout=45.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        for item in data[:count]:
            image_url = item.get("url")
            b64 = item.get("b64_json")
            if b64:
                target = store / f"{uuid.uuid4().hex}.png"
                target.write_bytes(base64.b64decode(b64))
                entries.append({"file_path": str(target)})
            elif image_url:
                dl = await client.get(image_url, timeout=15.0)
                dl.raise_for_status()
                ext = ".jpg" if ("jpeg" in dl.headers.get("content-type", "") or "jpg" in image_url) else ".png"
                target = store / f"{uuid.uuid4().hex}{ext}"
                target.write_bytes(dl.content)
                entries.append({"file_path": str(target)})
    return entries


async def _fetch_single_pollination(
    client: httpx.AsyncClient,
    prompt: str,
    store: Path,
    reference_image: str | None = None,
    seed: int | None = None,
    model: str | None = None,
) -> dict | None:
    used_seed = seed if seed is not None else random.randint(1000, 999999)
    enc_prompt = urllib.parse.quote(prompt[:350])
    image_param = ""
    if reference_image and reference_image.startswith("http"):
        image_param = f"&image={urllib.parse.quote(reference_image)}"

    # Resolve target model: flux, flux-anime, flux-realism, flux-3d, turbo
    target_model = (model or "").lower().strip()
    if not target_model:
        lowered_p = prompt.lower()
        if any(k in lowered_p for k in ("anime", "manga", "waifu", "kawaii", "chibi", "comic")):
            target_model = "flux-anime"
        elif any(k in lowered_p for k in ("photo", "photorealistic", "realism", "portrait", "dslr")):
            target_model = "flux-realism"
        elif any(k in lowered_p for k in ("3d", "render", "unreal", "blender", "cgi")):
            target_model = "flux-3d"
        else:
            target_model = "flux"

    url = f"https://image.pollinations.ai/prompt/{enc_prompt}?width=1024&height=1024&nologo=true&seed={used_seed}&model={urllib.parse.quote(target_model)}{image_param}"
    try:
        resp = await client.get(url, timeout=40.0)
        if resp.status_code == 200 and len(resp.content) > 1000:
            target = store / f"{uuid.uuid4().hex}.jpg"
            target.write_bytes(resp.content)
            return {"file_path": str(target), "seed": used_seed, "model": target_model}
    except Exception as exc:
        logger.warning("Pollinations image fetch error (model=%s, seed=%s): %s", target_model, used_seed, exc)
    return None


async def _generate_via_pollinations(
    prompt: str,
    count: int,
    store: Path,
    reference_images: list[str] | None = None,
    seed: int | None = None,
    model: str | None = None,
) -> list[dict]:
    num_to_fetch = min(max(1, count), 4)
    ref_img = reference_images[0] if reference_images else None
    base_seed = seed if seed is not None else random.randint(1000, 900000)
    async with httpx.AsyncClient(timeout=45.0, follow_redirects=True) as client:
        tasks = [
            _fetch_single_pollination(
                client,
                prompt,
                store,
                reference_image=ref_img,
                seed=base_seed + i,
                model=model,
            )
            for i in range(num_to_fetch)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        entries: list[dict] = []
        for res in results:
            if isinstance(res, dict) and res.get("file_path"):
                entries.append(res)
        return entries


async def generate_cloud_images(
    prompt: str,
    count: int = 1,
    reference_images: list[str] | None = None,
    seed: int | None = None,
    model: str | None = None,
) -> list[dict]:
    """Generate images over cloud APIs and persist them locally.

    Falls through Freepik -> Custom Gateway / OpenAI -> Pollinations fallback.
    Returns list of {"file_path": str | None}.
    """
    settings = get_settings()
    store = _image_store_dir()
    entries: list[dict] = []

    # Map Seedance image requests to FLUX rather than raising an error
    if model and "seedance" in model.lower():
        model = "flux"
    elif model and any(marker in model.lower() for marker in ("video", "animate", "motion", "clip")):
        from ..errors import HinaaError
        raise HinaaError(
            "VIDEO_GENERATION_FORBIDDEN",
            "Video generation is strictly forbidden in this environment.",
            status_code=403,
        )

    # If reference images were passed as base64 data URIs, persist them locally
    if reference_images:
        for idx, ref in enumerate(reference_images):
            if ref and ref.startswith("data:image"):
                try:
                    header, b64_data = ref.split(",", 1)
                    ref_path = store / f"ref_{uuid.uuid4().hex}.jpg"
                    ref_path.write_bytes(base64.b64decode(b64_data))
                    logger.info("Persisted local reference asset %d: %s", idx + 1, ref_path.name)
                except Exception as ex:
                    logger.debug("Could not decode base64 reference: %s", ex)

    # 1. Try Freepik/Magnific API if configured
    active_image_key = settings.active_freepik_key
    if active_image_key:
        try:
            logger.info("Generating cloud image via Freepik/Magnific AI Suite...")
            entries = await _generate_via_freepik(
                prompt, count, active_image_key.get_secret_value(), store
            )
            if entries:
                return entries
        except Exception as exc:
            logger.warning("Freepik/Magnific generation failed: %s", exc)

    # 2. Try Custom Base URL / OpenAI if configured
    custom_key = settings.active_custom_key
    custom_base = settings.active_custom_base_url
    if custom_key and custom_base:
        try:
            logger.info("Generating cloud image via custom gateway (model=%s)...", model or "default")
            entries = await _generate_via_openai_compat(
                prompt, count, custom_key.get_secret_value(), custom_base, store, model=model
            )
            if entries:
                return entries
        except Exception as exc:
            logger.warning("Custom gateway image generation failed: %s", exc)

    # 3. Try OpenAI Direct if configured
    if settings.openai_api_key:
        try:
            logger.info("Generating cloud image via OpenAI DALL-E (model=%s)...", model or "dall-e-3")
            entries = await _generate_via_openai_compat(
                prompt, count, settings.openai_api_key.get_secret_value(), "https://api.openai.com/v1", store, model=model
            )
            if entries:
                return entries
        except Exception as exc:
            logger.warning("OpenAI image generation failed: %s", exc)

    # 4. Zero-cost Cloud Fallback: Pollinations.ai (Flux, Anime, Realism, 3D)
    try:
        logger.info("Generating cloud image via Pollinations.ai (model=%s, seed=%s)...", model or "auto", seed)
        entries = await _generate_via_pollinations(
            prompt, count, store, reference_images=reference_images, seed=seed, model=model
        )
        if entries:
            return entries
    except Exception as exc:
        logger.error("Pollinations image generation failed: %s", exc)

    while len(entries) < min(max(1, count), 10):
        entries.append({"file_path": None})
    return entries