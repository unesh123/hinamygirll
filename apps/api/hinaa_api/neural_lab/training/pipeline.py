"""Supervised Fine-Tuning & QLoRA Execution Pipeline for HINAA Neural Lab."""

from __future__ import annotations

import importlib.util
import logging
import time
import uuid
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field

from .lora_config import QLoRAHyperparameters

logger = logging.getLogger("hinaa.neural_lab.training")


class TrainingMetrics(BaseModel):
    train_loss_history: list[dict[str, float]] = Field(default_factory=list)
    val_loss_history: list[dict[str, float]] = Field(default_factory=list)
    final_train_loss: Optional[float] = None
    final_val_loss: Optional[float] = None
    peak_vram_mb: Optional[float] = None
    total_training_duration_seconds: float = 0.0
    completed_steps: int = 0
    total_steps: int = 0


class TrainingExperiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: f"exp-{uuid.uuid4().hex[:8]}")
    base_model_id: str = "Qwen/Qwen2.5-1.5B-Instruct"
    adapter_name: str = "hinaa-core-v1"
    dataset_name: str = "hinaa_gold_sft_v1"
    hyperparameters: QLoRAHyperparameters = Field(default_factory=QLoRAHyperparameters)
    output_dir: str
    status: str = "CONFIGURED"  # "CONFIGURED", "TRAINING", "COMPLETED", "FAILED", "BLOCKED"
    metrics: TrainingMetrics = Field(default_factory=TrainingMetrics)
    error_message: Optional[str] = None
    created_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None


class TrainingPipelineManager:
    """Orchestrates end-to-end QLoRA / LoRA training experiments."""

    def __init__(self, experiments_root: Optional[str] = None) -> None:
        self.root = Path(experiments_root or Path(__file__).resolve().parents[1] / "experiments")
        self.root.mkdir(parents=True, exist_ok=True)
        self._experiments: dict[str, TrainingExperiment] = {}

    def create_experiment(
        self,
        base_model_id: str = "Qwen/Qwen2.5-1.5B-Instruct",
        adapter_name: str = "hinaa-core-v1",
        dataset_name: str = "hinaa_gold_sft_v1",
        hyperparameters: Optional[QLoRAHyperparameters] = None,
    ) -> TrainingExperiment:
        """Initialize and persist a new training experiment configuration."""
        exp_id = f"exp-{uuid.uuid4().hex[:8]}"
        out_path = self.root / exp_id
        out_path.mkdir(parents=True, exist_ok=True)

        exp = TrainingExperiment(
            experiment_id=exp_id,
            base_model_id=base_model_id,
            adapter_name=adapter_name,
            dataset_name=dataset_name,
            hyperparameters=hyperparameters or QLoRAHyperparameters(),
            output_dir=str(out_path),
        )

        # Save experiment config JSON
        cfg_file = out_path / "experiment_config.json"
        with open(cfg_file, "w", encoding="utf-8") as f:
            f.write(exp.model_dump_json(indent=2))

        self._experiments[exp_id] = exp
        return exp

    def run_training_experiment(self, experiment_id: str, dry_run: bool = False) -> TrainingExperiment:
        """Run an SFT / QLoRA experiment, or report truthfully why it cannot run.

        The training loop is not implemented yet. This used to return a COMPLETED
        run with hardcoded loss curves and a placeholder weights file; it now
        reports BLOCKED and produces no adapter, weights or metrics.
        """
        exp = self._experiments.get(experiment_id)
        if not exp:
            raise ValueError(f"Experiment '{experiment_id}' not found.")

        missing = [name for name in ("torch", "transformers", "peft") if importlib.util.find_spec(name) is None]
        if missing:
            reason = (
                f"Training stack not installed ({', '.join(missing)}). "
                "Install torch, transformers and peft on a GPU host to train adapters."
            )
        else:
            reason = "The QLoRA training loop is not implemented in this build; no adapter, weights or metrics were produced."
        return self._block(exp, reason)

    def _block(self, exp: TrainingExperiment, reason: str) -> TrainingExperiment:
        exp.status = "BLOCKED"
        exp.error_message = reason
        out_dir = Path(exp.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        with open(out_dir / "experiment_result.json", "w", encoding="utf-8") as f:
            f.write(exp.model_dump_json(indent=2))
        logger.warning("Training experiment '%s' blocked: %s", exp.experiment_id, reason)
        return exp
