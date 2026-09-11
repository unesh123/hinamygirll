"""HINAA image generation — Magnific FLUX cloud brain with a local fallback.

The cloud path (Magnific / Freepik FLUX) is the primary renderer whenever a
key is configured: prompts are enhanced with the same discipline ChatGPT uses
for DALL·E (lighting, camera, medium, mood, quality markers, sane negatives),
style presets append tuned suffixes, and a reference image — a URL, a data URL,
or a subject Hinaa finds on the web right now — turns the request into a
reference-guided generation. `ultra` mode runs the second Magnific upscale
pass. When cloud keys are absent, the durable local ComfyUI worker takes the
same job contract, so the studio UI never needs to know which brain rendered.
"""

import asyncio
import re
import uuid
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel

from .registry import ToolDefinition, registry
from ..providers.local_comfyui import LocalComfyUIProvider, ComfyUIConfig
from ..providers.magnific import MagnificError, MagnificProvider
from .newbie_prompt_planner import NewBiePromptBuilder
from ..persistence.db import get_session_factory, session_scope
from ..persistence.orm import GenerationSet, ImageJob
from ..config import get_settings

settings = get_settings()

# ─── style + prompt engineering ──────────────────────────────────────────────

DEFAULT_NEGATIVE = (
    "blurry, low quality, artifacts, watermark, deformed, bad anatomy, "
    "disfigured, jpeg noise, oversaturated, text overlay"
)

STYLE_PRESETS: Dict[str, Dict[str, str]] = {
    "anime": {
        "suffix": ", anime style, cel shaded, vibrant colors, sharp clean lineart, expressive eyes",
        "negative": "realistic, photographic, 3d render, plastic skin",
    },
    "realistic": {
        "suffix": ", photorealistic, 8k uhd, dslr photo, natural skin texture, sharp focus",
        "negative": "anime, cartoon, illustration, painting, cgi",
    },
    "cinematic": {
        "suffix": ", cinematic lighting, movie still, anamorphic lens, dramatic shadows, film grain",
        "negative": "flat lighting, overexposed, stock photo",
    },
    "3d-art": {
        "suffix": ", 3d render, octane, subsurface scattering, volumetric lighting, high poly detail",
        "negative": "flat, 2d, sketch, low poly",
    },
    "watercolor": {
        "suffix": ", watercolor painting, soft pigment washes, paper texture, delicate edges",
        "negative": "photographic, hard lines, digital artifacts",
    },
    "digital": {
        "suffix": ", digital art, concept art, trending artstation quality, rich color grading",
        "negative": "amateur, blurry, muddy colors",
    },
    "custom": {"suffix": "", "negative": ""},
}

_QUALITY_MARKERS = re.compile(r"8k|uhd|highly detailed|sharp focus|masterpiece", re.I)
_LIGHTING_MARKERS = re.compile(r"lighting|lit|glow|golden hour|candlelight|neon|backlit", re.I)
_CAMERA_MARKERS = re.compile(r"camera|lens|angle|portrait shot|wide shot|close-?up|bokeh", re.I)
_MOOD_MARKERS = re.compile(r"mood|atmosphere|cinematic|ethereal|gritty|cozy|dramatic", re.I)


def enhance_prompt(prompt: str, style: str, mode: str) -> tuple[str, str]:
    """ChatGPT-style prompt engineering: enrich a short user idea into a
    precise generation prompt without overwriting what the user chose."""
    enriched = prompt.strip().rstrip(",")
    lower = enriched.lower()
    if not _LIGHTING_MARKERS.search(lower):
        enriched += ", cinematic soft key lighting with gentle rim light"
    if not _CAMERA_MARKERS.search(lower):
        enriched += ", balanced composition, eye-level 50mm lens"
    if not _MOOD_MARKERS.search(lower):
        enriched += ", atmospheric mood"
    preset = STYLE_PRESETS.get(style, STYLE_PRESETS["custom"])
    enriched += preset["suffix"]
    if not _QUALITY_MARKERS.search(lower):
        enriched += ", masterpiece, best quality, highly detailed"
    if mode == "ultra":
        enriched += ", ultra high resolution, fine texture detail"
    negative = ", ".join(filter(None, [DEFAULT_NEGATIVE, preset["negative"]]))
    return enriched, negative


def reference_from_query_result(search_result: Dict[str, Any]) -> Optional[str]:
    images = search_result.get("images") if isinstance(search_result, dict) else None
    if not isinstance(images, list):
        return None
    for item in images:
        url = None
        if isinstance(item, str):
            url = item
        elif isinstance(item, dict):
            url = item.get("url") or item.get("image_url") or item.get("thumbnailUrl")
        if isinstance(url, str) and url.startswith(("http://", "https://")):
            return url
    return None


# ─── tool contract ───────────────────────────────────────────────────────────

class ImageGenerateParams(BaseModel):
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: Literal["fast", "quality", "ultra"] = "fast"
    style: Literal["anime", "realistic", "cinematic", "3d-art", "watercolor", "digital", "custom"] = "custom"
    enhance: bool = True
    upscale: Optional[bool] = None
    reference_url: Optional[str] = None
    reference_image_b64: Optional[str] = None
    reference_query: Optional[str] = None
    strategy: str = "VARIATIONS"
    # Filled by the authenticated tool dispatcher. Making it required prevents
    # a durable image record from ever silently falling back to a placeholder owner.
    userId: str
    conversationId: Optional[str] = None

image_generate_def = ToolDefinition(
    name="image_generate",
    display_name="Generate Image",
    description=(
        "Generate high quality images with the Magnific FLUX cloud brain (style presets, "
        "prompt enhancement, optional reference-guided generation, ultra upscale pass); "
        "falls back to local ComfyUI when no cloud key is configured. Batch count up to 10. "
        "modes: fast, quality, ultra."
    ),
    parameters={
        "prompt": {"type": "string", "description": "What to draw, in the user's words."},
        "negative_prompt": {"type": "string", "description": "What to avoid (auto-filled with quality negatives when empty)."},
        "seed": {"type": "integer", "description": "Random seed (optional). Same seed + prompt reproduces a variation family."},
        "count": {"type": "integer", "description": "Number of images to generate (max 10)."},
        "mode": {"type": "string", "description": "'fast' 768², 'quality' 1024², 'ultra' 1024×1536 with Magnific upscale pass."},
        "style": {"type": "string", "description": "anime | realistic | cinematic | 3d-art | watercolor | digital | custom."},
        "enhance": {"type": "boolean", "description": "Apply the prompt enhancer (default true)."},
        "upscale": {"type": "boolean", "description": "Force or skip the Magnific upscale second pass (default: only for ultra)."},
        "reference_url": {"type": "string", "description": "Public image URL to use as a visual reference."},
        "reference_image_b64": {"type": "string", "description": "data:image/... base64 upload to use as a visual reference."},
        "reference_query": {"type": "string", "description": "Subject to look up and use as a reference (e.g. 'Mikasa Ackerman')."},
    },
    required_parameters=["prompt"],
    requires_confirmation=True,
    cancellable=True,
    voice_aliases=["draw", "generate an image", "create a picture", "make an image"],
)

comfyui_provider = LocalComfyUIProvider(ComfyUIConfig())


def _image_store() -> Path:
    store = Path("apps/api/data/images").absolute()
    store.mkdir(parents=True, exist_ok=True)
    return store


_LOCAL_REF = re.compile(r"/v1/generated-images/(?P<job_id>[0-9a-fA-F-]+)")


async def _resolve_reference(params: ImageGenerateParams) -> tuple[Optional[str], Optional[str]]:
    """Return (reference_url, reference_b64) from explicit inputs or context."""
    if params.reference_url:
        url = params.reference_url.strip()
        # A reference pointing at Hinaa's own gallery cannot be fetched by the
        # cloud vendor; resolve it to the durable local file instead.
        local = _LOCAL_REF.search(url)
        if local:
            factory = get_session_factory(get_settings())
            with factory() as lookup:
                source_job = lookup.get(ImageJob, local.group("job_id"))
                if source_job and source_job.file_path and Path(source_job.file_path).exists():
                    import base64 as _b64

                    mime = "image/png" if source_job.file_path.lower().endswith(".png") else "image/jpeg"
                    data = _b64.b64encode(Path(source_job.file_path).read_bytes()).decode("ascii")
                    return None, f"data:{mime};base64,{data}"
        return url, None
    if params.reference_image_b64 and params.reference_image_b64.startswith("data:image"):
        return None, params.reference_image_b64.strip()
    query = (params.reference_query or "").strip()
    if query:
        try:
            from ..providers.youcom import YouComClient

            result = await YouComClient(get_settings()).image_search(query, count=6)
            found = reference_from_query_result(result)
            if found:
                return found, None
        except Exception:  # noqa: BLE001 - reference lookup is best-effort
            return None, None
    return None, None


async def run_image_job(generation_set_id: str, params: ImageGenerateParams):
    count = min(max(1, params.count), 10)

    if params.mode == "ultra":
        width, height = 1024, 1536
    elif params.mode == "quality":
        width, height = 1024, 1024
    else:
        width, height = 768, 768

    user_negative = params.negative_prompt.strip()
    if params.enhance:
        final_prompt, auto_negative = enhance_prompt(params.prompt, params.style, params.mode)
    else:
        final_prompt = (
            NewBiePromptBuilder.build_xml_prompt(params.prompt)
            if params.mode == "ultra"
            else params.prompt.strip()
        )
        auto_negative = DEFAULT_NEGATIVE
    negative = f"{user_negative}, {auto_negative}" if user_negative else auto_negative

    session_factory = get_session_factory(settings)
    with session_factory() as session:
        base_seed = params.seed if params.seed is not None else random.randint(1, 1_000_000)
        for i in range(count):
            seed = base_seed + i
            job = ImageJob(
                generation_set_id=generation_set_id,
                seed=seed,
                status="pending",
                width=width,
                height=height,
            )
            session.add(job)
        session.commit()

    cloud = MagnificProvider(settings)
    use_cloud = cloud.available()

    try:
        reference_url, reference_b64 = (await _resolve_reference(params)) if use_cloud else (None, None)
        should_upscale = params.upscale if params.upscale is not None else (params.mode == "ultra")

        if use_cloud:
            with session_factory() as session:
                jobs = session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all()
                store = _image_store()
                for job in jobs:
                    if job.status == "cancelled":
                        continue
                    job.status = "processing"
                    session.commit()
                    try:
                        result = await cloud.generate(
                            final_prompt,
                            negative_prompt=negative,
                            width=job.width,
                            height=job.height,
                            seed=job.seed,
                            reference_image_url=reference_url,
                            reference_image_b64=reference_b64,
                        )
                        source = result.image_urls[0]
                        if should_upscale:
                            try:
                                source = await cloud.upscale(source, scale=2.0)
                            except MagnificError:
                                # An upscale failure must not lose the draft.
                                pass
                        blob = await cloud.download(source)
                        file_path = store / f"HINAA_{job.id}_{job.seed}.png"
                        file_path.write_bytes(blob)
                        job.file_path = str(file_path)
                        job.comfy_prompt_id = result.provider
                        job.status = "completed"
                        job.completed_at = datetime.now(timezone=True)
                        session.commit()
                    except MagnificError as error:
                        job.status = "failed"
                        session.commit()
                        if error.code in {"MAGNIFIC_KEY_INVALID", "MAGNIFIC_NOT_CONFIGURED"}:
                            # Do not burn the remaining batch on a dead key.
                            for rest in jobs:
                                if rest.status in {"pending", "processing"}:
                                    rest.status = "failed"
                            session.commit()
                            break
                    except Exception:  # noqa: BLE001 - one slot failing must not kill the set
                        job.status = "failed"
                        session.commit()
            return

        # ── local fallback (unchanged job contract) ──────────────────────
        if not await comfyui_provider.health_check():
            with session_factory() as session:
                for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id, status="pending").all():
                    job.status = "failed"
                session.commit()
            return

        with session_factory() as session:
            jobs = session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all()
            for job in jobs:
                if job.status == "cancelled":
                    continue
                job.status = "processing"
                session.commit()
                prefix = f"HINAA_{job.id}_{job.seed}"
                try:
                    res = await comfyui_provider.submit_prompt(
                        prompt=params.prompt,
                        negative_prompt=params.negative_prompt,
                        seed=job.seed,
                        width=job.width,
                        height=job.height,
                        filename_prefix=prefix,
                        mode=params.mode,
                    )
                    job.comfy_prompt_id = res.prompt_id
                    if not res.output_files:
                        raise ValueError("ComfyUI completed without a downloadable image output.")
                    job.file_path = res.output_files[0]
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone=True)
                    session.commit()
                except Exception as e:
                    job.status = "failed"
                    session.commit()
                    if "CUDA out of memory" in str(e) or "Memory" in str(e):
                        break

    except Exception:
        # Never leave a durable slot in an untruthful in-progress state after
        # the worker itself fails. The poll route can then surface a clear
        # failure or partial-success result while keeping completed outputs.
        with session_factory() as session:
            for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all():
                if job.status in {"pending", "processing"}:
                    job.status = "failed"
            session.commit()


async def image_generate_handler(params: ImageGenerateParams) -> Dict[str, Any]:
    cloud = MagnificProvider(settings)
    cloud_ready = cloud.available()

    if not cloud_ready:
        # Fail before creating durable pending slots when the only supported
        # local renderer is offline. This keeps the chat action truthful and
        # gives the user a direct recovery path instead of a delayed generic
        # poll failure.
        if not await comfyui_provider.health_check():
            return {
                "status": "error",
                "error": (
                    "No image renderer is available. Add MAGNIFIC_API_KEY (or FREEPIK_API_KEY) "
                    "for cloud FLUX generation, or start ComfyUI on http://127.0.0.1:8188."
                ),
                "code": "COMFYUI_UNAVAILABLE",
                "localOnly": True,
            }

    generation_set_id = str(uuid.uuid4())

    settings_local = get_settings()
    session_factory = get_session_factory(settings_local)
    with session_factory() as session:
        # Validate conversationId — only use it if it exists in the DB to avoid FK failures
        validated_conv_id: str | None = None
        if params.conversationId:
            from hinaa_api.persistence.orm import Conversation

            exists = session.get(Conversation, params.conversationId)
            if exists:
                validated_conv_id = params.conversationId

        gen_set = GenerationSet(
            id=generation_set_id,
            user_id=params.userId,
            conversation_id=validated_conv_id,
            prompt=params.prompt,
            workflow_mode=params.mode,
        )
        session.add(gen_set)
        session.commit()

    final_prompt = enhance_prompt(params.prompt, params.style, params.mode)[0] if params.enhance else params.prompt

    # Fire and forget
    asyncio.create_task(run_image_job(generation_set_id, params))

    return {
        "status": "processing",
        "job_id": generation_set_id,
        "renderer": "magnific-flux" if cloud_ready else "comfyui-local",
        "style": params.style,
        "mode": params.mode,
        "reference_applied": bool(params.reference_url or params.reference_image_b64 or params.reference_query),
        "upscale": bool(params.upscale or params.mode == "ultra"),
        "prompt": params.prompt,
        "enhanced_prompt": final_prompt,
    }


registry.register(image_generate_def, image_generate_handler)
