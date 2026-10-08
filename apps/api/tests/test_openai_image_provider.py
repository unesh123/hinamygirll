import base64
import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr
from hinaa_api.providers.openai_image import OpenAIImageProvider

@pytest.fixture
def image_env(monkeypatch):
    for name in ["OPENAI_IMAGE_API_KEY", "IMAGE_PROXY_API_KEY", "OPENAI_API_KEY", "OPENAI_IMAGE_BASE_URL", "IMAGE_PROXY_BASE_URL", "OPENAI_BASE_URL", "OPENAI_IMAGE_MODEL", "IMAGE_MODEL"]:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_chat_proxy_credential_does_not_imply_image_support(image_env):
    provider = OpenAIImageProvider(SimpleNamespace(openai_api_key=None, active_openai_key=SecretStr("chat-only-key"), openai_codex_base_url="https://chat.example/v1"))
    assert not provider.available()


def test_custom_image_proxy_requires_explicit_model(image_env):
    image_env.setenv("OPENAI_IMAGE_API_KEY", "image-test-key")
    image_env.setenv("OPENAI_IMAGE_BASE_URL", "https://images.example/v1")
    provider = OpenAIImageProvider(SimpleNamespace(openai_api_key=None))
    assert not provider.available()
    image_env.setenv("OPENAI_IMAGE_MODEL", "vendor-image-model")
    assert OpenAIImageProvider(SimpleNamespace(openai_api_key=None)).available()


@pytest.mark.asyncio
async def test_gpt_image_contract_uses_supported_output_format_and_aspect(image_env):
    seen = []
    encoded = base64.b64encode(b"test-image-bytes").decode()
    def handler(request):
        seen.append(json.loads(request.content))
        assert request.url.path == "/v1/images/generations"
        return httpx.Response(200, json={"data": [{"b64_json": encoded}]})
    original = httpx.AsyncClient
    image_env.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    provider = OpenAIImageProvider(SimpleNamespace(openai_api_key=SecretStr("image-test-key")))
    result = await provider.generate_image("blue cup", width=1536, height=1024, seed=10)
    assert result.image_bytes == b"test-image-bytes"
    assert seen[0]["size"] == "1536x1024"
    assert seen[0]["output_format"] == "png"
    assert "response_format" not in seen[0]
    assert "seed" not in seen[0]
