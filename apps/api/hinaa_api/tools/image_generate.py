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

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timezone
import logging
from pathlib import Path
import random
import re
from typing import Any, Dict, Literal, Optional
import uuid

from pydantic import BaseModel

from ..config import DATA_DIR, get_settings
from ..persistence.db import get_session_factory
from ..persistence.orm import Conversation, GenerationSet, ImageJob
from ..errors import HinaaError
from ..providers.local_comfyui import ComfyUIConfig, LocalComfyUIProvider
from ..providers.magnific import MagnificError, MagnificProvider
from .newbie_prompt_planner import NewBiePromptBuilder
from .registry import ToolDefinition, registry

logger = logging.getLogger("hinaa.image_generate")

settings = get_settings()
comfyui_provider = LocalComfyUIProvider(
    ComfyUIConfig(
        base_url=settings.comfyui_base_url,
        max_concurrency=settings.comfyui_max_concurrent_jobs,
    )
)


def cloud_image_available() -> bool:
    """Check if Stability AI, Magnific, or Freepik cloud image rendering is configured."""
    try:
        from ..providers.stability_ai import StabilityAIProvider
        if StabilityAIProvider(get_settings()).available():
            return True
    except Exception:
        pass
    try:
        return MagnificProvider(get_settings()).available()
    except Exception:
        return False


def resolve_upscale(params: "ImageGenerateParams") -> bool:
    """Whether the Magnific upscale second pass runs for this request.

    An explicit `upscale` always wins; `ultra` upscales unconditionally; the
    `quality` tier follows MAGNIFIC_UPSCALE_DEFAULT; `fast` stays single-pass.
    """
    if params.upscale is not None:
        return params.upscale
    if params.mode == "ultra":
        return True
    return params.mode == "quality" and settings.magnific_upscale_default


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


_REF_STOPWORDS = {
    "image", "images", "picture", "pictures", "photo", "photos", "pic",
    "find", "fetch", "search", "show", "give", "get", "me", "the", "a",
    "an", "of", "for", "some", "any", "like", "reference", "based", "use",
}


def _subject_tokens(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9']+", text.lower())
        if len(token) > 2 and token not in _REF_STOPWORDS
    }


def reference_from_query_result(search_result: Dict[str, Any], subject: str = "") -> Optional[str]:
    """Pick the reference image whose metadata best matches the requested subject."""
    images = search_result.get("images") if isinstance(search_result, dict) else None
    if not isinstance(images, list):
        return None
    wanted = _subject_tokens(subject)
    best: tuple[float, int, str] | None = None
    for position, item in enumerate(images):
        url = None
        haystack = ""
        if isinstance(item, str):
            url = item
            haystack = item
        elif isinstance(item, dict):
            url = item.get("url") or item.get("image_url") or item.get("thumbnailUrl") or item.get("imageUrl")
            haystack = " ".join(
                str(item.get(key) or "") for key in ("title", "alt", "name", "description", "source")
            ) + " " + str(url or "")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        tokens = _subject_tokens(haystack)
        score = (len(wanted & tokens) / len(wanted)) if wanted else 0.0
        ranked = score * 10 - position * 0.01
        if best is None or ranked > best[0]:
            best = (ranked, position, url)
    return best[2] if best else None


# ─── tool contract ───────────────────────────────────────────────────────────

class ImageGenerateParams(BaseModel):
    model_config = {"extra": "ignore"}
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: Literal["fast", "quality", "ultra"] = "quality"
    style: Literal["anime", "realistic", "cinematic", "3d-art", "watercolor", "digital", "custom"] = "custom"
    enhance: bool = True
    upscale: Optional[bool] = None
    reference_url: Optional[str] = None
    reference_image_b64: Optional[str] = None
    reference_query: Optional[str] = None
    strategy: str = "VARIATIONS"
    # Filled by authenticated tool dispatcher
    userId: str = "default_user"
    conversationId: Optional[str] = None
    attachment_ids: list[str] = []
    reference_images: list[str] = []
    imageUrl: Optional[str] = None
    engine: Optional[str] = None
    references: list[dict[str, Any]] = []


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
    requires_confirmation=False,
    cancellable=True,
    voice_aliases=["draw", "generate an image", "create a picture", "make an image"],
)


def _image_store() -> Path:
    store = DATA_DIR / "images"
    store.mkdir(parents=True, exist_ok=True)
    return store


_LOCAL_REF = re.compile(r"/(?:api/)?v1/generated-images/(?P<image_id>[a-zA-Z0-9_.-]+)")

# A scheme means the gateway can read it itself -- a link it fetches or a data URL
# it decodes. Two letters minimum, so a Windows path is not mistaken for one.
_FETCHABLE = re.compile(r"^(?:[a-zA-Z][a-zA-Z0-9+.\-]+:|//)")

_STORE_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}


def _reference_file(image_id: str, user_id: str) -> Optional[Path]:
    """The picture on disk behind a generated-images link, in either shape.

    A job id carries an owner and is refused across users; a saved file name has
    no job row at all (Freepik renders are written straight to the store) and is
    only accepted when it resolves inside the image store.
    """
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        job = session.get(ImageJob, image_id)
        if job:
            owner = session.get(GenerationSet, job.generation_set_id)
            if owner is None or owner.user_id != user_id:
                raise HinaaError("IMAGE_NOT_FOUND", "Reference image not found.", 404)
            if job.file_path and Path(job.file_path).is_file():
                return Path(job.file_path)

    store = _image_store()
    name = Path(image_id).name
    candidates = [store / name, *(store / f"{name}{ext}" for ext in _STORE_MIME)]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if resolved.is_relative_to(store.resolve()):
            return resolved
    return None


def _reference_candidate(params: ImageGenerateParams) -> str:
    """The one reference this workflow takes, in whichever shape it arrived."""
    candidate = params.reference_url or ""
    if not candidate and not params.reference_image_b64 and params.reference_images:
        # A picture from his own grid arrives as the serve route's link, in
        # whichever shape that route answers: a job id or a saved file name.
        candidate = params.reference_images[0]
    return candidate.strip()


def _resolve_reference_target(candidate: str, user_id: str) -> tuple[Optional[str], Optional[Path]]:
    """Return (link the gateway opens, picture on this server) for a reference.

    A scheme means the gateway reads it itself: a link it fetches or a data URL
    it decodes. Anything else names a picture this server already has, and is
    looked up here. Posted to the vendor as it arrived, a bare job id cost a
    credit and came back "Invalid or corrupted image" after this server had
    already said the reference applied.
    """
    url = candidate.strip()
    if _FETCHABLE.match(url):
        return url, None
    local = _LOCAL_REF.search(url)
    image_id = local.group("image_id") if local else url
    path = _reference_file(image_id, user_id)
    if path is None:
        if local:
            raise HinaaError("IMAGE_NOT_FOUND", "Reference image not found.", 404)
        raise HinaaError(
            "IMAGE_REFERENCE_UNREADABLE",
            f"That reference ({image_id[:60]}) is not a web address and not a picture "
            "this server has. Attach the image again, or ask for it by its link.",
            400,
        )
    return None, path


async def _resolve_reference(params: ImageGenerateParams) -> tuple[Optional[str], Optional[str]]:
    """Return (reference_url, reference_b64) from explicit inputs or context."""
    candidate = _reference_candidate(params)
    if candidate:
        url, path = _resolve_reference_target(candidate, params.userId)
        if url is not None:
            return url, None
        # The gateway reads bytes, not a link to this machine: a relative
        # path or a tunnel URL would either fail or fetch the wrong thing.
        mime = _STORE_MIME.get(path.suffix.lower(), "image/png")
        data = base64.b64encode(path.read_bytes()).decode("ascii")
        return None, f"data:{mime};base64,{data}"
    if params.reference_image_b64 and params.reference_image_b64.startswith("data:image"):
        return None, params.reference_image_b64.strip()
    query = (params.reference_query or "").strip()
    if query:
        try:
            from ..providers.youcom import YouComClient

            result = await YouComClient(get_settings()).image_search(query, count=6)
            found = reference_from_query_result(result, query)
            if found:
                return found, None
        except Exception:
            return None, None
    return None, None


def _update_status(job_id: str, status: str, *, prompt_id: str | None = None, file_path: str | None = None) -> None:
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        job = session.get(ImageJob, job_id)
        if not job or job.status == "cancelled":
            return
        job.status = status
        if prompt_id:
            job.comfy_prompt_id = prompt_id
        if file_path:
            job.file_path = file_path
        if status in {"completed", "failed"}:
            job.completed_at = datetime.now(timezone.utc)
        session.commit()


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
        jobs = [
            ImageJob(
                generation_set_id=generation_set_id,
                seed=base_seed + index,
                status="pending",
                width=width,
                height=height,
            )
            for index in range(count)
        ]
        session.add_all(jobs)
        session.commit()

    cloud = MagnificProvider(settings)
    stability = None
    try:
        from ..providers.stability_ai import StabilityAIProvider
        stability_cand = StabilityAIProvider(settings)
        if stability_cand.available():
            stability = stability_cand
    except Exception:
        pass

    use_cloud = cloud.available() or (stability is not None and stability.available())

    try:
        reference_url, reference_b64 = (await _resolve_reference(params)) if use_cloud else (None, None)
        should_upscale = resolve_upscale(params)

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
                        blob = None
                        provider_tag = "magnific"
                        if cloud.available():
                            try:
                                result = await cloud.generate(
                                    final_prompt,
                                    negative_prompt=negative,
                                    width=job.width,
                                    height=job.height,
                                    seed=job.seed,
                                    model=(
                                        cloud.settings.magnific_model_fast
                                        if params.mode == "fast"
                                        else cloud.settings.magnific_model_quality
                                    ),
                                    reference_image_url=reference_url,
                                    reference_image_b64=reference_b64,
                                )
                                source = result.image_urls[0]
                                if should_upscale:
                                    try:
                                        upscale_profile = {
                                            "anime": "art_n_illustration",
                                            "watercolor": "art_n_illustration",
                                            "3d-art": "3d_renders",
                                            "realistic": "films_n_photography",
                                            "cinematic": "films_n_photography",
                                        }.get(params.style, "standard")
                                        upscaled = await cloud.upscale(
                                            source,
                                            scale=2.0,
                                            prompt=final_prompt,
                                            optimized_for=upscale_profile,
                                        )
                                        asset_ref = getattr(upscaled, "asset_ref", None)
                                        if asset_ref is not None:
                                            blob = cloud.asset_store.read_bytes(asset_ref.id)
                                        elif isinstance(upscaled, str):
                                            source = upscaled
                                    except Exception:
                                        logger.warning(
                                            "Upscale pass failed for job %s; the render is kept",
                                            job.id,
                                            exc_info=True,
                                        )
                                if blob is None:
                                    blob = await cloud.download(source)
                                provider_tag = result.provider
                            except Exception as m_err:
                                logger.warning(
                                    "Magnific/Freepik render failed (%s); failing over to Stability AI...",
                                    m_err,
                                )
                                if stability and stability.available():
                                    st_res = await stability.generate_image(
                                        final_prompt,
                                        negative_prompt=negative,
                                        seed=job.seed,
                                        style_preset=params.style,
                                    )
                                    blob = st_res.image_bytes
                                    provider_tag = st_res.provider
                                else:
                                    raise
                        elif stability and stability.available():
                            st_res = await stability.generate_image(
                                final_prompt,
                                negative_prompt=negative,
                                seed=job.seed,
                                style_preset=params.style,
                            )
                            blob = st_res.image_bytes
                            provider_tag = st_res.provider
                        else:
                            raise RuntimeError("No cloud image provider is configured.")

                        file_path = store / f"HINAA_{job.id}_{job.seed}.png"
                        file_path.write_bytes(blob)
                        job.file_path = str(file_path)
                        job.comfy_prompt_id = provider_tag
                        job.status = "completed"
                        job.completed_at = datetime.now(timezone.utc)
                        session.commit()
                    except MagnificError as error:
                        job.status = "failed"
                        session.commit()
                        logger.warning(
                            "Image job %s failed on %s: [%s] %s",
                            job.id, cloud.settings.magnific_base_url or "magnific",
                            error.code, error,
                        )
                        if error.code in {"MAGNIFIC_KEY_INVALID", "MAGNIFIC_NOT_CONFIGURED"}:
                            for rest in jobs:
                                if rest.status in {"pending", "processing"}:
                                    rest.status = "failed"
                            session.commit()
                            break
                    except Exception:
                        job.status = "failed"
                        session.commit()
                        logger.exception("Image job %s failed after the render started", job.id)
            return

        # ── local fallback (ComfyUI) ─────────────────────────────────────
        if not await comfyui_provider.health_check():
            with session_factory() as session:
                for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id, status="pending").all():
                    job.status = "failed"
                session.commit()
            return

        async def enqueue_one(job_id: str) -> tuple[str, str] | None:
            session_factory = get_session_factory(settings)
            with session_factory() as session:
                job = session.get(ImageJob, job_id)
                if not job or job.status == "cancelled":
                    return None
                seed = job.seed
                prefix = f"HINAA_{job.id}_{seed}"
            try:
                prompt_id = await comfyui_provider.enqueue_prompt(
                    prompt=params.prompt,
                    negative_prompt=params.negative_prompt,
                    seed=seed,
                    width=width,
                    height=height,
                    filename_prefix=prefix,
                    mode=params.mode,
                    reference_image=params.reference_images[0] if params.reference_images else None,
                )
                _update_status(job_id, "queued", prompt_id=prompt_id)
                return job_id, prompt_id
            except Exception:
                _update_status(job_id, "failed")
                return None

        with session_factory() as session:
            job_ids = [j.id for j in session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all()]

        enqueued = [item for item in await asyncio.gather(*(enqueue_one(job_id) for job_id in job_ids)) if item]

        async def collect_one(job_id: str, prompt_id: str) -> None:
            try:
                result = await comfyui_provider.collect_prompt(prompt_id)
                first_output = result.output_files[0] if result.output_files else None
                if first_output:
                    _update_status(job_id, "completed", prompt_id=result.prompt_id, file_path=first_output)
                else:
                    _update_status(job_id, "failed", prompt_id=result.prompt_id)
            except Exception:
                _update_status(job_id, "failed", prompt_id=prompt_id)

        await asyncio.gather(*(collect_one(job_id, prompt_id) for job_id, prompt_id in enqueued))

    except Exception:
        logger.exception("Image workflow %s failed before any render landed", generation_set_id)
        with session_factory() as session:
            for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all():
                if job.status in {"pending", "processing"}:
                    job.status = "failed"
            session.commit()


async def image_generate_handler(params: ImageGenerateParams) -> Dict[str, Any]:
    if params.imageUrl and not params.reference_images:
        params.reference_images = [params.imageUrl]
    if params.reference_images and len(params.reference_images) > 1:
        return {
            "status": "error",
            "code": "MULTI_REFERENCE_UNSUPPORTED",
            "error": "This image workflow supports one reference at a time. Remove additional references and retry.",
        }

    cloud_ready = cloud_image_available()
    comfy_ready = await comfyui_provider.health_check()
    gateway_carries_reference = cloud_ready and MagnificProvider(get_settings()).honours_reference_image()

    if params.reference_images and not (gateway_carries_reference or comfy_ready):
        return {
            "status": "error",
            "code": "REFERENCE_RENDERER_UNAVAILABLE",
            "error": (
                "No renderer in this deployment can take your picture: the cloud gateway here "
                "generates from text only and local ComfyUI is not running. Nothing was started; "
                "ask for a new image from the description instead."
            ),
        }

    if not comfy_ready and not cloud_ready:
        return {
            "status": "error",
            "code": "IMAGE_RENDERER_UNAVAILABLE",
            "error": (
                "Local ComfyUI is unavailable and no cloud image gateway is configured. "
                "Start ComfyUI on http://127.0.0.1:8188 or configure Freepik/Codex keys."
            ),
        }

    candidate = _reference_candidate(params)
    if candidate:
        # The same check the worker runs, before this server promises the
        # reference applied and files a job that can only fail.
        try:
            _resolve_reference_target(candidate, params.userId)
        except HinaaError as error:
            return {"status": "error", "code": error.code, "error": error.message}

    generation_set_id = str(uuid.uuid4())
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        validated_conv_id: str | None = None
        if params.conversationId:
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
    total_count = min(max(1, params.count), 10)
    strategy = "independent-queue-variations" if comfy_ready else "cloud-gateway-step-image"

    # Fire and forget
    asyncio.create_task(run_image_job(generation_set_id, params))

    return {
        "status": "processing",
        "job_id": generation_set_id,
        "total": total_count,
        "strategy": strategy,
        "renderer": "magnific-flux" if cloud_ready else "comfyui-local",
        "style": params.style,
        "mode": params.mode,
        "reference_applied": bool(params.reference_url or params.reference_image_b64 or params.reference_query or params.reference_images),
        "upscale": resolve_upscale(params),
        "prompt": params.prompt,
        "enhanced_prompt": final_prompt,
    }


registry.register(image_generate_def, image_generate_handler)
