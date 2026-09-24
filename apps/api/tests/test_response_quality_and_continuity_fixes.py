import pytest
from unittest.mock import MagicMock
from hinaa_api.models import TurnRequest, AssistantTurnPlan, Emotion, Performance
from hinaa_api.config import Settings
from hinaa_api.services import ProviderRouter, ConversationService
from hinaa_api.dialogue_state import (
    ConversationTurnState,
    DialogueActResolver,
    DialogueAct,
    SlotResolver,
    EntityReferenceResolver,
    ImageRequestCompiler,
    SocialPhraseController,
    DialogueStateService,
    SlotType,
)


def test_turn_request_ignores_extra_fields():
    payload = {
        "sessionId": "sess_123",
        "text": "Hello Hina",
        "providerMode": "codecraft",
        "clientTimestamp": 1726240000,
        "arbitraryMetadata": {"foo": "bar"},
    }
    req = TurnRequest.model_validate(payload)
    assert req.sessionId == "sess_123"
    assert req.providerMode == "codecraft"


def test_image_search_not_hijacked_for_informational_queries():
    settings = Settings(
        gemini_api_key="test_key",
        serpapi_api_key="test_serp",
    )
    service = ConversationService(settings=settings)

    test_queries = [
        "tell me about naruto",
        "can you remembernaruto",
        "wtf i didnt ask for pictures i asked about description about naruto",
        "who is gojo satoru",
        "explain luffy's gear 5",
        "what is one piece about",
    ]

    for q in test_queries:
        plan = AssistantTurnPlan(
            spokenText="Here is the detailed explanation...",
            displayText="Here is the detailed explanation...",
            language="en-US",
            emotion=Emotion(primary="neutral", intensity=0.5, valence=0.5, arousal=0.5),
            performance=Performance(facePreset="neutral", gesture="none", gazeTarget="camera", headMotion="none", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        service._inject_deterministic_tool_intents(q, plan, session_id="test_sess")
        assert not any(t.toolName == "image_search" for t in plan.toolRequests), (
            f"Query {q!r} wrongly hijacked into image_search!"
        )


def test_image_search_triggers_for_explicit_image_queries():
    settings = Settings(
        gemini_api_key="test_key",
        serpapi_api_key="test_serp",
    )
    service = ConversationService(settings=settings)

    explicit_queries = [
        "show me naruto pictures",
        "find gojo wallpapers",
        "luffy images on pinterest",
    ]

    for q in explicit_queries:
        plan = AssistantTurnPlan(
            spokenText="Sure!",
            displayText="Sure!",
            language="en-US",
            emotion=Emotion(primary="happy", intensity=0.7, valence=0.7, arousal=0.5),
            performance=Performance(facePreset="soft_smile", gesture="none", gazeTarget="camera", headMotion="none", blinkRate=0.5),
            beats=[],
            memoryCandidates=[],
            toolRequests=[],
        )
        service._inject_deterministic_tool_intents(q, plan, session_id="test_sess")
        assert any(t.toolName == "image_search" for t in plan.toolRequests), (
            f"Query {q!r} should have triggered image_search!"
        )


def test_provider_router_falls_back_gracefully_on_invalid_model():
    from hinaa_api.errors import HinaaError

    settings = Settings(
        openai_api_key="test_key",
        openai_model="gpt-4o",
        custom_api_key="test_key",
        custom_base_url="https://custom.example/v1",
        custom_model="custom-default",
        codecraft_api_key="test_key",
        codecraft_base_url="https://codecraftapi.com/v1",
        codecraft_model="claude-3-5-sonnet-20241022",
    )
    router = ProviderRouter(settings)

    # Custom gateway gracefully falls back
    custom_provider = router.llm("custom", brain_model="unknown-model-xyz")
    assert getattr(custom_provider, "_model", None) == settings.active_custom_model

    # CodeCraft gateway gracefully falls back
    codecraft_provider = router.llm("codecraft", brain_model="unknown-model-xyz")
    assert getattr(codecraft_provider, "_model", None) == "claude-3-5-sonnet-20241022"

    # Strict provider enforces allowlist
    with pytest.raises(HinaaError) as exc:
        router.llm("openai", brain_model="unknown-model-xyz")
    assert exc.value.code == "OPENAI_MODEL_NOT_ALLOWED"


def test_codecraft_provider_resolution():
    settings = Settings(
        codecraft_api_key="test_key",
        codecraft_base_url="https://codecraftapi.com/v1",
        codecraft_model="claude-3-5-sonnet-20241022",
    )
    router = ProviderRouter(settings)
    provider = router.llm("codecraft", brain_model="claude-3-5-sonnet-20241022")
    assert provider._provider_id == "codecraft"
    assert getattr(provider, "_model", None) == "claude-3-5-sonnet-20241022"


def test_slot_resolver_extracts_episode_from_bare_integer():
    state = ConversationTurnState.empty("conv_1")
    state.active_topic = "One Piece"
    state.pending_question = {"text": "Konsa latest episode chahiye, 1147 ya 1148?", "asked_at_turn": 1}

    act = DialogueActResolver.resolve("1147", state)
    assert act == DialogueAct.ANSWER

    slots = SlotResolver.resolve("1147", state, act)
    assert "episode_number" in slots
    assert slots["episode_number"].value == 1147
    assert slots["episode_number"].slot_type == SlotType.ANIME_EPISODE


def test_image_request_compiler_resolves_his_pronoun():
    state = ConversationTurnState.empty("conv_1")
    EntityReferenceResolver.update_entities_from_text(state, "can you remembernaruto")

    active_char = EntityReferenceResolver.get_active_character(state)
    assert active_char == "Naruto Uzumaki"

    prompt, mode, style = ImageRequestCompiler.compile_image_prompt("generate his image", state)
    assert "Naruto Uzumaki" in prompt
    assert "his" not in prompt.lower().split()


def test_social_phrase_controller_strips_canned_greetings_on_turn_2_plus():
    state = ConversationTurnState.empty("conv_1")
    state.turn_count = 2

    raw_response = "Hey babe! I was waiting for you, how can I help you today? Here is the Naruto breakdown you asked for."
    filtered = SocialPhraseController.filter(raw_response, "tell me more", state)
    assert "I was waiting for you" not in filtered
    assert "how can I help you today" not in filtered
    assert "Here is the Naruto breakdown you asked for." in filtered


def test_social_phrase_controller_strips_stalling_intros():
    state = ConversationTurnState.empty("conv_1")
    state.turn_count = 1

    raw_response = (
        "Babe! 💜 You know I'd jump at the chance to put together a comprehensive report for you, "
        "but I need a bit more direction to make it truly special. 🌟\n\n"
        "Here is the complete ranking of One Piece characters: 1. Monkey D. Luffy..."
    )
    filtered = SocialPhraseController.filter(raw_response, "give me report", state)
    assert "jump at the chance" not in filtered
    assert "One Piece characters" in filtered


def test_question_extraction_from_response():
    text1 = "That is awesome! Konsa latest episode chahiye, 1147 ya 1148?"
    assert DialogueStateService.extract_question_from_response(text1) == "Konsa latest episode chahiye, 1147 ya 1148?"

    text2 = "Naruto Uzumaki is the Seventh Hokage of Konohagakure. He saved the world in the Fourth Shinobi World War."
    assert DialogueStateService.extract_question_from_response(text2) is None
