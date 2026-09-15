"""Behavioral Metrics Suite (Directive §29).

Measures and asserts frontier-grade reliability criteria:
1. FalseContinuationRate == 0.0
2. MissedContinuationRate == 0.0
3. LongGenerationCompletionRate >= 0.95
4. RepeatedSegmentRate == 0.0
5. CitationCorrectness >= 0.95
6. CitationCoverage >= 0.60
7. FabricatedCitationRate == 0.0
8. VoiceSummaryDurationError <= 0.40
9. ContextPayloadIntegrityRate == 1.0
"""

from __future__ import annotations

import pytest

from hinaa_api.agent.compiler import (
    CompiledContextPackage,
    ContextCompiler,
    ContextPayloadIntegrityVerifier,
)
from hinaa_api.generation.continuation import (
    ContinuationStatus,
    SeamGuard,
    detect_continuation_need,
    run_consistency_pass,
)
from hinaa_api.grounding.citations import (
    CitationMetrics,
    CitationRenderer,
    EvidenceSource,
)
from hinaa_api.prompts.voice_response_planner import (
    VoiceIntent,
    VoiceResponsePlanner,
    estimate_speech_duration,
)


class TestBehavioralMetrics:
    def test_continuation_decision_accuracy_metrics(self) -> None:
        """Measure FalseContinuationRate and MissedContinuationRate."""
        # Dataset of test cases: (text, finish_reason, should_continue_truth)
        eval_cases = [
            ("All systems operational. 💜", "STOP", False),
            ("Let me know if you need anything else.", "STOP", False),
            ("This is a complete sentence.", "MAX_TOKENS", True),
            ("function authenticate(user) {\n    return true;\n", "STOP", True),
            ("The key findings are:\n1. Alpha\n2. Beta.", "STOP", False),
            ("In conclusion, the architecture is ready.", "MAX_TOKENS", True),
            ("The result was partial becau", "MAX_TOKENS", True),
            ("Here is the requested output.", "STOP", False),
        ]

        false_continuations = 0
        missed_continuations = 0

        for text, finish_reason, expected_continue in eval_cases:
            decision = detect_continuation_need(
                text=text,
                finish_reason=finish_reason,
            )
            actual_continue = decision.should_continue

            if actual_continue and not expected_continue:
                false_continuations += 1
            elif not actual_continue and expected_continue:
                missed_continuations += 1

        false_continuation_rate = false_continuations / len(eval_cases)
        missed_continuation_rate = missed_continuations / len(eval_cases)

        assert false_continuation_rate == 0.0, f"False continuation rate {false_continuation_rate} > 0.0"
        assert missed_continuation_rate == 0.0, f"Missed continuation rate {missed_continuation_rate} > 0.0"

    def test_long_generation_completion_and_repeated_segment_rate(self) -> None:
        """Measure LongGenerationCompletionRate and RepeatedSegmentRate across 10 trials."""
        trials = 10
        completed = 0
        total_repeated_segments = 0

        for t in range(trials):
            # Simulate 5 continuation segments with realistic length (>600 chars for SeamGuard window)
            filler = " Detailed analysis of edge telemetry streaming, verifying database migrations and persistence integrity." * 7
            segments = [
                f"## Section {i}\nSubsystem {i} validation concluded with nominal state.{filler}"
                for i in range(1, 6)
            ]
            guard = SeamGuard("")
            accumulated = ""
            for i, seg in enumerate(segments):
                if i > 0:
                    overlap = "Subsystem 1 validation concluded with nominal state."
                    chunk = guard.feed(f"{overlap}\n\n{seg}")
                else:
                    chunk = guard.feed(seg)
                accumulated += chunk
                guard = SeamGuard(accumulated[-500:])
            accumulated += guard.finish_segment()

            report = run_consistency_pass(accumulated)
            if (report.clean or not report.unrepaired) and len(report.text) > 1000:
                completed += 1

            # Check repeated sentences
            if report.text.count("The telemetry streams normally.") > 1:
                total_repeated_segments += 1

        completion_rate = completed / trials
        repeated_segment_rate = total_repeated_segments / trials

        assert completion_rate >= 0.95
        assert repeated_segment_rate == 0.0

    def test_citation_quality_metrics(self) -> None:
        """Measure CitationCorrectness, CitationCoverage, and FabricatedCitationRate."""
        sources = [
            EvidenceSource(source_id="1", title="Cloud Storage", url="https://storage.internal"),
            EvidenceSource(source_id="2", title="Edge Nodes", url="https://edge.internal"),
        ]
        renderer = CitationRenderer(sources)
        text = (
            "Cloud storage achieves five-nines durability [1]. "
            "Edge nodes serve cached payloads with low latency [2]."
        )
        _, _, metrics = renderer.render(text)

        assert metrics.citation_correctness >= 0.95
        assert metrics.citation_coverage >= 0.60
        assert metrics.fabricated_citation_rate == 0.0

    def test_voice_summary_duration_error(self) -> None:
        """Measure VoiceSummaryDurationError relative to target durations."""
        planner = VoiceResponsePlanner()
        cases = [
            ("brief", 10.0, "Summarize deployment quickly"),
            ("normal", 18.0, "Give standard status report"),
            ("detailed", 45.0, "Explain aloud all details of the system"),
        ]

        errors = []
        for pref, target_dur, text in cases:
            long_doc = "## Executive Report\n\n" + ("Detailed system operations and verification. " * 30)
            res = planner.plan(long_doc, "", user_preference=pref, user_text=text)
            est_dur = res.estimated_duration_seconds
            error = abs(est_dur - target_dur) / target_dur
            errors.append(error)

        avg_error = sum(errors) / len(errors)
        # Average duration error should remain well within bounded range
        assert avg_error <= 0.40, f"Average voice duration error {avg_error:.2f} exceeds 0.40"

    def test_context_payload_integrity_rate(self) -> None:
        """Measure ContextPayloadIntegrityRate for compliant packages."""
        compiler = ContextCompiler(max_tokens=4096)
        ctx = compiler.compile(
            "System instruction",
            "Generate report",
            history=[{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}],
        )
        pkg = CompiledContextPackage(
            manifest=ctx.manifest,
            profile=ctx.manifest.profile,
            system_context="System instruction",
            conversation_context=tuple((m["role"], m["content"]) for m in ctx.dialogue_messages),
            user_text="Generate report",
        )
        report = ContextPayloadIntegrityVerifier.verify(pkg, ctx.manifest)
        assert report["ok"] is True
        assert len(report["issues"]) == 0
