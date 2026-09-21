from __future__ import annotations

import asyncio

from hinaa_api.config import Settings
from hinaa_api.models import AssistantTurnPlan, TurnRequest
from hinaa_api.services import ConversationService, ParsedCommand
from hinaa_api.tools import browser


from hinaa_api.prompts import neutral_fallback_plan


def _test_plan() -> AssistantTurnPlan:
    return neutral_fallback_plan(
        user_text="Thinking about that.",
        companion_id="hinaa",
        language="en-US",
        depth="standard",
    )


def test_explicit_search_command_with_image_keywords_routes_to_image_search():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    cmd = ParsedCommand(command="search", args="mikasa ackerman pintrest images", raw="/search mikasa ackerman pintrest images")
    service._map_explicit_command(cmd, plan)

    assert len(plan.toolRequests) == 1
    req = plan.toolRequests[0]
    assert req.toolName == "image_search"
    assert req.parameters["query"] == "Mikasa Ackerman Attack on Titan"
    assert req.parameters["canonicalSubject"] == "Mikasa Ackerman"
    assert plan.displayText == "Found 6 relevant Mikasa Ackerman images."


def test_explicit_image_alias_command_disambiguates_character():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    cmd = ParsedCommand(command="image", args="gojo", raw="/image gojo")
    service._map_explicit_command(cmd, plan)

    assert len(plan.toolRequests) == 1
    req = plan.toolRequests[0]
    assert req.toolName == "image_search"
    assert req.parameters["query"] == "Gojo Satoru Jujutsu Kaisen"
    assert req.parameters["canonicalSubject"] == "Gojo Satoru"
    assert plan.displayText == "Found 6 relevant Gojo Satoru images."


def test_natural_language_show_me_some_mikasa_images_injects_intent():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("show me some mikasa images", plan)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Mikasa Ackerman Attack on Titan"
    assert req.parameters["canonicalSubject"] == "Mikasa Ackerman"
    assert plan.displayText == "Found 6 relevant Mikasa Ackerman images."


def test_natural_language_show_character_disambiguates():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("show mikasa", plan)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Mikasa Ackerman Attack on Titan"
    assert req.parameters["canonicalSubject"] == "Mikasa Ackerman"


def test_stated_want_for_pics_routes_to_image_search():
    """Measured on the live turn: "i want pics of tokyo ghoul" produced no tool
    event at all, and she answered with an apology about not being able to fetch
    copyrighted images after promising twice that she was fetching them."""
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("i want pics of tokyo ghoul", plan)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Tokyo Ghoul"


def test_declining_pics_does_not_fetch_pics():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("i don't want pics", plan)

    assert not any(t.toolName == "image_search" for t in plan.toolRequests)


def test_search_web_for_character_does_not_hijack_to_image_search():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("search the web for mikasa ackerman", plan)

    assert not any(t.toolName == "image_search" for t in plan.toolRequests)


def test_mikasa_followup_image_search_uses_active_entity_not_previous_sentence(client):
    owner = client.get("/v1/workspace/identity", headers={"X-HINAA-Dev-User": "alice"}).json()["userId"]
    service = client.app.state.service
    conversation_id = "mikasa-media-grounding"

    first = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=conversation_id,
            conversationId=conversation_id,
            text="FETCH ME SOME DEATAILS OF MIKAS AKERMAN",
            providerMode="mock",
        ),
        user_id=owner,
    ))
    assert first.value.toolRequests == []

    second = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=conversation_id,
            conversationId=conversation_id,
            text="I NNED FULL DESCRIPTION ABOUT HER",
            providerMode="mock",
        ),
        user_id=owner,
    ))
    assert not any(t.toolName == "image_search" for t in second.value.toolRequests)

    third = asyncio.run(service.create_plan(
        TurnRequest(
            sessionId=conversation_id,
            conversationId=conversation_id,
            text="FETCH ME SOME IMAGES",
            providerMode="mock",
        ),
        user_id=owner,
    ))
    req = next(t for t in third.value.toolRequests if t.toolName == "image_search")
    query = req.parameters["query"]
    assert query == "Mikasa Ackerman Attack on Titan"
    assert req.parameters["canonicalSubject"] == "Mikasa Ackerman"
    assert "full description" not in query.lower()
    assert "about her" not in query.lower()
    assert "fetch me some images" not in query.lower()
    assert third.value.displayText == "Found 6 relevant Mikasa Ackerman images."


def test_mikasa_raw_command_noise_is_not_echoed_into_search_query():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("I NEED MIKASA IMGES HINA FETCH THEM", plan)

    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Mikasa Ackerman Attack on Titan"
    assert req.parameters["canonicalSubject"] == "Mikasa Ackerman"
    assert "I NEED" not in req.parameters["query"]
    assert "FETCH THEM" not in req.parameters["query"]
    assert plan.displayText == "Found 6 relevant Mikasa Ackerman images."


def test_slash_image_search_command_token_never_reaches_the_vendor():
    """Measured before the fix: '/image_search sakura anime wallpaper' was
    compiled into the vendor query '/Imagesearch Sakura Anime', so every
    provider searched for the word 'imagesearch' instead of the subject.
    """
    assert browser.clean_image_query("/image_search sakura anime wallpaper") == "sakura anime wallpaper"
    assert browser.clean_image_query("/imagesearch Vite logo transparent") == "Vite logo transparent"
    assert browser.clean_image_query("/image search sakura") == "sakura"
    assert browser.clean_image_query("sakura wallpaper") == "sakura wallpaper"


def test_image_search_relevance_verifier_drops_unrelated_stock_results(monkeypatch):
    async def fake_safebooru(query: str, count: int = 6):
        return [
            {"id": "bad-1", "title": "Gender pronouns non-binary person holding sign", "imageUrl": "https://example.test/pronoun.jpg", "pageUrl": "https://example.test/pronoun"},
            {"id": "bad-2", "title": "Random brunette stock portrait", "imageUrl": "https://example.test/brunette.jpg", "pageUrl": "https://example.test/brunette"},
            {"id": "bad-3", "title": "Bee anime character", "imageUrl": "https://example.test/bee.jpg", "pageUrl": "https://example.test/bee"},
            {"id": "good-4", "title": "Mikasa Ackerman official character artwork Attack on Titan", "imageUrl": "https://example.test/mikasa.jpg", "pageUrl": "https://attackontitan.example/mikasa"},
            {"id": "bad-5", "title": "Fencing woman stock photo", "imageUrl": "https://example.test/fencing.jpg", "pageUrl": "https://example.test/fencing"},
            {"id": "bad-6", "title": "Random game character", "imageUrl": "https://example.test/game.jpg", "pageUrl": "https://example.test/game"},
        ]

    monkeypatch.setattr(browser, "search_safebooru_images", fake_safebooru)

    result = asyncio.run(browser.search_images({
        "query": "Mikasa Ackerman Attack on Titan",
        "canonicalSubject": "Mikasa Ackerman",
        "expectedEntities": ["Mikasa Ackerman", "Attack on Titan"],
        "providerProfile": "general_web_named_character",
        "count": 6,
    }))

    assert result["imageCount"] == 1
    assert result["images"][0]["id"] == "good-4"
    assert result["resultSet"]["canonicalSubject"] == "Mikasa Ackerman"
    assert result["trace"]["filteredResultCount"] == 1
    assert result["trace"]["rejected"]


def test_nepal_flood_followup_image_search_does_not_hijack_to_mikasa(client):
    """Verify that when the active topic is a real-world event (e.g. Nepal flood),
    a followup 'fetch some images of it' searches for Nepal flood, NOT Mikasa Ackerman."""
    service = client.app.state.service
    session_id = "test-nepal-flood-session"

    # Set up dialogue state with active topic 'Nepal flood situation'
    d_state = service.dialogue_state_service.load(session_id)
    d_state.active_topic = "Nepal flood situation"
    service.dialogue_state_service.save(d_state)

    plan = _test_plan()
    service._inject_deterministic_tool_intents("Fetch some images of it", plan, session_id=session_id)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert "Nepal" in req.parameters["query"] and "flood" in req.parameters["query"]
    assert "Mikasa" not in req.parameters["query"]



def test_negation_purges_mikasa_and_sets_nepal_flood():
    """Verify that saying 'not mikasa about nepal flood hina' clears Mikasa and sets Nepal flood."""
    from hinaa_api.dialogue_state import ConversationTurnState, DialogueStateService, EntityReferenceResolver

    state = ConversationTurnState.empty("negation_test")
    # Simulate Mikasa being active previously
    state.active_topic = "Mikasa Ackerman"
    state.active_entities = [{"type": "character", "name": "Mikasa Ackerman", "normalized": "mikasa ackerman"}]

    # User explicitly negates Mikasa and introduces Nepal flood
    user_text = "not mikasa about nepal flood hina"
    EntityReferenceResolver.update_entities_from_text(state, user_text)
    DialogueStateService.update_topic_from_request(state, user_text)

    # Mikasa must be purged
    assert not any(e.get("name") == "Mikasa Ackerman" for e in state.active_entities)
    # Active topic must be Nepal flood, NOT Mikasa
    assert state.active_topic is not None
    assert "nepal flood" in state.active_topic.lower()
    assert "mikasa" not in state.active_topic.lower()


def test_stop_searching_for_mikasa_multiword_negation():
    """Verify that multi-word negation phrases like 'Stop searching for Mikasa, tell me about Nepal floods'
    completely purge Mikasa and extract Nepal floods as the active topic."""
    from hinaa_api.dialogue_state import ConversationTurnState, DialogueStateService, EntityReferenceResolver

    state = ConversationTurnState.empty("negation_test_multiword")
    state.active_topic = "Mikasa Ackerman"
    state.active_entities = [{"type": "character", "name": "Mikasa Ackerman", "normalized": "mikasa ackerman"}]

    user_text = "Stop searching for Mikasa, tell me about Nepal floods"
    EntityReferenceResolver.update_entities_from_text(state, user_text)
    DialogueStateService.update_topic_from_request(state, user_text)

    # Mikasa must be purged from active entities and topic
    assert not any(e.get("name") == "Mikasa Ackerman" for e in state.active_entities)
    assert state.active_topic == "Nepal floods"



def test_runtime_image_step_never_sends_his_sentence_to_the_vendor():
    """Measured live: the runtime executed image_search with query
    "i want pics of tokyo ghoul". Every planner fills this step differently, so
    the compiler runs at execution and the card shows the same subject."""
    from hinaa_api.agent.kernel import _compiled_visual_query

    compiled = _compiled_visual_query({"query": "i want pics of tokyo ghoul", "count": 6})
    assert compiled["query"] == "Tokyo Ghoul"
    assert compiled["canonicalSubject"] == "Tokyo Ghoul"


def test_runtime_image_step_keeps_a_query_the_compiler_cannot_resolve():
    from hinaa_api.agent.kernel import _compiled_visual_query

    compiled = _compiled_visual_query({"query": "it", "count": 4})
    assert compiled["query"] == "it"
    assert compiled["count"] == 4


def test_every_path_that_can_plan_an_image_search_compiles_its_query():
    """The helpers being right is not enough — the measured raw query came from
    the model's own plan JSON, which used to be handed to ToolRequest as-is."""
    import inspect

    from hinaa_api import services
    from hinaa_api.agent import kernel
    from hinaa_api.media import search_intelligence
    from hinaa_api.prompts import fallback

    assert hasattr(search_intelligence, "compiled_image_query_parameters")
    for module in (kernel, services, fallback):
        source = inspect.getsource(module)
        assert "compiled_image_query_parameters" in source, (
            f"{module.__name__} no longer compiles image_search queries"
        )


def test_a_model_written_image_plan_gets_a_subject_not_his_sentence():
    """Measured live: the plan event carried
    {"query": "i want pics of tokyo ghoul", "canonicalSubject": "i want pics of
    tokyo ghoul"} straight from the model's JSON, so the vendor search and the
    card the user is shown both repeated his sentence."""
    from hinaa_api.prompts.fallback import parse_turn_plan

    plan = parse_turn_plan(
        '{"displayText":"sure babe","spokenText":"sure","language":"en-US",'
        '"emotion":{"primary":"happy","intensity":0.6,"valence":0.6,"arousal":0.5},'
        '"toolRequests":[{"toolName":"image_search","parameters":'
        '{"query":"i want pics of tokyo ghoul","count":6,'
        '"canonicalSubject":"i want pics of tokyo ghoul"}}]}'
    )
    request = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert request.parameters["query"] == "Tokyo Ghoul"
    assert request.parameters["canonicalSubject"] == "Tokyo Ghoul"
    assert request.parameters["count"] == 6
