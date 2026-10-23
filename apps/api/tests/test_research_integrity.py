"""
Directive §11: Research Integrity Regression Suite.

Automated verification based on the exact failures diagnosed in the audit:
1. Unsupported "latest release" claim.
2. Conflicting source counts preservation.
3. Unresolved citation numbers rejection.
4. Unidentified case study detection.
5. Tool HTTP 200 without outcome validation.
6. Document card shown without validated artifact.
7. Speculative explanation of stream truncation.
8. Durable report checkpointing and card gating.
"""

from pathlib import Path
import tempfile
import pytest

from hinaa_api.intelligence.research_integrity import (
    BibliographicRecord,
    ResearchIntegrityAuditor,
)
from hinaa_api.artifacts.durable_report import DurableReportPipeline


def test_unresolved_citation_rejection():
    text = "The Claude Code leak was analyzed by researchers [1] and [99]."
    bib = [
        BibliographicRecord(
            index=1,
            url="https://example.com/analysis",
            title="Claude Code Analysis",
            publisher="Tech Analysis",
            publication_date="2026-04-01",
        )
    ]
    res = ResearchIntegrityAuditor.audit_citations(text, bib)
    assert res.passed is False
    assert any("UNRESOLVED_CITATION" in v and "99" in v for v in res.violations)
    assert res.resolved_citations == 1
    assert res.citations_audited == 2


def test_conflicting_source_counts():
    # Flawed: asserting 1,906 as flat settled fact
    flawed_text = "The leak exposed 1,906 source files across the codebase."
    flawed_violations = ResearchIntegrityAuditor.audit_source_conflicts(flawed_text)
    assert len(flawed_violations) >= 1
    assert "UNACKNOWLEDGED_SOURCE_CONFLICT" in flawed_violations[0]

    # Correct: preserving the conflicting estimates
    valid_text = (
        "Reports on the leak file count conflict: community analyses report variously "
        "1,884, approximately 1,900, and 1,906 files."
    )
    valid_violations = ResearchIntegrityAuditor.audit_source_conflicts(valid_text)
    assert len(valid_violations) == 0


def test_unidentified_case_study_detection():
    # Flawed: concrete numbers for an anonymous entity
    anon_text = "An unnamed EU sovereign logistics firm built a private cloud dropping latency to 120ms."
    violations = ResearchIntegrityAuditor.audit_case_study_attribution(anon_text)
    assert len(violations) >= 1
    assert "UNIDENTIFIED_CASE_STUDY" in violations[0]


def test_tool_outcome_validation():
    # Flawed: envelope returns generic text without DOM or URL confirmation
    passed, err = ResearchIntegrityAuditor.validate_tool_outcome(
        "browser_execute_task",
        {"result": "Task completed.", "status": 200},
    )
    assert passed is False
    assert "OUTCOME_VALIDATION_FAILED" in err

    # Valid: includes verified URL and DOM evidence
    passed, msg = ResearchIntegrityAuditor.validate_tool_outcome(
        "browser_execute_task",
        {"result": "Successfully navigated to https://example.com with 1 page owned.", "url": "https://example.com"},
    )
    assert passed is True


def test_document_card_shown_without_artifact():
    # Non-existent file
    passed, err = ResearchIntegrityAuditor.validate_artifact_card({"filePath": "/tmp/non_existent_report.pdf"})
    assert passed is False
    assert "DOCUMENT_CARD_SHOWN_WITHOUT_ARTIFACT" in err

    # Valid real file
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tf:
        tf.write(b"Valid artifact bytes")
        tf.flush()
        temp_path = tf.name

    try:
        passed, msg = ResearchIntegrityAuditor.validate_artifact_card({"filePath": temp_path})
        assert passed is True
        assert msg == "ARTIFACT_CARD_VALIDATED"
    finally:
        Path(temp_path).unlink(missing_ok=True)


def test_speculative_stream_truncation_explanation():
    excuse_text = "that was a hard output token limit or a UI stream collapse cutting off my generation"
    violations = ResearchIntegrityAuditor.audit_stream_truncation_explanation(excuse_text, has_telemetry_abort=False)
    assert len(violations) >= 1
    assert "SPECULATIVE_TRUNCATION_EXPLANATION" in violations[0]

    # When corroborated by actual telemetry abort
    clean_violations = ResearchIntegrityAuditor.audit_stream_truncation_explanation(excuse_text, has_telemetry_abort=True)
    assert len(clean_violations) == 0


def test_unsupported_latest_release_claim():
    violations = ResearchIntegrityAuditor.audit_latest_release_claim("v0.1.4", "v0.1.6")
    assert len(violations) >= 1
    assert "UNSUPPORTED_LATEST_RELEASE_CLAIM" in violations[0]


def test_durable_report_generation_and_card_gate():
    rep_id = "test_durable_rep_001"
    sections = ["Architecture Overview", "Security Threat Model", "Implementation Verification"]

    # 1. Initialize
    state = DurableReportPipeline.init_report(rep_id, "Durable Test Report", sections, max_section_chars=5000)
    assert state.status == "draft"

    # Card must be blocked while draft is incomplete
    with pytest.raises(ValueError, match="DOCUMENT_CARD_BLOCKED"):
        DurableReportPipeline.emit_completed_card(rep_id)

    # 2. Checkpoint sections sequentially
    DurableReportPipeline.checkpoint_section(rep_id, "Architecture Overview", "Content for architecture.")
    assert DurableReportPipeline.can_resume(rep_id) is True

    DurableReportPipeline.checkpoint_section(rep_id, "Security Threat Model", "Content for threat model.")
    DurableReportPipeline.checkpoint_section(rep_id, "Implementation Verification", "Content for verification.")

    # 3. Assemble and validate
    final_state = DurableReportPipeline.assemble_and_validate(rep_id, output_format="md")
    assert final_state.status == "validated"
    assert final_state.assembled_path is not None
    assert Path(final_state.assembled_path).is_file()

    # 4. Now card generation succeeds
    card = DurableReportPipeline.emit_completed_card(rep_id)
    assert card["status"] == "ready"
    assert card["sectionCount"] == 3
    assert card["fileSizeBytes"] > 0
