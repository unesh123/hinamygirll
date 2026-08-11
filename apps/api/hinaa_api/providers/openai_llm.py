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

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _sanitize_delta(value: str) -> str:
    value = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)
    return value.replace("<", "").replace(">", "").replace("{", "").replace("}", "")


def _messages(prompt: PromptPackage) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt.system_instruction},
        {"role": "user", "content": "\n\n".join(str(item) for item in prompt.user_contents)},
    ]


def _custom_text_from_raw(raw: str) -> str:
    cleaned = raw.strip()
    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return cleaned
    if isinstance(payload, dict):
        for key in ("displayText", "spokenText", "text", "message", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    if isinstance(payload, list):
        # A JSON array is likely broken chat output; speak the joined pieces
        # rather than raw JSON syntax.
        parts = [item for item in payload if isinstance(item, str) and item.strip()]
        if parts:
            return " ".join(parts)
    return cleaned


class OpenAILLMProvider:
    """Official OpenAI chat-completions adapter for HINAA's structured brain."""

    id = "openai"

    def __init__(
        self,
        key: str,
        model: str,
        *,
        base_url: str = OPENAI_CHAT_COMPLETIONS_URL,
        provider_id: str = "openai",
    ) -> None:
        self._key = key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._provider_id = provider_id

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
                "Prompt package is required for OpenAI planning.",
                500,
                True,
            )
        started = perf_counter()
        try:
            raw = await self._chat_json(prompt)
            plan = validate_or_none(raw)
            if (
                plan is None
                and self._provider_id in {"custom", "cx-gateway"}
                and raw.strip()
            ):
                # Reasoning/gateway models often answer in plain prose even when
                # asked for JSON. Turn the prose itself into a valid plan so the
                # CX brain (gpt-5.6-sol) never degrades to the canned fallback.
                fallback_text = _custom_text_from_raw(raw)
                plan = build_plan_from_text(
                    text=fallback_text,
                    companion_id=companion_id,
                    language=language,
                    depth=prompt.response_depth,
                )
                try:
                    import json
                    from ..prompts.fallback import extract_json_object
                    payload = json.loads(extract_json_object(raw))
                    if isinstance(payload, dict):
                        if "toolRequests" in payload and isinstance(payload["toolRequests"], list):
                            from ..models import ToolRequest
                            for tr in payload["toolRequests"]:
                                if isinstance(tr, dict) and "toolName" in tr and "parameters" in tr:
                                    plan.toolRequests.append(ToolRequest(**tr))
                        if "memoryCandidates" in payload and isinstance(payload["memoryCandidates"], list):
                            from ..models import MemoryCandidate
                            for mc in payload["memoryCandidates"]:
                                if isinstance(mc, dict) and "content" in mc:
                                    plan.memoryCandidates.append(MemoryCandidate(**mc))
                except Exception:
                    pass
            if plan is None and self._provider_id in {"custom", "cx-gateway"}:
                # Prose-recovery is the real path for gateway models; a schema
                # repair round trip would send response_format these gateways
                # may reject. Fail typed instead of burning a second call.
                raise HinaaError(
                    "MODEL_RESPONSE_INVALID",
                    "The model returned an invalid safe response plan.",
                    502,
                    True,
                )
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
            plan, f"{self._provider_id}:{self._model}", int((perf_counter() - started) * 1000)
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
                "Prompt package is required for OpenAI live planning.",
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
            f"{self._provider_id}:{self._model}",
            int((perf_counter() - started) * 1000),
            stages=stages,
        )

    async def _chat_json(self, prompt: PromptPackage) -> str:
        if self._provider_id in {"custom", "cx-gateway"}:
            return await self._chat_text(prompt)
        payload = {
            "model": self._model,
            "messages": _messages(prompt),
            "temperature": 0.45,
            "max_completion_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        return content if isinstance(content, str) else ""

    async def _chat_text(self, prompt: PromptPackage) -> str:
        payload = {
            "model": self._model,
            "messages": _messages(prompt),
            "temperature": 0.35,
            # Reasoning models spend hidden tokens before the answer; a small
            # cap starves the visible reply entirely.
            "max_tokens": 2200,
        }
        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        return content if isinstance(content, str) else ""

    async def _repair_json(self, invalid_raw: str) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "system",
                    "content": "SCHEMA REPAIR MODE: output valid AssistantTurnPlan JSON only.",
                },
                {"role": "user", "content": "\n\n".join(schema_repair_contents(invalid_raw))},
            ],
            "temperature": 0.0,
            "max_completion_tokens": 1800,
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._chat_url(),
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        choices = data.get("choices") or []
        content = choices[0].get("message", {}).get("content") if choices else None
        return content if isinstance(content, str) else ""

    async def _stream_text(self, prompt: PromptPackage) -> AsyncIterator[str]:
        if self._provider_id in {"custom", "cx-gateway"}:
            # OpenAI-compatible gateways host reasoning models (e.g. Kimi,
            # cx/gpt-5.6-sol) that spend tokens on hidden "reasoning_content"
            # before any spoken "content". A small cap starves the actual
            # answer, so allow more headroom and a longer gateway timeout.
            payload: dict[str, object] = {
                "model": self._model,
                "messages": _messages(prompt),
                "temperature": 0.45,
                "max_tokens": 2200,
                "stream": True,
            }
            timeout = 90.0
        else:
            payload = {
                "model": self._model,
                "messages": _messages(prompt),
                "temperature": 0.45,
                "max_completion_tokens": 600,
                "stream": True,
            }
            timeout = 30.0
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "POST",
                self._chat_url(),
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
                    choices = data.get("choices") or []
                    if not choices:
                        # Usage/heartbeat events legally carry no choices;
                        # indexing [0] here used to crash the whole live turn.
                        continue
                    delta = choices[0].get("delta", {}).get("content")
                    # reasoning_content (private chain-of-thought) is
                    # intentionally never yielded or spoken.
                    if isinstance(delta, str):
                        yield delta

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }

    def _chat_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        return f"{self._base_url.rstrip('/')}/chat/completions"

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        if response.status_code in {401, 403}:
            raise HinaaError(
                "PROVIDER_KEY_INVALID",
                f"{self._provider_label()} needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if response.status_code == 429:
            raise HinaaError(
                "PROVIDER_RATE_LIMIT",
                f"{self._provider_label()} is rate limited right now.",
                429,
                True,
            )
        raise HinaaError(
            "PROVIDER_UNAVAILABLE",
            f"{self._provider_label()} is unavailable safely.",
            502,
            True,
        )

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
                f"{self._provider_label()} needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if "429" in redacted or "quota" in redacted or "rate limit" in redacted:
            return HinaaError(
                "PROVIDER_RATE_LIMIT",
                f"{self._provider_label()} is rate limited right now.",
                429,
                True,
            )
        return HinaaError(
            "PROVIDER_UNAVAILABLE", f"{self._provider_label()} is unavailable safely.", 502, True
        )

    def _provider_label(self) -> str:
        if self._provider_id == "cx-gateway":
            return "CX gateway"
        if self._provider_id == "custom":
            return "Custom model gateway"
        return "OpenAI"


__all__ = ["OpenAILLMProvider"]
