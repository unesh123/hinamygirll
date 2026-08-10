import asyncio
import pytest
from unittest.mock import patch, MagicMock
from hinaa_api.config import Settings
from hinaa_api.services import ProviderRouter
from hinaa_api.errors import HinaaError
from hinaa_api.providers.agent_router import AgentRouterProvider
from hinaa_api.providers.openai_llm import OpenAILLMProvider


def test_cx_gateway_uses_configured_base_url():
    """CX gateway uses its own configured URL/key/model, never another provider's."""
    settings = Settings(
        CX_GATEWAY_API_KEY="test_cx_key",
        CX_GATEWAY_BASE_URL="https://cx.example.com",
        CX_GATEWAY_MODEL="cx/gpt-5.6-sol",
        CX_GATEWAY_ALLOWED_MODELS="cx/gpt-5.6-sol",
    )
    router = ProviderRouter(settings)

    provider = router.llm("cx-gateway", "cx/gpt-5.6-sol")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider._key == "test_cx_key"
    assert provider._base_url == "https://cx.example.com/v1"
    assert provider._model == "cx/gpt-5.6-sol"


def test_cx_gateway_prose_fallback_builds_plan():
    """Prose from the CX brain becomes a real turn plan, never the canned fallback.

    gpt-5.6-sol answers in plain text even when asked for JSON; the text itself
    must be promoted into a valid AssistantTurnPlan so live/rest turns respond
    with her actual words instead of the "technical glitch" canned reply.
    """
    from hinaa_api.prompts.models import (
        MoodSnapshot,
        PersonalitySettings,
        PromptPackage,
    )

    provider = OpenAILLMProvider(
        "key",
        "cx/gpt-5.6-sol",
        base_url="https://cx.example.com/v1",
        provider_id="cx-gateway",
    )
    prompt = PromptPackage(
        companion_id="hinaa",
        interaction_mode="rest",
        system_instruction="identity",
        user_contents="user text",
        layers=[],
        prompt_version="test",
        safety_policy_version="test",
        companion_profile_version="test",
        fingerprint="test",
        response_depth="conversational",
        language="mixed",
        personality=PersonalitySettings(),
        mood=MoodSnapshot(),
    )

    async def fake_chat_json(_prompt):
        return "मेरो हजुर! I missed you so much today. 🥰"

    provider._chat_json = fake_chat_json  # type: ignore[method-assign]

    result = asyncio.run(
        provider.create_plan("I'm back!", "hinaa", "mixed", (), prompt)
    )
    assert result.value.displayText == "मेरो हजुर! I missed you so much today. 🥰"
    assert not result.provider.startswith("fallback:")


def test_cx_gateway_prose_fallback_handles_json_strings():
    """If the CX brain does return JSON, the wrapped text fields are extracted."""
    from hinaa_api.prompts.models import (
        MoodSnapshot,
        PersonalitySettings,
        PromptPackage,
    )

    provider = OpenAILLMProvider(
        "key",
        "cx/gpt-5.6-sol",
        base_url="https://cx.example.com/v1",
        provider_id="cx-gateway",
    )
    prompt = PromptPackage(
        companion_id="hinaa",
        interaction_mode="rest",
        system_instruction="identity",
        user_contents="user text",
        layers=[],
        prompt_version="test",
        safety_policy_version="test",
        companion_profile_version="test",
        fingerprint="test",
        response_depth="conversational",
        language="mixed",
        personality=PersonalitySettings(),
        mood=MoodSnapshot(),
    )

    async def fake_chat_json(_prompt):
        return '{"displayText": "आज तिम्रो दिन कस्तो रह्यो, हजुर?", "spokenText": "आज तिम्रो दिन कस्तो रह्यो?"}'

    provider._chat_json = fake_chat_json  # type: ignore[method-assign]

    result = asyncio.run(
        provider.create_plan("How was your day?", "hinaa", "mixed", (), prompt)
    )
    assert result.value.displayText == "आज तिम्रो दिन कस्तो रह्यो, हजुर?"

def test_agent_router_uses_configured_base_url():
    """Test that agent-router explicitly uses the configured environment URL and never receives custom URL."""
    settings = Settings(
        AGENT_ROUTER_API_KEY="test_agent_key",
        AGENT_ROUTER_BASE_URL="https://api.agentrouter.com/v1",
        AGENT_ROUTER_ALLOWED_MODELS="gpt-5.6-sol"
    )
    router = ProviderRouter(settings)
    
    provider = router.llm("agent-router", "gpt-5.6-sol")
    assert isinstance(provider, AgentRouterProvider)
    assert provider._key == "test_agent_key"
    assert provider._base_url == "https://api.agentrouter.com/v1"
    assert provider._model == "gpt-5.6-sol"

def test_custom_gateway_uses_configured_base_url():
    """Test that custom gateway uses its own configured URL and key, not agent router's."""
    settings = Settings(
        OPENAI_CODEX_API_KEY="test_custom_key",
        OPENAI_CODEX_BASE_URL="https://my.tunnel.com",
        AGENT_ROUTER_API_KEY="test_agent_key",
        AGENT_ROUTER_BASE_URL="https://api.agentrouter.com/v1"
    )
    router = ProviderRouter(settings)
    
    provider = router.llm("custom")
    assert isinstance(provider, OpenAILLMProvider)
    assert provider._key == "test_custom_key"
    assert provider._base_url == "https://my.tunnel.com/v1"

def test_agent_router_rejects_unapproved_model():
    """Test that agent-router rejects models not in the allowlist."""
    settings = Settings(
        AGENT_ROUTER_API_KEY="test_agent_key",
        AGENT_ROUTER_BASE_URL="https://api.agentrouter.com/v1",
        AGENT_ROUTER_ALLOWED_MODELS="gpt-5.6-sol"
    )
    router = ProviderRouter(settings)
    
    with pytest.raises(HinaaError) as exc_info:
        router.llm("agent-router", "hacker-model-X")
    
    assert exc_info.value.code == "AGENT_ROUTER_MODEL_NOT_ALLOWED"
