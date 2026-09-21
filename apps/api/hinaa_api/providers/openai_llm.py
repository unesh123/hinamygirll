from __future__ import annotations

import base64
import json
import re
from typing import Any
from collections.abc import AsyncIterator, Awaitable, Callable
from time import perf_counter

import httpx
from pydantic import ValidationError

from ..circuit_breaker import get_circuit_breaker
from ..errors import HinaaError, safe_error_text
from ..generation.orchestrator import GenerationOrchestrator
from ..generation.continuation_contract import (
    ContinuationRequest,
    render_continuation_prompt,
    PromptInvariantVerifier,
)
from ..models import AssistantTurnPlan, CompanionId, Language
from ..prompts.depth import depth_word_floor
from ..prompts import (
    PromptPackage,
    build_plan_from_text,
    schema_repair_contents,
    validate_or_none,
)
from .base import ProviderResult
from .timing import ProviderTiming
from .display_stream_decoder import AdaptiveStreamDecoder

OPENAI_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"


def _sanitize_delta(value: str) -> str:
    """Strip only control characters — preserve Markdown/JSON structure."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)


def _orchestrator_continuations() -> int:
    try:
        from ..config import get_settings

        return max(0, int(get_settings().llm_max_continuations))
    except Exception:  # pragma: no cover
        return 4


def _llm_budget_tokens() -> int:
    try:
        from ..config import get_settings

        return int(get_settings().llm_max_output_tokens)
    except Exception:  # pragma: no cover
        return 16_384


def _messages(prompt: PromptPackage) -> list[dict[str, Any]]:
    from hinaa_api.models import safe_extract_display_text

    system_msg = {"role": "system", "content": prompt.system_instruction}
    messages: list[dict[str, Any]] = [system_msg]

    attachments = getattr(prompt, "attachments", None) or []
    image_parts: list[dict[str, Any]] = []
    for att in attachments:
        bytes_data = getattr(att, "bytes_data", None)
        mime = getattr(att, "mime_type", "image/png")
        if bytes_data and mime.startswith("image/"):
            b64 = base64.b64encode(bytes_data).decode("utf-8")
            image_parts.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{mime};base64,{b64}",
                },
            })

    recent_turns = getattr(prompt, "recent_turns", None)
    raw_user_text = getattr(prompt, "raw_user_text", None)

    # Use native multi-turn messages if raw_user_text is available
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

        final_text = raw_user_text.strip()
        if not image_parts:
            messages.append({"role": "user", "content": final_text})
        else:
            user_content: list[dict[str, Any]] = [{"type": "text", "text": final_text}]
            user_content.extend(image_parts)
            messages.append({"role": "user", "content": user_content})
        return messages

    # Fallback to contiguous user_contents
    if isinstance(prompt.user_contents, str):
        user_text = prompt.user_contents
    elif isinstance(prompt.user_contents, (list, tuple)):
        user_text = "\n\n".join(str(item) for item in prompt.user_contents)
    else:
        user_text = str(prompt.user_contents)

    if not image_parts:
        messages.append({"role": "user", "content": user_text})
    else:
        user_content = [{"type": "text", "text": user_text}]
        user_content.extend(image_parts)
        messages.append({"role": "user", "content": user_content})
    return messages


def _extract_xml_metadata(raw: str) -> tuple[str, dict[str, Any]]:
    """Extract XML tag metadata blocks and return clean text plus parsed metadata."""
    cleaned = raw.strip()
    meta: dict[str, Any] = {}

    # Extract <language>
    lang_match = re.search(r"<language[^>]*>(.*?)</language>", cleaned, re.DOTALL | re.IGNORECASE)
    if lang_match:
        meta["language"] = lang_match.group(1).strip()
        cleaned = cleaned[:lang_match.start()] + cleaned[lang_match.end():]

    # Extract <emotion>
    emotion_match = re.search(r"<emotion[^>]*>(.*?)</emotion>", cleaned, re.DOTALL | re.IGNORECASE)
    if emotion_match:
        meta["emotion_raw"] = emotion_match.group(1).strip()
        cleaned = cleaned[:emotion_match.start()] + cleaned[emotion_match.end():]

    # Extract <performance>
    perf_match = re.search(r"<performance[^>]*>(.*?)</performance>", cleaned, re.DOTALL | re.IGNORECASE)
    if perf_match:
        meta["performance_raw"] = perf_match.group(1).strip()
        cleaned = cleaned[:perf_match.start()] + cleaned[perf_match.end():]

    # Extract <memoryCandidates>
    mem_match = re.search(r"<memoryCandidates[^>]*>(.*?)</memoryCandidates>", cleaned, re.DOTALL | re.IGNORECASE)
    if mem_match:
        meta["memory_candidates_raw"] = mem_match.group(1).strip()
        cleaned = cleaned[:mem_match.start()] + cleaned[mem_match.end():]

    # Extract <toolRequests>
    tool_match = re.search(r"<toolRequests[^>]*>(.*?)</toolRequests>", cleaned, re.DOTALL | re.IGNORECASE)
    if tool_match:
        meta["tool_requests_raw"] = tool_match.group(1).strip()
        cleaned = cleaned[:tool_match.start()] + cleaned[tool_match.end():]

    # Strip wrapper tags
    cleaned = re.sub(r"</?response[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</?(?:spokenText|displayText|think|thought|content|message)[^>]*>", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(), meta


def _custom_text_from_raw(raw: str) -> str:
    cleaned, _ = _extract_xml_metadata(raw)
    try:
        from ..prompts.fallback import extract_json_object

        payload = json.loads(extract_json_object(cleaned))
    except (json.JSONDecodeError, ValueError):
        payload = None
    if isinstance(payload, dict):
        for key in ("displayText", "spokenText", "text", "message", "content"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                cleaned = value.strip()
                break
    elif isinstance(payload, list):
        parts = [item for item in payload if isinstance(item, str) and item.strip()]
        if parts:
            cleaned = " ".join(parts)
    cleaned = re.sub(
        r"</?(?:response|spokenText|displayText|think|thought|content|message|language|emotion|performance|memoryCandidates|toolRequests)[^>]*>",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\s*\([a-zA-Z_]+=[0-9.]+(?:,\s*[a-zA-Z_]+=[0-9.]+)*\)\s*$",
        "",
        cleaned,
    )
    return cleaned.strip()


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
        # Instance identity drives routing diagnostics and fast-brain recovery.
        # Keep it aligned with the selected compatible gateway rather than the
        # class-level OpenAI default.
        self.id = provider_id
        self._circuit_breaker = get_circuit_breaker(provider_id)

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
        can_exec, reason, remaining = self._circuit_breaker.can_execute()
        if not can_exec:
            code = "PROVIDER_RATE_LIMIT" if "rate_limited" in (reason or "") else "PROVIDER_UNAVAILABLE"
            status_code = 429 if code == "PROVIDER_RATE_LIMIT" else 503
            raise HinaaError(code, reason or f"{self._provider_label()} is currently in cooldown.", status_code, True)
        started = perf_counter()
        try:
            raw = await self._chat_json(prompt)
            plan = validate_or_none(raw)
            if (
                plan is None
                and self._provider_id in {"custom", "cx-gateway", "claude", "ollama"}
                and raw.strip()
            ):
                # Reasoning/gateway/local models often answer in plain prose even when
                # asked for JSON. Turn the prose itself into a valid plan so local
                # models (dolphin-mistral) and CX brain never degrade to canned fallback.
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
            if plan is None and self._provider_id in {"custom", "cx-gateway", "claude", "ollama"}:
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
        latency_ms = int((perf_counter() - started) * 1000)
        self._circuit_breaker.record_success(latency_ms)
        return ProviderResult(
            plan, f"{self._provider_id}:{self._model}", latency_ms
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
        prompt = PromptInvariantVerifier.verify_or_sync(prompt)
        can_exec, reason, remaining = self._circuit_breaker.can_execute()
        if not can_exec:
            code = "PROVIDER_RATE_LIMIT" if "rate_limited" in (reason or "") else "PROVIDER_UNAVAILABLE"
            status_code = 429 if code == "PROVIDER_RATE_LIMIT" else 503
            raise HinaaError(code, reason or f"{self._provider_label()} is currently in cooldown.", status_code, True)
        if self._provider_id == "qwen":
            # QwenCloud supports JSON-object plans, but live token deltas are
            # still the raw contract. Validate the complete plan first, then
            # stream only the companion-facing display text to chat and TTS.
            result = await self.create_plan(text, companion_id, language, history, prompt)
            for start in range(0, len(result.value.displayText), 96):
                await emit_delta(result.value.displayText[start : start + 96])
            return result

        started = perf_counter()
        timing = ProviderTiming()
        chunks: list[str] = []
        provider_events = 0
        try:
            timing.mark("provider_client_ready")
            holder: dict[str, str | None] = {"value": None}

            async def _first_stream() -> AsyncIterator[str]:
                decoder = AdaptiveStreamDecoder()
                try:
                    stream_iter = self._stream_text(prompt, holder)
                except TypeError:
                    stream_iter = self._stream_text(prompt)
                async for d in stream_iter:
                    clean = decoder.feed(d)
                    if clean:
                        yield clean
                rest = decoder.finish()
                if rest:
                    yield rest

            def _continuation_contents(prior: str) -> PromptPackage:
                base_text = prompt.raw_user_text or (
                    prompt.user_contents
                    if isinstance(prompt.user_contents, str)
                    else "\n\n".join(str(item) for item in prompt.user_contents)
                )
                continuation_req = ContinuationRequest(
                    generation_id=f"{self._provider_id}:{started:.0f}",
                    segment_number=len(orchestrator.segment_results) + 2,
                    original_goal=base_text,
                    previous_tail=prior[-6_000:],
                    remaining_words=orchestrator.words_short(prior),
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
                    try:
                        stream_iter = self._stream_text(_continuation_contents(prior), cont_holder)
                    except TypeError:
                        stream_iter = self._stream_text(_continuation_contents(prior))
                    async for d in stream_iter:
                        clean = decoder.feed(d)
                        if clean:
                            yield clean
                    rest = decoder.finish()
                    if rest:
                        yield rest

                return gen(), cont_holder

            orchestrator = GenerationOrchestrator(
                max_continuations=_orchestrator_continuations(),
                char_budget=_llm_budget_tokens() * 4,  # chars ≈ 4× token budget
                generation_id=f"{self._provider_id}:{started:.0f}",
                min_words=depth_word_floor(prompt.response_depth),
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
        latency_ms = int((perf_counter() - started) * 1000)
        self._circuit_breaker.record_success(latency_ms)
        return ProviderResult(
            plan,
            f"{self._provider_id}:{self._model}",
            latency_ms,
            stages=stages,
        )

    def _model_for_payload(self) -> str:
        if self._provider_id == "cx-gateway" and self._model.startswith("cx/"):
            return self._model[3:]
        return self._model

    async def _chat_json(self, prompt: PromptPackage) -> str:
        if self._provider_id in {"custom", "cx-gateway", "claude", "ollama"}:
            return await self._chat_text(prompt)
        payload: dict[str, object] = {
            "model": self._model_for_payload(),
            "messages": _messages(prompt),
            "temperature": 0.45,
            "response_format": {"type": "json_object"},
        }
        # QwenCloud & custom gateways document `max_tokens`; standard
        # OpenAI uses `max_completion_tokens`. Both get the full budget.
        payload["max_tokens" if self._provider_id in {"qwen", "custom", "agent-router", "codecraft"} else "max_completion_tokens"] = _llm_budget_tokens()
        async with httpx.AsyncClient(timeout=300.0) as client:
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
            "model": self._model_for_payload(),
            "messages": _messages(prompt),
            "temperature": 0.35,
            # Generous token budget so high-level reasoning and rich technical/creative
            # responses are never truncated prematurely.
            "max_tokens": _llm_budget_tokens(),
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
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
            "model": self._model_for_payload(),
            "messages": [
                {
                    "role": "system",
                    "content": "SCHEMA REPAIR MODE: output valid AssistantTurnPlan JSON only.",
                },
                {"role": "user", "content": "\n\n".join(schema_repair_contents(invalid_raw))},
            ],
            "temperature": 0.0,
            "max_completion_tokens": _llm_budget_tokens(),
            "response_format": {"type": "json_object"},
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
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

    async def _stream_text(
        self, prompt: PromptPackage, finish_reason_holder: dict[str, str | None] | None = None
    ) -> AsyncIterator[str]:
        """Stream one completion; optionally record the raw finish reason.

        Metadata only — continuation POLICY lives in the shared
        GenerationOrchestrator (Phase B1.1).
        """
        if self._provider_id in {"custom", "cx-gateway", "claude", "qwen", "codecraft", "agent-router", "ollama"}:
            # Gateways host reasoning models (e.g. Kimi, Claude Fable, cx/gpt-5.6-sol)
            # that spend tokens on hidden reasoning_content before any visible content.
            # A generous token budget guarantees comprehensive, unclipped output.
            payload: dict[str, object] = {
                "model": self._model_for_payload(),
                "messages": _messages(prompt),
                "temperature": 0.45,
                "max_tokens": _llm_budget_tokens(),
                "stream": True,
            }
            timeout = 300.0
        else:
            payload = {
                "model": self._model,
                "messages": _messages(prompt),
                "temperature": 0.45,
                "max_completion_tokens": _llm_budget_tokens(),
                "stream": True,
            }
            timeout = 300.0
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
                    if finish_reason_holder is not None:
                        raw_fr = choices[0].get("finish_reason")
                        if raw_fr:
                            finish_reason_holder["value"] = str(raw_fr)
                    delta = choices[0].get("delta", {}).get("content")
                    # reasoning_content (private chain-of-thought) is
                    # intentionally never yielded or spoken.
                    if isinstance(delta, str):
                        yield delta

    def _headers(self) -> dict[str, str]:
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/event-stream, */*",
        }
        if self._key and self._key.strip() and self._provider_id != "ollama":
            headers["Authorization"] = f"Bearer {self._key.strip()}"
        return headers

    def _chat_url(self) -> str:
        if self._base_url.endswith("/chat/completions"):
            return self._base_url
        base = self._base_url.rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return f"{base}/chat/completions"

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.status_code < 400:
            return
        retry_after_str = response.headers.get("retry-after")
        retry_after: float | None = None
        if retry_after_str and retry_after_str.strip().isdigit():
            retry_after = float(retry_after_str.strip())

        if response.status_code == 404:
            provider_text = safe_error_text(response.text, [self._key]).lower()
            if "model" in provider_text:
                msg = f"{self._provider_label()} model '{self._model}' was not found on upstream provider."
                self._circuit_breaker.record_failure("MODEL_UNAVAILABLE", msg)
                raise HinaaError("MODEL_UNAVAILABLE", msg, 404, user_action_required=True)
            msg = f"{self._provider_label()} returned 404 (endpoint or model mismatch)."
            self._circuit_breaker.record_failure("ENDPOINT_MISMATCH", msg)
            raise HinaaError("ENDPOINT_MISMATCH", msg, 404, user_action_required=True)

        if response.status_code in {401, 403}:
            msg = f"{self._provider_label()} needs its backend connection fixed."
            self._circuit_breaker.record_failure("PROVIDER_KEY_INVALID", msg)
            raise HinaaError(
                "PROVIDER_KEY_INVALID",
                msg,
                503,
                user_action_required=True,
            )
        if response.status_code == 429:
            msg = f"{self._provider_label()} is rate limited right now."
            self._circuit_breaker.record_failure("PROVIDER_RATE_LIMIT", msg, retry_after=retry_after)
            raise HinaaError(
                "PROVIDER_RATE_LIMIT",
                msg,
                429,
                True,
            )
        provider_text = safe_error_text(response.text, [self._key]).lower()
        if response.status_code == 400 and any(
            m in provider_text for m in ("content_filter", "safety", "refusal", "policy")
        ):
            msg = f"{self._provider_label()} declined to generate content due to safety policy."
            raise HinaaError("SAFETY_REFUSAL", msg, 400, False)
        if response.status_code == 503 and any(
            marker in provider_text
            for marker in ("no available accounts", "no available account", "upstream account unavailable")
        ):
            msg = f"{self._provider_label()} accepted the request, but its upstream service has no available accounts right now. Check the gateway balance/account status or retry later."
            self._circuit_breaker.record_failure("PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE", msg)
            raise HinaaError(
                "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE",
                msg,
                503,
                True,
                True,
            )
        msg = f"{self._provider_label()} is unavailable safely."
        self._circuit_breaker.record_failure("PROVIDER_UNAVAILABLE", msg)
        raise HinaaError(
            "PROVIDER_UNAVAILABLE",
            msg,
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
        if any(m in redacted for m in ("content_filter", "safety", "refusal")):
            msg = f"{self._provider_label()} declined to generate content due to safety policy."
            return HinaaError("SAFETY_REFUSAL", msg, 400, False)
        if "api key" in redacted or "401" in redacted or "403" in redacted:
            msg = f"{self._provider_label()} needs its backend connection fixed."
            self._circuit_breaker.record_failure("PROVIDER_KEY_INVALID", msg)
            return HinaaError(
                "PROVIDER_KEY_INVALID",
                msg,
                503,
                user_action_required=True,
            )
        if "429" in redacted or "quota" in redacted or "rate limit" in redacted:
            msg = f"{self._provider_label()} is rate limited right now."
            self._circuit_breaker.record_failure("PROVIDER_RATE_LIMIT", msg)
            return HinaaError(
                "PROVIDER_RATE_LIMIT",
                msg,
                429,
                True,
            )
        if "no available accounts" in redacted or "no available account" in redacted:
            msg = f"{self._provider_label()} accepted the request, but its upstream service has no available accounts right now. Check the gateway balance/account status or retry later."
            self._circuit_breaker.record_failure("PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE", msg)
            return HinaaError(
                "PROVIDER_ACCOUNT_CAPACITY_UNAVAILABLE",
                msg,
                503,
                True,
                True,
            )
        if "timeout" in redacted or "timed out" in redacted:
            msg = f"{self._provider_label()} timed out."
            self._circuit_breaker.record_failure("PROVIDER_TIMEOUT", msg)
            return HinaaError(
                "PROVIDER_TIMEOUT", msg, 504, True
            )
        msg = f"{self._provider_label()} is unavailable safely."
        self._circuit_breaker.record_failure("PROVIDER_UNAVAILABLE", msg)
        return HinaaError(
            "PROVIDER_UNAVAILABLE", msg, 502, True
        )

    def _provider_label(self) -> str:
        if self._provider_id == "cx-gateway":
            return "CX gateway"
        if self._provider_id == "codecraft":
            return "CodeCraft"
        if self._provider_id == "custom":
            return "Custom model gateway"
        if self._provider_id == "claude":
            return "Claude gateway"
        if self._provider_id == "qwen":
            return "Qwen"
        if self._provider_id == "ollama":
            return "Ollama local engine"
        if self._provider_id in {"agent-router", "agent-router-openai", "agent-router-anthropic"}:
            return "Agent router"
        return "OpenAI"


__all__ = ["OpenAILLMProvider"]
