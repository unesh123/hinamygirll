"""Voice Duration Matrix Tests (Directive §28).

Tests:
1. Voice planning across all 7 semantic intents:
   - SHORT_FULL
   - QUESTION
   - EXECUTIVE_SUMMARY
   - PROGRESS_UPDATE
   - ERROR
   - COMPLETION
   - ARTIFACT_READY
2. Duration estimation function across languages and paces.
3. User preference handling:
   - brief (5–15s target)
   - normal (10–25s target)
   - detailed (30–60s target)
   - Natural language query detection ("quick version" vs "explain aloud").
"""

from __future__ import annotations

import pytest

from hinaa_api.prompts.voice_response_planner import (
    VoiceIntent,
    VoicePlanResult,
    VoiceResponsePlanner,
    estimate_speech_duration,
    infer_voice_preference,
)


class TestVoiceDurationMatrix:
    def test_estimate_speech_duration_english(self) -> None:
        # ~25 words at 2.5 wps = 10.0 seconds
        text = "This is a clean English sentence demonstrating the calculated speech duration of conversational responses produced by the frontier voice engine for the companion interface."
        words = len(text.split())
        expected = round(words / 2.5, 2)
        dur = estimate_speech_duration(text, language="en-US", pace=1.0)
        assert dur == expected
        assert 8.0 <= dur <= 12.0

        # Faster pace reduces duration
        fast_dur = estimate_speech_duration(text, language="en-US", pace=1.25)
        assert fast_dur < dur

    def test_estimate_speech_duration_devanagari(self) -> None:
        hindi_text = "नमस्ते! म तपाइँको काम पूरा गरिसकेको छु, हेर्नुहोस् र भन्नुहोस्।"
        dur = estimate_speech_duration(hindi_text, language="hi-IN", pace=1.0)
        assert dur > 0.0

    def test_infer_voice_preference(self) -> None:
        assert infer_voice_preference("can you summarize it quickly?") == "brief"
        assert infer_voice_preference("just give me the quick version") == "brief"
        assert infer_voice_preference("keep it short please") == "brief"
        assert infer_voice_preference("explain aloud in detail") == "detailed"
        assert infer_voice_preference("tell me everything aloud") == "detailed"
        assert infer_voice_preference("What is SQLite?") == "normal"

    def test_intent_short_full(self) -> None:
        planner = VoiceResponsePlanner()
        display = "I'm doing great, thanks for asking! Ready to tackle today's project together. 💜"
        res = planner.plan(display, display)
        assert res.intent == VoiceIntent.SHORT_FULL
        assert res.spoken_text == display
        assert 4.0 <= res.estimated_duration_seconds <= 15.0

    def test_intent_question(self) -> None:
        planner = VoiceResponsePlanner()
        q = "Would you like me to deploy these database migrations to production now?"
        res = planner.plan(q, q)
        assert res.intent == VoiceIntent.QUESTION
        assert res.spoken_text == q
        assert res.spoken_text.endswith("?")

    def test_intent_executive_summary_normal(self) -> None:
        planner = VoiceResponsePlanner()
        long_doc = (
            "## Architecture Review\n\n"
            "All nine core subsystems have completed deterministic verification. "
            "The memory layer guarantees durable SQLite storage across restarts, "
            "while citation pipelines ensure claim attribution against retrieved sources.\n\n"
            + ("Additional in-depth technical analysis of edge latency and telemetry streaming. " * 30)
        )
        res = planner.plan(long_doc, "", user_preference="normal")
        assert res.intent == VoiceIntent.EXECUTIVE_SUMMARY
        assert len(res.spoken_text) <= 500
        assert not res.spoken_text.startswith("Here is your")
        assert 10.0 <= res.target_duration_seconds <= 25.0
        assert res.estimated_duration_seconds > 0.0

    def test_intent_executive_summary_brief_preference(self) -> None:
        planner = VoiceResponsePlanner()
        long_doc = (
            "## Cloud Deployment Status\n\n"
            "The staging cluster deployment succeeded with zero errors. "
            "All service health checks are passing across all pods.\n\n"
            + ("Deep cluster logs and resource utilization breakdowns. " * 30)
        )
        res = planner.plan(long_doc, "", user_text="give me the quick version")
        assert res.intent == VoiceIntent.EXECUTIVE_SUMMARY
        assert len(res.spoken_text) <= 250
        assert res.target_duration_seconds == 10.0
        assert res.estimated_duration_seconds <= 18.0

    def test_intent_executive_summary_detailed_preference(self) -> None:
        planner = VoiceResponsePlanner()
        long_doc = (
            "## Research Synthesis on Quantum Algorithms\n\n"
            "We evaluated fault-tolerant quantum error correction codes across 12 topological designs. "
            "Surface codes achieved threshold error rates under 0.1%, enabling scalable logical qubit operations. "
            "Furthermore, transversal non-Clifford gates demonstrated fault tolerance when combined with magic state distillation.\n\n"
            + ("Detailed mathematical proofs and circuit simulation outputs. " * 40)
        )
        res = planner.plan(long_doc, "", user_text="explain aloud in full detail")
        assert res.intent == VoiceIntent.EXECUTIVE_SUMMARY
        assert res.target_duration_seconds == 45.0
        assert len(res.spoken_text) >= 100

    def test_intent_progress_update(self) -> None:
        planner = VoiceResponsePlanner()
        res = planner.plan("", "", is_progress=True)
        assert res.intent == VoiceIntent.PROGRESS_UPDATE
        assert "working on it" in res.spoken_text.lower()
        assert res.target_duration_seconds == 4.0

    def test_intent_error(self) -> None:
        planner = VoiceResponsePlanner()
        res = planner.plan("", "", has_error=True)
        assert res.intent == VoiceIntent.ERROR
        assert "went wrong" in res.spoken_text.lower()
        assert res.target_duration_seconds == 5.0

    def test_intent_completion_pdf_and_images(self) -> None:
        planner = VoiceResponsePlanner()
        res_pdf = planner.plan("PDF generated", "", has_pdf=True)
        assert res_pdf.intent == VoiceIntent.COMPLETION
        assert "PDF" in res_pdf.spoken_text

        res_img = planner.plan("Images generated", "", has_image=True)
        assert res_img.intent == VoiceIntent.COMPLETION
        assert "images" in res_img.spoken_text

    def test_intent_artifact_ready(self) -> None:
        planner = VoiceResponsePlanner()
        res = planner.plan("Code artifact", "", has_artifact=True, artifact_title="AuthService.ts")
        assert res.intent == VoiceIntent.ARTIFACT_READY
        assert "AuthService.ts" in res.spoken_text
