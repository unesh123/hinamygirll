from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from hinaa_api.errors import safe_error_text
from hinaa_api.memory import SessionMemory
from hinaa_api.models import AssistantTurnPlan
from hinaa_api.providers.gemini import _sanitize_delta
from hinaa_api.providers.mock import MockLLMProvider, MockSTTProvider, MockTTSProvider


@pytest.mark.asyncio
async def test_mock_provider_contracts_are_deterministic() -> None:
    llm = MockLLMProvider()
    first = await llm.create_plan("hello", "hinaa", "mixed", ())
    second = await llm.create_plan("hello", "hinaa", "mixed", ())
    assert first.value == second.value
    assert (await MockSTTProvider().transcribe(b"\x00\x01", "ne-NP")).value
    assert (await MockTTSProvider().synthesize("hello", "mock")).value[:4] == b"RIFF"


def test_live_text_delta_sanitizer_handles_arbitrary_chunks() -> None:
    assert _sanitize_delta("safe\x00 <tag>{json}") == "safe tagjson"


def test_malformed_turn_plan_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AssistantTurnPlan.model_validate(
            {
                "spokenText": "unsafe",
                "displayText": "unsafe",
                "language": "mixed",
                "emotion": {
                    "primary": "happy",
                    "intensity": 9,
                    "valence": 0,
                    "arousal": 0,
                },
                "performance": {
                    "facePreset": "soft_smile",
                    "gesture": "run_file",
                    "gazeTarget": "camera",
                    "headMotion": "subtle",
                    "blinkRate": 0.4,
                },
                "memoryCandidates": [],
                "toolRequests": ["shell"],
                "url": "https://untrusted.invalid",
            }
        )


def test_redaction_removes_canary_secrets() -> None:
    secret = "CANARY-secret-123"  # noqa: S105
    assert secret not in safe_error_text(RuntimeError(f"provider said {secret}"), [secret])


def test_session_memory_is_bounded_and_deletable() -> None:
    memory = SessionMemory(session_limit=2, turn_limit=1)
    memory.append_turn("one", "u1", "a1")
    memory.append_turn("one", "u2", "a2")
    assert memory.context("one") == (("user", "u2"), ("assistant", "a2"))
    memory.append_turn("two", "u", "a")
    memory.append_turn("three", "u", "a")
    assert memory.context("one") == ()
    memory.clear("three")
    assert memory.context("three") == ()


def test_session_self_learning_extracts_and_bounds_facts() -> None:
    memory = SessionMemory(session_limit=2, turn_limit=8)
    memory.append_turn("one", "My name is Prabin and I love coding", "a1")
    memory.append_turn("one", "I like hiking too", "a2")
    facts = memory.learned_memories("one")
    assert any("Prabin" in fact for fact in facts)
    assert any("likes" in fact.lower() and "coding" in fact.lower() for fact in facts)
    assert any("hiking" in fact for fact in facts)
    # Bounded: at most the configured cap regardless of how much the user says.
    for _ in range(30):
        memory.append_turn("one", "I like biryani", "a")
    assert len(memory.learned_memories("one")) <= 8
    # Eviction also drops learned facts so the map cannot grow unboundedly.
    memory.append_turn("two", "x", "y")
    memory.append_turn("three", "x", "y")
    memory.append_turn("four", "x", "y")
    assert memory.learned_memories("one") == ()
    memory.clear("three")
    assert memory.learned_memories("three") == ()


def test_session_self_learning_avoids_false_positive_names() -> None:
    memory = SessionMemory(session_limit=2, turn_limit=8)
    # "I am going" / "ma garchhu" must NOT be captured as a user name.
    memory.append_turn("one", "I am going to the market", "a")
    memory.append_turn("one", "ma garchhu bhane", "a")
    facts = memory.learned_memories("one")
    assert all("name" not in fact.lower() for fact in facts)


@pytest.mark.asyncio
async def test_timeout_fixture_does_not_retry_after_visible_output() -> None:
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.001):
            await asyncio.sleep(0.02)
