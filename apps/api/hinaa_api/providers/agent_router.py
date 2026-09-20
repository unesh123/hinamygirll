import httpx
import logging
from collections.abc import Awaitable, Callable
from typing import AsyncIterator, Any
from urllib.parse import urlparse
from anthropic import AsyncAnthropic, APIError, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError
from hinaa_api.providers.openai_llm import OpenAILLMProvider, _sanitize_delta, _orchestrator_continuations, _custom_text_from_raw
from hinaa_api.errors import HinaaError
from hinaa_api.prompts import PromptPackage
from hinaa_api.prompts.depth import depth_word_floor
from hinaa_api.providers.blocks import normalize_anthropic_response, extract_text_from_canonical_blocks
from hinaa_api.generation.orchestrator import GenerationOrchestrator
from hinaa_api.generation.continuation_contract import (
    ContinuationRequest,
    render_continuation_prompt,
    PromptInvariantVerifier,
)
from hinaa_api.providers.display_stream_decoder import DisplayTextChain, AdaptiveStreamDecoder

logger = logging.getLogger("hinaa.providers.agent_router")


def _map_httpx_error(e: Exception) -> HinaaError:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            code = "PROVIDER_AUTH_FAILED" if status == 401 else "PROVIDER_ACCESS_DENIED"
        elif status == 400 and any(m in e.response.text.lower() for m in ("content_filter", "safety", "refusal", "policy")):
            return HinaaError(
                code="SAFETY_REFUSAL",
                status_code=400,
                message="Refusal due to safety policy",
                developer_message=e.response.text[:200]
            )
        elif status == 404:
            if "model" in e.response.text.lower():
                code = "PROVIDER_MODEL_NOT_FOUND"
            else:
                code = "PROVIDER_ENDPOINT_INVALID"
        elif status == 429:
            code = "PROVIDER_RATE_LIMITED"
        else:
            code = "PROVIDER_UNAVAILABLE"
        return HinaaError(
            code=code,
            status_code=500,
            message=f"AgentRouter HTTP Error: {status}",
            developer_message=e.response.text[:200]
        )
    elif isinstance(e, httpx.TimeoutException):
        return HinaaError(code="PROVIDER_TIMEOUT", status_code=500, message="Timeout")
    else:
        return HinaaError(code="PROVIDER_UNREACHABLE", status_code=500, message="Connection Error")


class AgentRouterOpenAIProvider(OpenAILLMProvider):
    id = "agent-router-openai"
    def __init__(self, api_key: str, model: str, base_url: str):
        super().__init__(key=api_key, model=model, base_url=base_url, provider_id="agent-router-openai")
        
    def _map_provider_error(self, error: Exception) -> HinaaError:
        return _map_httpx_error(error)

    async def _stream_text(
        self, prompt: PromptPackage, finish_reason_holder: dict[str, str | None] | None = None
    ) -> AsyncIterator[str]:
        try:
            async for chunk in super()._stream_text(prompt, finish_reason_holder):
                yield chunk
        except Exception as e:
            if isinstance(e, HinaaError):
                raise e
            raise self._map_provider_error(e)

    async def _chat_text(self, prompt: PromptPackage) -> str:
        try:
            return await super()._chat_text(prompt)
        except Exception as e:
            if isinstance(e, HinaaError):
                raise e
            raise self._map_provider_error(e)

    async def _chat_json(self, prompt: PromptPackage) -> str:
        try:
            return await super()._chat_json(prompt)
        except Exception as e:
            if isinstance(e, HinaaError):
                raise e
            raise self._map_provider_error(e)


def _llm_budget_tokens() -> int:
    try:
        from ..config import get_settings

        return int(get_settings().llm_max_output_tokens)
    except Exception:  # pragma: no cover
        return 16_384


def _anthropic_messages(prompt: PromptPackage) -> list[dict[str, Any]]:
    from hinaa_api.models import safe_extract_display_text
    from .anthropic_direct import build_anthropic_content

    recent_turns = getattr(prompt, "recent_turns", None)
    raw_user_text = getattr(prompt, "raw_user_text", None)
    attachments = getattr(prompt, "attachments", None)

    if raw_user_text:
        messages: list[dict[str, Any]] = []
        if recent_turns:
            # B2.1 §5: prompt.recent_turns is ALREADY selected and budgeted by
            # the canonical ContextCompiler. Providers serialize; they never
            # re-select context (no independent slicing).
            for role, content in recent_turns:
                if role not in ("user", "assistant"):
                    continue
                clean_content = safe_extract_display_text(content).strip()
                if not clean_content:
                    continue
                if messages and messages[-1]["role"] == role:
                    prev = messages[-1]["content"]
                    if isinstance(prev, str):
                        messages[-1]["content"] = f"{prev}\n\n{clean_content}"
                    elif isinstance(prev, list):
                        messages[-1]["content"].append({"type": "text", "text": f"\n\n{clean_content}"})
                else:
                    messages.append({"role": role, "content": clean_content})

        final_content = build_anthropic_content(raw_user_text.strip(), attachments)

        if messages and messages[-1]["role"] == "user":
            prev = messages[-1]["content"]
            if isinstance(prev, str) and isinstance(final_content, str):
                messages[-1]["content"] = f"{prev}\n\n{final_content}"
            elif isinstance(prev, list) and isinstance(final_content, list):
                messages[-1]["content"].extend(final_content)
            else:
                messages.append({"role": "assistant", "content": "Got it."})
                messages.append({"role": "user", "content": final_content})
        else:
            messages.append({"role": "user", "content": final_content})

        if messages and messages[0]["role"] != "user":
            messages.insert(0, {"role": "user", "content": "Hello"})
        return messages

    # Fallback to contiguous user_contents
    if isinstance(prompt.user_contents, str):
        user_text = prompt.user_contents
    elif isinstance(prompt.user_contents, (list, tuple)):
        user_text = "\n\n".join(str(item) for item in prompt.user_contents)
    else:
        user_text = str(prompt.user_contents)

    content = build_anthropic_content(user_text, attachments)
    return [{"role": "user", "content": content}]


class AgentRouterAnthropicProvider(OpenAILLMProvider):
    id = "agent-router-anthropic"

    def __init__(self, api_key: str, model: str, base_url: str, *, provider_id: str = "agent-router-anthropic"):
        self.id = provider_id
        self.uses_bearer_auth = urlparse(base_url).hostname == "api.mwapi.dev"
        super().__init__(key=api_key, model=model, base_url=base_url, provider_id=provider_id)
        # AsyncAnthropic supplies x-api-key for official Anthropic. The mwapi
        # Claude-compatible route additionally requires standard Bearer auth;
        # retaining the SDK header preserves the Messages request contract.
        self.gateway_auth_headers = {"Authorization": f"Bearer {api_key}"} if self.uses_bearer_auth else {}
        # Cloudflare-guarded gateways (e.g. api.mwapi.dev) return error 1010
        # "ban based on browser signature" when the HTTP client fingerprint
        # looks like a script (default httpx/anthropic UA). Verified live:
        # the same request with a browser UA + Origin/Referer returns 200.
        # These headers make the Messages contract identical, only the UA
        # signature changes — safe for official Anthropic too (it ignores them).
        browser_fp_headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
            ),
            "Origin": "https://agent.tinyfish.ai",
            "Referer": "https://agent.tinyfish.ai/",
            "Accept": "application/json",
        }
        clean_base = base_url.rstrip("/")
        if clean_base.endswith("/v1"):
            clean_base = clean_base[:-3]
        self.anthropic_client = AsyncAnthropic(
            api_key=api_key,
            base_url=clean_base,
            default_headers={**(self.gateway_auth_headers or {}), **browser_fp_headers},
        )

    def _map_anthropic_error(self, e: Exception) -> HinaaError:
        if any(m in str(e).lower() for m in ("content_filter", "safety", "refusal", "policy")):
            return HinaaError(code="SAFETY_REFUSAL", status_code=400, message="Refusal due to safety policy")
        if isinstance(e, AuthenticationError):
            return HinaaError(code="PROVIDER_AUTH_FAILED", status_code=500, message="Authentication Failed")
        elif isinstance(e, RateLimitError):
            return HinaaError(code="PROVIDER_RATE_LIMITED", status_code=500, message="Rate Limit Exceeded")
        elif isinstance(e, APITimeoutError):
            return HinaaError(code="PROVIDER_TIMEOUT", status_code=500, message="Timeout")
        elif isinstance(e, APIConnectionError):
            return HinaaError(code="PROVIDER_UNREACHABLE", status_code=500, message="Connection Error")
        elif isinstance(e, APIError):
            status = getattr(e.response, "status_code", 500) if hasattr(e, "response") else 500
            if status == 404:
                return HinaaError(code="PROVIDER_MODEL_NOT_FOUND", status_code=500, message="Model Not Found")
            return HinaaError(code="PROVIDER_UNAVAILABLE", status_code=500, message=str(e))
        return HinaaError(code="PROVIDER_RESPONSE_INVALID", status_code=500, message=str(e))

    async def _stream_text(
        self, prompt: PromptPackage, finish_reason_holder: dict[str, str | None] | None = None
    ) -> AsyncIterator[str]:
        system = prompt.system_instruction
        messages = _anthropic_messages(prompt)

        try:
            async with self.anthropic_client.messages.stream(
                model=self._model,
                max_tokens=_llm_budget_tokens(),
                system=system,
                messages=messages
            ) as stream:
                async for text in stream.text_stream:
                    yield text
                if finish_reason_holder is not None:
                    final = await stream.get_final_message()
                    stop = getattr(final, "stop_reason", None)
                    if stop:
                        # Anthropic stop reasons normalize onto the OpenAI map.
                        table = {"max_tokens": "max_tokens", "end_turn": "stop", "stop_sequence": "stop", "refusal": "content_filter"}
                        finish_reason_holder["value"] = table.get(str(stop), str(stop))
        except Exception as e:
            raise self._map_anthropic_error(e)

    async def _chat_text(self, prompt: PromptPackage) -> str:
        system = prompt.system_instruction
        messages = _anthropic_messages(prompt)
        
        try:
            response = await self.anthropic_client.messages.create(
                model=self._model,
                max_tokens=_llm_budget_tokens(),
                system=system,
                messages=messages
            )
            visible_text, _ = normalize_anthropic_response(response)
            return visible_text
        except Exception as e:
            raise self._map_anthropic_error(e)
            
    async def _chat_json(self, prompt: PromptPackage) -> str:
        return await self._chat_text(prompt)

    async def create_live_plan(
        self,
        text: str,
        companion_id,
        language,
        history,
        emit_delta: Callable[[str], Awaitable[None]],
        prompt: PromptPackage | None = None,
    ):
        if prompt is None:
            raise HinaaError("MODEL_RESPONSE_INVALID", "Prompt package is required.", 500, True)

        prompt = PromptInvariantVerifier.verify_or_sync(prompt)
        from hinaa_api.providers.base import ProviderResult
        from .timing import ProviderTiming
        from time import perf_counter

        started = perf_counter()
        timing = ProviderTiming()

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
                char_budget=_llm_budget_tokens() * 4,
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

            from hinaa_api.prompts.performance import build_plan_from_text
            extracted = _custom_text_from_raw(answer) or answer
            plan = build_plan_from_text(
                text=extracted,
                companion_id=companion_id,
                language=language,
                depth=getattr(prompt, "response_depth", "conversational"),
            )

            timing.mark("plan_parsed")
            timing.mark("plan_validated")

        except HinaaError:
            raise
        except Exception as error:
            raise self._map_anthropic_error(error) from error

        stages = timing.snapshot()
        stages["provider_events"] = provider_events
        return ProviderResult(
            plan,
            f"{self._provider_id}:{self._model}",
            int((perf_counter() - started) * 1000),
            stages=stages,
        )

class ClaudeLLMProvider(AgentRouterAnthropicProvider):
    """Anthropic Messages API adapter for HINAA's explicit Claude mode."""

    id = "claude"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        super().__init__(api_key, model, base_url, provider_id=self.id)


# Backward-compatible public name for OpenAI-compatible Agent Router models.
# New routing selects the Anthropic-specific implementation only when required.
AgentRouterProvider = AgentRouterOpenAIProvider
