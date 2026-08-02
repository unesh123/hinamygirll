from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts import PromptPackage


@dataclass(frozen=True, slots=True)
class ProviderResult[T]:
    value: T
    provider: str
    latency_ms: int
    # Sanitized ms-from-start stages only; never prompt/secret content.
    stages: dict[str, int] | None = None


class STTProvider(Protocol):
    id: str

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]: ...


class LLMProvider(Protocol):
    id: str

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]: ...


class LiveLLMProvider(Protocol):
    id: str

    async def create_live_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        emit_delta: Callable[[str], Awaitable[None]],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]: ...


class TTSProvider(Protocol):
    id: str

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]: ...
