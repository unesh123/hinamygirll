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


@pytest.mark.asyncio
async def test_xkiro_async_202_polling_and_25_per_day_quota(image_env, tmp_path):
    quota_file = tmp_path / "xkiro_quota.json"
    image_env.setenv("HINAA_XKIRO_IMAGE_QUOTA_FILE", str(quota_file))
    image_env.setenv("OPENAI_IMAGE_API_KEY", "xk-test-key-12345")
    image_env.setenv("OPENAI_IMAGE_BASE_URL", "https://api.xkiro.com/v1")
    image_env.setenv("OPENAI_IMAGE_MODEL", "openai/gpt-image-2.5")

    polls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal polls
        if request.method == "POST" and request.url.path == "/v1/images/generations":
            return httpx.Response(202, json={"id": "img_job_202", "status": "processing"})
        if request.method == "GET" and request.url.path == "/v1/images/generations/img_job_202":
            polls += 1
            return httpx.Response(
                200,
                json={"id": "img_job_202", "status": "succeeded", "data": [{"url": "https://cdn.xkiro.com/out.png"}]},
            )
        if request.method == "GET" and request.url.host == "cdn.xkiro.com":
            return httpx.Response(200, content=b"PNGDATA" * 20)
        return httpx.Response(404)

    original = httpx.AsyncClient
    image_env.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))

    from hinaa_api.providers.openai_image import get_xkiro_image_quota_status
    provider = OpenAIImageProvider(SimpleNamespace(openai_api_key=None, xkiro_daily_image_limit=2))
    res1 = await provider.generate_image("neon cyber shrine")
    assert res1.model == "openai/gpt-image-2.5"
    assert len(res1.image_bytes) == 140
    assert polls == 1
    assert get_xkiro_image_quota_status(limit=2)["used"] == 1

    await provider.generate_image("second image")
    assert get_xkiro_image_quota_status(limit=2)["remaining"] == 0

    with pytest.raises(RuntimeError, match="daily image limit reached"):
        await provider.generate_image("third image exceeds cap")
