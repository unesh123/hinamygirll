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

    assert plan.spokenText == "I’ve put the key details in chat, babe."
