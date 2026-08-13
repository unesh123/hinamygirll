from __future__ import annotations

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from hinaa_api.config import Settings
from hinaa_api.main import create_app
from hinaa_api.providers.youcom import YouComClient, YouComError
from hinaa_api.tools.browser import (
    finance_research_def,
    image_search_def,
    web_answer_def,
    web_extract_def,
    web_research_def,
    web_research_status_def,
    web_search_def,
)


def _youcom_settings() -> Settings:
    return Settings(
        HINAA_PROVIDER_MODE="mock",
        YDC_API_KEY="local-test-key",
        HINAA_DATABASE_URL="sqlite+pysqlite:///:memory:",
        HINAA_AUTH_MODE="dev",
        HINAA_PERSISTENCE_ENABLED=True,
        _env_file=None,
    )


def test_youcom_search_normalizes_highlights_and_keeps_key_out_of_result() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["header"] = request.headers.get("X-API-Key")
        observed["body"] = request.json() if hasattr(request, "json") else request.content
        return httpx.Response(
            200,
            json={
                "results": {
                    "web": [
                        {
                            "url": "https://example.com/article",
                            "title": "Example article",
                            "contents": {"highlights": ["The relevant current passage."]},
                        }
                    ],
                    "news": [
                        {"url": "https://news.example.com/item", "title": "Example news", "snippets": ["Fresh news."]}
                    ],
                }
            },
        )

    client = YouComClient(_youcom_settings(), transport=httpx.MockTransport(handler))
    result = asyncio.run(client.search("current example", count=5))

    assert observed["url"] == "https://api.you.com/v1/search"
    assert observed["header"] == "local-test-key"
    assert result["provider"] == "you.com"
    assert result["sourceCount"] == 2
    assert result["sources"][0]["snippet"] == "The relevant current passage."
    assert "local-test-key" not in str(result)


def test_youcom_answer_preserves_citations_as_source_cards() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "answer": "A grounded answer [[1]].",
                "citations": [
                    {"source": "https://source.example.com", "excerpts": ["Verbatim supporting passage."]}
                ],
            },
        )

    client = YouComClient(_youcom_settings(), transport=httpx.MockTransport(handler))
    result = asyncio.run(client.answer("give a grounded answer"))

    assert result["content"] == "A grounded answer [[1]]."
    assert result["sources"] == [
        {
            "id": "Y1",
            "title": "https://source.example.com",
            "url": "https://source.example.com",
            "snippet": "Verbatim supporting passage.",
            "publishedDate": None,
            "kind": "citation",
        }
    ]


def test_youcom_image_search_normalizes_bounded_public_cards() -> None:
    observed: dict[str, str] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "images": {
                    "results": [
                        {"title": "HINAA reference", "page_url": "https://images.example.com/page", "image_url": "https://cdn.example.com/hinaa.png"},
                        {"title": "Unsafe result", "page_url": "http://127.0.0.1/private", "image_url": "http://127.0.0.1/private.png"},
                    ]
                }
            },
        )

    client = YouComClient(_youcom_settings(), transport=httpx.MockTransport(handler))
    result = asyncio.run(client.image_search("HINAA companion", count=6))

    assert observed["url"] == "https://api.you.com/v1/images?q=HINAA+companion"
    assert result["mode"] == "image-search-beta"
    assert result["imageCount"] == 1
    assert result["images"][0]["imageUrl"] == "https://cdn.example.com/hinaa.png"
    assert result["images"][0]["pageUrl"] == "https://images.example.com/page"


def test_youcom_image_search_explains_beta_access_denial() -> None:
    client = YouComClient(_youcom_settings(), transport=httpx.MockTransport(lambda _: httpx.Response(403, json={"message": "Forbidden"})))

    with pytest.raises(YouComError) as error:
        asyncio.run(client.image_search("HINAA companion"))

    assert error.value.code == "YOUCOM_IMAGE_ACCESS_REQUIRED"
    assert "early-access" in str(error.value)


def test_youcom_contents_rejects_private_urls_without_network() -> None:
    client = YouComClient(_youcom_settings(), transport=httpx.MockTransport(lambda _: pytest.fail("network must not run")))

    with pytest.raises(YouComError, match="public HTTP"):
        asyncio.run(client.contents(["http://127.0.0.1:8000/private"]))


def test_youcom_provider_status_reports_configured_capabilities_without_calling_remote() -> None:
    with TestClient(create_app(_youcom_settings())) as client:
        response = client.get("/v1/providers")
    assert response.status_code == 200
    youcom = next(item for item in response.json() if item["id"] == "youcom")
    assert youcom["state"] == "healthy"
    assert "web-search" in youcom["capabilities"]
    assert "cited-research" in youcom["capabilities"]
    assert "YDC_API_KEY" not in youcom["userMessage"]


def test_youcom_tools_remain_confirmation_gated() -> None:
    for tool in [web_search_def, image_search_def, web_answer_def, web_research_def, web_research_status_def, web_extract_def, finance_research_def]:
        assert tool.requires_confirmation is True
    assert finance_research_def.permission_level == "high"
