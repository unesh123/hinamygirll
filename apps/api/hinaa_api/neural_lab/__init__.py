"""HINAA Neural Lab - Model Training, Adaptation & Evolution Subsystem."""

from .audit import TrainingReadinessReport, run_system_audit
from .datasets.schema import DatasetCategory, DatasetExample, DatasetManifest
from .datasets.builder import DatasetBuilder
from .models.registry import BaseModelEntry, ModelRegistry, get_model_registry
from .training.lora_config import QLoRAHyperparameters
from .training.pipeline import (
    TrainingExperiment,
    TrainingMetrics,
    TrainingPipelineManager,
)
from .evaluation.benchmarks import (
    EvaluationDimension,
    ModelBenchmarkReport,
    run_model_benchmark_comparison,
)
from .adapters.manager import (
    AdapterMetadata,
    AdapterManager,
    get_adapter_manager,
)
from .router_integration import LocalNeuralLabProvider

__all__ = [
    "TrainingReadinessReport",
    "run_system_audit",
    "DatasetCategory",
    "DatasetExample",
    "DatasetManifest",
    "DatasetBuilder",
    "BaseModelEntry",
    "ModelRegistry",
    "get_model_registry",
    "QLoRAHyperparameters",
    "TrainingExperiment",
    "TrainingMetrics",
    "TrainingPipelineManager",
    "EvaluationDimension",
    "ModelBenchmarkReport",
    "run_model_benchmark_comparison",
    "AdapterMetadata",
    "AdapterManager",
    "get_adapter_manager",
    "LocalNeuralLabProvider",
]
