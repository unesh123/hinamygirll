from __future__ import annotations

import pytest

from hinaa_api.intent_router import (
    ALL_ROUTES,
    MUTATION_ROUTES,
    ROUTE_AUTOMATION,
    ROUTE_BROWSER,
    ROUTE_CHAT,
    ROUTE_CODING,
    ROUTE_CREATIVE,
    ROUTE_DOCUMENTS,
    ROUTE_PLAN,
    ROUTE_RESEARCH,
    ROUTE_TOOLS,
    IntentRouter,
    route_intent,
)

router = IntentRouter()


def test_empty_and_whitespace_go_to_chat():
    for raw in ("", "   ", "\n"):
        d = router.route(raw)
        assert d.route == ROUTE_CHAT
        assert d.confidence >= 0.9


def test_plain_conversation_routes_to_chat():
    d = router.route("hey, what's your favorite movie?")
    assert d.route == ROUTE_CHAT
    assert d.candidate_tools == ()
    assert not d.requires_planning


def test_negated_tool_keyword_stays_chat():
    d = router.route("explain how a bill split algorithm works")
    assert d.route == ROUTE_CHAT
    assert d.metadata.get("negated_tool_match") is True


def test_research_route():
    d = router.route("search for the latest breakthroughs in fusion energy")
    assert d.route == ROUTE_RESEARCH
    assert "web_search" in d.candidate_tools
    assert not d.requires_confirmation


def test_coding_route():
    d = router.route("fix this traceback: TypeError in parser.py line 42")
    assert d.route == ROUTE_CODING
    assert d.requires_confirmation
    assert "run_tests" in d.candidate_tools


def test_creative_route():
    d = router.route("generate an image of a sakura sunset wallpaper")
    assert d.route == ROUTE_CREATIVE
    assert d.requires_confirmation


def test_documents_route():
    d = router.route("summarize this pdf into a report")
    assert d.route == ROUTE_DOCUMENTS


def test_browser_route():
    d = router.route("open youtube and play lo-fi beats")
    assert d.route == ROUTE_BROWSER
    assert "browser_act" in d.candidate_tools


def test_automation_route():
    d = router.route("set a timer for 25 minutes")
    assert d.route == ROUTE_AUTOMATION
    assert d.requires_confirmation


def test_plan_route_wins_for_multi_step():
    d = router.route("first research competitors, then build a landing page, then deploy it")
    assert d.route == ROUTE_PLAN
    assert d.requires_planning and d.requires_confirmation


def test_competing_routes_dampen_confidence_and_force_planning():
    d = router.route("search for competitor logos and generate an image deck")
    assert d.route in {ROUTE_RESEARCH, ROUTE_CREATIVE}
    assert d.confidence <= 0.75
    assert d.requires_planning
    assert d.metadata.get("competing_routes")


def test_large_context_flag():
    d = router.route("x" * 13_000)
    assert d.is_large_context is True
    assert d.confidence < 0.9


def test_route_intent_module_level_matches_instance():
    a = route_intent("remind me to stretch")
    b = router.route("remind me to stretch")
    assert a.route == b.route == ROUTE_AUTOMATION
    assert a.to_dict()["route"] == a.route


def test_to_dict_shape():
    d = router.route("fix the login bug in the api endpoint").to_dict()
    assert set(d) == {
        "route",
        "confidence",
        "goal",
        "candidate_tools",
        "requires_planning",
        "requires_confirmation",
        "is_large_context",
        "metadata",
    }
    assert isinstance(d["candidate_tools"], list)


def test_every_route_has_registry_entry_and_mutation_set_is_valid():
    assert set(ROUTE_TOOLS) == set(ALL_ROUTES)
    assert MUTATION_ROUTES <= set(ALL_ROUTES)
    assert ROUTE_CHAT not in MUTATION_ROUTES
    assert ROUTE_RESEARCH not in MUTATION_ROUTES


def test_deterministic_and_thread_safe_shape():
    outs = {router.route("deploy the workflow pipeline then remind me").route for _ in range(20)}
    assert outs == {ROUTE_PLAN}


def test_none_and_non_string_inputs_do_not_crash():
    assert router.route(None).route == ROUTE_CHAT
    assert router.route(12345).route == ROUTE_CHAT


@pytest.mark.parametrize(
    "text,expected",
    [
        ("what's the weather", ROUTE_CHAT),
        ("open google", ROUTE_BROWSER),
        ("start a pomodoro focus session", ROUTE_AUTOMATION),
        ("parse this csv and extract the invoice totals", ROUTE_DOCUMENTS),
        ("make a cinematic video animation", ROUTE_CREATIVE),
        ("refactor this class and add unit tests", ROUTE_CODING),
        ("investigate market trends", ROUTE_RESEARCH),
    ],
)
def test_parametrized_routes(text, expected):
    assert router.route(text).route == expected
