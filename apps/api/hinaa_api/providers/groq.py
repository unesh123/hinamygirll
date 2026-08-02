from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from time import perf_counter

import httpx
from pydantic import ValidationError

from ..errors import HinaaError, safe_error_text
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts import (
    PromptPackage,
    build_plan_from_text,
    schema_repair_contents,
    validate_or_none,
)
from .base import ProviderResult
from .timing import ProviderTiming

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


def _sanitize_delta(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value.replace("<", "").replace(">", "").replace("{", "").replace("}", "")


def _messages(prompt: PromptPackage) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt.system_instruction},
        {
            "role": "user",
            "content": "\n\n".join(str(item) for item in prompt.user_contents),
        },
    ]


class GroqLLMProvider:
    """Official Groq OpenAI-compatible chat adapter.

    This provider is intentionally LLM-only. It does not send microphone audio
    or TTS text to Groq; STT/TTS remain behind separate local/real interfaces.
    """

    id = "groq"

    def __init__(self, key: str, model: str) -> None:
        self._key = key
        self._model = model

    async def create_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        if prompt is None:
            raise HinaaError(
                "MODEL_RESPONSE_INVALID",
                "Prompt package is required for Groq planning.",
                500,
                True,
            )
        started = perf_counter()
        try:
            raw = await self._chat_json(prompt)
            plan = validate_or_none(raw)
            if plan is None:
                repaired = await self._repair_json(raw)
                plan = validate_or_none(repaired)
            if plan is None:
                raise HinaaError(
                    "MODEL_RESPONSE_INVALID",
                    "The model returned an invalid safe response plan.",
                    502,
                    True,
                )
        except HinaaError:
            raise
        except Exception as error:
            raise self._map_provider_error(error) from error
        return ProviderResult(
            plan, f"{self.id}:{self._model}", int((perf_counter() - started) * 1000)
        )

    async def create_live_plan(
        self,
        text: str,
        companion_id: CompanionId,
        language: Language,
        history: tuple[tuple[str, str], ...],
        emit_delta: Callable[[str], Awaitable[None]],
        prompt: PromptPackage | None = None,
    ) -> ProviderResult[AssistantTurnPlan]:
        if prompt is None:
            raise HinaaError(
                "MODEL_RESPONSE_INVALID",
                "Prompt package is required for Groq live planning.",
                500,
                True,
            )
        started = perf_counter()
        timing = ProviderTiming()
        chunks: list[str] = []
        provider_events = 0
        try:
            timing.mark("provider_client_ready")
            async for delta in self._stream_text(prompt):
                provider_events += 1
                if provider_events == 1:
                    timing.mark("first_provider_event")
                delta = _sanitize_delta(delta)
                if not delta:
                    continue
                chunks.append(delta)
                timing.mark("first_text_delta")
                await emit_delta(delta)
            timing.mark("text_complete")
            answer = "".join(chunks).strip()
            if not answer:
                raise HinaaError(
                    "MODEL_RESPONSE_INVALID", "The model returned no safe text.", 502, True
                )
            plan = build_plan_from_text(
                text=answer,
                companion_id=companion_id,
                language=language,
                depth=prompt.response_depth,
            )
            timing.mark("plan_parsed")
            timing.mark("plan_validated")
        except HinaaError:
            raise
        except Exception as error:
            raise self._map_provider_error(error) from error
        stages = timing.snapshot()
        stages["provider_events"] = provider_events
        return ProviderResult(
            plan,
            f"{self.id}:{self._model}",
            int((perf_counter() - started) * 1000),
            stages=stages,
        )

    async def _chat_json(self, prompt: PromptPackage) -> str:
        payload = {
            "model": self._model,
            "messages": _messages(prompt),
            "temperature": 0.35,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    async def _repair_json(self, invalid_raw: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "SCHEMA REPAIR MODE: output valid AssistantTurnPlan JSON only.",
                },
                {
                    "role": "user",
                    "content": "\n\n".join(schema_repair_contents(invalid_raw)),
                },
            ],
            "temperature": 0.0,
            "max_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    async def _stream_text(self, prompt: PromptPackage) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": _messages(prompt),
            "temperature": 0.4,
            "max_tokens": 500,
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            async with client.stream(
                "POST",
                GROQ_CHAT_COMPLETIONS_URL,
                headers=self._headers(),
                json=payload,
            ) as response:
                self._raise_for_status(response)
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    event = line.removeprefix("data:").strip()
                    if event == "[DONE]":
                        break
                    try:
                        data = json.loads(event)
                    except json.JSONDecodeError:
                        continue
                    delta = data.get("choices", [{}])[0].get("delta", {}).get("content")
                    if isinstance(delta, str):
                        yield delta

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise HinaaError(
                "PROVIDER_KEY_INVALID",
                "Groq needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if response.status_code == 429:
            raise HinaaError("PROVIDER_RATE_LIMIT", "Groq is rate limited right now.", 429, True)
        raise HinaaError("PROVIDER_UNAVAILABLE", "Groq is unavailable safely.", 502, True)

    def _map_provider_error(self, error: Exception) -> HinaaError:
        if isinstance(error, ValidationError):
            return HinaaError(
                "MODEL_RESPONSE_INVALID",
                "The model returned an invalid safe response plan.",
                502,
                True,
            )
        redacted = safe_error_text(error, [self._key]).lower()
        if "api key" in redacted or "401" in redacted or "403" in redacted:
            return HinaaError(
                "PROVIDER_KEY_INVALID",
                "Groq needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if "429" in redacted or "quota" in redacted or "rate limit" in redacted:
            return HinaaError("PROVIDER_RATE_LIMIT", "Groq is rate limited right now.", 429, True)
        return HinaaError("PROVIDER_UNAVAILABLE", "Groq is unavailable safely.", 502, True)


__all__ = ["GroqLLMProvider"]
