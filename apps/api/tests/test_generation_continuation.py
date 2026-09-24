"""Tests for the coherent long-form generation engine (Phase B1).

Covers directive §2–§6, §37, §39, §43, §55:
- continuation detection (finish reasons, structure, bounded stops)
- seam deduplication (exact/normalized overlap)
- consistency pass (fence repair, placeholder/heading reports)
- config validation (dangerous combos clamped, profiles)
- provider budgets (a multi-segment generation is not capped by one call's window)
- voice planner (semantic types, no mid-thought cuts)
"""

from __future__ import annotations

import os
import re

import pytest


from hinaa_api.generation.continuation import (
    CollapseGuard,
    ContinuationReason,
    ContinuationStatus,
    GenerationContinuationState,
    SeamGuard,
    _count_unbalanced,
    detect_collapse,
    detect_continuation_need,
    run_consistency_pass,
    seam_dedup,
    word_count,
)
from hinaa_api.generation.continuation_contract import (
    ContinuationRequest,
    render_continuation_prompt,
)
from hinaa_api.generation.orchestrator import GenerationOrchestrator
from hinaa_api.prompts.depth import depth_guidance, depth_word_floor, depth_words


# ---------------------------------------------------------------------------
# Continuation detection
# ---------------------------------------------------------------------------


class TestDetectContinuationNeed:
    def test_complete_text_does_not_continue(self) -> None:
        text = "This is a complete paragraph.\n\n## Section\n\nMore prose. Done."
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED

    def test_a_wavy_dash_closes_a_casual_reply(self) -> None:
        """Measured: a casual turn ended "…for you right now~", carried no
        terminal punctuation by the old rule, and the orchestrator spent three
        more provider calls writing a fresh greeting each time."""
        for tail in (
            "I'll get those Tokyo Ghoul pics for you right now~",
            "今から探してくるね〜",
            "One sec for the wallpapers～",
        ):
            decision = detect_continuation_need(
                text=tail,
                finish_reason="STOP",
                char_budget=100_000,
                segment_number=1,
                max_segments=5,
            )
            assert not decision.continue_needed, tail

    def test_a_word_cut_in_half_still_continues(self) -> None:
        decision = detect_continuation_need(
            text="Here are the Tokyo Ghoul pictur",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed

    def test_an_unfinished_casual_tail_does_not_buy_another_call(self) -> None:
        """Measured: a 62-word chat reply ran 9 segments and ended TRUNCATED on
        "max segments budget reached" because its tail never carried a full stop
        while no length contract existed to satisfy."""
        text = "Let me search that for you right now, babe!  Here are the pics for Tokyo Ghoul"
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed

    def test_the_same_tail_still_continues_when_a_contract_is_unmet(self) -> None:
        text = "Let me search that for you right now, babe!  Here are the pics for Tokyo Ghoul"
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            min_words=4_900,
        )
        assert decision.continue_needed
        assert ContinuationReason.INCOMPLETE_SENTENCE in decision.reason_ids

    def test_a_casual_reply_with_no_finished_sentence_still_continues(self) -> None:
        decision = detect_continuation_need(
            text="Right so the reason that reply kept going was",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed

    def test_finish_reason_max_tokens_triggers_continuation(self) -> None:
        text = "The architecture layer handles retrieval, and the memory subsystem"
        decision = detect_continuation_need(
            text=text,
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert ContinuationReason.FINISH_REASON_MAX_TOKENS in decision.reason_ids

    def test_open_code_fence_continues(self) -> None:
        text = "Here is the config:\n\n```python\nvalue = 1\n"
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert ContinuationReason.OPEN_CODE_FENCE in decision.reason_ids

    def test_mid_word_continues(self) -> None:
        text = "The implementation continu"
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert ContinuationReason.INCOMPLETE_SENTENCE in decision.reason_ids

    def test_open_json_structure_continues(self) -> None:
        text = "Here is the manifest:\n\n{\"name\": \"hinaa\", \"sections\": ["
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert ContinuationReason.OPEN_JSON_STRUCTURE in decision.reason_ids

    def test_json_inside_fence_does_not_flag_braces(self) -> None:
        text = 'Config:\n\n```json\n{"a": 1}\n```\n\nThat is all you need. Done.'
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert ContinuationReason.OPEN_JSON_STRUCTURE not in decision.reason_ids

    def test_an_unclosed_invented_call_does_not_buy_another_segment(self) -> None:
        """Measured live: the model wrote `<|tool_call_section_begin|>`
        `<|tool_call|>function_call[name="pdf_generate"]` plus a whole document
        as its argument and stopped of its own accord. The pass resumed it
        eight times — every segment reporting "unbalanced braces outside code
        fences (depth 1)" — and the browser had given up minutes earlier."""
        text = (
            "I'd love to help you with that! Let me create a comprehensive PDF "
            "on quantum computing for you right away.\n\n"
            "<|" + "tool_call_section_begin|" + "><|" + "tool_call|" + ">"
            'function_call[name="pdf_generate"]<arg_key>content</arg_key>'
            "<arg_value># Quantum Computing\n\nQubits superpose.\n\nRegister: {" "alpha\n"
        )
        assert _count_unbalanced(text)[1] > 0  # the runaway evidence, still there
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED

    def test_a_call_cut_off_by_the_token_cap_still_continues(self) -> None:
        """Same shape, but the provider says it ran out of room: here the call
        really was interrupted mid-argument and resuming it is correct."""
        text = (
            "One sec!\n\n<|" + "tool_call|" + ">"
            'function_call[name="pdf_generate"]<arg_key>content</arg_key><arg_value>{"a":'
        )
        decision = detect_continuation_need(
            text=text,
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert ContinuationReason.FINISH_REASON_MAX_TOKENS in decision.reason_ids

    def test_a_closed_invented_call_leaves_the_brace_rule_alone(self) -> None:
        text = (
            "Here is the manifest:\n\n"
            "<tool_call>" + 'name="pdf_generate"' + "</tool_" + "call" + ">\n\n"
            'It reads {"name": "hinaa", "sections": ['
        )
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            min_words=4_900,
        )
        assert ContinuationReason.OPEN_JSON_STRUCTURE in decision.reason_ids

    def test_a_fence_surviving_a_resume_does_not_buy_another_one(self) -> None:
        """Measured live on "write me a pdf about black holes": segments 1-8 each
        resumed for nothing but "odd number of ``` fences", adding 86,384
        characters before the budget ran out, while the browser's connection had
        already died. A model that quoted something and never closed the fence is
        not interrupted -- and the consistency pass appends the missing fence."""
        first = "# Black Holes\n\nA star collapses.\n\n```text\nSpaghettification is real.\n"
        opening = detect_continuation_need(
            text=first,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
        )
        assert ContinuationReason.OPEN_CODE_FENCE in opening.reason_ids

        second = detect_continuation_need(
            text=first + "\nTidal forces stretch the body. Done.\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=2,
            max_segments=9,
            previous_evidence=opening.evidence,
        )
        assert not second.continue_needed
        assert second.status == ContinuationStatus.COMPLETED
        assert second.evidence.no_progress_resume
        assert "repair" in second.reason

    def test_unbalanced_braces_surviving_a_resume_also_stop(self) -> None:
        """The other half of the same nine-segment turn: once a resume proved it
        cannot close the block, the eighth resume proves nothing new."""
        first = "Manifest:\n\n{\"name\": \"hinaa\", \"sections\": [\n"
        opening = detect_continuation_need(
            text=first,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
        )
        assert ContinuationReason.OPEN_JSON_STRUCTURE in opening.reason_ids

        again = detect_continuation_need(
            text=first + "{\"title\": \"Intro\"},\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=2,
            max_segments=9,
            previous_evidence=opening.evidence,
        )
        assert not again.continue_needed
        assert again.evidence.no_progress_resume

    def test_the_depth_contract_outranks_a_stuck_fence(self) -> None:
        text = "# Report\n\nIntro.\n\n```text\nQuoted.\n\nMore prose.\n"
        opening = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
            min_words=4_900,
        )
        again = detect_continuation_need(
            text=text + "A further paragraph.\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=2,
            max_segments=9,
            min_words=4_900,
            previous_evidence=opening.evidence,
        )
        assert again.continue_needed
        assert not again.evidence.no_progress_resume

    def test_a_cap_cut_is_never_no_progress(self) -> None:
        text = "# Black Holes\n\nA star collapses.\n\n```text\nSpaghettificatio"
        opening = detect_continuation_need(
            text=text,
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
        )
        again = detect_continuation_need(
            text=text + "n is real.\n\nMore abo",
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=2,
            max_segments=9,
            previous_evidence=opening.evidence,
        )
        assert again.continue_needed
        assert ContinuationReason.FINISH_REASON_MAX_TOKENS in again.reason_ids

    def test_the_guard_tracks_the_construct_that_stayed_open(self) -> None:
        """Fence closed and braces opened in the same resume: that IS progress,
        so the guard must not fire on it."""
        opening = detect_continuation_need(
            text="Config:\n\n```json\n{\"a\": 1}\n\nEnds here.\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=9,
        )
        assert opening.evidence.open_fence
        assert not opening.evidence.open_json

        again = detect_continuation_need(
            text="Config:\n\n```json\n{\"a\": 1}\n\nEnds here.\n```\n\nIt reads {\"x\": 1\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=2,
            max_segments=9,
            previous_evidence=opening.evidence,
        )
        assert again.continue_needed
        assert ContinuationReason.OPEN_JSON_STRUCTURE in again.reason_ids

    def test_incomplete_table_row_continues(self) -> None:
        text = (
            "| Feature | Status |\n"
            "|---------|--------|\n"
            "| Memory  | Done   |\n"
            "| Router  | In pro"
        )
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed

    def test_complete_table_does_not_continue(self) -> None:
        text = (
            "| Feature | Status |\n"
            "|---------|--------|\n"
            "| Memory  | Done   |\n"
            "| Router  | Done   |"
        )
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        # A complete table followed by nothing else still ends without
        # terminal punctuation, but does NOT flag table incompleteness.
        assert ContinuationReason.INCOMPLETE_TABLE not in decision.reason_ids

    def test_emoji_ending_and_conversational_closing_does_not_continue(self) -> None:
        text = "That report is fully documented now, babe. Just say the word. 💜"
        decision = detect_continuation_need(
            text=text,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED

    def test_max_segments_bounds_stop_as_truncated(self) -> None:
        decision = detect_continuation_need(
            text="incomplete tail without punctuation",
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=5,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.TRUNCATED

    def test_char_budget_bounds_stop_as_truncated(self) -> None:
        decision = detect_continuation_need(
            text="x" * 100,
            finish_reason="STOP",
            char_budget=50,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.TRUNCATED

    def test_missing_planned_sections_flags_only_with_other_signal(self) -> None:
        complete = "# Alpha\n\nDone text.\n\n# Beta\n\nAlso done."
        decision = detect_continuation_need(
            text=complete,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            planned_sections=("Alpha", "Beta", "Gamma"),
        )
        # Complete prose with natural stop: do NOT chase missing sections
        # (avoids unnecessary extra generations — §4).
        assert not decision.continue_needed

        truncated = "# Alpha\n\nPartial text that stops here"
        decision2 = detect_continuation_need(
            text=truncated,
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            planned_sections=("Alpha", "Beta", "Gamma"),
        )
        assert decision2.continue_needed
        assert ContinuationReason.MISSING_REQUESTED_SECTIONS in decision2.reason_ids

    def test_p014_edge_case_1_done_emoji_natural_stop_completes(self) -> None:
        """1. 'Done. 💜' -> complete on natural STOP"""
        decision = detect_continuation_need(
            text="Your report is completely finished and verified. Done. 💜",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED
        assert decision.evidence.natural_stop

    def test_p014_edge_case_2_done_emoji_max_tokens_remaining_section_continues(self) -> None:
        """2. 'Done. 💜' + MAX_TOKENS + remaining section -> CONTINUE"""
        decision = detect_continuation_need(
            text="# Section 1\nDone with part 1. Done. 💜",
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            remaining_sections=("Section 2",),
        )
        assert decision.continue_needed
        assert decision.status == ContinuationStatus.ACTIVE
        assert decision.evidence.max_tokens
        assert "Section 2" in decision.evidence.remaining_sections

    def test_p014_edge_case_3_let_me_know_all_sections_complete_stop_completes(self) -> None:
        """3. 'Let me know.' + all sections complete + STOP -> complete"""
        decision = detect_continuation_need(
            text="# Section 1\nContent.\n# Section 2\nContent.\nThat is everything. Let me know.",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            remaining_sections=(),
            planned_sections=("Section 1", "Section 2"),
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED
        assert decision.evidence.conversational_closing

    def test_p014_edge_case_4_let_me_know_section_7_missing_continues(self) -> None:
        """4. 'Let me know.' + section 7 missing -> continue"""
        decision = detect_continuation_need(
            text="# Section 1\nContent.\n# Section 2\nContent.\nThat is all so far. Let me know.",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
            remaining_sections=("Section 7",),
        )
        assert decision.continue_needed
        assert decision.status == ContinuationStatus.ACTIVE
        assert "Section 7" in decision.evidence.remaining_sections

    def test_p014_edge_case_5_conclusion_open_code_fence_continues(self) -> None:
        """5. 'Conclusion.' + open code fence -> continue/repair"""
        decision = detect_continuation_need(
            text="```python\ndef test():\n    pass\nConclusion.",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert decision.status == ContinuationStatus.ACTIVE
        assert decision.evidence.open_fence

    def test_p014_edge_case_6_no_punctuation_emoji_stop_conversational_closing(self) -> None:
        """6. 'No punctuation 💜' + STOP + conversational closing phrase -> may complete"""
        decision = detect_continuation_need(
            text="I will always be right here for you, just say the word 💜",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED
        assert decision.evidence.conversational_closing

    def test_p014_edge_case_7_no_punctuation_max_tokens_continues(self) -> None:
        """7. 'No punctuation' + MAX_TOKENS -> continue"""
        decision = detect_continuation_need(
            text="The architecture requires four key subsystems including the memory bus",
            finish_reason="MAX_TOKENS",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert decision.continue_needed
        assert decision.status == ContinuationStatus.ACTIVE
        assert decision.evidence.max_tokens


# ---------------------------------------------------------------------------
# Depth contract (written length the response-depth prompt promised)
# ---------------------------------------------------------------------------


def _prose(words: int) -> str:
    """Exactly `words` whole words, ending on a clean sentence boundary."""
    unit = (
        "The routing layer balances requests across the configured brains "
        "while the memory store keeps every verified turn safe"
    ).split()
    body = (unit * (words // len(unit) + 1))[: max(words - 1, 0)]
    return " ".join(body + ["complete."])


class TestDepthContract:
    def test_clean_stop_below_the_floor_continues(self) -> None:
        """The failure the old detector could not see: nothing broken, just thin."""
        decision = detect_continuation_need(
            text=_prose(480),
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=8,
            min_words=1_000,
        )
        assert decision.continue_needed
        assert ContinuationReason.DEPTH_CONTRACT_UNMET in decision.reason_ids
        assert decision.evidence.shallow_vs_contract
        assert decision.evidence.words_short == 520

    def test_meeting_the_floor_stops(self) -> None:
        decision = detect_continuation_need(
            text=_prose(1_100),
            finish_reason="STOP",
            char_budget=1_000_000,
            segment_number=1,
            max_segments=8,
            min_words=1_000,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.COMPLETED
        assert not decision.evidence.shallow_vs_contract
        assert decision.evidence.words_short == 0

    def test_no_floor_keeps_the_old_verdict(self) -> None:
        """Callers that pass no contract must behave exactly as before."""
        short = "Everything about the memory subsystem is working as designed."
        without = detect_continuation_need(
            text=short,
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=5,
        )
        assert not without.continue_needed
        assert not without.evidence.shallow_vs_contract

    def test_structural_damage_is_not_stacked_with_the_contract(self) -> None:
        """An unclosed fence already forces a continuation; don't add a second cause."""
        decision = detect_continuation_need(
            text="Here is the config:\n\n```python\nvalue = 1\n",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=8,
            min_words=1_000,
        )
        assert decision.continue_needed
        assert ContinuationReason.OPEN_CODE_FENCE in decision.reason_ids
        assert ContinuationReason.DEPTH_CONTRACT_UNMET not in decision.reason_ids

    def test_segment_budget_still_bounds_expansion(self) -> None:
        """The contract must never override the hard budget."""
        decision = detect_continuation_need(
            text=_prose(200),
            finish_reason="STOP",
            char_budget=1_000_000,
            segment_number=8,
            max_segments=8,
            min_words=4_900,
        )
        assert not decision.continue_needed
        assert decision.status == ContinuationStatus.TRUNCATED

    def test_the_promised_numbers_are_the_enforced_numbers(self) -> None:
        """The prompt renders the same table the orchestrator enforces against.

        Pinned here because a silent edit to one side would either promise an
        essay and accept a paragraph, or the other way round.
        """
        assert depth_words("explanatory") == (1_000, 2_000)
        assert depth_words("report") == (4_900, 5_000)
        assert "1,000-2,000 words" in depth_guidance("explanatory", "chat")
        assert "4,900-5,000+ words" in depth_guidance("report", "chat")

    def test_the_short_reply_classes_have_no_contract(self) -> None:
        """A floor on `minimal` would turn "I love you too" into an essay."""
        for depth in ("minimal", "conversational", "procedural", "supportive", "clarification"):
            assert depth_word_floor(depth) == 0, depth

    def test_a_closing_offer_does_not_defeat_the_contract(self) -> None:
        """A real shallow answer ended with an offer to continue and stopped."""
        decision = detect_continuation_need(
            text=_prose(470) + "\n\nLet me know if you want me to walk any layer in more detail.",
            finish_reason="STOP",
            char_budget=100_000,
            segment_number=1,
            max_segments=8,
            min_words=1_000,
        )
        assert decision.continue_needed
        assert decision.evidence.conversational_closing
        assert ContinuationReason.DEPTH_CONTRACT_UNMET in decision.reason_ids


# ---------------------------------------------------------------------------
# Depth contract enforced end-to-end
# ---------------------------------------------------------------------------


def _unique_prose(words: int, tag: str) -> str:
    """Prose with no repeated sentence, so seam dedup cannot eat fixture text."""
    out: list[str] = []
    written = 0
    i = 0
    while written < words:
        i += 1
        sentence = f"{tag} detail {i} records the measured behaviour of subsystem {i} completely."
        out.append(sentence)
        written += len(sentence.split())
    return " ".join(out)


class TestDepthContractEnforcement:
    def test_shortfall_helper_reports_real_numbers(self) -> None:
        orchestrator = GenerationOrchestrator(
            max_continuations=8,
            char_budget=65_536,
            generation_id="floor",
            min_words=1_000,
        )
        assert orchestrator.words_short(_prose(480)) == 520
        assert orchestrator.words_short(_prose(1_100)) == 0
        assert orchestrator.trace.depth_floor_words == 1_000

    def test_no_floor_means_no_shortfall(self) -> None:
        orchestrator = GenerationOrchestrator(
            max_continuations=8,
            char_budget=65_536,
            generation_id="unbounded",
        )
        assert orchestrator.words_short("a short answer") == 0

    def test_continuation_prompt_carries_the_length_contract(self) -> None:
        rendered = render_continuation_prompt(
            ContinuationRequest(
                generation_id="g1",
                segment_number=2,
                original_goal="Explain the current state of Hina.",
                previous_tail="### Routing\n\nThe gateway selects a brain.",
                remaining_words=463,
            )
        )
        assert "STILL LEFT TO COVER" in rendered
        assert "463 more words" in rendered

    def test_length_contract_omitted_when_nothing_is_missing(self) -> None:
        rendered = render_continuation_prompt(
            ContinuationRequest(
                generation_id="g1",
                segment_number=2,
                original_goal="Explain the current state of Hina.",
                previous_tail="### Routing\n\nThe gateway selects a brain.",
            )
        )
        assert "STILL LEFT TO COVER" not in rendered

    def test_gemini_resume_is_framed_as_his_ask_not_as_a_directive(self) -> None:
        """The brain that actually answers in production refused him over this text.

        Measured on a live image turn: "it's an injected instruction trying to get
        me to pad a response to hit an artificial word count, and that's not
        something I'll do." A capitalised imperative about an unmet contract reads
        as injection to a hardened model — and the canonical prompt already tells
        her never to mention contracts, so the two directives fought and the
        refusal won. The shortfall still has to reach her; only its framing moves.
        """
        from types import SimpleNamespace

        from hinaa_api.providers.gemini import _build_continuation_contents

        draft = _prose(400)
        prompt = SimpleNamespace(
            response_depth="report", attachments=[], user_contents="Explain the pipeline."
        )
        text = _build_continuation_contents(prompt, draft)[-1].text

        assert "contract" not in text.lower()
        assert "LENGTH" not in text
        assert "He asked for" in text
        assert f"{depth_word_floor('report') - word_count(draft):,} more words" in text

    @pytest.mark.asyncio
    async def test_shallow_answer_is_continued_to_the_floor(self) -> None:
        """A report that stopped cleanly at a fraction of its promised length must keep going."""
        first = _prose(480)
        floor = depth_word_floor("explanatory")
        assert word_count(first) < floor

        async def first_stream():
            yield first

        seen_priors: list[str] = []

        def cont_factory(prior: str):
            seen_priors.append(prior)
            holder = {"value": "stop"}

            async def gen():
                yield " " + _unique_prose(1_500, "Appendix")

            return gen(), holder

        deltas: list[str] = []

        async def emit(d: str) -> None:
            deltas.append(d)

        orchestrator = GenerationOrchestrator(
            max_continuations=8,
            char_budget=65_536,
            generation_id="shallow-report",
            min_words=floor,
        )
        outcome = await orchestrator.run(
            first_segment_stream=first_stream(),
            first_finish_reason_holder={"value": "stop"},
            continuation_stream_factory=cont_factory,
            emit_delta=emit,
        )

        assert outcome.segments == 2, "a natural stop below the floor must still continue"
        assert word_count(outcome.text) >= floor
        assert "Appendix detail 1" in outcome.text
        # The provider was told the real shortfall, not a fixed guess.
        assert orchestrator.words_short(seen_priors[0]) > 0
        # Everything the model wrote reached the UI, including the expansion.
        assert "".join(deltas).strip() == outcome.text

    @pytest.mark.asyncio
    async def test_without_a_floor_a_clean_stop_is_one_segment(self) -> None:
        async def first_stream():
            yield _prose(480)

        called = False

        def cont_factory(prior: str):
            nonlocal called
            called = True
            holder = {"value": "stop"}

            async def gen():
                yield "should not be requested"

            return gen(), holder

        async def emit(d: str) -> None:
            return None

        orchestrator = GenerationOrchestrator(
            max_continuations=8,
            char_budget=65_536,
            generation_id="no-floor",
        )
        outcome = await orchestrator.run(
            first_segment_stream=first_stream(),
            first_finish_reason_holder={"value": "stop"},
            continuation_stream_factory=cont_factory,
            emit_delta=emit,
        )
        assert outcome.segments == 1
        assert not called


# ---------------------------------------------------------------------------
# State model
# ---------------------------------------------------------------------------


class TestGenerationContinuationState:
    def test_register_segment_accumulates(self) -> None:
        state = GenerationContinuationState(generation_id="g1", max_segments=3)
        state.register_segment(1_000)
        state.register_segment(2_000)
        assert state.segment_number == 2
        assert state.character_count == 3_000
        assert state.can_continue()

    def test_can_continue_stops_at_max_segments(self) -> None:
        state = GenerationContinuationState(generation_id="g1", max_segments=2)
        state.register_segment(10)
        state.register_segment(10)
        assert not state.can_continue()

    def test_can_continue_stops_at_char_budget(self) -> None:
        state = GenerationContinuationState(generation_id="g1", char_budget=100)
        state.register_segment(150)
        assert not state.can_continue()

    def test_failed_status_blocks_continuation(self) -> None:
        state = GenerationContinuationState(generation_id="g1")
        state.status = ContinuationStatus.FAILED
        assert not state.can_continue()


# ---------------------------------------------------------------------------
# Seam deduplication
# ---------------------------------------------------------------------------


class TestSeamDedup:
    def test_exact_overlap_removed(self) -> None:
        prev = "Memory retrieval should prioritize relevance over recency because users need current answers."
        nxt = "Memory retrieval should prioritize relevance over recency because users need current answers. Next section begins here."
        cleaned = seam_dedup(prev, nxt)
        assert cleaned.startswith("Next section begins here.")
        assert "Memory retrieval should prioritize" not in cleaned

    def test_normalized_overlap_with_punctuation_difference(self) -> None:
        prev = "The system stores facts, entities, and assets."
        nxt = "The system stores facts entities and assets.  Continuing with more detail."
        cleaned = seam_dedup(prev, nxt)
        assert cleaned.startswith("Continuing")

    def test_short_overlap_preserved(self) -> None:
        prev = "He said yes."
        nxt = "Yes, and then the plan was approved."
        cleaned = seam_dedup(prev, nxt)
        # Overlap is 1 word (< min_words=6): must NOT be stripped.
        assert cleaned == nxt

    def test_no_overlap_untouched(self) -> None:
        prev = "Completely different ending sentence here."
        nxt = "A brand new paragraph starts with fresh words."
        assert seam_dedup(prev, nxt) == nxt

    def test_partial_overlap_below_threshold_kept(self) -> None:
        prev = "one two three four five"
        nxt = "four five six seven eight nine ten."
        cleaned = seam_dedup(prev, nxt)
        assert cleaned == nxt


class TestSeamGuard:
    def test_first_segment_streams_verbatim(self) -> None:
        guard = SeamGuard("")  # no previous tail
        out = guard.feed("Hello ")
        out += guard.feed("world.")
        out += guard.finish_segment()
        assert out == "Hello world."

    def test_overlap_suppressed_across_feed(self) -> None:
        overlap = "Memory retrieval should prioritize relevance over recency."
        prev_tail = f"...some long prior text {overlap}"
        guard = SeamGuard(prev_tail)
        seg = f"{overlap} The next paragraph discusses storage formats in detail."
        # Feed the segment in small deltas like a real stream.
        out = ""
        step = 40
        for i in range(0, len(seg), step):
            out += guard.feed(seg[i : i + step])
        out += guard.finish_segment()
        assert out.startswith("The next paragraph")
        assert out.count("Memory retrieval should prioritize") == 0

    def test_after_resolution_deltas_stream_through(self) -> None:
        guard = SeamGuard("previous tail with several words in it")
        _ = guard.feed("A sufficiently long opening that resolves the seam quickly.")
        assert guard.resolved
        out = guard.feed("more text")
        assert out == "more text"


# ---------------------------------------------------------------------------
# Degenerate repetition collapse (#71)
# ---------------------------------------------------------------------------


def _stream_through_guard(text: str, *, step: int = 9) -> str:
    """Feed `text` in delta-sized chunks the way a provider stream does."""
    guard = CollapseGuard()
    released = ""
    for i in range(0, len(text), step):
        released += guard.feed(text[i : i + step])
        if guard.collapsed:
            break
    return released + guard.finish()


class TestCollapseDetector:
    def test_a_glyph_spray_is_a_run(self) -> None:
        run = detect_collapse(_unique_prose(8, "Head") + " " + "固" * 300)
        assert run is not None
        assert run.unit == "固"
        assert run.chars >= 30

    def test_a_short_phrase_spray_is_a_run(self) -> None:
        run = detect_collapse("measured behaviour:" + " the answer is" * 20)
        assert run is not None
        assert run.unit == " the answer is"

    def test_punctuation_runs_are_not_collapse(self) -> None:
        for text in ("-" * 60, "." * 40, "| " * 40, "\n\n\n\n" * 20):
            assert detect_collapse(text) is None, text[:12]

    def test_honest_emphasis_is_not_collapse(self) -> None:
        assert detect_collapse("No way, hahahahaha!") is None
        assert detect_collapse(_unique_prose(40, "Section")) is None

    def test_a_run_that_already_stopped_is_history(self) -> None:
        # The loop ended and real prose followed, so nothing at the tail is a run.
        assert detect_collapse("固" * 200 + " and here is the closing sentence.") is None


class TestCollapseGuard:
    def test_the_loop_never_reaches_the_reader(self) -> None:
        answer = _unique_prose(30, "Reply") + " " + "固" * 4_000
        released = _stream_through_guard(answer)
        assert "固" not in released
        assert released.rstrip() == _unique_prose(30, "Reply").rstrip()

    def test_real_content_before_the_run_is_kept(self) -> None:
        guard = CollapseGuard()
        answer = _unique_prose(12, "Kept") + " " + "啦" * 200
        out = ""
        for i in range(0, len(answer), 7):
            out += guard.feed(answer[i : i + 7])
            if guard.collapsed:
                break
        assert out == _unique_prose(12, "Kept") + " "
        # Only what had already been fed counts as suppressed: the caller stops
        # consuming the stream once the run is confirmed, which is the point.
        assert 14 <= guard.suppressed_chars <= CollapseGuard.HOLD_CHARS

    def test_a_clean_answer_is_released_in_full(self) -> None:
        answer = _unique_prose(25, "Whole") + " Thanks for asking, love you."
        assert _stream_through_guard(answer) == answer

    def test_repeated_letters_a_reader_wants_are_kept(self) -> None:
        answer = "Okay, hahahahaha! You got me good."
        assert _stream_through_guard(answer) == answer

    def test_an_answer_that_is_only_the_loop_is_not_called_a_reply(self) -> None:
        assert _stream_through_guard("固" * 1_000) == ""

    def test_the_cut_lands_at_the_run_not_a_window_early(self) -> None:
        # HOLD_CHARS must not swallow the sentence that came before the loop.
        head = _unique_prose(8, "Exact")
        guard = CollapseGuard()
        out = guard.feed(head + " " + "嗯" * 40)
        assert out == head + " "
        assert "嗯" not in out


class TestConsistencyPassCollapse:
    def test_a_trailing_run_is_cut_from_the_canonical_text(self) -> None:
        text = _unique_prose(20, "Doc") + "\n" + "ha" * 60
        report = run_consistency_pass(text)
        kinds = {i.kind for i in report.issues}
        assert "DEGENERATE_COLLAPSE" in kinds
        assert "ha" * 60 not in report.text
        assert report.text.rstrip() == _unique_prose(20, "Doc").rstrip()

    def test_the_run_is_reported_even_when_not_repaired(self) -> None:
        text = "Final line of substance.\n" + "ok " * 40
        report = run_consistency_pass(text, apply_repairs=False)
        flagged = [i for i in report.issues if i.kind == "DEGENERATE_COLLAPSE"]
        assert flagged and not flagged[0].repaired
        assert report.text == text

    def test_a_fence_under_a_run_is_still_closed(self) -> None:
        text = "```python\nx = 1\n" + "固" * 200
        report = run_consistency_pass(text)
        assert "DEGENERATE_COLLAPSE" in {i.kind for i in report.issues}
        assert "OPEN_CODE_FENCE" in {i.kind for i in report.issues}
        assert report.text.rstrip().endswith("```")


class TestOrchestratorCollapse:
    """#71 end to end. The loop must not reach `emit_delta` (that is what the
    chat bubble renders), and a brain that collapsed must not be asked to
    resume — each resume was another provider call that looped again."""

    @pytest.mark.asyncio
    async def test_a_collapsed_stream_is_never_emitted_and_buys_no_resume(self) -> None:
        seen: list[str] = []
        resumes = 0

        async def first_stream():
            yield _unique_prose(20, "Real") + " "
            for _ in range(60):
                yield "固" * 20

        def cont_factory(prior: str):
            nonlocal resumes
            resumes += 1

            async def gen():
                yield "this should never be asked for"

            return gen(), {"value": "stop"}

        async def emit(d: str) -> None:
            seen.append(d)

        orchestrator = GenerationOrchestrator(
            max_continuations=4,
            char_budget=200_000,
            generation_id="collapse",
        )
        outcome = await orchestrator.run(
            first_segment_stream=first_stream(),
            first_finish_reason_holder={"value": "length"},
            continuation_stream_factory=cont_factory,
            emit_delta=emit,
        )
        assert "固" not in "".join(seen)
        assert "固" not in outcome.text
        assert outcome.text.startswith("Real detail 1")
        assert resumes == 0
        assert outcome.status == ContinuationStatus.TRUNCATED
        assert outcome.trace.segments[-1].decision_reason == "degenerate_collapse"
        # Raw model text still carries the loop for diagnostics.
        assert "固" in outcome.raw_text


# ---------------------------------------------------------------------------
# Consistency pass
# ---------------------------------------------------------------------------


class TestConsistencyPass:
    def test_open_fence_repaired_at_end(self) -> None:
        text = "Here is code:\n\n```python\nx = 1"
        report = run_consistency_pass(text)
        kinds = {i.kind for i in report.issues}
        assert "OPEN_CODE_FENCE" in kinds
        assert report.text.rstrip().endswith("```")
        assert all(i.repaired for i in report.issues if i.kind == "OPEN_CODE_FENCE")

    def test_closed_fence_not_flagged(self) -> None:
        text = "```python\nx = 1\n```\n\nDone."
        report = run_consistency_pass(text)
        assert "OPEN_CODE_FENCE" not in {i.kind for i in report.issues}

    def test_duplicated_heading_reported_unrepaired(self) -> None:
        text = "# Overview\n\nBody one.\n\n# Overview\n\nBody two."
        report = run_consistency_pass(text)
        dup = [i for i in report.issues if i.kind == "DUPLICATED_HEADING"]
        assert dup
        assert not dup[0].repaired

    def test_placeholder_reported(self) -> None:
        text = "The value is [TODO: fill this in] for now."
        report = run_consistency_pass(text)
        assert any(i.kind == "PLACEHOLDER_TEXT" for i in report.issues)

    def test_trailing_mid_word_reported_not_rewritten(self) -> None:
        text = "The implementation continu"
        report = run_consistency_pass(text)
        assert any(i.kind == "TRAILING_MID_WORD" for i in report.issues)
        # Canonical text untouched (§37) except for unambiguous fence repair.
        assert report.text == text

    def test_clean_text_no_issues(self) -> None:
        text = "# Title\n\nA complete, well-formed paragraph with punctuation."
        report = run_consistency_pass(text)
        assert report.clean


# ---------------------------------------------------------------------------
# Config validation (§43)
# ---------------------------------------------------------------------------


class TestConfigValidation:
    def test_dangerous_continuation_count_clamped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hinaa_api.config import Settings

        for key in list(os.environ):
            if key.startswith("HINAA_LLM") or key.startswith("HINAA_SESSION"):
                monkeypatch.delenv(key, raising=False)
        settings = Settings(HINAA_LLM_MAX_CONTINUATIONS="20", _env_file=None)
        assert settings.llm_max_continuations == 8
        assert any("ceiling" in c for c in settings.generation_config_corrections)

    def test_absurd_char_budget_clamped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hinaa_api.config import Settings

        for key in list(os.environ):
            if key.startswith("HINAA_LLM") or key.startswith("HINAA_SESSION"):
                monkeypatch.delenv(key, raising=False)
        settings = Settings(HINAA_LLM_STREAM_CHAR_BUDGET="10", _env_file=None)
        assert settings.llm_stream_char_budget == 1_000

    def test_sane_config_has_no_corrections(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hinaa_api.config import Settings

        for key in list(os.environ):
            if key.startswith("HINAA_LLM") or key.startswith("HINAA_SESSION"):
                monkeypatch.delenv(key, raising=False)
        settings = Settings(_env_file=None)
        assert settings.generation_config_corrections == []

    def test_profile_application_respects_existing_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hinaa_api.config import apply_config_profile

        monkeypatch.setenv("HINAA_LLM_MAX_OUTPUT_TOKENS", "12345")
        applied = apply_config_profile("MAX_QUALITY")
        assert "HINAA_LLM_MAX_OUTPUT_TOKENS" not in applied
        assert "HINAA_LLM_MAX_CONTINUATIONS" in applied

    def test_unknown_profile_noop(self) -> None:
        from hinaa_api.config import apply_config_profile

        assert apply_config_profile("NONEXISTENT_PROFILE_XYZ") == {}


# ---------------------------------------------------------------------------
# Voice planner (§32)
# ---------------------------------------------------------------------------


class TestVoiceResponsePlanner:
    def _long_doc(self) -> str:
        return "# Report\n\n" + (
            "This is a complete sentence about the system architecture we designed together. " * 30
        )

    def test_long_document_gets_executive_summary(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        vtype, text = plan_voice_response(self._long_doc(), "", is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(text) <= 950
        assert text.rstrip().endswith(("✨", "!", ".", "?"))

    def test_prompt_compliant_summary_survives_the_chat_path(self) -> None:
        """Measured before the fix: the report-depth prompt asks for 600-1,400
        characters of spoken summary, and chat's 700-character ceiling rejected
        a compliant 930-character one, replacing it with a 104-character teaser.
        Her voice went from a minute of substance to one sentence."""
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        summary = (
            "Here is the honest picture of where you stand after everything we fixed today. "
            "The runtime now gates every machine-touching tool by the real request origin "
            "instead of trusting the caller, and ten unit tests plus three live HTTP probes "
            "confirm the exploit is closed on the public tunnel. The report depth contract is "
            "enforced with a real continuation pass rather than a truncated first draft, and "
            "voice on mobile uses the production stream, so the mic and the speaker both work "
            "without the dev proxy. The avatar's lip sync needed the VRM expression names "
            "remapped before the morph targets animated at all, and private data routes still "
            "need Clerk instance keys before I can call the session genuinely authenticated. "
            "Three areas remain theater: the parallel agent cluster, the durable worker "
            "fabric, and the named tunnel. If you want, I can take those leftovers in order "
            "and finish them one at a time. 💜"
        )
        assert 850 <= len(summary) <= 1_050, len(summary)

        vtype, text = plan_voice_response(self._long_doc(), summary, is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert text == summary

    def test_closing_offer_survives_a_long_document(self) -> None:
        """Measured on production: an 8,248-character status answer ended with
        "### Exploration Paths" and a bullet asking whether he wanted the deep
        dive. Her voice spoke 694 characters and stopped on a mid-document
        bullet about colour palettes, so the offer existed on screen but was
        never said — which is the whole point of asking for it."""
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        body = (
            "Hinaa is live on Vercel with a FastAPI companion brain. "
            "The runtime gates machine-touching tools by request origin. "
        ) * 30
        display = (
            f"## Core Presence\n\n{body}\n\n"
            "### Exploration Paths\n"
            "* Would you like to dive deeper into how my tool execution pipeline "
            "handles multi-step agentic workflows, or shall we explore optimizing "
            "your current coding project right now?"
        )
        spoken = (
            "Your companion Hina is running end to end. The gateway recovers from "
            "provider drops and the depth contract holds. Core Presence: Violet-blue "
            "state palette with a crystalline core, maintaining a warm tone."
        )
        assert len(display) > 1_500

        vtype, text = plan_voice_response(display, spoken, is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert text.rstrip().endswith("?")
        assert "Would you like to dive deeper" in text
        assert "#" not in text and "*" not in text
        assert len(text) <= 1_500

    def test_a_tangent_question_does_not_outrank_the_report_offer(self) -> None:
        """Measured on production right after the first fix: the offer she spoke
        was her *last* question, which happened to be "Would you prefer a
        focused deep dive into PyTorch performance tuning?" Nothing about a
        documented report. He asked never to have to request it twice."""
        from hinaa_api.services import _closing_ask

        display = (
            "## Status\n\nThe runtime is healthy.\n\n"
            "### Paths\n"
            "* Would you like the full documented report on my architecture?\n"
            "* Would you prefer a focused deep dive into PyTorch performance tuning?"
        )
        ask = _closing_ask(display)
        assert "documented report" in ask.lower()
        assert "PyTorch" not in ask

    def test_a_thin_summary_is_not_enough_for_a_report(self) -> None:
        """Measured on production: a 39,503-character / 5,056-word report came
        back with 398 characters of speech — about 20 seconds for a 40-minute
        read. Every sentence rule passed, so the only thing that accepted it was
        chat's 40-character floor."""
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        report = (
            "The orchestration layer assigns each subtask to a worker and reconciles "
            "the results before the reply is composed. " * 200
        ) + "\n\n### Next\n* Would you like me to go deeper on the orchestration layer?"
        assert len(report) > 12_000
        thin = (
            "Your system is healthy and every layer is operational. The gateway "
            "recovers from drops and the depth contract holds firmly. "
            "Shall we examine the concurrency control primitives?"
        )
        assert len(thin) < 450

        vtype, text = plan_voice_response(report, thin, is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(text) >= 600
        assert "Would you like me to go deeper on the orchestration layer?" in text

    def test_a_document_without_a_question_keeps_the_canned_sign_off(self) -> None:
        from hinaa_api.services import plan_voice_response

        vtype, text = plan_voice_response(self._long_doc(), "", is_progress=False)
        assert text.rstrip().endswith("✨")

    def test_long_document_never_repeats_spoken_recitation(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        recitation = "I will now read you the whole document. " * 20
        vtype, text = plan_voice_response(self._long_doc(), recitation, is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert "read you the whole document" not in text

    def test_short_chat_kept_verbatim(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        msg = "Hey, I finished the setup for you!"
        vtype, text = plan_voice_response(msg, msg, is_progress=False)
        assert vtype == VoiceResponseType.SHORT_FULL
        assert text == msg

    def test_question_preserved(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        q = "Should I use the dark theme for your dashboard?"
        vtype, text = plan_voice_response(q, q, is_progress=False)
        assert vtype == VoiceResponseType.QUESTION
        assert text.endswith("?")

    def test_live_report_ignores_a_thin_model_summary(self) -> None:
        """A live call has no second surface, so a lead-in is not a summary."""
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        thin = (
            "I wrote you a full report on every subsystem, her providers, "
            "her tools, and her limits. " * 4
        )
        assert 320 <= len(thin) < 600
        vtype, text = plan_voice_response(
            self._long_doc(), thin, is_progress=False, live=True
        )
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(text) > len(thin)
        # Measured run-on: "...current limitations Want me to walk you…".
        assert re.search(r"[.!?:] Want me to walk", text), text

    def test_error_path_safe_fallback(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        vtype, text = plan_voice_response("", "", has_error=True)
        assert vtype == VoiceResponseType.ERROR
        assert "error" in text.lower() or "wrong" in text.lower()

    def test_completion_pdf(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        vtype, text = plan_voice_response("big doc", "", has_pdf=True)
        assert vtype == VoiceResponseType.COMPLETION
        assert "PDF" in text

    def test_live_voice_rejects_a_lead_in_as_the_whole_answer(self) -> None:
        """Measured live: a 125-char warm-up over a 3,145-char report became her
        entire spoken reply, so she stopped after one sentence."""
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        teaser = (
            "Great question, babe. Let me be completely honest with you about how "
            "my memory and learning system actually works — no fluff."
        )
        vtype, text = plan_voice_response(
            self._long_doc(), teaser, is_progress=False, live=True
        )
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert len(text) > 600, "live voice must carry substance, not a warm-up"
        # The same turn in chat may stay terse — the display text carries content.
        _, chat_text = plan_voice_response(self._long_doc(), teaser, is_progress=False)
        assert len(chat_text) < 400

    def test_question_fallback_never_speaks_markdown(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        doc = "## How My Memory Works\n\n" + "Session memory is fed back to me each turn. " * 20
        vtype, text = plan_voice_response(doc + "\n\nWant the full list?", "", is_progress=False, live=True)
        assert vtype == VoiceResponseType.QUESTION
        for marker in ("##", "\n", "```"):
            assert marker not in text

    def test_no_mid_thought_cut_on_clause_truncation(self) -> None:
        from hinaa_api.services import _truncate_at_clause_boundary

        long = "First complete sentence here. Second sentence keeps going, and then it has more clauses, until it exceeds the limit entirely without stopping."
        cut = _truncate_at_clause_boundary(long, 60)
        assert len(cut) <= 61
        assert cut.endswith((".", "!", "?"))
        assert not cut.endswith(",")

    def test_truncate_respects_word_boundary(self) -> None:
        from hinaa_api.services import _truncate_at_clause_boundary

        cut = _truncate_at_clause_boundary("word " * 50, 30)
        assert not cut.endswith(" ")
        assert " " not in cut[-1:]

    def test_substantive_spoken_summary_is_preserved(self) -> None:
        from hinaa_api.services import VoiceResponseType, plan_voice_response

        spoken_summary = (
            "I've synthesized the entire 2026 infrastructure roadmap for you. "
            "All nine core subsystems are verified, real-time grounding is active, "
            "and your database migrations are fully prepared. 💜"
        )
        vtype, text = plan_voice_response(self._long_doc(), spoken_summary, is_progress=False)
        assert vtype == VoiceResponseType.EXECUTIVE_SUMMARY
        assert text == spoken_summary

    def test_voice_response_planner_class_preserves_substantive_summary(self) -> None:
        from hinaa_api.prompts.voice_response_planner import VoiceIntent, VoiceResponsePlanner

        planner = VoiceResponsePlanner()
        spoken_summary = (
            "I've synthesized the entire 2026 infrastructure roadmap for you. "
            "All nine core subsystems are verified, real-time grounding is active, "
            "and your database migrations are fully prepared. 💜"
        )
        res = planner.plan(self._long_doc(), spoken_summary)
        assert res.intent == VoiceIntent.EXECUTIVE_SUMMARY
        assert res.spoken_text == spoken_summary


# ---------------------------------------------------------------------------
# Character budget ownership
# ---------------------------------------------------------------------------


class TestProviderCharacterBudget:
    """A whole generation may span several provider calls, so its ceiling cannot
    be one call's output window. Deriving it from `max_tokens` stopped a deep
    report with `character budget reached` while the model still had segments and
    room left, which cut the last sentence in half on screen."""

    ONE_CALL_WINDOW = 16_384 * 4
    STREAM_BUDGET = 200_000

    async def _run(self, char_budget: int):
        async def first_stream():
            yield _unique_prose(6_000, "Head")

        def cont_factory(prior: str):
            holder = {"value": "stop"}

            async def gen():
                yield " " + _unique_prose(5_000, "Tail")

            return gen(), holder

        async def emit(d: str) -> None:
            return None

        orchestrator = GenerationOrchestrator(
            max_continuations=4,
            char_budget=char_budget,
            generation_id="provider-budget",
        )
        return await orchestrator.run(
            first_segment_stream=first_stream(),
            first_finish_reason_holder={"value": "max_tokens"},
            continuation_stream_factory=cont_factory,
            emit_delta=emit,
        )

    @pytest.mark.asyncio
    async def test_one_call_window_truncates_a_report_sized_draft(self) -> None:
        outcome = await self._run(self.ONE_CALL_WINDOW)
        assert outcome.trace is not None
        # The canonical text gets clamped to the budget, so the draft size that
        # triggered the stop only survives in the per-segment trace.
        assert sum(s.characters for s in outcome.trace.segments) > self.ONE_CALL_WINDOW, (
            "the fixture must straddle the one-call window to test it"
        )
        assert outcome.status == ContinuationStatus.TRUNCATED
        assert outcome.trace.segments[-1].decision_reason == "character budget reached"

    @pytest.mark.asyncio
    async def test_stream_budget_lets_the_same_draft_finish(self) -> None:
        outcome = await self._run(self.STREAM_BUDGET)
        assert len(outcome.text) > self.ONE_CALL_WINDOW
        assert outcome.status == ContinuationStatus.COMPLETED
        assert outcome.text.rstrip().endswith("completely.")

    def test_every_provider_sizes_a_generation_from_the_stream_budget(self) -> None:
        """openai_llm, agent_router and groq share one helper; gemini reads the
        same setting through `_llm_budgets()`. Both must return the ceiling for a
        whole multi-segment run, not one call's token window."""
        from hinaa_api.config import get_settings
        from hinaa_api.providers.gemini import _llm_budgets
        from hinaa_api.providers.openai_llm import (
            _llm_budget_tokens,
            _llm_stream_char_budget,
        )

        configured = int(get_settings().llm_stream_char_budget)
        one_call_window = _llm_budget_tokens() * 4
        assert _llm_stream_char_budget() == configured
        assert _llm_budgets()[1] == configured
        assert configured > one_call_window, (
            "a generation ceiling equal to one call's output window "
            "truncates a long report mid-sentence"
        )

    def test_the_openai_family_call_sites_use_that_ceiling(self) -> None:
        """The helpers being right is not enough — the fix was a call site."""
        import inspect

        from hinaa_api.providers import agent_router, openai_llm

        for module in (openai_llm, agent_router):
            passes = [
                line.strip()
                for line in inspect.getsource(module).splitlines()
                if line.strip().startswith("char_budget=")
            ]
            assert passes, f"{module.__name__} no longer builds an orchestrator"
            for line in passes:
                assert "stream_char_budget" in line, f"{module.__name__}: {line}"
