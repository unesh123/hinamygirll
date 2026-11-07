"""Hina mirrors the user's language (English, Nepali, Hindi) instead of defaulting to Hindi."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from hinaa_api.config import Settings
from hinaa_api.prompts.companions import HINAA_IDENTITY
from hinaa_api.prompts.language import LANGUAGE_LAYER, language_hint
from hinaa_api.prompts.response_modes import response_mode_layer
from hinaa_api.prompts.safety import REALTIME_TOOL_POLICY_LAYER
from hinaa_api.providers.base import ProviderResult
from hinaa_api.providers.mock import MockLLMProvider
from hinaa_api.realtime import ClientHello, CommitMessage, LiveSession, RealtimeGateway

ALL_LANGUAGE_RULES = (HINAA_IDENTITY, LANGUAGE_LAYER, REALTIME_TOOL_POLICY_LAYER, response_mode_layer("conversation"))


def test_no_rule_bans_nepali_or_defaults_to_hindi() -> None:
    for text in ALL_LANGUAGE_RULES:
        assert "unprompted Nepali" not in text
        assert "NEVER insert random Nepali" not in text
        assert "By default, speak in pure fluent English or sweet, loving Romanized Hindi" not in text


def test_rules_mirror_his_language_and_tell_nepali_from_hindi() -> None:
    assert "MATCH HIS LANGUAGE" in HINAA_IDENTITY and "MATCH HIS LANGUAGE" in LANGUAGE_LAYER
    assert "Never blend the two" in LANGUAGE_LAYER or "never blend Nepali and Hindi" in HINAA_IDENTITY
    for marker in ("malai", "मलाई", "mujhe", "मुझे"):
        assert marker in LANGUAGE_LAYER


def test_auto_turns_mirror_instead_of_forcing_a_language() -> None:
    hint = language_hint("mixed")
    assert hint.startswith("Mirror the language and script of his latest message")
    assert "Nepali" in hint and "Hindi" in hint
    # Fixed choices from Settings still win.
    assert "Nepali" in language_hint("ne-NP") and "Hindi" in language_hint("hi-IN")


@pytest.mark.asyncio
@pytest.mark.parametrize(("hello_language", "expected"), [("mixed", "mixed"), ("ne-NP", "ne-NP"), ("en-US", "en-US")])
async def test_voice_turn_language_is_not_forced_to_hindi(hello_language: str, expected: str) -> None:
    seen: list[str] = []

    async def plan(request, emit, user_id=None):
        seen.append(request.language)
        result = await MockLLMProvider().create_plan(request.text, "hinaa", "en-US", ())
        await emit(result.value.spokenText)
        return result

    service = SimpleNamespace(
        transcribe=AsyncMock(return_value=ProviderResult("k cha babe", "batch-test", 1)),
        create_live_plan=plan,
        synthesize_text=AsyncMock(return_value=ProviderResult(b"audio", "mock", 1)),
    )
    recognition = SimpleNamespace(
        finish=AsyncMock(return_value=ProviderResult("k cha babe", "stream-test", 0)),
        abort=AsyncMock(),
        failure_code="STT_STREAM_CONNECTION_FAILED",
    )
    gateway = RealtimeGateway(Settings(_env_file=None), service)
    hello = ClientHello(type="session.hello", protocolVersion="1.0", sessionId="lang", providerMode="real", generation=1, language=hello_language)
    session = LiveSession(hello, turn=1)

    class Browser:
        async def send_json(self, event):
            pass

    await gateway._process_turn(Browser(), session, CommitMessage(type="audio.commit", generation=1, endedAtMs=1), b"\x01\x00" * 320, recognition)
    assert seen == [expected]


def test_voice_rule_gives_nepali_speech_a_nepali_example() -> None:
    assert "Romanized Nepali for Nepali" in REALTIME_TOOL_POLICY_LAYER
    assert "Never switch to a language he did not use" in REALTIME_TOOL_POLICY_LAYER
