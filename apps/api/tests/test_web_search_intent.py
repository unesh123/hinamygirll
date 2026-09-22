"""Web search intent normalization.

His complaint: "intent_normalize so Mikasa search isn't the whole sentence".
Measured in the code, `planner.py` handed `web_search` the raw utterance at both
of its call sites, so the search provider was asked to match her name, the
command verb and the trailing "please" as literal terms. These tests pin the
compile, what it must NOT touch, and the fact that every path able to plan this
call goes through it.
"""

from __future__ import annotations

from hinaa_api.agent.planner import AgentPlanner, normalized_web_query
from hinaa_api.agent.state import AgentGoal, GoalType
from hinaa_api.media.search_intelligence import (
    clean_web_query,
    compile_web_search_query,
    compiled_web_query_parameters,
)


def _planned_web_query(text: str) -> tuple[AgentGoal, str]:
    goal = AgentGoal(user_id="test-user", text=text)
    steps = AgentPlanner().create_plan(goal)
    search_steps = [s for s in steps if s.skill_id == "web_search"]
    assert search_steps, f"no web_search step planned for {text!r}"
    return goal, str(search_steps[0].parameters["query"])


def test_her_name_and_the_command_verb_never_reach_the_search_provider():
    goal, query = _planned_web_query("hinaa please search who is Mikasa Ackerman")
    assert goal.goal_type == GoalType.INFORMATIONAL
    assert query == "who is Mikasa Ackerman"
    assert "hinaa" not in query.lower()
    assert "please" not in query.lower()
    assert query != goal.text


def test_a_bare_character_name_searches_the_character_and_her_series():
    assert compile_web_search_query("mikasa ackerman").primary_query == "Mikasa Ackerman Attack on Titan"


def test_a_misspelled_character_is_searched_by_her_real_name():
    # He types "mikas akerman" at speed; the provider should still get the canon name.
    assert compile_web_search_query("search mikas akerman").primary_query == "Mikasa Ackerman Attack on Titan"


def test_a_question_about_a_character_keeps_asking_that_question():
    """Collapsing to the bare entity would answer a different question than he asked."""
    assert compile_web_search_query("tell me about eren yeager's death").primary_query == "Eren Yeager's death"
    assert compile_web_search_query("why is mikasa so strong").primary_query == "why is Mikasa Ackerman so strong"


def test_time_sensitive_queries_keep_their_time_terms():
    query = compile_web_search_query("can you look up the latest news about nepal floods").primary_query
    assert query == "latest news about nepal floods"
    assert "latest" in query and "news" in query


def test_a_query_that_is_already_a_query_is_left_alone():
    for text in (
        "what is the capital of australia",
        "Mikasa Ackerman Attack on Titan",
        "how does redis persistence work",
    ):
        assert compiled_web_query_parameters({"query": text})["query"] == text


def test_search_operators_and_quoted_phrases_survive():
    assert clean_web_query("site:github.com hinaa agent") == "site:github.com hinaa agent"
    assert clean_web_query('search "attack on titan" finale analysis') == 'search "attack on titan" finale analysis'


def test_an_addressee_prefix_cannot_eat_the_start_of_a_real_query():
    """Addressee prefixes match on word boundaries, so a query that merely starts
    with one of them keeps its first word ("bro" is also the head of "broccoli")."""
    for text in ("broccoli recipes", "girlfriend gift ideas", "hidden gem restaurants kathmandu"):
        assert compiled_web_query_parameters({"query": text})["query"] == text


def test_the_compile_is_idempotent():
    once = compiled_web_query_parameters({"query": "hinaa search who is mikasa ackerman bro"})["query"]
    twice = compiled_web_query_parameters({"query": once})["query"]
    assert once == twice == "who is Mikasa Ackerman"


def test_parameters_the_compiler_has_nothing_to_rewrite_are_returned_untouched():
    assert compiled_web_query_parameters({"count": 6}) == {"count": 6}
    assert compiled_web_query_parameters({"query": "   "}) == {"query": "   "}
    # An unknown key is never invented for the sake of the compile.
    compiled = compiled_web_query_parameters({"query": "hinaa find gojo satoru please", "count": 5})
    assert set(compiled) == {"query", "count"}
    assert compiled["count"] == 5
    assert compiled["query"] == "Gojo Satoru Jujutsu Kaisen"


def test_the_runtime_web_step_compiles_and_degrades_safely():
    from hinaa_api.agent.kernel import _compiled_web_query

    compiled = _compiled_web_query({"query": "hey hina can you search eren yeager", "count": 3})
    assert compiled["query"] == "Eren Yeager Attack on Titan"
    assert compiled["count"] == 3
    # Nothing to compile must not lose the step.
    assert _compiled_web_query({"count": 2}) == {"count": 2}


def test_normalization_failure_keeps_his_request_instead_of_dropping_it(monkeypatch):
    import hinaa_api.media.search_intelligence as si

    def explode(_text: str):
        raise RuntimeError("provider blew up")

    monkeypatch.setattr(si, "compile_web_search_query", explode)
    assert si.compiled_web_query_parameters({"query": "hinaa search mikasa"}) == {"query": "hinaa search mikasa"}
    assert normalized_web_query("hinaa search mikasa") == "hinaa search mikasa"


def test_every_path_that_can_plan_a_web_search_normalizes_its_query():
    """The helpers being right is not enough — the same defect reached the vendor
    through the model's own plan JSON, the runtime step, and /tools/execute."""
    import inspect

    from hinaa_api import main, services
    from hinaa_api.agent import kernel, planner
    from hinaa_api.prompts import fallback

    for module in (planner, kernel, services, fallback, main):
        source = inspect.getsource(module)
        assert "compiled_web_query_parameters" in source, (
            f"{module.__name__} no longer normalizes web_search queries"
        )


def test_a_model_written_web_plan_gets_a_query_not_his_sentence():
    from hinaa_api.prompts.fallback import parse_turn_plan

    plan = parse_turn_plan(
        '{"displayText":"sure babe","spokenText":"sure","language":"en-US",'
        '"emotion":{"primary":"happy","intensity":0.6,"valence":0.6,"arousal":0.5},'
        '"toolRequests":[{"toolName":"web_search","parameters":'
        '{"query":"hinaa please search who is mikasa ackerman","count":6}}]}'
    )
    assert len(plan.toolRequests) == 1
    assert plan.toolRequests[0].parameters["query"] == "who is Mikasa Ackerman"
