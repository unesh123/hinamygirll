import asyncio
import time
import uuid
import random
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from .registry import ToolDefinition, registry
from ..providers.local_comfyui import LocalComfyUIProvider, ComfyUIConfig
from .newbie_prompt_planner import NewBiePromptBuilder
from ..persistence.db import get_session_factory, session_scope
from ..persistence.orm import GenerationSet, ImageJob
from ..config import get_settings

settings = get_settings()

class ImageGenerateParams(BaseModel):
    prompt: str
    negative_prompt: str = ""
    seed: Optional[int] = None
    count: int = 1
    mode: str = "fast" # "fast" (768x768), "quality" (1024x1024), "ultra" (1024x1536)
    strategy: str = "VARIATIONS"
    userId: Optional[str] = None
    conversationId: Optional[str] = None

image_generate_def = ToolDefinition(
    name="image_generate",
    display_name="Generate Image",
    description="Generate high quality images using local ComfyUI. Supports batch count up to 10. modes: fast, quality, ultra.",
    parameters={
        "prompt": {"type": "string", "description": "Positive prompt describing the image."},
        "negative_prompt": {"type": "string", "description": "Negative prompt (optional)."},
        "seed": {"type": "integer", "description": "Random seed (optional)."},
        "count": {"type": "integer", "description": "Number of images to generate (max 10)."},
        "mode": {"type": "string", "description": "'fast' for 768x768, 'quality' for 1024x1024, 'ultra' for 1024x1536."},
    },
    required_parameters=["prompt"],
    requires_confirmation=True,
    cancellable=True
)

comfyui_provider = LocalComfyUIProvider(ComfyUIConfig())

async def run_image_job(generation_set_id: str, params: ImageGenerateParams):
    count = min(max(1, params.count), 10)
    
    if params.mode == "ultra":
        width = 1024
        height = 1536
        prompt_val = NewBiePromptBuilder.build_xml_prompt(params.prompt)
    else:
        width = 768 if params.mode == "fast" else 1024
        height = 768 if params.mode == "fast" else 1024
        prompt_val = params.prompt
        
    session_factory = get_session_factory(settings)
    with session_factory() as session:
        base_seed = random.randint(1, 1000000)
        for i in range(count):
            seed = base_seed + i
            job = ImageJob(
                generation_set_id=generation_set_id,
                seed=seed,
                status="pending",
                width=width,
                height=height
            )
            session.add(job)
        session.commit()
    
    try:
        if not await comfyui_provider.health_check():
            session_factory = get_session_factory(settings)
            with session_factory() as session:
                for job in session.query(ImageJob).filter_by(generation_set_id=generation_set_id, status="pending").all():
                    job.status = "failed"
                session.commit()
            return
            
        session_factory = get_session_factory(settings)
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
                        prompt=prompt_val,
                        negative_prompt=params.negative_prompt,
                        seed=job.seed,
                        width=job.width,
                        height=job.height,
                        filename_prefix=prefix,
                        mode=params.mode
                    )
                    
                    job.comfy_prompt_id = res.prompt_id
                    if res.output_files:
                        job.file_path = res.output_files[0]
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    session.commit()
                        
                except Exception as e:
                    job.status = "failed"
                    session.commit()
                    if "CUDA out of memory" in str(e) or "Memory" in str(e):
                        break
        
    except Exception as e:
        pass

async def image_generate_handler(params: ImageGenerateParams) -> Dict[str, Any]:
    generation_set_id = str(uuid.uuid4())
    
    settings = get_settings()
    session_factory = get_session_factory(settings)
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
            user_id=params.userId or "anonymous",
            conversation_id=validated_conv_id,
            prompt=params.prompt,
            workflow_mode=params.mode
        )
        session.add(gen_set)
        session.commit()
    
    # Fire and forget
    asyncio.create_task(run_image_job(generation_set_id, params))
    
    return {
        "status": "processing",
        "job_id": generation_set_id
    }

registry.register(image_generate_def, image_generate_handler)


