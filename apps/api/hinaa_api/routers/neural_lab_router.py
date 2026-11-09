"""
HINAA OS — Neural Lab Router.
Hardware audit, base models, dataset manifests, fine-tuning experiments, and benchmarks.
"""

from __future__ import annotations

from typing import Any, Dict, List
from fastapi import APIRouter, Body

router = APIRouter(tags=["Neural Lab"])


@router.get("/api/neural-lab/audit")
@router.get("/v1/neural-lab/audit")
async def get_neural_lab_audit() -> Dict[str, Any]:
    """Hardware, VRAM, CUDA, PyTorch, and Ollama training readiness audit."""
    from ..neural_lab import run_system_audit
    return run_system_audit().model_dump()


@router.get("/api/neural-lab/models")
@router.get("/v1/neural-lab/models")
async def get_base_models() -> List[Dict[str, Any]]:
    """Base model catalog with VRAM budgets and license specifications."""
    from ..neural_lab import get_model_registry
    return [m.model_dump() for m in get_model_registry().list_models()]


@router.get("/api/neural-lab/datasets")
@router.get("/v1/neural-lab/datasets")
async def get_neural_lab_datasets() -> Dict[str, Any]:
    """Manifest of curated training datasets across the 5 domains."""
    from ..neural_lab import DatasetBuilder
    builder = DatasetBuilder()
    builder.load_gold_standards()
    manifest = builder.build_and_export()
    return manifest.model_dump()


@router.post("/api/neural-lab/train")
@router.post("/v1/neural-lab/train")
async def run_training_experiment(body: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    """Execute SFT / QLoRA training experiment."""
    from ..neural_lab import TrainingPipelineManager
    mgr = TrainingPipelineManager()
    exp = mgr.create_experiment(
        base_model_id=body.get("baseModelId", "Qwen/Qwen2.5-1.5B-Instruct"),
        adapter_name=body.get("adapterName", "hinaa-core-v1"),
        dataset_name=body.get("datasetName", "hinaa_gold_sft_v1"),
    )
    finished = mgr.run_training_experiment(exp.experiment_id)
    return finished.model_dump()


@router.get("/api/neural-lab/benchmark")
@router.get("/v1/neural-lab/benchmark")
async def get_model_benchmark() -> Dict[str, Any]:
    """Comparative evaluation report between base model and fine-tuned adapter."""
    from ..neural_lab import run_model_benchmark_comparison
    return run_model_benchmark_comparison().model_dump()


@router.get("/api/neural-lab/adapters")
@router.get("/v1/neural-lab/adapters")
async def list_adapters() -> List[Dict[str, Any]]:
    """List registered LoRA adapters and active status."""
    from ..neural_lab import get_adapter_manager
    return [a.model_dump() for a in get_adapter_manager().list_adapters()]
