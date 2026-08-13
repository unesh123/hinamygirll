from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from pathlib import Path
from time import monotonic
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ComfyUIConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8188"
    # This gate controls lightweight prompt submission, not unsafe latent-image
    # batching. ComfyUI's own queue remains the source of GPU scheduling truth.
    max_concurrency: int = Field(1, ge=1, le=4)
    completion_timeout_seconds: int = Field(900, ge=30, le=3600)
    poll_interval_seconds: float = Field(1.0, ge=0.25, le=10.0)


# Kept for backwards-compatible local diagnostics. Durable records live in DB.
_jobs: Dict[str, Dict[str, Any]] = {}


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)


class ComfyUIGenerationResult(BaseModel):
    prompt_id: str
    output_files: list[str]


class LocalComfyUIProvider:
    """Local-only, queue-aware ComfyUI adapter.

    Multiple requested variations are submitted as independent prompt IDs. This
    gets the whole set into ComfyUI's queue promptly and lets HINAA surface each
    image as soon as it completes. A single workflow's latent batch remains 1
    by default because simultaneous 1024px batches can exhaust an 8 GB GPU.
    """

    def __init__(self, config: ComfyUIConfig | None = None) -> None:
        self.config = config or ComfyUIConfig()
        self._submission_semaphore = asyncio.Semaphore(self.config.max_concurrency)
        self._http = httpx.AsyncClient(base_url=self.config.base_url.rstrip("/"), timeout=300.0)

    async def health_check(self) -> bool:
        try:
            response = await self._http.get("/system_stats")
            response.raise_for_status()
            return True
        except Exception as error:
            logger.info("ComfyUI health check failed: %s", type(error).__name__)
            return False

    @staticmethod
    def _project_root() -> Path:
        return Path(__file__).resolve().parents[4]

    def load_base_workflow(self) -> Dict[str, Any]:
        path = self._project_root() / "HINAA_ANIMA_QUALITY_API.json"
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def load_ultra_workflow(self) -> Dict[str, Any]:
        path = self._project_root() / "HINAA_NEWBIE_ULTRA_API.json"
        with path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _map_nodes(self, workflow: Dict[str, Any]) -> Dict[str, str]:
        mapping: dict[str, str] = {}
        sampler_id: str | None = None
        for node_id, node in workflow.items():
            if node.get("class_type") == "KSampler":
                sampler_id = node_id
                mapping["sampler"] = node_id
            elif node.get("class_type") == "SaveImage":
                mapping["save_image"] = node_id
            elif node.get("class_type") == "EmptyLatentImage":
                mapping["latent"] = node_id

        if sampler_id and sampler_id in workflow:
            sampler_inputs = workflow[sampler_id].get("inputs", {})
            positive_link = sampler_inputs.get("positive")
            if isinstance(positive_link, list) and positive_link:
                mapping["positive_prompt"] = str(positive_link[0])
            negative_link = sampler_inputs.get("negative")
            if isinstance(negative_link, list) and negative_link:
                mapping["negative_prompt"] = str(negative_link[0])
        return mapping

    def _map_ultra_nodes(self, workflow: Dict[str, Any]) -> Dict[str, str]:
        mapping: dict[str, str] = {}
        for node_id, node in workflow.items():
            class_type = node.get("class_type")
            title = node.get("_meta", {}).get("title", "")
            if class_type == "KSampler":
                mapping["sampler"] = node_id
            elif class_type == "SaveImage":
                mapping["save_image"] = node_id
            elif class_type == "EmptySD3LatentImage":
                mapping["latent"] = node_id
            elif class_type == "PrimitiveStringMultiline":
                if title == "User Prompt":
                    mapping["user_prompt"] = node_id
                elif title == "Caption":
                    mapping["caption"] = node_id
                elif title == "Prompt Template":
                    mapping["prompt_template"] = node_id
        return mapping

    def _build_workflow(
        self,
        *,
        prompt: str,
        negative_prompt: str,
        seed: int,
        width: int,
        height: int,
        filename_prefix: str,
        mode: str,
    ) -> Dict[str, Any]:
        if mode == "ultra":
            workflow = self.load_ultra_workflow()
            mapping = self._map_ultra_nodes(workflow)
            if "user_prompt" in mapping:
                workflow[mapping["user_prompt"]]["inputs"]["value"] = prompt
        else:
            workflow = self.load_base_workflow()
            mapping = self._map_nodes(workflow)
            if "positive_prompt" in mapping:
                workflow[mapping["positive_prompt"]]["inputs"]["text"] = prompt
            if "negative_prompt" in mapping and negative_prompt:
                base_negative = workflow[mapping["negative_prompt"]]["inputs"].get("text", "")
                workflow[mapping["negative_prompt"]]["inputs"]["text"] = (
                    f"{base_negative}, {negative_prompt}".strip(", ")
                )

        if "sampler" in mapping:
            workflow[mapping["sampler"]]["inputs"]["seed"] = seed
        if "latent" in mapping:
            latent_inputs = workflow[mapping["latent"]]["inputs"]
            latent_inputs["width"] = width
            latent_inputs["height"] = height
            # Independent queue entries are much more responsive and safer than
            # forcing several high-resolution latent tensors into one GPU pass.
            latent_inputs["batch_size"] = 1
        if "save_image" in mapping:
            workflow[mapping["save_image"]]["inputs"]["filename_prefix"] = filename_prefix
        return workflow

    async def enqueue_prompt(
        self,
        *,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 0,
        width: int = 1024,
        height: int = 1024,
        filename_prefix: str = "HINAA_Anima",
        mode: str = "fast",
    ) -> str:
        """Submit a distinct prompt to the local ComfyUI queue and return its ID."""
        async with self._submission_semaphore:
            if not await self.health_check():
                raise ConnectionError("Local ComfyUI is unavailable or offline.")
            workflow = self._build_workflow(
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=seed,
                width=width,
                height=height,
                filename_prefix=filename_prefix,
                mode=mode,
            )
            response = await self._http.post("/prompt", json={"prompt": workflow})
            response.raise_for_status()
            prompt_id = response.json().get("prompt_id")
            if not isinstance(prompt_id, str) or not prompt_id:
                raise ValueError("ComfyUI did not return a prompt_id")
            _jobs[prompt_id] = {"status": "queued", "filenamePrefix": filename_prefix}
            return prompt_id

    async def collect_prompt(self, prompt_id: str) -> ComfyUIGenerationResult:
        """Wait for one queued prompt and copy only its returned images locally."""
        started = monotonic()
        while monotonic() - started < self.config.completion_timeout_seconds:
            await asyncio.sleep(self.config.poll_interval_seconds)
            history_response = await self._http.get(f"/history/{prompt_id}")
            history_response.raise_for_status()
            history = history_response.json()
            result = history.get(prompt_id)
            if not isinstance(result, dict):
                continue

            status = result.get("status")
            if isinstance(status, dict) and status.get("status_str") in {"error", "cancelled"}:
                messages = status.get("messages", [])
                raise RuntimeError(f"ComfyUI {status.get('status_str')}: {str(messages)[:240]}")

            output_files = await self._download_outputs(result.get("outputs", {}))
            if not output_files:
                raise ValueError("ComfyUI completed without a downloadable image output.")
            _jobs[prompt_id] = {"status": "completed", "outputFiles": output_files}
            return ComfyUIGenerationResult(prompt_id=prompt_id, output_files=output_files)

        _jobs[prompt_id] = {"status": "timed_out"}
        raise TimeoutError("ComfyUI did not complete before HINAA's local image timeout.")

    async def _download_outputs(self, outputs: Any) -> list[str]:
        if not isinstance(outputs, dict):
            return []
        data_dir = Path(__file__).resolve().parents[2] / "data" / "images"
        data_dir.mkdir(parents=True, exist_ok=True)
        output_files: list[str] = []
        for output in outputs.values():
            images = output.get("images", []) if isinstance(output, dict) else []
            if not isinstance(images, list):
                continue
            for image in images:
                if not isinstance(image, dict) or not image.get("filename"):
                    continue
                query = urlencode(
                    {
                        "filename": image["filename"],
                        "type": image.get("type", "output"),
                        **({"subfolder": image["subfolder"]} if image.get("subfolder") else {}),
                    }
                )
                response = await self._http.get(f"/view?{query}")
                response.raise_for_status()
                extension = os.path.splitext(str(image["filename"]))[1] or ".png"
                local_path = data_dir / f"{uuid.uuid4().hex}{extension}"
                local_path.write_bytes(response.content)
                output_files.append(str(local_path))
        return output_files

    async def submit_prompt(
        self,
        prompt: str,
        negative_prompt: str = "",
        seed: int = 0,
        width: int = 1024,
        height: int = 1024,
        filename_prefix: str = "HINAA_Anima",
        mode: str = "fast",
    ) -> ComfyUIGenerationResult:
        """Compatibility convenience method for callers that need one full result."""
        prompt_id = await self.enqueue_prompt(
            prompt=prompt,
            negative_prompt=negative_prompt,
            seed=seed,
            width=width,
            height=height,
            filename_prefix=filename_prefix,
            mode=mode,
        )
        return await self.collect_prompt(prompt_id)
