"""Base Model Registry & Hardware Budget Specification for HINAA Neural Lab."""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class BaseModelEntry(BaseModel):
    model_id: str
    name: str
    architecture: str
    parameter_count_b: float
    license_type: str
    context_window_tokens: int
    recommended_quantization: str  # "4bit_nf4", "8bit", "fp16"
    estimated_qlora_vram_gb: float
    hardware_suitability_rtx4060_8gb: str  # "EXCELLENT", "GOOD", "TIGHT", "UNSUPPORTED"
    download_url: str
    ollama_tag: Optional[str] = None
    training_notes: str


BASE_MODEL_CATALOG: list[BaseModelEntry] = [
    BaseModelEntry(
        model_id="Qwen/Qwen2.5-1.5B-Instruct",
        name="Qwen 2.5 1.5B Instruct",
        architecture="qwen2",
        parameter_count_b=1.54,
        license_type="Apache-2.0 (Permissive Open Weights)",
        context_window_tokens=32768,
        recommended_quantization="4bit_nf4",
        estimated_qlora_vram_gb=2.8,
        hardware_suitability_rtx4060_8gb="EXCELLENT",
        download_url="https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct",
        ollama_tag="qwen2.5:1.5b",
        training_notes=(
            "Primary recommended candidate for RTX 4060 8GB VRAM. "
            "Fits comfortably with batch size 2-4 and gradient accumulation. "
            "Strong multilingual performance in English, Nepali, and Hindi."
        ),
    ),
    BaseModelEntry(
        model_id="Qwen/Qwen2.5-3B-Instruct",
        name="Qwen 2.5 3B Instruct",
        architecture="qwen2",
        parameter_count_b=3.09,
        license_type="Apache-2.0 (Permissive Open Weights)",
        context_window_tokens=32768,
        recommended_quantization="4bit_nf4",
        estimated_qlora_vram_gb=4.5,
        hardware_suitability_rtx4060_8gb="GOOD",
        download_url="https://huggingface.co/Qwen/Qwen2.5-3B-Instruct",
        ollama_tag="qwen2.5:3b",
        training_notes=(
            "Higher reasoning depth. Requires batch size 1 or 2 with gradient accumulation. "
            "Uses ~4.5 GB VRAM leaving ~3.5 GB for OS/display buffer."
        ),
    ),
    BaseModelEntry(
        model_id="meta-llama/Llama-3.2-1B-Instruct",
        name="Llama 3.2 1B Instruct",
        architecture="llama",
        parameter_count_b=1.23,
        license_type="Llama 3.2 Community License",
        context_window_tokens=131072,
        recommended_quantization="4bit_nf4",
        estimated_qlora_vram_gb=2.4,
        hardware_suitability_rtx4060_8gb="EXCELLENT",
        download_url="https://huggingface.co/meta-llama/Llama-3.2-1B-Instruct",
        ollama_tag="llama3.2:1b",
        training_notes="Ultra-lightweight edge model with massive 128k context support.",
    ),
    BaseModelEntry(
        model_id="meta-llama/Llama-3.2-3B-Instruct",
        name="Llama 3.2 3B Instruct",
        architecture="llama",
        parameter_count_b=3.21,
        license_type="Llama 3.2 Community License",
        context_window_tokens=131072,
        recommended_quantization="4bit_nf4",
        estimated_qlora_vram_gb=4.8,
        hardware_suitability_rtx4060_8gb="GOOD",
        download_url="https://huggingface.co/meta-llama/Llama-3.2-3B-Instruct",
        ollama_tag="llama3.2:3b",
        training_notes="Strong reasoning and instruction following with modest VRAM footprint.",
    ),
    BaseModelEntry(
        model_id="Qwen/Qwen2.5-7B-Instruct",
        name="Qwen 2.5 7B Instruct",
        architecture="qwen2",
        parameter_count_b=7.61,
        license_type="Apache-2.0 (Permissive Open Weights)",
        context_window_tokens=32768,
        recommended_quantization="4bit_nf4",
        estimated_qlora_vram_gb=6.4,
        hardware_suitability_rtx4060_8gb="TIGHT",
        download_url="https://huggingface.co/Qwen/Qwen2.5-7B-Instruct",
        ollama_tag="qwen2.5:7b",
        training_notes=(
            "Demanding on 8GB VRAM. Requires gradient checkpointing, batch size 1, "
            "paged_adamw_8bit optimizer, and closing heavy background applications."
        ),
    ),
]


class ModelRegistry:
    """Registry holding candidate downloadable base models and their hardware profiles."""

    def __init__(self) -> None:
        self._models = {m.model_id: m for m in BASE_MODEL_CATALOG}

    def list_models(self) -> list[BaseModelEntry]:
        return list(self._models.values())

    def get_model(self, model_id: str) -> Optional[BaseModelEntry]:
        return self._models.get(model_id)

    def get_recommended_for_gpu(self, vram_gb: float = 8.0) -> list[BaseModelEntry]:
        """Filter base models that fit safely within available GPU VRAM headroom."""
        headroom = vram_gb * 0.75  # Safe 75% limit leaving 25% for OS and buffers
        return [m for m in self._models.values() if m.estimated_qlora_vram_gb <= headroom]


_GLOBAL_REGISTRY: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = ModelRegistry()
    return _GLOBAL_REGISTRY
