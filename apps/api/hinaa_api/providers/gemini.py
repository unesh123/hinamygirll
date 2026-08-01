from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from time import perf_counter

from google import genai
from google.genai import types
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


def _sanitize_delta(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value.replace("<", "").replace(">", "").replace("{", "").replace("}", "")


class GeminiLLMProvider:
    id = "gemini"

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
                "Prompt package is required for Gemini planning.",
                500,
                True,
            )
        started = perf_counter()
        client = genai.Client(api_key=self._key)
        try:
            raw = await self._stream_json(client, prompt)
            plan = validate_or_none(raw)
            if plan is None:
                repaired = await self._repair_json(client, prompt, raw)
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
        finally:
            await client.aio.aclose()
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
                "Prompt package is required for Gemini live planning.",
                500,
                True,
            )
        started = perf_counter()
        client = genai.Client(api_key=self._key)
        chunks: list[str] = []
        try:
            stream = await client.aio.models.generate_content_stream(
                model=self._model,
                contents=prompt.user_contents,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    temperature=0.4,
                    max_output_tokens=500,
                    response_mime_type="text/plain",
                ),
            )
            size = 0
            async for response in stream:
                delta = _sanitize_delta(response.text or "")
                if not delta:
                    continue
                remaining = 4_000 - size
                if remaining <= 0:
                    break
                delta = delta[:remaining]
                size += len(delta)
                chunks.append(delta)
                await emit_delta(delta)
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
        except HinaaError:
            raise
        except Exception as error:
            raise self._map_provider_error(error) from error
        finally:
            await client.aio.aclose()
        return ProviderResult(
            plan, f"{self.id}:{self._model}", int((perf_counter() - started) * 1000)
        )

    async def _stream_json(self, client: genai.Client, prompt: PromptPackage) -> str:
        chunks: list[str] = []
        stream = await client.aio.models.generate_content_stream(
            model=self._model,
            contents=prompt.user_contents,
            config=types.GenerateContentConfig(
                system_instruction=prompt.system_instruction,
                temperature=0.45,
                max_output_tokens=1800,
                response_mime_type="application/json",
                response_json_schema=AssistantTurnPlan.model_json_schema(),
            ),
        )
        async for response in stream:
            if response.text:
                chunks.append(response.text)
        return "".join(chunks)

    async def _repair_json(
        self, client: genai.Client, prompt: PromptPackage, invalid_raw: str
    ) -> str:
        chunks: list[str] = []
        stream = await client.aio.models.generate_content_stream(
            model=self._model,
            contents=schema_repair_contents(invalid_raw),
            config=types.GenerateContentConfig(
                system_instruction=(
                    prompt.system_instruction
                    + "\n\nSCHEMA REPAIR MODE: output valid AssistantTurnPlan JSON only."
                ),
                temperature=0.0,
                max_output_tokens=1800,
                response_mime_type="application/json",
                response_json_schema=AssistantTurnPlan.model_json_schema(),
            ),
        )
        async for response in stream:
            if response.text:
                chunks.append(response.text)
        return "".join(chunks)

    def _map_provider_error(self, error: Exception) -> HinaaError:
        if isinstance(error, (ValidationError,)):
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
                "Gemini needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if "429" in redacted or "quota" in redacted:
            return HinaaError(
                "PROVIDER_RATE_LIMIT", "Gemini is busy right now.", 429, True
            )
        return HinaaError(
            "PROVIDER_UNAVAILABLE", "Gemini is unavailable safely.", 502, True
        )


__all__ = ["GeminiLLMProvider"]
