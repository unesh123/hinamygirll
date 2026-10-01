"""
Test Suite for Agent-Reach and Social Intelligence Tool.
"""

import pytest
from hinaa_api.tools.registry import registry
from hinaa_api.tools.social_reach import AgentReachEngine, SocialPost


@pytest.mark.asyncio
async def test_agent_reach_registration():
    tool = registry.get_tool("agent_reach")
    assert tool is not None
    assert "query" in tool.required_parameters
    assert tool.risk_level == "low"
    assert tool.requires_confirmation is False


@pytest.mark.asyncio
async def test_agent_reach_engine_github():
    # Test github extraction
    posts = await AgentReachEngine.search_github("hinaa agent harness", limit=2)
    assert isinstance(posts, list)
    # Validate SocialPost schema if any returned
    for p in posts:
        assert isinstance(p, SocialPost)
        assert p.platform == "github"
        assert p.url.startswith("https://")


@pytest.mark.asyncio
async def test_agent_reach_sentiment_synthesis():
    res = await AgentReachEngine.execute_reach(
        query="fast modern artificial intelligence",
        platforms=["github"],
        limit_per_platform=2,
    )
    assert res.query == "fast modern artificial intelligence"
    assert "github" in res.platforms_searched
    assert isinstance(res.sentiment_summary, str)
