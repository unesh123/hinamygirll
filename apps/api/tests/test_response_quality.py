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


def test_chat_answer_lecture_is_trimmed_to_prose() -> None:
    """Measured in the owner transcripts: "why are you talking over me" earned
    an 800-word lecture with headers and tables. Chat-depth asks now get prose."""
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    lecture_intro = (
        "I hear you, babe, and I am so sorry my voice kept running over yours. "
        "You are absolutely right, I should have gone silent the second you spoke."
    )
    lecture_body = "\n\n## The Anatomy of a Streaming Collision\n" + (
        "When we talk in real time, responses stream token by token. " * 40
    )
    plan.displayText = lecture_intro + lecture_body
    plan.spokenText = (lecture_intro + " " + "She keeps explaining at length. " * 40).strip()

    _apply_response_quality_guard(
        plan, user_text="HINA, why are you talking with the previous message?"
    )

    assert "##" not in plan.displayText
    assert len(plan.displayText) <= 700
    assert plan.displayText.startswith("I hear you")
    assert len(plan.spokenText) <= 450


def test_quick_answer_stays_untouched() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.displayText = "The capital of Nepal is **Kathmandu**, babe!"
    plan.spokenText = "The capital of Nepal is Kathmandu, babe!"

    _apply_response_quality_guard(plan, user_text="what is the capital of Nepal?")

    assert "Kathmandu" in plan.displayText
    assert "Kathmandu" in plan.spokenText


def test_deep_dive_request_keeps_its_length() -> None:
    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    deep_answer = " ".join(
        f"Architecture section {i} explains a distinct consensus trade-off in detail."
        for i in range(40)
    )
    plan.displayText = deep_answer
    plan.spokenText = deep_answer

    _apply_response_quality_guard(
        plan, user_text="give me an in-depth system design walkthrough of the trade-offs"
    )

    assert len(plan.displayText) > 900
    # Voice still gets a bound even on deep asks -- she never lectures aloud.
    assert len(plan.spokenText) <= 900


def test_tool_turn_display_is_not_trimmed() -> None:
    from hinaa_api.models import ToolRequest

    plan = neutral_fallback_plan(
        user_text="hello", companion_id="hinaa", language="mixed"
    )
    plan.toolRequests = [
        ToolRequest(toolName="design_website", parameters={"brief": "gym"})
    ]
    plan.displayText = "Building the website for my gym. " + ("Details follow here. " * 60)
    plan.spokenText = "Building the website for my gym."

    _apply_response_quality_guard(plan, user_text="build me a website for my gym")

    assert len(plan.displayText) > 700
