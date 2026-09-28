"""The pre-send self-check must never ship these defects."""
from __future__ import annotations

from hinaa_api.reply_guard import check_reply


def test_a_clean_reply_is_untouched() -> None:
    out = check_reply("Hello Unesh, I am here.")
    assert out.text == "Hello Unesh, I am here."
    assert out.repaired is False


def test_empty_reply_becomes_an_honest_prompt() -> None:
    out = check_reply("   ")
    assert out.text
    assert any(i.kind == "empty_reply" for i in out.issues)


def test_none_reply_is_handled() -> None:
    out = check_reply(None)
    assert out.text
    assert out.issues[0].kind == "empty_reply"


def test_generator_trace_lines_are_removed() -> None:
    raw = (
        "Here is your answer.\n"
        "WHY DID HINA CONTINUE? -> the draft was short\n"
        "seg1:provider stopped at the output token cap\n"
        "That is all."
    )
    out = check_reply(raw)
    assert "WHY DID HINA" not in out.text
    assert "seg1:" not in out.text
    assert out.text == "Here is your answer.\nThat is all."
    assert any(i.kind == "internal_trace" for i in out.issues)


def test_a_reply_that_is_only_trace_becomes_the_empty_prompt() -> None:
    out = check_reply("WHY DID HINA STOP? -> done\ndepth floor 0 words")
    assert "WHY DID HINA" not in out.text
    assert any(i.kind == "empty_reply" for i in out.issues)


def test_unbalanced_fence_is_closed() -> None:
    out = check_reply("Here:\n```python\nprint(1)\n")
    assert out.text.endswith("```")
    assert out.text.count("```") % 2 == 0
    assert any(i.kind == "unbalanced_fence" for i in out.issues)


def test_balanced_fence_is_left_alone() -> None:
    raw = "Here:\n```python\nprint(1)\n```"
    out = check_reply(raw)
    assert out.text == raw
    assert out.repaired is False


def test_verbatim_echo_is_flagged_not_rewritten() -> None:
    out = check_reply("what time is it?", user_text="what time is it?")
    assert out.text == "what time is it?"
    assert any(i.kind == "parrot" for i in out.issues)


def test_the_full_reply_survives_the_repair() -> None:
    raw = "A long answer.\nWHY DID HINA STOP? -> complete\nSecond paragraph."
    out = check_reply(raw, user_text="tell me something", language="en")
    assert "A long answer." in out.text
    assert "Second paragraph." in out.text
