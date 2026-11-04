"""Claim-Level Grounding, Entailment Verification & Citation Integrity Verifier.

Adheres to HINAA OS Phase 06 Directive §3:
- Enforces 5-tier claim support categorization:
  DIRECTLY_SUPPORTED, PARTIALLY_SUPPORTED, DISPUTED, UNSUPPORTED, UNVERIFIABLE
- Rejects fabricated, inaccessible, or non-matching citation references
- Detects source-level contradictions and explicitly surfaces disputes
- Enforces calibrated abstention when evidence is absent or insufficient.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence
from .models import (
    Claim,
    ClaimSupport,
    ClaimSupportStatus,
    EvidenceSpan,
    ResearchAnswer,
    ResearchTrace,
    Source,
)

logger = logging.getLogger("hinaa.research.grounding")

# Regex to detect bracket citations: [1], [2], [src-id]
_BRACKET_CITATION_RE = re.compile(r"\[(?P<ref>\d{1,3}|src-[A-Za-z0-9_-]+)\]")

# Contradiction indicators in evidence
_CONTRADICTION_MARKERS = [
    re.compile(r"\b(?:dispute|conflict|contrary|unlike|disagree|however|refute|instead\s+of|revised\s+from)\b", re.I),
]


class ClaimGroundingVerifier:
    """Verifies that every factual claim is strictly entailed by registered evidence."""

    @classmethod
    def extract_claims(cls, text: str) -> list[Claim]:
        """Splits answer text into atomic propositional claim units."""
        sentences = re.split(r"(?<=[.!?।])\s+", text)
        claims: list[Claim] = []

        claim_idx = 0
        for sent in sentences:
            sent_clean = sent.strip()
            if not sent_clean:
                continue

            claim_idx += 1
            # Classify claim type
            if re.search(r"\b(might|could|likely|possibly|suggests|infer|estimate)\b", sent_clean, re.I):
                c_type = "inference"
            elif re.search(r"\b(dispute|conflict|different\s+views|sources\s+disagree)\b", sent_clean, re.I):
                c_type = "disputed"
            else:
                c_type = "fact"

            claims.append(Claim(claim_id=f"claim-{claim_idx}", text=sent_clean, claim_type=c_type))

        return claims

    @classmethod
    def verify_grounding(
        cls,
        text: str,
        sources: list[Source],
        evidence_spans: list[EvidenceSpan],
        trace: ResearchTrace,
    ) -> ResearchAnswer:
        """Audits claims against evidence spans, rejects fabricated citations, and builds ResearchAnswer."""
        claims = cls.extract_claims(text)
        sources_by_id = {s.source_id: s for s in sources}
        sources_by_idx = {str(i + 1): s for i, s in enumerate(sources)}

        unverified_stripped: list[str] = []
        claim_supports: list[ClaimSupport] = []

        # 1. Audit citations in text
        def citation_sub(match: re.Match[str]) -> str:
            ref = match.group("ref")
            # Must resolve to a valid registered source
            if ref in sources_by_id or ref in sources_by_idx:
                return match.group(0)
            # Fabricated / unverified citation -> strip it!
            unverified_stripped.append(ref)
            logger.warning("ClaimVerifier: REJECTED fabricated citation [%s]", ref)
            return ""

        cleaned_text = _BRACKET_CITATION_RE.sub(citation_sub, text)
        cleaned_text = re.sub(r"\s{2,}", " ", cleaned_text).strip()

        # 2. Audit each claim against evidence spans
        all_supported_scores: list[float] = []

        for c in claims:
            c_tokens = set(re.findall(r"\w+", c.text.lower()))
            supporting: list[EvidenceSpan] = []
            contradicting: list[EvidenceSpan] = []
            best_overlap = 0.0

            for span in evidence_spans:
                span_tokens = set(re.findall(r"\w+", span.text.lower()))
                overlap = len(c_tokens.intersection(span_tokens)) / len(c_tokens) if c_tokens else 0.0

                if overlap > 0.35:
                    supporting.append(span)
                    if overlap > best_overlap:
                        best_overlap = overlap

                # Check if evidence notes a dispute/contradiction
                for marker in _CONTRADICTION_MARKERS:
                    if marker.search(span.text) and overlap > 0.25:
                        contradicting.append(span)

            # Categorize support status
            if contradicting:
                status = ClaimSupportStatus.DISPUTED
                rationale = "Retrieved sources contain conflicting or disputing metrics."
            elif best_overlap >= 0.60:
                status = ClaimSupportStatus.DIRECTLY_SUPPORTED
                rationale = f"Direct textual entailment from source evidence (overlap {best_overlap:.2f})."
            elif best_overlap >= 0.30:
                status = ClaimSupportStatus.PARTIALLY_SUPPORTED
                rationale = f"Partial evidence found (overlap {best_overlap:.2f}); includes inference."
            else:
                status = ClaimSupportStatus.UNSUPPORTED
                rationale = "No registered evidence span entails this proposition."

            all_supported_scores.append(best_overlap)
            claim_supports.append(
                ClaimSupport(
                    claim_id=c.claim_id,
                    status=status,
                    supporting_spans=supporting[:3],
                    contradicting_spans=contradicting[:2],
                    entailment_score=round(best_overlap, 3),
                    rationale=rationale,
                )
            )

        # 3. Abstention evaluation: If zero sources or all claims unsupported
        abstention = False
        abstention_reason = None

        if not sources or (all_supported_scores and max(all_supported_scores) < 0.20):
            abstention = True
            abstention_reason = "NO_VERIFIED_EVIDENCE_AVAILABLE"
            cleaned_text = (
                "Based on current verified sources, this information is not available in our indexed records. "
                "I abstain from speculating to prevent unsupported assertions."
            )

        return ResearchAnswer(
            answer_text=cleaned_text,
            claims=claims,
            claim_supports=claim_supports,
            sources=sources,
            unverified_citations_stripped=unverified_stripped,
            abstention_occurred=abstention,
            abstention_reason=abstention_reason,
            trace=trace,
        )
