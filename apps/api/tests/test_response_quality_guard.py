"""Guards against degenerate padding loops in final plan text.

Measured live: a factual question carrying an explicit brevity ask ("one line
answer") was classified `explanatory`, whose 1,000-word floor forced
continuations while a fallback model padded "Tokyo, babe." into repeated
paragraphs. Two guards pin the fix: brevity asks drop the essay contract, and
back-to-back identical sentences collapse no matter how short they are.
"""

from __future__ import annotations

from hinaa_api.prompts.depth import infer_response_depth
from hinaa_api.services import _remove_repeated_passages


class TestBrevityAskDropsEssayContract:
    def test_one_line_answer_is_not_explanatory(self) -> None:
        assert (
            infer_response_depth("what is the capital of japan, one line answer", "rest")
            == "conversational"
        )

    def test_briefly_beats_explain_wording(self) -> None:
        assert (
            infer_response_depth("explain recursion briefly", "rest")
            == "conversational"
        )

    def test_brevity_ask_beats_selected_deep_mode(self) -> None:
        assert (
            infer_response_depth(
                "what is quantum entanglement, in short", "rest", "research"
            )
            == "conversational"
        )

    def test_plain_explain_keeps_explanatory_contract(self) -> None:
        assert infer_response_depth("explain recursion please", "rest") == "explanatory"

    def test_report_ask_without_brevity_stays_report(self) -> None:
        assert (
            infer_response_depth("prepare a full report on the codebase", "rest")
            == "report"
        )


class TestConsecutiveRepetitionCollapse:
    def test_back_to_back_short_sentences_collapse(self) -> None:
        text = "Tokyo, babe. Tokyo, babe. Tokyo, babe."
        assert _remove_repeated_passages(text) == "Tokyo, babe."

    def test_padding_loop_with_interleaved_detail(self) -> None:
        text = (
            "Tokyo, babe. Tokyo, babe. "
            "(It's been Japan's capital since 1868, when the court moved from Kyoto.) "
            "Tokyo, babe. Tokyo, babe. "
            "(It's been Japan's capital since 1868, when the court moved from Kyoto.)"
        )
        cleaned = _remove_repeated_passages(text)
        # The padding run collapses and the long detail keeps one copy.
        assert cleaned.count("Tokyo, babe.") <= 2
        assert cleaned.count("capital since 1868") == 1

    def test_non_consecutive_short_repeat_is_kept(self) -> None:
        # Natural speech repeats short sentences with real content between
        # them; only padding loops are removed.
        text = (
            "I love you. We talked about your day and the plans you made for "
            "tomorrow morning. I love you."
        )
        assert _remove_repeated_passages(text).count("I love you.") == 2

    def test_distinct_sentences_untouched(self) -> None:
        text = "First point stands. Second point differs. Third point closes."
        assert _remove_repeated_passages(text) == text
