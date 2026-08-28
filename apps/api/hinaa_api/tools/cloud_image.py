"""
hinaa_api/tools/cloud_image.py
Cloud image generation fallback (hcnsec OpenAI-compatible /images/generations).

When local ComfyUI is offline, image_generate routes here and stores the PNGs
under apps/api/data/images so the existing /v1/generated-images serve path and
tool-poll flow work unchanged.
"""
from __future__ import annotations

import logging
import uuid
from pathlib import Path

import httpx

from ..config import get_settings

logger = logging.getLogger("hinaa.cloud_image")

_IMAGE_STORE = Path("apps/api/data/images")


def cloud_image_available() -> bool:
    settings = get_settings()
    key = settings.active_custom_key
    base = settings.active_custom_base_url
    return bool(key and base)


def _image_store_dir() -> Path:
    store = _IMAGE_STORE.resolve()
    store.mkdir(parents=True, exist_ok=True)
    return store


async def generate_cloud_images(prompt: str, count: int = 1) -> list[dict]:
    """Generate images over the cloud gateway and persist them locally.

    Returns one entry per image: {"file_path": str | None}. Downloads are
    bounded to the first `count` results (max 10).
    """
    settings = get_settings()
    key = settings.active_custom_key
    base = settings.active_custom_base_url
    if not key or not base:
        return [{"file_path": None}] * min(max(1, count), 10)

    url = f"{base.rstrip('/')}/images/generations"
    headers = {"Authorization": f"Bearer {key.get_secret_value()}"}
    payload = {
        "model": "step-image-edit-2",
        "prompt": prompt,
        "n": min(max(1, count), 10),
        "size": "1024x1024",
    }

    entries: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=150.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json().get("data", [])
            store = _image_store_dir()
            for item in data[:count]:
                image_url = item.get("url")
                if not image_url:
                    entries.append({"file_path": None})
                    continue
                try:
                    img_resp = await client.get(image_url, timeout=120.0)
                    img_resp.raise_for_status()
                    ext = ".png"
                    ctype = img_resp.headers.get("content-type", "")
                    if "jpeg" in ctype or "jpg" in image_url:
                        ext = ".jpg"
                    file_name = f"{uuid.uuid4().hex}{ext}"
                    target = store / file_name
                    target.write_bytes(img_resp.content)
                    entries.append({"file_path": str(target)})
                except Exception as exc:  # noqa: BLE001 - one bad image must not fail the batch
                    logger.warning("cloud image download failed: %s", type(exc).__name__)
                    entries.append({"file_path": None})
    except Exception as exc:  # noqa: BLE001
        logger.error("cloud image generation failed: %s", type(exc).__name__)
        return [{"file_path": None}] * min(max(1, count), 10)

    while len(entries) < min(max(1, count), 10):
        entries.append({"file_path": None})
    return entries