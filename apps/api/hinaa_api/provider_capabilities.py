"""Typed provider capability declarations verified against installed adapters.

Capabilities are configuration/code facts, not inferences from model name strings.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

WorkloadClass = Literal[
    "live_voice",
    "normal_conversation",
    "complex_explanation",
    "performance_planning",
    "memory_candidate_extraction",
    "conversation_summary",
]


class ProviderCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str
    text_streaming: bool = False
    audio_input: bool = False
    audio_output: bool = False
    continuous_stt: bool = False
    structured_output: bool = False
    cancellation: bool = False
    usage_reporting: bool = False
    supported_locales: list[str] = Field(default_factory=list)
    stable_or_preview: Literal["stable", "preview", "mock"] = "mock"
    maximum_configured_output: int = 512
    reasoning_controls: bool = False


GEMINI_CAPABILITIES = ProviderCapabilities(
    provider_id="gemini-llm",
    text_streaming=True,
    structured_output=True,
    cancellation=True,
    usage_reporting=False,
    supported_locales=["en", "hi", "mixed"],
    stable_or_preview="preview",
    maximum_configured_output=512,
    reasoning_controls=False,
)

AZURE_SPEECH_CAPABILITIES = ProviderCapabilities(
    provider_id="azure-speech",
    audio_input=True,
    audio_output=True,
    continuous_stt=True,
    cancellation=True,
    usage_reporting=False,
    supported_locales=["hi-IN", "en-US"],
    stable_or_preview="stable",
)

MOCK_CAPABILITIES = ProviderCapabilities(
    provider_id="mock",
    text_streaming=True,
    audio_input=True,
    audio_output=True,
    continuous_stt=False,
    structured_output=True,
    cancellation=True,
    supported_locales=["en", "hi", "mixed"],
    stable_or_preview="mock",
)


WORKLOAD_ROUTING: dict[WorkloadClass, str] = {
    "live_voice": "lowest-latency verified Gemini + Azure continuous STT/TTS",
    "normal_conversation": "fast cost-efficient Gemini with streaming",
    "complex_explanation": "stronger configured Gemini only when depth warrants",
    "performance_planning": "deterministic server planner by default",
    "memory_candidate_extraction": "structured validated extraction; consent required",
    "conversation_summary": "low-cost model; never blocks first spoken response",
}
