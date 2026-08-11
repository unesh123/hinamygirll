import json
import logging
import asyncio
from typing import Any, Dict, Optional
import httpx
from pydantic import BaseModel
from pathlib import Path

logger = logging.getLogger(__name__)

import uuid

class ComfyUIConfig(BaseModel):
    base_url: str = "http://127.0.0.1:8188"
    max_concurrency: int = 1

# Global queue for async jobs
_jobs: Dict[str, Dict[str, Any]] = {}

def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    return _jobs.get(job_id)

class ComfyUIGenerationResult(BaseModel):
    prompt_id: str
    output_files: list[str]

class LocalComfyUIProvider:
    def __init__(self, config: ComfyUIConfig = ComfyUIConfig()):
        self.config = config
        self._semaphore = asyncio.Semaphore(config.max_concurrency)
        self._http = httpx.AsyncClient(base_url=self.config.base_url, timeout=300.0)

    async def health_check(self) -> bool:
        try:
            response = await self._http.get("/system_stats")
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"ComfyUI health check failed: {e}")
            return False

    def load_base_workflow(self) -> Dict[str, Any]:
        root_dir = Path(__file__).parent.parent.parent.parent.parent
        path = root_dir / "HINAA_ANIMA_QUALITY_API.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def load_ultra_workflow(self) -> Dict[str, Any]:
        root_dir = Path(__file__).parent.parent.parent.parent.parent
        path = root_dir / "HINAA_NEWBIE_ULTRA_API.json"
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _map_nodes(self, workflow: Dict[str, Any]) -> Dict[str, str]:
        """Dynamically maps the semantic nodes based on links and class_types."""
        mapping = {}
        
        # Find Sampler and SaveImage
        sampler_id = None
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
            pos_link = sampler_inputs.get("positive")
            if pos_link and isinstance(pos_link, list):
                mapping["positive_prompt"] = pos_link[0]
            neg_link = sampler_inputs.get("negative")
            if neg_link and isinstance(neg_link, list):
                mapping["negative_prompt"] = neg_link[0]

        return mapping

    def _map_ultra_nodes(self, workflow: Dict[str, Any]) -> Dict[str, str]:
        """Dynamically maps the semantic nodes for NewBie Ultra based on titles and classes."""
        mapping = {}
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

    async def submit_prompt(
        self, 
        prompt: str, 
        negative_prompt: str = "", 
        seed: int = 0, 
        width: int = 1024, 
        height: int = 1024,
        filename_prefix: str = "HINAA_Anima",
        mode: str = "fast"
    ) -> ComfyUIGenerationResult:
        async with self._semaphore:
            if not await self.health_check():
                raise ConnectionError("Local ComfyUI is unavailable or offline.")

            # Prepare the workflow
            if mode == "ultra":
                workflow = self.load_ultra_workflow()
                mapping = self._map_ultra_nodes(workflow)
                
                if "user_prompt" in mapping:
                    workflow[mapping["user_prompt"]]["inputs"]["value"] = prompt
                
                if "sampler" in mapping:
                    workflow[mapping["sampler"]]["inputs"]["seed"] = seed
                    
                if "latent" in mapping:
                    workflow[mapping["latent"]]["inputs"]["width"] = width
                    workflow[mapping["latent"]]["inputs"]["height"] = height
                    workflow[mapping["latent"]]["inputs"]["batch_size"] = 1 # STRICTLY 1
                    
                if "save_image" in mapping:
                    workflow[mapping["save_image"]]["inputs"]["filename_prefix"] = filename_prefix
            else:
                workflow = self.load_base_workflow()
                mapping = self._map_nodes(workflow)
                
                # Apply dynamic mapping injections
                if "positive_prompt" in mapping:
                    workflow[mapping["positive_prompt"]]["inputs"]["text"] = prompt
                
                if "negative_prompt" in mapping and negative_prompt:
                    base_neg = workflow[mapping["negative_prompt"]]["inputs"].get("text", "")
                    workflow[mapping["negative_prompt"]]["inputs"]["text"] = f"{base_neg}, {negative_prompt}"
                    
                if "sampler" in mapping:
                    workflow[mapping["sampler"]]["inputs"]["seed"] = seed
                    
                if "latent" in mapping:
                    workflow[mapping["latent"]]["inputs"]["width"] = width
                    workflow[mapping["latent"]]["inputs"]["height"] = height
                    workflow[mapping["latent"]]["inputs"]["batch_size"] = 1 # STRICTLY 1
                    
                if "save_image" in mapping:
                    workflow[mapping["save_image"]]["inputs"]["filename_prefix"] = filename_prefix

            # Submit to API
            response = await self._http.post("/prompt", json={"prompt": workflow})
            response.raise_for_status()
            data = response.json()
            prompt_id = data.get("prompt_id")
            
            if not prompt_id:
                raise ValueError("ComfyUI did not return a prompt_id")

            # Wait for completion (Monitor /history endpoint)
            while True:
                await asyncio.sleep(2)
                hist_res = await self._http.get(f"/history/{prompt_id}")
                hist_data = hist_res.json()
                if prompt_id in hist_data:
                    # Job completed
                    outputs = hist_data[prompt_id].get("outputs", {})
                    output_files = []
                    import os
                    import uuid
                    import aiofiles
                    from pathlib import Path
                    
                    data_dir = Path("apps/api/data/images").absolute()
                    data_dir.mkdir(parents=True, exist_ok=True)
                    
                    for node_id, output_data in outputs.items():
                        if "images" in output_data:
                            for img in output_data["images"]:
                                fn = img.get("filename")
                                folder = img.get("subfolder", "")
                                typ = img.get("type", "output")
                                query = f"filename={fn}&type={typ}"
                                if folder:
                                    query += f"&subfolder={folder}"
                                url = f"{self.config.base_url}/view?{query}"
                                
                                # Download the image
                                img_res = await self._http.get(f"/view?{query}")
                                img_res.raise_for_status()
                                
                                ext = os.path.splitext(fn)[1] if fn else ".png"
                                local_filename = f"{uuid.uuid4().hex}{ext}"
                                local_path = data_dir / local_filename
                                
                                async with aiofiles.open(local_path, "wb") as f:
                                    await f.write(img_res.content)
                                    
                                output_files.append(str(local_path))
                    return ComfyUIGenerationResult(prompt_id=prompt_id, output_files=output_files)

