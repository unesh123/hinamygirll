from __future__ import annotations

from hinaa_api.config import Settings
from hinaa_api.models import AssistantTurnPlan
from hinaa_api.services import ConversationService, ParsedCommand


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
    assert req.parameters["query"] == "Mikasa Ackerman"
    assert "Mikasa Ackerman" in plan.displayText
    assert "✨" in plan.displayText


def test_explicit_image_alias_command_disambiguates_character():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    cmd = ParsedCommand(command="image", args="gojo", raw="/image gojo")
    service._map_explicit_command(cmd, plan)

    assert len(plan.toolRequests) == 1
    req = plan.toolRequests[0]
    assert req.toolName == "image_search"
    assert req.parameters["query"] == "Gojo Satoru"
    assert "Gojo Satoru" in plan.displayText


def test_natural_language_show_me_some_mikasa_images_injects_intent():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("show me some mikasa images", plan)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Mikasa Ackerman"
    assert "Mikasa Ackerman" in plan.displayText
    assert "✨" in plan.displayText


def test_natural_language_show_character_disambiguates():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("show mikasa", plan)

    assert any(t.toolName == "image_search" for t in plan.toolRequests)
    req = next(t for t in plan.toolRequests if t.toolName == "image_search")
    assert req.parameters["query"] == "Mikasa Ackerman"


def test_search_web_for_character_does_not_hijack_to_image_search():
    settings = Settings()
    service = ConversationService(settings)
    plan = _test_plan()

    service._inject_deterministic_tool_intents("search the web for mikasa ackerman", plan)

    assert not any(t.toolName == "image_search" for t in plan.toolRequests)
