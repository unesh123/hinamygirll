"""Tests for Exa API integration (Search, Contents, Agent)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from hinaa_api.tools.exa_tool import (
    ExaClient,
    exa_search_tool,
    exa_get_contents_tool,
    exa_agent_run_tool,
    exa_client,
)
from hinaa_api.tools.registry import registry


def test_exa_tools_registered():
    """Verify all Exa tools are registered in the ToolRegistry."""
    assert "exa_search" in registry._tools
    assert "exa_get_contents" in registry._tools
    assert "exa_agent_run" in registry._tools


@pytest.mark.asyncio
async def test_exa_client_unconfigured():
    """Verify unconfigured client returns error gracefully without throwing."""
    client = ExaClient(api_key="")
    assert not client.is_configured

    search_res = await client.search("test query")
    assert "error" in search_res
    assert search_res["status"] if "status" in search_res else True

    contents_res = await client.get_contents(["https://example.com"])
    assert "error" in contents_res

    agent_res = await client.run_agent("research query")
    assert "error" in agent_res
    assert agent_res["status"] == "failed"


@pytest.mark.asyncio
async def test_exa_agent_run_mocked():
    """Verify Exa Agent run lifecycle with mocked SDK."""
    client = ExaClient(api_key="test-key-123")
    mock_sdk = MagicMock()
    mock_run = MagicMock()
    mock_run.id = "agent_run_mock_123"
    mock_run.status = "queued"

    mock_finished = MagicMock()
    mock_finished.id = "agent_run_mock_123"
    mock_finished.status = "completed"
    mock_finished.output.text = "Comprehensive findings on topic."
    mock_finished.output.structured = {"findings": ["item1", "item2"]}
    mock_finished.output.grounding = [{"url": "https://example.com", "title": "Example"}]
    mock_finished.output.model_dump.return_value = {
        "text": "Comprehensive findings on topic.",
        "structured": {"findings": ["item1", "item2"]},
        "grounding": [{"url": "https://example.com", "title": "Example"}],
    }
    mock_finished.cost_dollars = 0.012

    mock_sdk.agent.runs.create.return_value = mock_run
    mock_sdk.agent.runs.poll_until_finished.return_value = mock_finished
    client._sdk = mock_sdk

    result = await client.run_agent(
        "Investigate topic thoroughly",
        effort="minimal",
        output_schema={"type": "object"},
    )

    assert result["provider"] == "exa-agent"
    assert result["runId"] == "agent_run_mock_123"
    assert result["status"] == "completed"
    assert "Comprehensive findings" in result["text"]
    assert result["structured"] == {"findings": ["item1", "item2"]}
    assert len(result["grounding"]) == 1
    assert result["costDollars"] == 0.012
