"""Tests for the coherent long-form generation engine (Phase B1).

Covers directive §2–§6, §37, §39, §43, §55:
- continuation detection (finish reasons, structure, bounded stops)
- seam deduplication (exact/normalized overlap)
- consistency pass (fence repair, placeholder/heading reports)
- config validation (dangerous combos clamped, profiles)
- voice planner (semantic types, no mid-thought cuts)
"""

from __future__ import annotations

import os
import re

import pytest


from hinaa_api.generation.continuation import (
    ContinuationReason,
    ContinuationStatus,
    GenerationContinuationState,
    SeamGuard,
    detect_continuation_need,
    run_consistency_pass,
    seam_dedup,
)


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
        assert len(text) <= 350
        assert text.rstrip().endswith(("✨", "!", ".", "?"))

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
