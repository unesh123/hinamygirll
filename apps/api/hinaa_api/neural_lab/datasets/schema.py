"""Schemas and data models for HINAA Training Dataset Laboratory."""

from __future__ import annotations

import enum
import hashlib
import time
from typing import Any, Optional
from pydantic import BaseModel, Field


class DatasetCategory(str, enum.Enum):
    IDENTITY = "character_identity"
    REASONING = "reasoning_instructions"
    TOOLS = "agent_tools"
    RESEARCH = "research_verification"
    MULTILINGUAL = "multilingual_dialogue"
    FORMATTING = "structured_rich_responses"


class DatasetExample(BaseModel):
    example_id: str
    category: DatasetCategory
    system_prompt: str = "You are Hina, an autonomous, intelligent AI companion with persistent identity, sharp analytical capabilities, and genuine initiative."
    user_prompt: str
    assistant_response: str
    negative_response: Optional[str] = None  # Used for contrastive learning / DPO
    language: str = "en"  # "en", "ne", "hi", "mixed"
    provenance: str = "curated_engineering_gold_standard"
    verified: bool = True
    created_at: float = Field(default_factory=time.time)

    @property
    def content_hash(self) -> str:
        raw = f"{self.user_prompt.strip().lower()}::{self.assistant_response.strip().lower()}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def to_chatml(self) -> list[dict[str, str]]:
        """Format as ChatML messages for SFTTrainer."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.user_prompt},
            {"role": "assistant", "content": self.assistant_response},
        ]

    def to_alpaca(self) -> dict[str, str]:
        """Format as Alpaca instruction dictionary."""
        return {
            "instruction": self.user_prompt,
            "input": "",
            "output": self.assistant_response,
            "system": self.system_prompt,
        }


class DatasetManifest(BaseModel):
    version: str = "1.0.0"
    name: str = "hinaa_sft_gold_v1"
    total_examples: int = 0
    categories_breakdown: dict[str, int] = Field(default_factory=dict)
    languages_breakdown: dict[str, int] = Field(default_factory=dict)
    splits: dict[str, int] = Field(default_factory=dict)  # train, val, test
    created_at: float = Field(default_factory=time.time)
