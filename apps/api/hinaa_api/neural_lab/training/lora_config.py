"""LoRA and QLoRA Hyperparameter Configuration Specification."""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, Field


class QLoRAHyperparameters(BaseModel):
    # LoRA Matrix Dimensions
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: list[str] = Field(
        default_factory=lambda: [
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ]
    )
    bias: str = "none"
    task_type: str = "CAUSAL_LM"

    # Quantization (4-bit NF4)
    load_in_4bit: bool = True
    bnb_4bit_quant_type: str = "nf4"
    bnb_4bit_use_double_quant: bool = True
    bnb_4bit_compute_dtype: str = "float16"

    # Training Hyperparameters
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.05
    num_train_epochs: int = 3
    per_device_train_batch_size: int = 2
    per_device_eval_batch_size: int = 2
    gradient_accumulation_steps: int = 4
    max_seq_length: int = 2048
    weight_decay: float = 0.01
    optimizer: str = "paged_adamw_8bit"
    lr_scheduler_type: str = "cosine"
    logging_steps: int = 5
    eval_steps: int = 25
    save_steps: int = 50
    gradient_checkpointing: bool = True
    fp16: bool = True
    bf16: bool = False

    def to_peft_kwargs(self) -> dict[str, Any]:
        """Export parameters suitable for peft.LoraConfig."""
        return {
            "r": self.lora_r,
            "lora_alpha": self.lora_alpha,
            "lora_dropout": self.lora_dropout,
            "target_modules": self.target_modules,
            "bias": self.bias,
            "task_type": self.task_type,
        }
