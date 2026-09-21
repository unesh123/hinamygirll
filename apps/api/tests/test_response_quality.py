from hinaa_api.prompts.fallback import neutral_fallback_plan
from hinaa_api.services import _apply_response_quality_guard


def test_response_quality_guard_removes_identical_repeated_sentence() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.displayText = (
        "Your local project is ready with three clear tasks. "
        "Your local project is ready with three clear tasks. "
        "Open Tasks whenever you want to continue."
    )
    plan.spokenText = "Your local project is ready."

    _apply_response_quality_guard(plan)

    assert plan.displayText == (
        "Your local project is ready with three clear tasks. "
        "Open Tasks whenever you want to continue."
    )


def test_response_quality_guard_replaces_long_verbatim_voice_echo() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    long_answer = (
        "The local work plan is ready. It includes discovery, creation, review, "
        "and an approval gate before consequential actions. Your sources and "
        "artifacts stay within the project workspace for later reference."
    )
    plan.displayText = long_answer
    plan.spokenText = long_answer

    _apply_response_quality_guard(plan)

    assert plan.spokenText == long_answer
    assert "key details" not in plan.spokenText.lower()
    assert "```" not in plan.spokenText


def test_response_quality_guard_keeps_markdown_out_of_the_spoken_channel() -> None:
    """Measured live: she answered "what model are you running on" with
    spokenText containing `tier-a-conversation-brain-1.0.0`. The guard only
    rejects triple backticks, so a single-backtick code span went straight to
    the voice engine. The document keeps its formatting; her voice must not.
    """
    plan = neutral_fallback_plan(
        user_text="what model are you running on right now?",
        companion_id="hinaa",
        language="en-US",
    )
    plan.displayText = (
        "Right now I run on **Claude** with prompt assembly version "
        "`tier-a-conversation-brain-1.0.0` and persistence enabled."
    )
    plan.spokenText = (
        "Right now I run on **Claude** with prompt assembly version "
        "`tier-a-conversation-brain-1.0.0` and persistence enabled."
    )

    _apply_response_quality_guard(plan)

    assert "`" not in plan.spokenText
    assert "*" not in plan.spokenText
    assert "tier-a-conversation-brain-1.0.0" in plan.spokenText
    assert "`tier-a-conversation-brain-1.0.0`" in plan.displayText
    assert "**Claude**" in plan.displayText
