"""Tests for Exa API integration and Coding Agent retrieval (build-with-exa).

Verifies:
1. Tool registration in ToolRegistry (exa_search, exa_get_contents).
2. Adherence to canonical request shapes (type='auto', highlights=True).
3. SDK call wrapping and non-blocking execution.
4. Top-level content extraction on /contents.
5. Integration with CodingAgentLoop documentation search.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hinaa_api.tools.registry import registry
from hinaa_api.tools.exa_tool import (
    ExaClient,
    exa_search_tool,
    exa_get_contents_tool,
)
from hinaa_api.agent.coding_agent import CodingAgentLoop


def test_exa_tools_registered_in_registry():
    """Verify exa_search and exa_get_contents are registered in ToolRegistry."""
    search_def = registry.get_tool("exa_search")
    assert search_def is not None
    assert search_def.name == "exa_search"
    assert "query" in search_def.required_parameters

    contents_def = registry.get_tool("exa_get_contents")
    assert contents_def is not None
    assert contents_def.name == "exa_get_contents"
    assert "urls" in contents_def.required_parameters


@pytest.mark.asyncio
async def test_exa_client_unconfigured_returns_safe_error():
    """When EXA_API_KEY is unset, client returns a safe error dictionary without crashing."""
    client = ExaClient(api_key="")
    assert client.is_configured is False

    res = await client.search("python fast api testing")
    assert res.get("error") == "EXA_API_KEY is not configured"
    assert res.get("results") == []

    c_res = await client.get_contents(["https://docs.exa.ai"])
    assert c_res.get("error") == "EXA_API_KEY is not configured"


@pytest.mark.asyncio
async def test_exa_search_formats_sdk_results_correctly():
    """Verify exa-py SDK results are formatted into standard source cards."""
    client = ExaClient(api_key="test-exa-key")

    mock_result_item = MagicMock()
    mock_result_item.url = "https://fastapi.tiangolo.com/tutorial/"
    mock_result_item.title = "FastAPI Tutorial - User Guide"
    mock_result_item.author = "Sebastián Ramírez"
    mock_result_item.published_date = "2026-01-15"
    mock_result_item.highlights = ["FastAPI is a modern, fast web framework for building APIs with Python."]
    mock_result_item.text = None

    mock_sdk_response = MagicMock()
    mock_sdk_response.results = [mock_result_item]

    with patch.object(client, "_sdk") as mock_sdk:
        mock_sdk.search.return_value = mock_sdk_response

        res = await client.search("FastAPI tutorial", search_type="auto", num_results=5)
        assert res["provider"] == "exa"
        assert res["mode"] == "search"
        assert res["sourceCount"] == 1
        assert res["sources"][0]["id"] == "S1"
        assert res["sources"][0]["title"] == "FastAPI Tutorial - User Guide"
        assert res["sources"][0]["domain"] == "fastapi.tiangolo.com"
        assert "FastAPI is a modern" in res["sources"][0]["snippet"]

        # Verify SDK was called with canonical snake_case kwargs per build-with-exa spec
        mock_sdk.search.assert_called_once()
        call_args, call_kwargs = mock_sdk.search.call_args
        assert call_args[0] == "FastAPI tutorial"
        assert call_kwargs["type"] == "auto"
        assert call_kwargs["num_results"] == 5
        assert call_kwargs["contents"] == {"highlights": True}


@pytest.mark.asyncio
async def test_exa_get_contents_calls_sdk_correctly():
    """Verify get_contents passes top-level text/highlights per canonical spec."""
    client = ExaClient(api_key="test-exa-key")

    mock_item = MagicMock()
    mock_item.url = "https://docs.pydantic.dev"
    mock_item.title = "Pydantic Documentation"
    mock_item.text = "Data validation using Python type hints."
    mock_item.highlights = []

    mock_sdk_response = MagicMock()
    mock_sdk_response.results = [mock_item]

    with patch.object(client, "_sdk") as mock_sdk:
        mock_sdk.get_contents.return_value = mock_sdk_response

        res = await client.get_contents(["https://docs.pydantic.dev"], text=True)
        assert res["provider"] == "exa"
        assert len(res["results"]) == 1
        assert res["results"][0]["url"] == "https://docs.pydantic.dev"
        assert res["results"][0]["text"] == "Data validation using Python type hints."

        mock_sdk.get_contents.assert_called_once_with(
            ["https://docs.pydantic.dev"],
            text=True,
            highlights=False,
        )


@pytest.mark.asyncio
async def test_coding_agent_loop_exa_integration():
    """Verify CodingAgentLoop.search_documentation queries Exa when configured."""
    sandbox = MagicMock()
    loop = CodingAgentLoop(workspace_root=".", sandbox=sandbox)

    with patch("hinaa_api.config.get_settings") as mock_settings, \
         patch("hinaa_api.tools.exa_tool.exa_client.search", new_callable=AsyncMock) as mock_search:

        mock_s = MagicMock()
        mock_s.exa_configured = True
        mock_settings.return_value = mock_s

        mock_search.return_value = {
            "provider": "exa",
            "sources": [{"title": "pytest mock guide", "url": "https://pytest.org"}],
            "sourceCount": 1,
        }

        res = await loop.search_documentation("how to mock async generators in pytest", num_results=3)
        assert res["provider"] == "exa"
        assert res["sourceCount"] == 1
        mock_search.assert_called_once_with(
            "how to mock async generators in pytest",
            search_type="auto",
            num_results=3,
            highlights=True,
        )
