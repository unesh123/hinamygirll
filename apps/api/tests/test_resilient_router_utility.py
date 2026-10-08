"""Utility-scored model routing: quality - latency - cost + fit, health-gated."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hinaa_api.cognitive.resilient_router import (  # noqa: E402
    CircuitState,
    ResilientProviderRouter,
    TaskProfile,
)


def make_router() -> ResilientProviderRouter:
    return ResilientProviderRouter()


def test_utility_prefers_quality_for_complex_tasks():
    router = make_router()
    task = TaskProfile(complexity=0.95, needs_tools=True, needs_speed=0.1)
    chain = router.rank_providers(task)
    assert chain[0] == "claude"  # highest quality + tool fit wins deep work


def test_utility_prefers_speed_for_latency_critical_tasks():
    router = make_router()
    task = TaskProfile(complexity=0.1, needs_tools=False, needs_speed=1.0)
    scores = {name: router.utility_score(name, task) for name in router._providers}
    # Fast cheap providers must outrank the slow premium tier on casual live chat
    assert scores["local_rule"] > scores["claude"]


def test_open_circuit_zeroes_utility_and_drops_from_chain():
    router = make_router()
    for _ in range(3):
        router.record_failure("claude", RuntimeError("boom"))
    assert router.get_provider_status("claude").state == CircuitState.OPEN
    assert router.utility_score("claude") == 0.0
    chain = router.rank_providers(TaskProfile(complexity=0.9))
    assert "claude" not in chain
    assert chain  # healthy fallbacks remain


def test_measured_latency_feeds_the_score():
    router = make_router()
    task = TaskProfile(needs_speed=0.8)
    slow = make_router()
    slow.record_success("gemini", 7000.0)  # EMA latency near the penalty ceiling
    assert router.utility_score("gemini", task) > slow.utility_score("gemini", task)


def test_half_open_gets_confidence_haircut():
    router = make_router()
    closed_score = router.utility_score("custom")
    router.get_provider_status("custom").state = CircuitState.HALF_OPEN
    half_open_score = router.utility_score("custom")
    assert half_open_score == round(closed_score * 0.5, 4)


def test_preference_leads_only_when_healthy():
    router = make_router()
    task = TaskProfile(complexity=0.8)
    assert router.rank_providers(task, preferred_provider="gemini")[0] == "gemini"
    for _ in range(3):
        router.record_failure("gemini", RuntimeError("down"))
    chain = router.rank_providers(task, preferred_provider="gemini")
    assert chain[0] != "gemini"  # unhealthy preference must not lead


def test_legacy_chain_behavior_unchanged_without_task():
    router = make_router()
    chain = router.select_healthy_provider_chain()
    assert chain[0] == "claude"  # static order preserved when no task profile


def test_statuses_expose_utility():
    router = make_router()
    statuses = router.get_all_statuses()
    assert "utility" in statuses["claude"]
    assert statuses["claude"]["utility"] > 0
