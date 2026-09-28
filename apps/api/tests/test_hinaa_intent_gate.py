from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from hinaa_intent_gate import Intent, decide


NOW = datetime(
    2026, 9, 24, 12, 0,
    tzinfo=ZoneInfo("Asia/Kathmandu"),
)


@pytest.mark.parametrize(
    "message",
    [
        "hey hina",
        "who is Mikasa Ackerman?",
        "what does a reminder mean?",
        "suggest isekai like Naruto",
        "make a decision",
        "why did you fetch images?",
    ],
)
def test_chat_does_not_receive_a_tool(message: str) -> None:
    result = decide(message, now=NOW)
    assert result.intent in {Intent.CHAT, Intent.CANCEL}
    assert result.arguments == {}


def test_explicit_image_search() -> None:
    result = decide("show me images of Mikasa", now=NOW)
    assert result.intent is Intent.IMAGE_SEARCH
    assert result.arguments == {"query": "Mikasa Ackerman"}


def test_generation_uses_extracted_subject_only() -> None:
    result = decide(
        "generate cinematic Mikasa in Kathmandu",
        now=NOW,
    )
    assert result.intent is Intent.IMAGE_GENERATE
    assert result.arguments == {
        "prompt": "cinematic Mikasa in Kathmandu"
    }


def test_reminder_has_persistable_time_and_task() -> None:
    result = decide(
        "remind me tomorrow at 8 to call Sile",
        now=NOW,
    )
    assert result.intent is Intent.REMINDER_CREATE
    assert result.arguments == {
        "title": "call Sile",
        "due_at": "2026-09-25T08:00:00+05:45",
        "timezone": "Asia/Kathmandu",
    }


@pytest.mark.parametrize(
    "message",
    [
        "stop I didn't ask",
        "stop generating",
        "you keep generating images",
    ],
)
def test_stop_never_starts_another_job(message: str) -> None:
    result = decide(message, now=NOW)
    assert result.intent is Intent.CANCEL
    assert result.arguments == {}


def test_ambiguous_reminder_does_not_guess_am_or_pm() -> None:
    result = decide(
        "remind me to call Sile at 4:00",
        now=NOW,
    )
    assert result.intent is Intent.CLARIFY
    assert result.arguments == {}


def test_search_is_not_generation() -> None:
    result = decide(
        "find images of Naruto",
        now=NOW,
    )
    assert result.intent is Intent.IMAGE_SEARCH
    assert result.arguments == {"query": "Naruto"}


def test_complaint_is_not_an_image_prompt() -> None:
    result = decide(
        "Again, you started to generate an image",
        now=NOW,
    )
    assert result.intent is Intent.CANCEL
    assert result.arguments == {}


def test_typo_in_generate_verb() -> None:
    result = decide("generte mikasa ackerman anime pic", now=NOW)
    assert result.intent is Intent.IMAGE_GENERATE
    assert "mikasa" in result.arguments.get("prompt", "").lower()


def test_imperative_directive() -> None:
    result = decide("just generate it", now=NOW)
    assert result.intent is Intent.IMAGE_GENERATE

    result_profane = decide("go and fuck generate it", now=NOW)
    assert result_profane.intent is Intent.IMAGE_GENERATE


def test_pasted_art_prompt() -> None:
    prompt = (
        "Mikasa Ackerman from Attack on Titan, standing on a rooftop in the evening light with "
        "the Survey Corps uniform, anime style, highly detailed, dramatic sunset lighting, masterpiece."
    )
    result = decide(prompt, now=NOW)
    assert result.intent is Intent.IMAGE_GENERATE
    assert result.arguments.get("prompt") == prompt


def test_multi_turn_affirmative_resolves_image() -> None:
    history = [
        ("user", "can you draw Mikasa?"),
        ("assistant", "Sure! I can create a dramatic portrait of Mikasa Ackerman. Should I generate it?"),
    ]
    result = decide("yes", now=NOW, history=history)
    assert result.intent is Intent.IMAGE_GENERATE
