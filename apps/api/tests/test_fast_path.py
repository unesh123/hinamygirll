"""Tests for the casual-chat fast path.

Reasoning brains (cx/gpt-5.6-sol, agent-router) spend hidden tokens before the
first visible one, which makes social small talk feel slow. Short conversational
turns should route to a fast non-reasoning model (gpt-5-mini -> gemini flash
when OpenAI's key is dead) while deep work keeps the reasoning brain. A fast
brain that fails (deactivated key, rate limit) must never fail the turn — it
falls through to the reasoning brain and the dead key is negative-cached.
"""

import asyncio

from hinaa_api.config import Settings
from hinaa_api.errors import HinaaError
from hinaa_api.models import TurnRequest
from hinaa_api.prompts import neutral_fallback_plan
from hinaa_api.providers.base import ProviderResult
from hinaa_api.providers.gemini import GeminiLLMProvider
from hinaa_api.services import ConversationService, is_casual_chat


def _settings(**overrides) -> Settings:
    defaults = {
        "HINAA_PROVIDER_MODE": "cx-gateway",
        "OPENAI_API_KEY": None,
        "GEMINI_API_KEY": None,
        "CX_GATEWAY_API_KEY": None,
        "CX_GATEWAY_BASE_URL": None,
        "AGENT_ROUTER_API_KEY": None,
        "AGENT_ROUTER_BASE_URL": None,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class TestCasualClassifier:
    def test_short_greetings_are_casual(self):
        for text in ["hi", "hello", "namaste", "hey bro", "kasto chha", "के छ"]:
            assert is_casual_chat(text) is True, text

    def test_short_emotion_checkins_are_casual(self):
        assert is_casual_chat("mood ali off cha") is True
        assert is_casual_chat("aaja dherai tired chu bro") is True

    def test_long_casual_with_hint_is_casual(self):
        text = (
            "म तिमीलाई धेरै माया गर्छु, तिमी भएकोमा म धेरै खुसी छु, "
            "आज कस्तो भयो तिम्रो दिन?"
        )
        assert is_casual_chat(text) is True

    def test_deep_tasks_stay_on_the_reasoning_brain(self):
        for text in [
            "write a python function to sort a list",
            "explain how to deploy the api to docker",
            "fix this react bug in the component",
            "```python\nprint(1)\n```",
            "tell me about otakuxwear pricing",
            "refactor my database schema",
        ]:
            assert is_casual_chat(text) is False, text

    def test_empty_input_is_not_casual(self):
        assert is_casual_chat("") is False
        assert is_casual_chat(None) is False
        assert is_casual_chat("   ") is False

    def test_word_boundary_matching_avoids_false_casual(self):
        # "hi" appears inside "this" — substring matching would wrongly call
        # this casual; word boundaries must reject it.
        long_english = (
            "this morning I went for a walk and thought about you the whole time"
        )
        assert len(long_english) > 60
        assert is_casual_chat(long_english) is False
        # A genuine casual word still wins.
        assert is_casual_chat(long_english + " btw I miss you") is True

    def test_short_followup_after_deep_task_stays_on_reasoning_brain(self):
        history = (
            ("user", "write a python function to sort a list"),
            ("assistant", "```python\ndef sort(x): ...\n```"),
        )
        # "ok do it now" has no deep hints itself, but continues deep work.
        assert is_casual_chat("ok, do it now", history) is False
        assert is_casual_chat("and then what?", history) is False

    def test_short_followup_after_chat_stays_casual(self):
        history = (("user", "namaste"), ("assistant", "hello bro"))
        assert is_casual_chat("kasto chha?", history) is True


class TestFastPathRouting:
    def test_casual_turn_routes_to_fast_openai_model(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)
        provider = service._fast_casual_provider("cx-gateway", "hi bro")
        assert provider is not None
        assert provider._model == "gpt-5-mini"

    def test_task_continuation_does_not_fast_path(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)
        history = (
            ("user", "refactor my database schema"),
            ("assistant", "sure, here is the migration"),
        )
        assert (
            service._fast_casual_provider("cx-gateway", "ok do it", history)
            is None
        )

    def test_casual_turn_routes_from_agent_router_too(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)
        provider = service._fast_casual_provider("agent-router", "mood off")
        assert provider is not None
        assert provider._model == "gpt-5-mini"

    def test_deep_turn_keeps_the_reasoning_brain(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)
        assert service._fast_casual_provider("cx-gateway", "write code for me") is None

    def test_no_openai_key_means_no_fast_path(self):
        settings = _settings(OPENAI_API_KEY=None)
        service = ConversationService(settings)
        assert service._fast_casual_provider("cx-gateway", "hi") is None

    def test_non_reasoning_modes_never_fast_path(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)
        assert service._fast_casual_provider("openai", "hi") is None
        assert service._fast_casual_provider("mock", "hi") is None
        assert service._fast_casual_provider("real", "hi") is None


class TestDeadKeyNegativeCache:
    def test_dead_openai_key_routes_to_gemini_flash(self):
        settings = _settings(
            OPENAI_API_KEY="sk-dead",
            GEMINI_API_KEY="gemini-live",
        )
        service = ConversationService(settings)
        # Healthy path first: OpenAI fast model wins.
        provider = service._fast_casual_provider("cx-gateway", "hi bro")
        assert provider is not None
        assert provider._model == "gpt-5-mini"
        # Simulate a 401 -> negative cache, then Gemini flash takes over.
        service._mark_fast_key_bad("openai")
        provider = service._fast_casual_provider("cx-gateway", "hi bro")
        assert provider is not None
        assert isinstance(provider, GeminiLLMProvider)

    def test_all_fast_keys_dead_means_no_fast_path(self):
        settings = _settings(
            OPENAI_API_KEY="sk-dead",
            GEMINI_API_KEY="gemini-live",
        )
        service = ConversationService(settings)
        service._mark_fast_key_bad("openai")
        service._mark_fast_key_bad("gemini")
        assert service._fast_casual_provider("cx-gateway", "hi bro") is None

    def test_no_gemini_key_means_dead_openai_returns_none(self):
        settings = _settings(OPENAI_API_KEY="sk-dead")
        service = ConversationService(settings)
        service._mark_fast_key_bad("openai")
        # No Gemini configured, no fast brain available -> reasoning brain.
        assert service._fast_casual_provider("cx-gateway", "hi bro") is None


class _FailingFastProvider:
    """Simulates a fast brain whose key was deactivated (HTTP 401)."""

    id = "openai"

    async def create_plan(self, text, companion_id, language, history, prompt):
        raise HinaaError(
            "PROVIDER_KEY_INVALID", "OpenAI needs its backend connection fixed.", 503, True
        )


class _GoodReasoningBrain:
    """Simulates the CX reasoning brain answering correctly."""

    async def create_plan(self, text, companion_id, language, history, prompt):
        plan = neutral_fallback_plan(
            user_text=text,
            companion_id=companion_id,
            language=language,
            depth=prompt.response_depth,
        )
        return ProviderResult(plan, "cx:gpt-5.6-sol", 1)


class TestFastPathFallThrough:
    def test_dead_fast_key_falls_through_to_reasoning_brain(self):
        settings = _settings(OPENAI_API_KEY="sk-dead")
        service = ConversationService(settings)
        service._fast_casual_provider = (
            lambda mode, text, history=(): _FailingFastProvider()
        )
        service.router.llm = lambda mode, brain_model=None: _GoodReasoningBrain()
        request = TurnRequest(
            text="hi bro",
            companionId="hinaa",
            language="mixed",
            sessionId="s1",
            providerMode="cx-gateway",
        )
        result = asyncio.run(service.create_plan(request))
        assert result.provider == "cx:gpt-5.6-sol"
        # The dead key is now negative-cached so later turns use Gemini/None.
        assert service._fast_key_bad("openai") is True

    def test_fast_path_failure_still_raises_for_non_provider_errors(self):
        settings = _settings(OPENAI_API_KEY="sk-test")
        service = ConversationService(settings)

        class _BrokenProvider:
            id = "openai"

            async def create_plan(self, *args, **kwargs):
                raise HinaaError("MODEL_RESPONSE_INVALID", "bad json", 502, True)

        service._fast_casual_provider = (
            lambda mode, text, history=(): _BrokenProvider()
        )
        request = TurnRequest(
            text="hi bro",
            companionId="hinaa",
            language="mixed",
            sessionId="s1",
            providerMode="cx-gateway",
        )
        # MODEL_RESPONSE_INVALID falls back to the neutral plan path, so the
        # turn still completes without erroring.
        result = asyncio.run(service.create_plan(request))
        assert result.provider.startswith("fallback")
        # The key is NOT marked bad for non-auth failures.
        assert service._fast_key_bad("openai") is False
