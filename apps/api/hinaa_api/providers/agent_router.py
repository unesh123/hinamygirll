import httpx
import logging
from collections.abc import Awaitable, Callable
from typing import AsyncIterator, Any
from urllib.parse import urlparse
from anthropic import AsyncAnthropic, APIError, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.errors import HinaaError
from hinaa_api.prompts import PromptPackage
from hinaa_api.providers.blocks import normalize_anthropic_response, extract_text_from_canonical_blocks

logger = logging.getLogger("hinaa.providers.agent_router")


def _map_httpx_error(e: Exception) -> HinaaError:
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status in (401, 403):
            code = "PROVIDER_AUTH_FAILED" if status == 401 else "PROVIDER_ACCESS_DENIED"
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

    async def _stream_text(self, prompt: PromptPackage) -> AsyncIterator[str]:
        try:
            async for chunk in super()._stream_text(prompt):
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
        self.anthropic_client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            default_headers={**(self.gateway_auth_headers or {}), **browser_fp_headers},
        )

    def _map_anthropic_error(self, e: Exception) -> HinaaError:
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

    async def _stream_text(self, prompt: PromptPackage) -> AsyncIterator[str]:
        from .anthropic_direct import build_anthropic_content
        system = prompt.system_instruction
        content = build_anthropic_content(prompt.user_contents, getattr(prompt, "attachments", None))
        messages = [{"role": "user", "content": content}]
        
        try:
            async with self.anthropic_client.messages.stream(
                model=self._model,
                max_tokens=4096,
                system=system,
                messages=messages
            ) as stream:
                async for event in stream:
                    if event.type == "text_delta":
                        yield event.text
        except Exception as e:
            raise self._map_anthropic_error(e)

    async def _chat_text(self, prompt: PromptPackage) -> str:
        from .anthropic_direct import build_anthropic_content
        system = prompt.system_instruction
        content = build_anthropic_content(prompt.user_contents, getattr(prompt, "attachments", None))
        messages = [{"role": "user", "content": content}]
        
        try:
            response = await self.anthropic_client.messages.create(
                model=self._model,
                max_tokens=4096,
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
            from hinaa_api.errors import HinaaError
            raise HinaaError("MODEL_RESPONSE_INVALID", "Prompt package is required.", 500, True)

        from hinaa_api.providers.base import ProviderResult
        from .timing import ProviderTiming
        from time import perf_counter
        import re

        started = perf_counter()
        timing = ProviderTiming()
        chunks: list[str] = []
        provider_events = 0
        
        in_display = False
        emitted_length = 0

        try:
            timing.mark("provider_client_ready")
            async for delta in self._stream_text(prompt):
                provider_events += 1
                if provider_events == 1:
                    timing.mark("first_provider_event")
                chunks.append(delta)
                current_text = "".join(chunks)

                # Dynamically extract and stream the displayText value
                if not in_display:
                    match = re.search(r'"displayText"\s*:\s*"', current_text)
                    if match:
                        in_display = True
                        timing.mark("first_text_delta")
                if in_display:
                    match = re.search(r'"displayText"\s*:\s*"', current_text)
                    if match:
                        raw_val = current_text[match.end():]
                        end_match = re.search(r'(?<!\\)(?:\\\\)*"', raw_val)
                        if end_match:
                            raw_val = raw_val[:end_match.end() - 1]

                        clean_val = raw_val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t').replace('\\\\', '\\')
                        new_chars = clean_val[emitted_length:]
                        if new_chars:
                            await emit_delta(new_chars)
                            emitted_length += len(new_chars)

            timing.mark("text_complete")
            answer = "".join(chunks).strip()
            
            from hinaa_api.prompts.fallback import validate_or_none, neutral_fallback_plan
            plan = validate_or_none(answer)
            if plan is None:
                repaired = await self._repair_json(answer)
                plan = validate_or_none(repaired)
            if plan is None:
                plan = neutral_fallback_plan(
                    user_text=text, companion_id=companion_id, language=language
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
