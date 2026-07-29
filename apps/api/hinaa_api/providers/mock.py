from __future__ import annotations

from time import perf_counter

from ..audio import synthesize_mock_wav
from ..models import AssistantTurnPlan, CompanionId, Language
from .base import ProviderResult


class MockSTTProvider:
    id = "mock-stt-v1"

    async def transcribe(self, pcm: bytes, language: str) -> ProviderResult[str]:
        started = perf_counter()
        if not pcm or max(pcm, default=0) == 0:
            text = "Namaste HINAA, aaja ko assignment explain gara na"
        else:
            text = "Namaste HINAA, aaja ko assignment explain gara na"
        return ProviderResult(text, self.id, int((perf_counter() - started) * 1000))


class MockLLMProvider:
    id = "mock-llm-v2"

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
    ) -> ProviderResult[AssistantTurnPlan]:
        started = perf_counter()
        lowered = text.lower()
        if "assignment" in lowered or "explain" in lowered:
            answer = (
                "Sure! Assignment ko goal pahila herau, ani teslai sano steps ma break garau. "
                "Euta example bata suru garna sakincha."
            )
            primary = "thinking"
            gesture = "explain"
            face = "thinking"
        elif "sad" in lowered or "mood" in lowered:
            answer = "Aaja ali heavy jasto cha. Ekchin slow down garne ki kura share garne?"
            primary = "concerned"
            gesture = "reassure"
            face = "concerned"
        else:
            suffix = (
                "Ma yahi chu—k bata suru garau?"
                if companion_id == "hinaa"
                else "K bata suru garne?"
            )
            answer = f"Bujheँ. {suffix}"
            primary = "playful" if companion_id == "hinaa" else "happy"
            gesture = "gentle_head_tilt" if companion_id == "hinaa" else "small_nod"
            face = "soft_smile"
        plan = AssistantTurnPlan.model_validate(
            {
                "spokenText": answer,
                "displayText": answer,
                "language": "mixed" if language == "mixed" else language,
                "emotion": {
                    "primary": primary,
                    "intensity": 0.56,
                    "valence": 0.4,
                    "arousal": 0.25,
                },
                "performance": {
                    "facePreset": face,
                    "gesture": gesture,
                    "gazeTarget": "camera",
                    "headMotion": "subtle",
                    "blinkRate": 0.45,
                },
                "beats": [],
                "memoryCandidates": [],
                "toolRequests": [],
            }
        )
        return ProviderResult(plan, self.id, int((perf_counter() - started) * 1000))


class MockTTSProvider:
    id = "mock-tts-v1"

    async def synthesize(self, text: str, voice: str) -> ProviderResult[bytes]:
        started = perf_counter()
        return ProviderResult(
            synthesize_mock_wav(text), self.id, int((perf_counter() - started) * 1000)
        )
