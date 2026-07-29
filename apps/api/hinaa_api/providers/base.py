from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from ..models import AssistantTurnPlan, CompanionId, Language


@dataclass(frozen=True, slots=True)
class ProviderResult[T]:
    value: T
    provider: str
    latency_ms: int


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
    ) -> ProviderResult[AssistantTurnPlan]: ...


class TTSProvider(Protocol):
    id: str

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]: ...
