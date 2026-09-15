"""P0.15 Claim-Level Citation Authority Tests (Directives §11–§18).

Verifies:
1. EvidenceSource has stable internal identity (SRC_001, SRC_002).
2. Model reasoning refers to source IDs; renderer owns final [1], [2] numbering.
3. If a source is removed or deduplicated, renderer renumbers automatically.
4. Unsupported model-invented bracket citations ([12]) are rejected/removed.
5. ClaimAttribution links claims to sources and spans.
6. EvidenceConflict represents contradictory sources without forcing fake consensus.
7. Stale evidence is evaluated in a query-aware manner (historical queries retain full freshness).
"""

from __future__ import annotations

import pytest

from hinaa_api.grounding.citations import (
    CitationMetrics,
    CitationRenderer,
    ClaimAttribution,
    EvidenceConflict,
    EvidenceSource,
    EvidenceSpan,
    ExternalEvidence,
)


class TestClaimCitationAuthority:
    def test_structured_source_ids_and_renderer_numbering(self) -> None:
        """P0.15 §11/§13: Model emits source IDs; renderer owns numbering."""
        sources = [
            EvidenceSource(
                source_id="SRC_ALPHA",
                title="Alpha Architecture Spec",
                url="https://internal.spec/alpha",
                snippet="Alpha system scales horizontally across 12 zones.",
            ),
            EvidenceSource(
                source_id="SRC_BETA",
                title="Beta Storage Engine",
                url="https://internal.spec/beta",
                snippet="Beta engine provides Raft consensus with sub-millisecond commits.",
            ),
        ]
        renderer = CitationRenderer(sources)

        # Model output cites internal source IDs [SRC_BETA] first, then [SRC_ALPHA]
        model_text = (
            "The storage engine guarantees Raft consensus [SRC_BETA]. "
            "Meanwhile, the core system scales across 12 zones [SRC_ALPHA]."
        )

        rendered, cited_sources, metrics = renderer.render(model_text)

        # Renderer assigns [1] to the first cited source (SRC_BETA) and [2] to the second (SRC_ALPHA)
        assert "The storage engine guarantees Raft consensus [1]." in rendered
        assert "scales across 12 zones [2]." in rendered
        assert cited_sources[0].source_id == "SRC_BETA"
        assert cited_sources[1].source_id == "SRC_ALPHA"
        assert metrics.reference_validity == 1.0
        assert metrics.claim_support_accuracy == 1.0
        assert metrics.fabricated_citation_rate == 0.0

    def test_dynamic_renumbering_on_source_removal(self) -> None:
        """P0.15 §13: If a source is removed or unreferenced, renumbering remains contiguous."""
        sources = [
            EvidenceSource(source_id="SRC_A", title="Source A", url="https://a.test", snippet="A snippet."),
            EvidenceSource(source_id="SRC_B", title="Source B", url="https://b.test", snippet="B snippet."),
            EvidenceSource(source_id="SRC_C", title="Source C", url="https://c.test", snippet="C snippet."),
        ]
        renderer = CitationRenderer(sources)

        # Text only references SRC_B and SRC_C (SRC_A is omitted/removed)
        model_text = "Claim supported by B [SRC_B]. Another claim supported by C [SRC_C]."

        rendered, cited_sources, metrics = renderer.render(model_text)

        assert "Claim supported by B [1]." in rendered
        assert "Another claim supported by C [2]." in rendered
        assert len(cited_sources) == 2
        assert cited_sources[0].source_id == "SRC_B"
        assert cited_sources[1].source_id == "SRC_C"
        assert "### Sources & References" in rendered
        assert "[1] [a.test]" not in rendered
        assert "[1] [b.test]" in rendered
        assert "[2] [c.test]" in rendered

    def test_rejection_of_ungrounded_model_invented_numbers(self) -> None:
        """P0.15 §14: Model emits [12] with no source -> rejected and removed."""
        sources = [
            EvidenceSource(source_id="SRC_1", title="Source 1", url="https://1.test", snippet="Valid evidence."),
        ]
        renderer = CitationRenderer(sources)

        model_text = (
            "This statement has verified evidence [SRC_1]. "
            "This statement hallucinates a citation [12] and [SRC_FAKE]."
        )

        rendered, cited, metrics = renderer.render(model_text, remove_fabricated=True)

        assert "[SRC_1]" not in rendered
        assert "[1]" in rendered
        assert "[12]" not in rendered
        assert "[SRC_FAKE]" not in rendered
        assert metrics.fabricated_citations_count == 2
        assert metrics.valid_citations_count == 1
        assert metrics.reference_validity == round(1 / 3, 3)
        assert metrics.fabricated_citation_rate == round(2 / 3, 3)

    def test_claim_attribution_and_evidence_spans(self) -> None:
        """P0.15 §12/§15: ClaimAttribution with EvidenceSpan linking."""
        span1 = EvidenceSpan(
            source_id="SRC_10",
            span_id="SPAN_42",
            text="Revenue increased 18% year-over-year.",
            location="Section 4, Paragraph 2",
            retrieved_at="2026-09-15T00:00:00Z",
        )
        source = EvidenceSource(
            source_id="SRC_10",
            title="Q3 Financial Filing",
            url="https://sec.gov/filing/q3-2026",
            evidence_spans=[span1],
            snippet="Revenue increased 18% year-over-year in cloud services.",
        )

        claim = ClaimAttribution(
            claim_id="CLAIM_1",
            text="Cloud revenue grew by 18% over the prior year.",
            source_ids=["SRC_10"],
            evidence_span_ids=["SPAN_42"],
            confidence=0.99,
        )

        assert claim.claim_id == "CLAIM_1"
        assert claim.source_ids == ["SRC_10"]
        assert claim.evidence_span_ids == ["SPAN_42"]
        assert span1.location == "Section 4, Paragraph 2"

    def test_contradictory_sources_represented_in_conflict(self) -> None:
        """P0.15 §17: EvidenceConflict represents disagreement without forced fake consensus."""
        source_a = EvidenceSource(
            source_id="SRC_A",
            title="Telemetry Benchmarks 2026",
            snippet="Average p99 latency was 120ms.",
        )
        source_b = EvidenceSource(
            source_id="SRC_B",
            title="Independent Audit 2026",
            snippet="Average p99 latency exceeded 350ms under peak load.",
        )

        conflict = EvidenceConflict(
            topic="p99 Telemetry Latency",
            sources=[source_a.source_id, source_b.source_id],
            disagreement="Telemetry Benchmarks reports 120ms p99 whereas Independent Audit reports >350ms under peak load.",
        )

        assert conflict.topic == "p99 Telemetry Latency"
        assert len(conflict.sources) == 2
        assert "Independent Audit reports >350ms" in conflict.disagreement

    def test_query_aware_stale_source_handling(self) -> None:
        """P0.15 §18: Stale sources for historical queries are not penalized."""
        stale_source = EvidenceSource(
            source_id="SRC_HIST",
            title="Historical PostgreSQL Migration Case Study (2018)",
            date="2018-05-12",
            snippet="In 2018, our architecture transitioned from MySQL to PostgreSQL.",
            is_stale=True,
        )

        # Standard current query penalizes stale source
        current_weight = stale_source.calculate_freshness_weight("What is the latest database architecture?")
        assert current_weight == 0.5

        # Historical query recognizes historical intent and does not penalize
        historical_weight = stale_source.calculate_freshness_weight("What was the history of why we changed the database in 2018?")
        assert historical_weight == 1.0
