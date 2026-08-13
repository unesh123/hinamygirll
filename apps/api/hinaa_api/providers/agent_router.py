import httpx
from typing import AsyncIterator
from anthropic import AsyncAnthropic, APIError, APIConnectionError, APITimeoutError, RateLimitError, AuthenticationError
from hinaa_api.providers.openai_llm import OpenAILLMProvider
from hinaa_api.errors import HinaaError
from hinaa_api.prompts import PromptPackage

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
        super().__init__(key=api_key, model=model, base_url=base_url, provider_id=provider_id)
        self.anthropic_client = AsyncAnthropic(
            api_key=api_key,
            base_url=base_url.rstrip("/"),
            default_headers={"x-api-key": api_key}
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
        system = prompt.system_instruction
        messages = [{"role": "user", "content": "\n\n".join(str(item) for item in prompt.user_contents)}]
        
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
        system = prompt.system_instruction
        messages = [{"role": "user", "content": "\n\n".join(str(item) for item in prompt.user_contents)}]
        
        try:
            response = await self.anthropic_client.messages.create(
                model=self._model,
                max_tokens=4096,
                system=system,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            raise self._map_anthropic_error(e)
            
    async def _chat_json(self, prompt: PromptPackage) -> str:
        return await self._chat_text(prompt)

class ClaudeLLMProvider(AgentRouterAnthropicProvider):
    """Anthropic Messages API adapter for HINAA's explicit Claude mode."""

    id = "claude"

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        super().__init__(api_key, model, base_url, provider_id=self.id)


# Backward-compatible public name for OpenAI-compatible Agent Router models.
# New routing selects the Anthropic-specific implementation only when required.
AgentRouterProvider = AgentRouterOpenAIProvider
