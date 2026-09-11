from __future__ import annotations

import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Literal, Optional

from pydantic import BaseModel

from ..config import get_settings
from ..persistence.db import get_session_factory
from ..persistence.orm import GenerationSet, ImageJob
from ..providers.local_comfyui import ComfyUIConfig, LocalComfyUIProvider
from .cloud_image import generate_cloud_images, cloud_image_available
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


class ImageGenerateParams(BaseModel):
    model_config = {"extra": "ignore"}
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: Literal["fast", "quality", "ultra"] = "quality"
    strategy: str = "VARIATIONS"
    # Filled by the authenticated tool dispatcher. Making it required prevents
    # durable image records from silently falling back to a placeholder owner.
    userId: str
    conversationId: Optional[str] = None
    attachment_ids: list[str] = []
    reference_images: list[str] = []
    imageUrl: Optional[str] = None
    engine: Optional[str] = None
    references: list[dict[str, Any]] = []


image_generate_def = ToolDefinition(
    name="image_generate",
    display_name="Generate Image",
    description="Generate images privately through local ComfyUI. Variations are independent queue entries and may complete one at a time.",
    parameters={
        "prompt": {"type": "string", "description": "Positive prompt describing the image."},
        "negative_prompt": {"type": "string", "description": "Negative prompt (optional)."},
        "seed": {"type": "integer", "description": "Random seed (optional)."},
        "count": {"type": "integer", "description": "Number of images to generate (max 10)."},
        "mode": {"type": "string", "description": "'fast' for 768x768, 'quality' for 1024x1024, 'ultra' for 1024x1536."},
    },
    required_parameters=["prompt"],
    requires_confirmation=False,
    cancellable=True,
)


def _dimensions_and_prompt(params: ImageGenerateParams) -> tuple[int, int, str]:
    if params.mode == "ultra":
        return 1024, 1536, NewBiePromptBuilder.build_xml_prompt(params.prompt)
    if params.mode == "quality":
        return 1024, 1024, params.prompt
    return 768, 768, params.prompt


def _update_status(job_id: str, status: str, *, prompt_id: str | None = None, file_path: str | None = None) -> None:
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        job = session.get(ImageJob, job_id)
        if not job or job.status == "cancelled":
            return
        job.status = status
        if prompt_id is not None:
            job.comfy_prompt_id = prompt_id
        if file_path is not None:
            job.file_path = file_path
        if status == "completed":
            job.completed_at = datetime.now(timezone.utc)
        session.commit()


async def run_image_job(generation_set_id: str, params: ImageGenerateParams) -> None:
    """Queue variations independently and publish each durable result as it lands.

    This intentionally does *not* set a large ComfyUI latent `batch_size`.
    Independent prompt IDs are safer on a local GPU, make the UI responsive,
    and permit ComfyUI/custom nodes to schedule their own work correctly.
    """
    count = min(max(1, params.count), 10)
    width, height, prompt_value = _dimensions_and_prompt(params)
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
        job_ids = [job.id for job in jobs]

    if not await comfyui_provider.health_check():
        for job_id in job_ids:
            _update_status(job_id, "failed")
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
                prompt=prompt_value,
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

    # Submissions are bounded by the provider configuration. They finish quickly
    # because they only enqueue workflows; GPU execution remains ComfyUI-owned.
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

    # Each history poll is independent. The client sees the first completed slot
    # immediately rather than waiting for a whole batch to finish.
    await asyncio.gather(*(collect_one(job_id, prompt_id) for job_id, prompt_id in enqueued))

    # A cancellation can happen between queue submission and output collection;
    # every untouched durable slot must finish in a truthful terminal state.
    with session_factory() as session:
        for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id).all():
            if job.status in {"pending", "processing"}:
                job.status = "failed"
        session.commit()


async def image_generate_handler(params: ImageGenerateParams) -> dict[str, Any]:
    if params.imageUrl and not params.reference_images:
        params.reference_images = [params.imageUrl]
    if params.reference_images:
        if len(params.reference_images) > 1:
            return {"status": "error", "code": "MULTI_REFERENCE_UNSUPPORTED",
                    "error": "This image workflow supports one reference at a time. Remove additional references and retry."}
        try:
            comfyui_provider.validate_reference(params.reference_images[0])
        except ValueError as exc:
            return {"status": "error", "code": "INVALID_REFERENCE_IMAGE", "error": str(exc)}

    # Prefer local ComfyUI when it is online; otherwise fall back to the cloud image gateway
    if not await comfyui_provider.health_check():
        if params.reference_images:
            return {"status": "error", "code": "REFERENCE_RENDERER_UNAVAILABLE",
                    "error": "Reference editing needs local ComfyUI running. Cloud text-to-image fallback cannot preserve your reference; no job was started."}
        if not cloud_image_available():
            return {
                "status": "error",
                "error": "Local ComfyUI is unavailable and no cloud image gateway is configured. Start ComfyUI on http://127.0.0.1:8188 or configure Freepik/Codex keys.",
                "code": "IMAGE_RENDERER_UNAVAILABLE",
            }

        generation_set_id = str(uuid.uuid4())
        session_factory = get_session_factory(settings)
        total_count = min(max(1, params.count), 10)
        job_ids = [str(uuid.uuid4()) for _ in range(total_count)]
        with session_factory() as session:
            validated_conversation_id: str | None = None
            if params.conversationId:
                from hinaa_api.persistence.orm import Conversation

                if session.get(Conversation, params.conversationId):
                    validated_conversation_id = params.conversationId
            session.add(
                GenerationSet(
                    id=generation_set_id,
                    user_id=params.userId,
                    conversation_id=validated_conversation_id,
                    prompt=params.prompt,
                    workflow_mode=params.mode,
                )
            )
            for j_id in job_ids:
                session.add(
                    ImageJob(
                        id=j_id,
                        generation_set_id=generation_set_id,
                        seed=params.seed or 0,
                        status="processing",
                        width=1024,
                        height=1024,
                        file_path=None,
                    )
                )
            session.commit()

        async def run_cloud(generation_set_id: str, job_ids: list[str], params: ImageGenerateParams) -> None:
            try:
                results = await generate_cloud_images(
                    params.prompt,
                    len(job_ids),
                    reference_images=params.reference_images,
                    seed=params.seed,
                    model=params.engine,
                )
                session_factory = get_session_factory(settings)
                with session_factory() as session:
                    for idx, j_id in enumerate(job_ids):
                        job = session.query(ImageJob).filter_by(id=j_id).first()
                        if not job:
                            continue
                        file_path = results[idx].get("file_path") if idx < len(results) else None
                        if file_path:
                            job.status = "completed"
                            job.file_path = file_path
                            job.completed_at = datetime.now(timezone.utc)
                        else:
                            job.status = "failed"
                    session.commit()
            except Exception as exc:
                logger.error("Cloud image task failed for %s: %s", generation_set_id, exc, exc_info=True)
                session_factory = get_session_factory(settings)
                with session_factory() as session:
                    for j_id in job_ids:
                        job = session.query(ImageJob).filter_by(id=j_id).first()
                        if job and job.status == "processing":
                            job.status = "failed"
                    session.commit()

        asyncio.create_task(run_cloud(generation_set_id, job_ids, params))
        return {
            "status": "processing",
            "job_id": generation_set_id,
            "total": total_count,
            "strategy": "cloud-gateway-step-image",
            "engine": params.engine or "cloud-gateway",
        }

    generation_set_id = str(uuid.uuid4())
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        validated_conversation_id: str | None = None
        if params.conversationId:
            from hinaa_api.persistence.orm import Conversation

            if session.get(Conversation, params.conversationId):
                validated_conversation_id = params.conversationId

        session.add(
            GenerationSet(
                id=generation_set_id,
                user_id=params.userId,
                conversation_id=validated_conversation_id,
                prompt=params.prompt,
                workflow_mode=params.mode,
            )
        )
        session.commit()

    asyncio.create_task(run_image_job(generation_set_id, params))
    return {
        "status": "processing",
        "job_id": generation_set_id,
        "total": min(max(1, params.count), 10),
        "strategy": "independent-queue-variations",
        "engine": params.engine or "comfyui",
    }


registry.register(image_generate_def, image_generate_handler)
