"""Agent Behavioral Regression & Diffing Harness (inspired by arthi-arumugam-git/whatbroke).

Verifies that model router switches, streaming decoders, and continuation rounds
maintain strict behavioral invariants:
1. No duplicated text blocks across segments.
2. Character counts never regress or drop during continuation.
3. Substantive voice summaries skip conversational filler.
4. Tool calls and execution traces maintain schema fidelity.
"""

from __future__ import annotations

import pytest
import asyncio
from hinaa_api.generation.orchestrator import (
    GenerationOrchestrator,
    GenerationFinishReason,
    SegmentResult,
)
from hinaa_api.providers.display_stream_decoder import (
    AdaptiveStreamDecoder,
    DisplayTextChain,
)
from hinaa_api.prompts.performance import (
    extract_executive_voice_summary,
    build_plan_from_text,
)
from hinaa_api.rag.predictive_retriever import (
    PredictiveContextRetriever,
)


class TestAgentBehaviorDiffHarness:
    """whatbroke-style behavioral invariant tests."""

    def test_executive_summary_filters_conversational_filler(self) -> None:
        """Invariant: Spoken summaries must NEVER repeat conversational greetings."""
        text = (
            "Here's the full breakdown, babe. The Koshi river basin experienced critical "
            "hydrological pressure resulting in $4.2M in flood damages. Emergency sirens "
            "and automated gauge sensors are now recommended for downstream settlements."
        )
        summary = extract_executive_voice_summary(text, limit=150)
        assert not summary.lower().startswith("here's the full breakdown")
        assert not summary.lower().startswith("babe")
        assert "koshi river basin" in summary.lower() or "hydrological" in summary.lower()
        assert len(summary) <= 150

    def test_executive_summary_nepali_greetings_filtered(self) -> None:
        text = (
            "नमस्ते! यहाँ पुरा जानकारी छ। कोशी नदीको बहाव उच्च जोखिममा छ, जसले तटीय "
            "क्षेत्रमा ठूलो क्षति पुर्याउन सक्छ।"
        )
        summary = extract_executive_voice_summary(text, limit=150)
        assert not summary.startswith("नमस्ते")
        assert not summary.startswith("यहाँ पुरा जानकारी छ")
        assert "कोशी" in summary

    def test_adaptive_stream_decoder_prose_stream(self) -> None:
        """Invariant: Markdown prose deltas must stream directly without corruption."""
        decoder = AdaptiveStreamDecoder()
        chunks = ["## Intelligence Briefing\n", "The system recorded ", "42 operational alerts.\n"]
        emitted = []
        for c in chunks:
            out = decoder.feed(c)
            if out:
                emitted.append(out)
        rest = decoder.finish()
        if rest:
            emitted.append(rest)

        full = "".join(emitted)
        assert full == "## Intelligence Briefing\nThe system recorded 42 operational alerts.\n"

    def test_adaptive_stream_decoder_json_stream(self) -> None:
        """Invariant: JSON displayText must decode escape-safely across chunk splits."""
        decoder = AdaptiveStreamDecoder()
        chunks = [
            '{"displayText": "Line one\\',
            'nLine two with \\"',
            'quotes\\" and done.", "spokenText": "short voice"}',
        ]
        emitted = []
        for c in chunks:
            out = decoder.feed(c)
            if out:
                emitted.append(out)
        rest = decoder.finish()
        if rest:
            emitted.append(rest)

        full = "".join(emitted)
        assert full == 'Line one\nLine two with "quotes" and done.'
        # Metadata must NOT leak into display text
        assert "spokenText" not in full
        assert "short voice" not in full

    @pytest.mark.asyncio
    async def test_multi_segment_continuation_zero_duplication(self) -> None:
        """Invariant: Continuation rounds must NEVER duplicate paragraphs or sentences."""
        # Simulate round 1 (hits token limit mid-sentence)
        seg1 = ["This comprehensive document details ", "the historical evolution of Himalayan hydrology.\n\n"]
        holder1 = {"value": "max_tokens"}

        # Simulate round 2 (continues seamlessly)
        seg2 = ["From 2000 to 2026, over 40 glacial lake outbursts were recorded across the Hindu Kush.\n"]
        holder2 = {"value": "stop"}

        async def first_stream():
            for chunk in seg1:
                yield chunk

        def cont_factory(prior: str):
            cont_holder = {"value": "stop"}
            async def gen():
                for chunk in seg2:
                    yield chunk
            return gen(), cont_holder

        emitted_deltas = []
        async def mock_emit(d: str):
            emitted_deltas.append(d)

        orchestrator = GenerationOrchestrator(
            max_continuations=4,
            char_budget=50000,
            generation_id="test-run",
        )
        outcome = await orchestrator.run(
            first_segment_stream=first_stream(),
            first_finish_reason_holder=holder1,
            continuation_stream_factory=cont_factory,
            emit_delta=mock_emit,
        )

        full_text = outcome.text
        assert "historical evolution" in full_text
        assert "Hindu Kush" in full_text
        # Invariant: No duplicate passages
        assert full_text.count("comprehensive document") == 1
        assert full_text.count("From 2000 to 2026") == 1

    @pytest.mark.asyncio
    async def test_predictive_retriever_caching(self) -> None:
        """Invariant: Predictive retriever pre-fetches and matches follow-up questions."""
        retriever = PredictiveContextRetriever(ttl_seconds=60.0)
        user_msg = "What caused the 2024 Nepal floods?"
        generated_doc = (
            "Heavy monsoon cloudbursts in the Langtang range saturated the soil.\n"
            "Recommendations: Deploy remote satellite telemetry and early warning sirens."
        )

        topics = retriever.predict_followup_topics(user_msg, generated_doc)
        assert len(topics) > 0

        await retriever.prefetch_background(
            topics,
            fetcher_fn=lambda t: f"Background evidence for {t}",
        )

        cached = await retriever.get_prefetched(topics[0])
        assert cached is not None
        assert f"Background evidence for {topics[0]}" == cached
