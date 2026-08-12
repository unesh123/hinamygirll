import asyncio

from hinaa_api.tools.browser import search_web, web_search_def


def test_web_search_requires_explicit_confirmation() -> None:
    assert web_search_def.requires_confirmation is True


def test_web_search_rejects_empty_query_without_network() -> None:
    result = asyncio.run(search_web({"query": "  "}))
    assert result["error"] == "Query is required"
    assert result["results"] == []
    assert result["sources"] == []
