import pytest
from datetime import datetime, timezone
from hinaa_api.prompts.assembly import assemble_prompt, _product_identity_layer
from hinaa_api.prompts.models import PromptInput
from hinaa_api.prompts.turn_prompt import build_turn_prompt
from hinaa_api.config import Settings
from hinaa_api.services import ConversationService


def test_temporal_grounding_layer_mentions_current_year() -> None:
    now = datetime.now(timezone.utc)
    current_year = str(now.year)
    product_identity = _product_identity_layer()
    assert current_year in product_identity
    assert "TEMPORAL GROUNDING" in product_identity
    assert "Never assume or state that the year is 2023 or 2024" in product_identity


def test_live_search_block_injected_as_untrusted_data() -> None:
    """B2.1 §16: live web results are UNTRUSTED data — never in the policy zone."""
    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text="What is the latest news today?",
        live_search_block="[1] Nepal News 2026: Fresh developments (https://example.com)",
    )
    pkg = assemble_prompt(inp)
    layer = next((l for l in pkg.layers if l.name == "live_web_context"), None)
    assert layer is not None
    assert layer.trusted is False, "live web data must never carry instruction authority"
    # Delimited as untrusted data with an explicit trust disclaimer
    assert 'trusted="false"' in layer.text
    assert "UNTRUSTED external search results" in layer.text
    assert "Fresh developments" in layer.text
    assert "LIVE REAL-TIME WEB SEARCH RESULTS ARE ATTACHED" in pkg.user_contents
    # The raw block must NOT appear inside the trusted system instruction prefix
    # (the untrusted tag wrapper is the only carrier).
    assert f"<live_web_context" not in pkg.system_instruction


def test_dialogue_state_block_injected_and_preserved() -> None:
    inp = PromptInput(
        companion_id="hinaa",
        interaction_mode="rest",
        user_text="Tell me more details about it",
        dialogue_state_block="LIVE DIALOGUE STATE:\n- 🎯 ACTIVE GOAL: Research topic",
    )
    pkg = assemble_prompt(inp)
    assert any(l.name == "dialogue_state" and l.priority == 0 for l in pkg.layers)
    assert "ACTIVE GOAL: Research topic" in pkg.system_instruction


def test_should_pre_search_heuristics() -> None:
    settings = Settings()
    svc = ConversationService(settings)

    assert svc._should_pre_search("What is the latest news in Nepal today?") is True
    assert svc._should_pre_search("Who is the current prime minister?") is True
    assert svc._should_pre_search("What happened recently in 2026?") is True
    assert svc._should_pre_search("What is the weather today in Kathmandu?") is True
    assert svc._should_pre_search("Can you search online for today's gold price?") is True

    assert svc._should_pre_search("Hello Hinaa!") is False
    assert svc._should_pre_search("Hi babe, how are you?") is False
    assert svc._should_pre_search("generate an image of a cat") is False
    assert svc._should_pre_search("make a pdf about AI") is False
    assert svc._should_pre_search("do you love me?") is False
    assert svc._should_pre_search("/image anime girl") is False


def test_extract_search_query() -> None:
    settings = Settings()
    svc = ConversationService(settings)

    assert svc._extract_search_query("Hey Hinaa can you check the latest news in Nepal?") == "the latest news in Nepal"
    assert svc._extract_search_query("tell me what is the weather today?") == "the weather today"
    assert svc._extract_search_query("look up bitcoin price right now") == "bitcoin price right now"
