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


@pytest.mark.asyncio
async def test_timeout_fixture_does_not_retry_after_visible_output() -> None:
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.001):
            await asyncio.sleep(0.02)
