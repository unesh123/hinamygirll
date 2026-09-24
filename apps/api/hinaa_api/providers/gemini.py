from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from time import perf_counter
from typing import Any

from google import genai
from google.genai import types
from pydantic import ValidationError

from ..errors import HinaaError, safe_error_text
from ..generation.orchestrator import (
    GenerationOrchestrator,
)

logger = logging.getLogger(__name__)
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts.depth import depth_word_floor
from ..generation.continuation import word_count
from ..prompts import (
    PromptPackage,
    build_plan_from_text,
    schema_repair_contents,
    validate_or_none,
)
from .base import ProviderResult
from .timing import ProviderTiming


def _sanitize_delta(value: str) -> str:
    """Strip only control characters — NEVER angle brackets or braces.

    The old sanitizer stripped `<`, `>`, `{`, `}`, which silently deleted
    Markdown headings, code fences, tables, and JSON braces from every
    streamed token. Structured document output must survive streaming.
    """
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)


def _llm_budgets() -> tuple[int, int]:
    """(max_output_tokens, stream_char_budget) from settings with safe defaults."""
    try:
        from ..config import get_settings

        settings = get_settings()
        return settings.llm_max_output_tokens, settings.llm_stream_char_budget
    except Exception:  # pragma: no cover - settings unavailable in some tests
        return 16_384, 200_000


def _max_continuations() -> int:
    try:
        from ..config import get_settings

        return max(0, int(get_settings().llm_max_continuations))
    except Exception:  # pragma: no cover - settings unavailable in some tests
        return 4


def _validate_generation_budgets() -> list[str]:
    """Validate generation budgets and warn on dangerous combinations (§43)."""
    try:
        from ..config import validate_generation_settings

        return validate_generation_settings()
    except Exception:  # pragma: no cover
        return []


def _extract_finish_reason(response: Any) -> str | None:
    """Pull the provider finish reason off a streaming chunk (best effort)."""
    try:
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return None
        fr = getattr(candidates[0], "finish_reason", None)
        if fr is None:
            return None
        name = getattr(fr, "name", None)
        if name:
            return name
        return str(fr).rsplit(".", 1)[-1]
    except Exception:  # pragma: no cover - defensive
        return None


def _build_continuation_contents(prompt: PromptPackage, generated: str) -> Any:
    """Resume generation: replay the original ask plus what was already
    written, and instruct the model to continue seamlessly (no preamble,
    no restating)."""
    tail = generated[-6_000:]
    instruction = (
        "CONTINUE the response EXACTLY from where it stopped. "
        "Do not repeat any previous text, do not add a new heading or preamble, "
        "do not apologize, and do not summarize what you already wrote. "
        "Resume mid-sentence if that is where it stopped, and finish the complete response."
    )
    short_words = depth_word_floor(prompt.response_depth) - word_count(generated)
    if short_words > 0:
        # This provider is the brain that actually answers in production, and it
        # refused him out loud over the old wording: an imperative, capitalised
        # "LENGTH CONTRACT" directive reads as an injected instruction to a model
        # hardened against prompt injection. Same enforcement, stated as the
        # unfinished answer he asked for.
        instruction += (
            f" He asked for a complete, documented answer and this draft still needs about "
            f"{short_words:,} more words of substance to be it. Write what is missing — the "
            "sections never started and the ones left as a sentence or two, with worked detail, "
            "numbers and examples. Don't conclude, summarise or offer follow-up help yet; there "
            "is still answer left to write."
        )
    parts: list[Any] = []
    if getattr(prompt, "attachments", None):
        for att in prompt.attachments:
            bytes_data = getattr(att, "bytes_data", None)
            mime_type = getattr(att, "mime_type", "image/png")
            if bytes_data:
                parts.append(types.Part.from_bytes(data=bytes_data, mime_type=mime_type))
    parts.append(
        types.Part.from_text(
            text=(
                f"{prompt.user_contents}\n\n"
                f"--- YOUR PARTIAL OUTPUT SO FAR (verbatim tail) ---\n{tail}\n"
                f"--- END PARTIAL OUTPUT ---\n\n{instruction}"
            )
        )
    )
    return parts

def _build_gemini_contents(prompt: PromptPackage) -> Any:
    parts: list[Any] = []
    if getattr(prompt, "attachments", None):
        for att in prompt.attachments:
            bytes_data = getattr(att, "bytes_data", None)
            mime_type = getattr(att, "mime_type", "image/png")
            if bytes_data:
                parts.append(types.Part.from_bytes(data=bytes_data, mime_type=mime_type))
    if not parts:
        return prompt.user_contents
    parts.append(prompt.user_contents)
    return parts


class GeminiLLMProvider:
    id = "gemini"

    def __init__(self, key: str, model: str) -> None:
        self._key = key
        self._model = model

    @property
    def model(self) -> str:
        """The model id this instance sends, for whoever has to report it honestly."""
        return self._model

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
        timing = ProviderTiming()
        max_output_tokens, char_budget = _llm_budgets()
        for warning in _validate_generation_budgets():
            logger.warning("generation config: %s", warning)
        # Fresh client per call today — no shared HTTP session across turns.
        client = genai.Client(api_key=self._key)
        timing.mark("provider_client_ready")
        chunks: list[str] = []
        provider_events = 0
        try:
            # Phase B1.1: continuation policy lives in the SHARED
            # GenerationOrchestrator — this provider only supplies streaming
            # segments and finish-reason metadata. Policy no longer lives here.
            max_continuations = _max_continuations()
            holder: dict[str, str | None] = {"value": None}

            async def _gemini_segment_stream(contents: Any) -> AsyncIterator[str]:
                """One round: yield raw text deltas, record finish reason."""
                for attempt in range(2):
                    try:
                        stream = await client.aio.models.generate_content_stream(
                            model=self._model,
                            contents=contents,
                            config=types.GenerateContentConfig(
                                system_instruction=prompt.system_instruction,
                                temperature=0.4,
                                max_output_tokens=max_output_tokens,
                                response_mime_type="text/plain",
                            ),
                        )
                        break
                    except Exception as e:
                        msg = str(e).lower()
                        if attempt == 0 and not chunks and (
                            "503" in msg or "high demand" in msg or "unavailable" in msg or "overloaded" in msg
                        ):
                            logger.warning("Gemini 503/high demand transient error, retrying in 1s: %s", e)
                            await asyncio.sleep(1.0)
                            continue
                        raise
                if not chunks:
                    timing.mark("request_sent")
                events = 0
                async for response in stream:
                    events += 1
                    if events == 1 and not chunks:
                        timing.mark("first_provider_event")
                    fr = _extract_finish_reason(response)
                    if fr:
                        holder["value"] = fr
                    delta = _sanitize_delta(response.text or "")
                    if not delta:
                        continue
                    remaining = char_budget - len("".join(chunks))
                    if remaining <= 0:
                        break
                    yield delta[:remaining]

            async def _first_stream() -> AsyncIterator[str]:
                async for d in _gemini_segment_stream(_build_gemini_contents(prompt)):
                    yield d

            async def _continuation_factory(prior: str):
                async def gen() -> AsyncIterator[str]:
                    async for d in _gemini_segment_stream(_build_continuation_contents(prompt, prior)):
                        yield d
                return gen(), holder

            orchestrator = GenerationOrchestrator(
                max_continuations=max_continuations,
                char_budget=char_budget,
                generation_id=f"gemini:{started:.0f}",
                min_words=depth_word_floor(prompt.response_depth),
            )
            outcome = await orchestrator.run(
                first_segment_stream=_first_stream(),
                first_finish_reason_holder=holder,
                continuation_stream_factory=_continuation_factory,
                emit_delta=emit_delta,
                sanitize=lambda s: s,  # provider already sanitizes
                gemini_family=True,
            )
            provider_events += sum(r.events for r in orchestrator.segment_results)
            chunks = [outcome.text]
            if not chunks[0]:
                raise HinaaError(
                    "MODEL_RESPONSE_INVALID", "The model returned no safe text.", 502, True
                )
            answer = chunks[0]
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
        finally:
            await client.aio.aclose()
        stages = timing.snapshot()
        stages["provider_events"] = provider_events
        return ProviderResult(
            plan,
            f"{self.id}:{self._model}",
            int((perf_counter() - started) * 1000),
            stages=stages,
        )

    async def _stream_json(self, client: genai.Client, prompt: PromptPackage) -> str:
        max_output_tokens, _ = _llm_budgets()
        for attempt in range(2):
            try:
                chunks: list[str] = []
                stream = await client.aio.models.generate_content_stream(
                    model=self._model,
                    contents=_build_gemini_contents(prompt),
                    config=types.GenerateContentConfig(
                        system_instruction=prompt.system_instruction,
                        temperature=0.45,
                        max_output_tokens=max_output_tokens,
                        response_mime_type="application/json",
                    ),
                )
                async for response in stream:
                    if response.text:
                        chunks.append(response.text)
                return "".join(chunks)
            except Exception as e:
                msg = str(e).lower()
                if attempt == 0 and (
                    "503" in msg or "high demand" in msg or "unavailable" in msg or "overloaded" in msg
                ):
                    logger.warning("Gemini 503/high demand transient error in plan, retrying in 1s: %s", e)
                    await asyncio.sleep(1.0)
                    continue
                raise

    async def _repair_json(
        self, client: genai.Client, prompt: PromptPackage, invalid_raw: str
    ) -> str:
        max_output_tokens, _ = _llm_budgets()
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
                max_output_tokens=max_output_tokens,
                response_mime_type="application/json",
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
        if any(m in redacted for m in ("safety", "blocked", "content_filter", "harm_category", "finish_reason: safety")):
            return HinaaError("SAFETY_REFUSAL", "Gemini declined to generate content due to safety policies.", 400, False)
        if "api key" in redacted or "401" in redacted or "403" in redacted:
            return HinaaError(
                "PROVIDER_KEY_INVALID",
                "Gemini needs its backend connection fixed.",
                503,
                user_action_required=True,
            )
        if "429" in redacted or "quota" in redacted:
            return HinaaError("PROVIDER_RATE_LIMIT", "Gemini is busy right now.", 429, True)
        return HinaaError("PROVIDER_UNAVAILABLE", "Gemini is unavailable safely.", 502, True)


__all__ = ["GeminiLLMProvider"]
