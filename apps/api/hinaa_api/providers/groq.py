from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from time import perf_counter

import httpx
from pydantic import ValidationError

from ..errors import HinaaError, safe_error_text
from ..generation.orchestrator import GenerationOrchestrator
from ..generation.continuation_contract import (
    ContinuationRequest,
    render_continuation_prompt,
    PromptInvariantVerifier,
)
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts import (
    PromptPackage,
    build_plan_from_text,
    schema_repair_contents,
    validate_or_none,
)
from .base import ProviderResult
from .timing import ProviderTiming
from .display_stream_decoder import AdaptiveStreamDecoder

GROQ_CHAT_COMPLETIONS_URL = "https://api.groq.com/openai/v1/chat/completions"


def _llm_budget_tokens() -> int:
    try:
        from ..config import get_settings

        return int(get_settings().llm_max_output_tokens)
    except Exception:  # pragma: no cover
        return 16_384


def _llm_stream_char_budget() -> int:
    try:
        from ..config import get_settings

        return int(get_settings().llm_stream_char_budget)
    except Exception:  # pragma: no cover
        return 200_000


def _max_continuations() -> int:
    try:
        from ..config import get_settings

        return max(0, int(get_settings().llm_max_continuations))
    except Exception:  # pragma: no cover
        return 4


def _sanitize_delta(value: str) -> str:
    """Strip only control characters — preserve Markdown/JSON structure."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)


def _messages(prompt: PromptPackage) -> list[dict[str, str]]:
    from hinaa_api.models import safe_extract_display_text

    messages: list[dict[str, str]] = [
        {"role": "system", "content": prompt.system_instruction},
    ]

    recent_turns = getattr(prompt, "recent_turns", None)
    raw_user_text = getattr(prompt, "raw_user_text", None)

    if raw_user_text:
        if recent_turns:
            # B2.1 §5: prompt.recent_turns is ALREADY selected and budgeted by
            # the canonical ContextCompiler. Providers serialize; they never
            # re-select context (no independent slicing).
            for role, content in recent_turns:
                if role not in ("user", "assistant"):
                    continue
                clean_content = safe_extract_display_text(content).strip()
                if clean_content:
                    messages.append({"role": role, "content": clean_content})
        messages.append({"role": "user", "content": raw_user_text.strip()})
        return messages

    user_text = (
        prompt.user_contents
        if isinstance(prompt.user_contents, str)
        else "\n\n".join(str(item) for item in prompt.user_contents)
    )
    messages.append({"role": "user", "content": user_text})
    return messages


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
        prompt = PromptInvariantVerifier.verify_or_sync(prompt)
        started = perf_counter()
        timing = ProviderTiming()
        chunks: list[str] = []
        provider_events = 0
        try:
            timing.mark("provider_client_ready")
            holder: dict[str, str | None] = {"value": None}

            async def _first_stream() -> AsyncIterator[str]:
                decoder = AdaptiveStreamDecoder()
                async for d in self._stream_text(prompt, holder):
                    clean = decoder.feed(d)
                    if clean:
                        yield clean
                rest = decoder.finish()
                if rest:
                    yield rest

            def _continuation_contents(prior: str) -> PromptPackage:
                """Rebuild the prompt with a seamless-resume instruction using canonical contract."""
                base_text = prompt.raw_user_text or (
                    prompt.user_contents
                    if isinstance(prompt.user_contents, str)
                    else "\n\n".join(str(item) for item in prompt.user_contents)
                )
                continuation_req = ContinuationRequest(
                    generation_id=f"groq:{started:.0f}",
                    segment_number=len(orchestrator.segment_results) + 2,
                    original_goal=base_text,
                    previous_tail=prior[-6_000:],
                )
                continued_text = render_continuation_prompt(continuation_req)
                cont_prompt = prompt.model_copy(
                    update={
                        "user_contents": continued_text,
                        "raw_user_text": continued_text,
                    }
                )
                return PromptInvariantVerifier.verify_or_sync(cont_prompt)

            def _continuation_factory(prior: str):
                cont_holder: dict[str, str | None] = {"value": None}

                async def gen() -> AsyncIterator[str]:
                    decoder = AdaptiveStreamDecoder()
                    async for d in self._stream_text(_continuation_contents(prior), cont_holder):
                        clean = decoder.feed(d)
                        if clean:
                            yield clean
                    rest = decoder.finish()
                    if rest:
                        yield rest

                return gen(), cont_holder

            orchestrator = GenerationOrchestrator(
                max_continuations=_max_continuations(),
                char_budget=_llm_stream_char_budget(),
                generation_id=f"groq:{started:.0f}",
            )
            outcome = await orchestrator.run(
                first_segment_stream=_first_stream(),
                first_finish_reason_holder=holder,
                continuation_stream_factory=_continuation_factory,
                emit_delta=emit_delta,
                sanitize=_sanitize_delta,
            )
            provider_events = sum(r.events for r in orchestrator.segment_results)
            timing.mark("first_provider_event")
            timing.mark("first_text_delta")
            timing.mark("text_complete")
            answer = outcome.text.strip()
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
            "max_tokens": _llm_budget_tokens(),
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
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
            "max_tokens": _llm_budget_tokens(),
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                GROQ_CHAT_COMPLETIONS_URL,
                headers=self._headers(),
                json=payload,
            )
        self._raise_for_status(response)
        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content")
        return content if isinstance(content, str) else ""

    async def _stream_text(
        self, prompt: PromptPackage, finish_reason_holder: dict[str, str | None] | None = None
    ) -> AsyncIterator[str]:
        """Stream one completion; optionally record the raw finish reason.

        The finish reason is metadata only — continuation POLICY lives in
        the shared GenerationOrchestrator (Phase B1.1).
        """
        payload = {
            "model": self._model,
            "messages": _messages(prompt),
            "temperature": 0.4,
            "max_tokens": _llm_budget_tokens(),
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
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
                    choices = data.get("choices") or []
                    if not choices:
                        continue
                    if finish_reason_holder is not None:
                        raw_fr = choices[0].get("finish_reason")
                        if raw_fr:
                            finish_reason_holder["value"] = str(raw_fr)
                    delta = choices[0].get("delta", {}).get("content")
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
        if response.status_code == 400:
            provider_text = safe_error_text(response.text, [self._key]).lower()
            if any(m in provider_text for m in ("content_filter", "safety", "refusal", "policy")):
                raise HinaaError("SAFETY_REFUSAL", "Groq declined to generate content due to safety policy.", 400, False)
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
        if any(m in redacted for m in ("content_filter", "safety", "refusal")):
            return HinaaError("SAFETY_REFUSAL", "Groq declined to generate content due to safety policy.", 400, False)
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
