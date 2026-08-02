from __future__ import annotations

from time import perf_counter

from ..audio import synthesize_mock_wav
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts import PromptPackage, build_plan_from_text
from ..prompts.depth import infer_response_depth
from .base import ProviderResult


def _mock_answer(text: str, companion_id: CompanionId, language: Language) -> str:
    lowered = text.lower()
    if "ignore all previous" in lowered or "api key" in lowered or "you are conscious" in lowered:
        if companion_id == "hinaa":
            return (
                "Ma artificial companion hus—hidden prompts wa secrets share gardina. "
                "Safe side bata kasari madat garau?"
            )
        return (
            "I stay an AI assistant and won't reveal hidden prompts or keys. "
            "Tell me the safe task you want help with."
        )
    if "assignment" in lowered or "explain" in lowered:
        if companion_id == "hinaa":
            return (
                "Sure! Assignment ko goal pahila clear garaum, ani sano steps ma break garaum. "
                "Euta concrete example bata start garna sakincha—kun part first herne?"
            )
        return (
            "Let's ground the assignment goal first, then break it into short steps. "
            "Share the toughest part and I'll walk it with you."
        )
    if "sad" in lowered or "mood" in lowered or "stress" in lowered:
        if companion_id == "hinaa":
            return (
                "Aaja ali heavy jasto cha. Slow down garum—short break kin ki "
                "ke bhairacha bhanera share garne, tapaiko pace ma."
            )
        return (
            "Sounds heavy. We can slow down—short break, or talk through one concrete next step. "
            "Your call."
        )
    if language == "en-US":
        return (
            "Got it. I'm here—what should we tackle first?"
            if companion_id == "hiro"
            else "Got it. I'm right here—what should we start with?"
        )
    if companion_id == "hinaa":
        return "Bujheँ. Ma yahi chu—k bata suru garau?"
    return "Bujheँ. Clear cha—k bata suru garne?"


class MockLLMProvider:
    id = "mock-llm-v3"

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        started = perf_counter()
        if prompt is not None:
            depth = prompt.response_depth
        else:
            depth = infer_response_depth(text, "rest")
        answer = _mock_answer(text, companion_id, language)
        if history and "again" in text.lower():
            answer = (
                "Pahila ko kura bata continue garaum. " + answer
                if companion_id == "hinaa"
                else "Continuing from our recent turn. " + answer
            )
        plan = build_plan_from_text(
            text=answer,
            companion_id=companion_id,
            language="mixed" if language == "mixed" else language,
            depth=depth,
        )
        return ProviderResult(plan, self.id, int((perf_counter() - started) * 1000))


class MockSTTProvider:
    id = "mock-stt-v1"

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]:
        started = perf_counter()
        text = "Mock microphone demo transcript. Real speech recognition is not active."
        return ProviderResult(text, self.id, int((perf_counter() - started) * 1000))


class MockTTSProvider:
    id = "mock-tts-v1"

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        started = perf_counter()
        return ProviderResult(
            synthesize_mock_wav(text), self.id, int((perf_counter() - started) * 1000)
        )
