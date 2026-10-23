"""
Directive §6, §7, §8, §9, §11: Research Provenance, Attribution, and Integrity Engine.

Enforces zero-hallucination research integrity across the cognitive pipeline:
1. Strict 5-tier Evidence Grading (VERIFIED FACT, SOURCE CLAIM, CONFLICTING CLAIM, INFERENCE, UNVERIFIED).
2. Explicit Bibliographic Attribution Gate: Rejects bracket citation numbers that do not resolve to stored bibliography.
3. Source-Conflict Preservation: Flags unilateral declarations on contested metrics (e.g. leak file counts 1,884 vs 1,900 vs 1,906).
4. Feature Flag & Codename Maturity Gating: Prevents treating compile-time flags as confirmed product commitments.
5. Anonymous Case-Study Detection: Flags precise metrics attributed to anonymous or unverifiable organizations.
6. Outcome-Based Tool Success Validation: Rejects HTTP 200 envelope alone without verified state evidence.
7. Card Gate: Prevents rendering document cards before artifact validation.
8. Speculative Truncation Auditing: Prevents unverified rationalization of stream interruptions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Tuple


class EvidenceGrade(str, Enum):
    VERIFIED_FACT = "VERIFIED FACT"
    SOURCE_CLAIM = "SOURCE CLAIM"
    CONFLICTING_CLAIM = "CONFLICTING CLAIM"
    INFERENCE = "INFERENCE"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class BibliographicRecord:
    index: int
    url: str
    title: str
    publisher: str
    publication_date: str
    retrieval_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    quoted_evidence: str = ""
    confidence: float = 1.0
    source_type: Literal["primary", "secondary", "community", "unverified"] = "secondary"


@dataclass
class IntegrityAuditResult:
    passed: bool
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    citations_audited: int = 0
    resolved_citations: int = 0


class ResearchIntegrityAuditor:
    """Enforces empirical research integrity and provenance validation."""

    CLAUDE_LEAK_CONFLICTING_FILE_COUNTS = (1884, 1900, 1906)

    @classmethod
    def audit_citations(
        cls,
        text: str,
        bibliography: List[BibliographicRecord],
    ) -> IntegrityAuditResult:
        """Directive §7: Rejects citation numbers that do not resolve to stored bibliography."""
        violations = []
        warnings = []

        # Find all [N] bracket citations
        matches = re.findall(r"\[(\d+)\]", text)
        cited_indices = [int(m) for m in matches]
        bib_map = {b.index: b for b in bibliography}

        for idx in set(cited_indices):
            if idx not in bib_map:
                violations.append(
                    f"UNRESOLVED_CITATION: Citation [{idx}] appears in text but does not resolve to an accessible bibliography record."
                )
            else:
                record = bib_map[idx]
                if not record.url or not record.title or not record.publisher:
                    violations.append(
                        f"INCOMPLETE_CITATION_RECORD: Citation [{idx}] lacks mandatory provenance fields (url, title, or publisher)."
                    )
                if record.source_type == "community" and not record.quoted_evidence:
                    warnings.append(
                        f"COMMUNITY_SOURCE_WARNING: Citation [{idx}] ({record.publisher}) is a community source without direct quoted evidence."
                    )

        passed = len(violations) == 0
        return IntegrityAuditResult(
            passed=passed,
            violations=violations,
            warnings=warnings,
            citations_audited=len(set(cited_indices)),
            resolved_citations=len([i for i in set(cited_indices) if i in bib_map]),
        )

    @classmethod
    def audit_source_conflicts(cls, text: str) -> List[str]:
        """Directive §8: Flags unilateral selection of contested metrics without conflict preservation."""
        violations = []
        lowered = text.lower()

        # Check Claude Code leak file count claims
        if "leak" in lowered or "source map" in lowered or "claude" in lowered:
            mentions_1884 = "1,884" in text or "1884" in text
            mentions_1900 = "1,900" in text or "1900" in text
            mentions_1906 = "1,906" in text or "1906" in text

            count_mentions = sum([mentions_1884, mentions_1900, mentions_1906])
            # If exactly one is asserted without mentioning conflicting counts
            if count_mentions == 1 and not (
                "conflict" in lowered or "diverge" in lowered or "estimates range" in lowered or "variously" in lowered
            ):
                violations.append(
                    "UNACKNOWLEDGED_SOURCE_CONFLICT: Asserted an exact file count for the Claude Code leak as flat fact "
                    "without preserving known conflicting reports (1,884 vs ~1,900 vs 1,906 files)."
                )

        return violations

    @classmethod
    def audit_feature_flag_commitments(cls, text: str) -> List[str]:
        """Directive §9: Flags compile-time flags treated as confirmed commercial product commitments."""
        violations = []
        lowered = text.lower()

        unreleased_flags = ["kairos", "ultraplan", "buddy", "undercover mode"]
        for flag in unreleased_flags:
            if flag in lowered:
                # If described as an active released product feature rather than an unreleased compile-time flag
                if any(phrase in lowered for phrase in [f"{flag} is released", f"{flag} is an active product feature", f"{flag} product commitment"]):
                    violations.append(
                        f"UNVERIFIED_PRODUCT_COMMITMENT: Flag '{flag}' is an unreleased compile-time artifact, "
                        "not a confirmed product commitment."
                    )

        return violations

    @classmethod
    def audit_case_study_attribution(cls, text: str) -> List[str]:
        """Directive §11: Flags detailed telemetry claims attributed to anonymous entities."""
        violations = []
        anonymous_patterns = [
            r"(?i)\b(?:an?\s+)?unnamed\s+(?:eu[- ]sovereign|logistics|firm|enterprise|company)\b",
            r"(?i)\ba\s+logistics\s+firm\s+built\s+a\s+completely\s+sovereign\s+private\s+cloud\b",
        ]
        for pat in anonymous_patterns:
            if re.search(pat, text):
                violations.append(
                    "UNIDENTIFIED_CASE_STUDY: Concrete operational telemetry (latency, costs, IP topology) was asserted "
                    "for an unnamed or unidentifiable organization without verifiable primary citation."
                )
        return violations

    @classmethod
    def validate_tool_outcome(cls, tool_name: str, result_payload: Dict[str, Any]) -> Tuple[bool, str]:
        """Directive §4 & §11: Rejects HTTP 200 envelope alone as proof of task success."""
        if tool_name in ("browser_execute_task", "browser_navigate"):
            # Must verify real DOM state or page url
            res_str = str(result_payload.get("result", ""))
            has_url_verification = "url" in result_payload or "http" in res_str.lower()
            has_error = "error" in res_str.lower() or "failed" in res_str.lower()
            if has_error or not has_url_verification:
                return False, "OUTCOME_VALIDATION_FAILED: Browser execution lacks DOM/URL verification evidence."

        return True, "OUTCOME_VALIDATED"

    @classmethod
    def validate_artifact_card(cls, card_payload: Dict[str, Any]) -> Tuple[bool, str]:
        """Directive §10 & §11: Prevents document card completion before artifact file validation."""
        path_str = card_payload.get("filePath") or card_payload.get("canonicalPath")
        if not path_str:
            return False, "DOCUMENT_CARD_SHOWN_WITHOUT_ARTIFACT: Card indicates completion but specifies no artifact file path."

        p = Path(path_str)
        if not p.is_file():
            return False, f"DOCUMENT_CARD_SHOWN_WITHOUT_ARTIFACT: Specified artifact file does not exist on disk: {p}"

        if p.stat().st_size <= 0:
            return False, f"DOCUMENT_CARD_SHOWN_WITHOUT_ARTIFACT: Specified artifact file is 0 bytes: {p}"

        return True, "ARTIFACT_CARD_VALIDATED"

    @classmethod
    def audit_stream_truncation_explanation(cls, text: str, has_telemetry_abort: bool = False) -> List[str]:
        """Directive §11: Flags speculative rationalization of stream truncation."""
        violations = []
        lowered = text.lower()
        speculative_phrases = [
            "that was a hard output token limit",
            "ui stream collapse cutting off my generation",
            "platform hits that ceiling",
        ]
        if any(p in lowered for p in speculative_phrases) and not has_telemetry_abort:
            violations.append(
                "SPECULATIVE_TRUNCATION_EXPLANATION: Asserted platform token ceiling or UI collapse as root cause "
                "without supporting telemetry or abort log evidence."
            )
        return violations

    @classmethod
    def audit_latest_release_claim(cls, claim_version: str, actual_version: str) -> List[str]:
        """Directive §11: Flags unsupported 'latest release' claim when out of sync with actual release."""
        violations = []
        if claim_version != actual_version:
            violations.append(
                f"UNSUPPORTED_LATEST_RELEASE_CLAIM: Asserted '{claim_version}' as latest major release, "
                f"conflicting with actual repository tag/workspace version '{actual_version}'."
            )
        return violations
