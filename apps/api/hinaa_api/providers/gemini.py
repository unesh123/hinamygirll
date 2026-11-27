from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import AsyncIterator, Awaitable, Callable
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


def _llm_budgets(prompt: Any = None) -> tuple[int, int]:
    """(max_output_tokens, stream_char_budget) from settings with safe defaults."""
    try:
        from ..config import get_settings

        settings = get_settings()
        default_tokens, default_chars = settings.llm_max_output_tokens, settings.llm_stream_char_budget
    except Exception:  # pragma: no cover - settings unavailable in some tests
        default_tokens, default_chars = 16_384, 200_000

    if prompt is None:
        return default_tokens, default_chars

    depth = getattr(prompt, "response_depth", None)

    if depth in {"minimal", "clarification", "safety_redirect"}:
        return min(default_tokens, 1024), 8000
    if depth in {"conversational", "supportive"}:
        return min(default_tokens, 4096), 40_000
    if depth in {"explanatory", "procedural"}:
        return min(default_tokens, 8192), 100_000
    if depth == "report":
        return default_tokens, default_chars

    return default_tokens, default_chars


def _max_continuations(prompt: Any = None) -> int:
    depth = getattr(prompt, "response_depth", None) if prompt is not None else None
    if depth in ("minimal", "clarification", "safety_redirect", "conversational", "supportive"):
        return 0
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

    async def complete_raw_agentic(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 8192,
        images: list[tuple[str, bytes]] | None = None,
        tool_schemas: list[dict[str, Any]] | None = None,
        messages: list[dict[str, Any]] | None = None,
        tool_choice: str = "auto",
    ) -> str:
        """Direct raw completion for bounded coding/studio agent loops with native function calling + safe fallback."""
        import json as _json

        client = genai.Client(api_key=self._key)

        def _build_declarations() -> list[types.FunctionDeclaration]:
            decls: list[types.FunctionDeclaration] = []
            for item in tool_schemas or []:
                fn = item.get("function") if isinstance(item, dict) else None
                if not isinstance(fn, dict) or not fn.get("name"):
                    continue
                schema = fn.get("parameters") or {"type": "object", "properties": {}}
                decls.append(
                    types.FunctionDeclaration(
                        name=str(fn["name"]),
                        description=str(fn.get("description") or "")[:500],
                        parameters_json_schema=schema,
                    )
                )
            return decls

        def _build_contents(use_structured_msgs: bool) -> Any:
            if not use_structured_msgs or not messages:
                if images:
                    parts: list[Any] = [user_prompt]
                    for mime_type, raw_bytes in images[:8]:
                        if raw_bytes:
                            parts.append(types.Part.from_bytes(data=raw_bytes, mime_type=mime_type or "image/jpeg"))
                    if len(parts) > 1:
                        return parts
                return user_prompt

            built: list[types.Content] = []
            name_by_call_id: dict[str, str] = {}
            for msg in messages:
                role = str(msg.get("role") or "user")
                if role == "assistant" and isinstance(msg.get("tool_calls"), list):
                    parts_m: list[types.Part] = []
                    for tc in msg["tool_calls"]:
                        if not isinstance(tc, dict):
                            continue
                        tc_id = str(tc.get("id") or "")
                        fn = tc.get("function") or {}
                        fn_name = str(fn.get("name") or "")
                        if tc_id and fn_name:
                            name_by_call_id[tc_id] = fn_name
                        raw_args = fn.get("arguments")
                        try:
                            parsed_args = _json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
                        except Exception:
                            parsed_args = {}
                        if fn_name:
                            parts_m.append(
                                types.Part.from_function_call(
                                    name=fn_name,
                                    args=parsed_args if isinstance(parsed_args, dict) else {},
                                )
                            )
                    if parts_m:
                        built.append(types.Content(role="model", parts=parts_m))
                elif role == "tool":
                    tc_id = str(msg.get("tool_call_id") or "")
                    fn_name = str(msg.get("name") or name_by_call_id.get(tc_id) or "tool")
                    try:
                        parsed_obs = _json.loads(str(msg.get("content") or "{}"))
                    except Exception:
                        parsed_obs = {"result": str(msg.get("content") or "")}
                    if not isinstance(parsed_obs, dict):
                        parsed_obs = {"result": parsed_obs}
                    part_r = types.Part.from_function_response(name=fn_name, response=parsed_obs)
                    if built and built[-1].role == "user":
                        built[-1].parts.append(part_r)
                    else:
                        built.append(types.Content(role="user", parts=[part_r]))
                else:
                    txt = msg.get("content")
                    text_str = txt if isinstance(txt, str) else _json.dumps(txt or "", ensure_ascii=False)
                    if text_str.strip():
                        built.append(types.Content(role="user", parts=[types.Part.from_text(text=text_str)]))
            if images:
                img_parts: list[Any] = [
                    types.Part.from_bytes(data=raw_bytes, mime_type=mime_type or "image/jpeg")
                    for mime_type, raw_bytes in images[:8]
                    if raw_bytes
                ]
                if img_parts:
                    if built and built[-1].role == "user":
                        built[-1].parts.extend(img_parts)
                    else:
                        built.append(
                            types.Content(
                                role="user",
                                parts=[types.Part.from_text(text="Inspect the attached visual preview carefully."), *img_parts],
                            )
                        )
            return built or user_prompt

        decls = _build_declarations() if tool_schemas else []
        try:
            if decls:
                try:
                    gen_cfg_kw: dict[str, Any] = {
                        "system_instruction": system_prompt,
                        "temperature": 0.2,
                        "max_output_tokens": max_tokens,
                        "tools": [types.Tool(function_declarations=decls)],
                    }
                    if tool_choice == "required":
                        gen_cfg_kw["tool_config"] = types.ToolConfig(
                            function_calling_config=types.FunctionCallingConfig(
                                mode=types.FunctionCallingConfigMode.ANY
                            )
                        )
                    response = await client.aio.models.generate_content(
                        model=self._model,
                        contents=_build_contents(bool(messages)),
                        config=types.GenerateContentConfig(**gen_cfg_kw),
                    )
                    fcs = getattr(response, "function_calls", None) or []
                    if fcs:
                        if len(fcs) == 1:
                            fc0 = fcs[0]
                            return _json.dumps(
                                {
                                    "action": "call_tool",
                                    "tool": str(getattr(fc0, "name", "") or ""),
                                    "arguments": dict(getattr(fc0, "args", None) or {}),
                                    "rationale": (getattr(response, "text", None) or "Native function call")[:200],
                                },
                                ensure_ascii=False,
                            )
                        return _json.dumps(
                            {
                                "action": "call_tools",
                                "calls": [
                                    {
                                        "tool": str(getattr(fc, "name", "") or ""),
                                        "arguments": dict(getattr(fc, "args", None) or {}),
                                    }
                                    for fc in fcs[:6]
                                ],
                                "rationale": "Parallel native function calls",
                            },
                            ensure_ascii=False,
                        )
                    txt_native = (getattr(response, "text", None) or "").strip()
                    if txt_native:
                        return txt_native
                except Exception as fn_exc:
                    logger.debug("Gemini native tool call fell back to prompt mode: %s", fn_exc)

            response = await client.aio.models.generate_content(
                model=self._model,
                contents=_build_contents(False),
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    max_output_tokens=max_tokens,
                ),
            )
            return (response.text or "").strip()
        except HinaaError:
            raise
        except Exception as error:
            raise self._map_provider_error(error) from error
        finally:
            await client.aio.aclose()

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
        max_output_tokens, char_budget = _llm_budgets(prompt)
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
            max_continuations = _max_continuations(prompt)
            holder: dict[str, str | None] = {"value": None}

            async def _gemini_segment_stream(contents: Any) -> AsyncIterator[str]:
                """One round: yield raw text deltas, record finish reason."""
                for attempt in range(3):
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
                        if attempt < 2 and not chunks and (
                            "503" in msg
                            or "high demand" in msg
                            or "unavailable" in msg
                            or "overloaded" in msg
                            or "429" in msg
                            or "resource_exhausted" in msg
                            or "rate limit" in msg
                        ):
                            delay = 3.0 * (attempt + 1)
                            logger.warning(
                                "Gemini transient error (attempt %d/3), retrying in %.1fs: %s",
                                attempt + 1,
                                delay,
                                e,
                            )
                            await asyncio.sleep(delay)
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
                if outcome.thinking and outcome.thinking.strip():
                    chunks = [outcome.thinking.strip()]
                else:
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
        max_output_tokens, _ = _llm_budgets(prompt)
        for attempt in range(3):
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
                if attempt < 2 and (
                    "503" in msg
                    or "high demand" in msg
                    or "unavailable" in msg
                    or "overloaded" in msg
                    or "429" in msg
                    or "resource_exhausted" in msg
                    or "rate limit" in msg
                ):
                    delay = 3.0 * (attempt + 1)
                    logger.warning(
                        "Gemini transient error in plan (attempt %d/3), retrying in %.1fs: %s",
                        attempt + 1,
                        delay,
                        e,
                    )
                    await asyncio.sleep(delay)
                    continue
                raise

    async def _repair_json(
        self, client: genai.Client, prompt: PromptPackage, invalid_raw: str
    ) -> str:
        max_output_tokens, _ = _llm_budgets(prompt)
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
