"""
HINAA Frontier Model Registry & Capability Catalog.

Modeled directly on the public OpenAI Codex models manifest (codex-rs/models-manager/models.json):
1. Granular model capabilities: parallel tool calling, multi-agent v2, shell execution, web search, reasoning levels.
2. Context window tracking: input token bounds, max output token limits.
3. Cost and latency tiering: free, budget, standard, frontier.
4. Intelligent capability matching: task requirements -> optimal model selection.
5. Dynamic provider fallback chains (agent-router -> codecraft -> gemini -> mock).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CostTier(str, Enum):
    FREE = "free"
    BUDGET = "budget"
    STANDARD = "standard"
    FRONTIER = "frontier"


class ModelCapability(BaseModel):
    model_id: str
    display_name: str
    provider: str
    context_window_tokens: int = 128_000
    max_output_tokens: int = 16_384
    parallel_tool_calls: bool = True
    multi_agent_v2: bool = True
    shell_execution: bool = True
    web_search: bool = True
    vision_support: bool = False
    reasoning_levels: List[str] = Field(default_factory=lambda: ["low", "medium", "high"])
    cost_tier: CostTier = CostTier.STANDARD
    latency_p50_ms: float = 400.0
    supports_structured_outputs: bool = True
    active: bool = True


# Standard Catalog modeled after Codex models.json
_MODEL_CATALOG: Dict[str, ModelCapability] = {
    "agnes-2.5-flash": ModelCapability(
        model_id="agnes-2.5-flash",
        display_name="Agnes 2.5 Flash",
        provider="agent-router",
        context_window_tokens=200_000,
        max_output_tokens=16_384,
        parallel_tool_calls=True,
        multi_agent_v2=True,
        shell_execution=True,
        web_search=True,
        vision_support=True,
        reasoning_levels=["low", "medium", "high", "max"],
        cost_tier=CostTier.BUDGET,
        latency_p50_ms=180.0,
    ),
    "gpt-6-astra": ModelCapability(
        model_id="gpt-6-astra",
        display_name="GPT-6 Astra (Frontier Orchestrator)",
        provider="agent-router",
        context_window_tokens=256_000,
        max_output_tokens=32_768,
        parallel_tool_calls=True,
        multi_agent_v2=True,
        shell_execution=True,
        web_search=True,
        vision_support=True,
        reasoning_levels=["low", "medium", "high", "max", "ultra"],
        cost_tier=CostTier.FRONTIER,
        latency_p50_ms=520.0,
    ),
    "claude-fable-5": ModelCapability(
        model_id="claude-fable-5",
        display_name="Claude Fable 5 (Systems & Coding)",
        provider="codecraft",
        context_window_tokens=200_000,
        max_output_tokens=16_384,
        parallel_tool_calls=True,
        multi_agent_v2=True,
        shell_execution=True,
        web_search=False,
        vision_support=True,
        reasoning_levels=["low", "medium", "high"],
        cost_tier=CostTier.FRONTIER,
        latency_p50_ms=450.0,
    ),
    "claude-3-7-sonnet": ModelCapability(
        model_id="claude-3-7-sonnet",
        display_name="Claude 3.7 Sonnet (Hybrid Reasoning)",
        provider="codecraft",
        context_window_tokens=200_000,
        max_output_tokens=16_384,
        parallel_tool_calls=True,
        multi_agent_v2=True,
        shell_execution=True,
        web_search=False,
        vision_support=True,
        reasoning_levels=["low", "medium", "high", "max"],
        cost_tier=CostTier.FRONTIER,
        latency_p50_ms=480.0,
    ),
    "gemini-2.5-flash": ModelCapability(
        model_id="gemini-2.5-flash",
        display_name="Gemini 2.5 Flash (Ultra Fast)",
        provider="gemini",
        context_window_tokens=1_000_000,
        max_output_tokens=8_192,
        parallel_tool_calls=True,
        multi_agent_v2=False,
        shell_execution=False,
        web_search=True,
        vision_support=True,
        reasoning_levels=["low", "medium"],
        cost_tier=CostTier.FREE,
        latency_p50_ms=120.0,
    ),
}


class ModelRegistry:
    """
    Registry for dynamic model discovery, capability matching, and fallback chains.
    """

    def __init__(self, catalog: Optional[Dict[str, ModelCapability]] = None) -> None:
        self._catalog = dict(catalog or _MODEL_CATALOG)

    def register_model(self, capability: ModelCapability) -> None:
        self._catalog[capability.model_id] = capability

    def get_model(self, model_id: str) -> Optional[ModelCapability]:
        return self._catalog.get(model_id)

    def list_models(self, active_only: bool = True) -> List[ModelCapability]:
        models = list(self._catalog.values())
        if active_only:
            models = [m for m in models if m.active]
        return models

    def resolve_best_model(
        self,
        *,
        task_category: str = "general",
        reasoning_effort: str = "medium",
        requires_vision: bool = False,
        requires_shell: bool = False,
        prefer_speed: bool = False,
    ) -> ModelCapability:
        """
        Dynamically selects the optimal model satisfying capability constraints.
        """
        candidates = [m for m in self._catalog.values() if m.active]

        if requires_vision:
            candidates = [m for m in candidates if m.vision_support]
        if requires_shell:
            candidates = [m for m in candidates if m.shell_execution]

        if not candidates:
            # Fallback to default fast model
            return self._catalog.get("agnes-2.5-flash", next(iter(self._catalog.values())))

        if prefer_speed:
            candidates.sort(key=lambda m: m.latency_p50_ms)
            return candidates[0]

        if task_category in ("coding", "architecture", "refactoring"):
            # Prefer high-capacity coding models
            for preferred in ("claude-fable-5", "claude-3-7-sonnet", "gpt-6-astra"):
                for c in candidates:
                    if c.model_id == preferred:
                        return c

        if reasoning_effort in ("max", "ultra", "high"):
            candidates.sort(key=lambda m: (len(m.reasoning_levels), m.context_window_tokens), reverse=True)
            return candidates[0]

        # Default to fastest budget frontier model
        candidates.sort(key=lambda m: m.latency_p50_ms)
        return candidates[0]

    def provider_fallback_chain(self, primary_model_id: str) -> List[str]:
        """Returns deterministic provider fallback sequence."""
        primary = self.get_model(primary_model_id)
        if not primary:
            return ["agent-router", "codecraft", "gemini", "mock"]

        chain = [primary.provider]
        for fallback in ("agent-router", "codecraft", "gemini", "mock"):
            if fallback not in chain:
                chain.append(fallback)
        return chain


_global_registry: Optional[ModelRegistry] = None


def get_model_registry() -> ModelRegistry:
    global _global_registry
    if _global_registry is None:
        _global_registry = ModelRegistry()
    return _global_registry
