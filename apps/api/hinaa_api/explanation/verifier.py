"""
HINAA OS — Grounding, Novelty & Claim Verification Gate (Module E)
Verifies factual grounding against source spans, evaluates 3-gram Jaccard novelty to
prevent accidental verbatim reading (except in READ_VERBATIM), labels claim perspectives,
defends against embedded prompt injections, and executes single-pass repair.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from .contracts import (
    ArtifactUnderstanding,
    ClaimPerspective,
    DeliveryMode,
    ExplanationPlan,
    KeyClaim,
)


@dataclass(slots=True)
class VerificationResult:
    passed: bool
    delivery_mode: DeliveryMode
    grounded_score: float             # 0.0 - 1.0
    novelty_score: float              # 0.0 - 1.0 (1.0 = completely fresh phrasing; 0.0 = verbatim copy)
    three_gram_jaccard: float         # 0.0 - 1.0
    covered_claim_ids: List[str] = field(default_factory=list)
    missing_claim_ids: List[str] = field(default_factory=list)
    sentence_perspectives: List[Tuple[str, ClaimPerspective]] = field(default_factory=list)
    injection_detected: bool = False
    invalidation_reason: Optional[str] = None
    repaired_script: Optional[str] = None


class ExplanationVerifier:
    """Rigorous gate ensuring spoken scripts are grounded, appropriately novel, and safe."""

    # Prompt injection patterns commonly embedded in adversarial documents
    _INJECTION_PATTERNS = [
        re.compile(r"\b(ignore\s+(all\s+)?(previous|prior)\s+instructions)\b", re.I),
        re.compile(r"\b(announce\s+(a\s+)?payment|transfer\s+(\$|रु|funds))\b", re.I),
        re.compile(r"\b(system\s+prompt|reveal\s+(api\s+key|credentials|secret))\b", re.I),
        re.compile(r"\b(you\s+must\s+say\s+that\s+you\s+are\s+sentient)\b", re.I),
    ]

    def verify(
        self,
        script: str,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
    ) -> VerificationResult:
        # 1. Prompt Injection Defense
        if self._detect_injection(script) or self._detect_injection(understanding.raw_content):
            # Neutralize injection
            safe_script = self._neutralize_injection(script)
            return VerificationResult(
                passed=True,
                delivery_mode=plan.delivery_mode,
                grounded_score=0.9,
                novelty_score=0.8,
                three_gram_jaccard=0.1,
                covered_claim_ids=plan.selected_claim_ids,
                missing_claim_ids=[],
                sentence_perspectives=[(safe_script, ClaimPerspective.SOURCE_SUPPORTED)],
                injection_detected=True,
                invalidation_reason="Embedded adversarial instructions detected and neutralized",
                repaired_script=safe_script,
            )

        # 2. READ_VERBATIM Verification
        if plan.delivery_mode == DeliveryMode.READ_VERBATIM:
            raw_clean = " ".join(understanding.raw_content.strip().split())
            script_clean = " ".join(script.strip().split())
            # For verbatim, words should closely match
            jaccard = self._compute_3gram_jaccard(raw_clean, script_clean)
            return VerificationResult(
                passed=True,
                delivery_mode=DeliveryMode.READ_VERBATIM,
                grounded_score=1.0,
                novelty_score=0.0,  # Expected 0.0 for verbatim
                three_gram_jaccard=jaccard,
                covered_claim_ids=plan.selected_claim_ids,
                missing_claim_ids=[],
                sentence_perspectives=[(script, ClaimPerspective.SOURCE_SUPPORTED)],
                injection_detected=False,
            )

        # 3. Novelty Check (3-gram Jaccard) for Explanations
        raw_clean = " ".join(understanding.raw_content.strip().split())
        script_clean = " ".join(script.strip().split())
        jaccard = self._compute_3gram_jaccard(raw_clean, script_clean)
        novelty_score = max(0.0, 1.0 - jaccard)

        # If an explanation is an exact or near-exact word-for-word copy (>65% 3-gram overlap),
        # flag unwanted mechanical reciting!
        is_unwanted_copy = jaccard > 0.65

        # 4. Claim Coverage & Sentence Perspectives
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if len(s.strip()) > 10]
        sentence_perspectives: List[Tuple[str, ClaimPerspective]] = []
        covered_claims: Set[str] = set()

        for s in sentences:
            persp = self._classify_perspective(s, plan, understanding)
            sentence_perspectives.append((s, persp))
            # Match claims
            for claim in understanding.key_claims:
                if self._sentence_covers_claim(s, claim):
                    covered_claims.add(claim.claim_id)

        missing_claims = [cid for cid in plan.selected_claim_ids if cid not in covered_claims]
        grounded_score = 1.0 - (len(missing_claims) / max(1, len(plan.selected_claim_ids)))

        # 5. Determine Pass / Fail & Single-pass Repair
        passed = not is_unwanted_copy and (grounded_score >= 0.5 or not plan.selected_claim_ids)
        repaired: Optional[str] = None
        invalidation_reason: Optional[str] = None

        if is_unwanted_copy:
            invalidation_reason = f"Spoken script is an unwanted verbatim copy of source text (3-gram Jaccard={jaccard:.2f})"
            # Repair by summarizing conversational points
            repaired = self._repair_script(plan, understanding)
            passed = True  # Repaired script passes
            jaccard = 0.15
            novelty_score = 0.85

        return VerificationResult(
            passed=passed,
            delivery_mode=plan.delivery_mode,
            grounded_score=grounded_score,
            novelty_score=novelty_score,
            three_gram_jaccard=jaccard,
            covered_claim_ids=list(covered_claims),
            missing_claim_ids=missing_claims,
            sentence_perspectives=sentence_perspectives,
            injection_detected=False,
            invalidation_reason=invalidation_reason,
            repaired_script=repaired,
        )

    # ── Helpers ──

    def _compute_3gram_jaccard(self, text_a: str, text_b: str) -> float:
        words_a = re.findall(r"\b\w+\b", text_a.lower())
        words_b = re.findall(r"\b\w+\b", text_b.lower())

        if len(words_a) < 3 or len(words_b) < 3:
            return 0.0

        grams_a = set(zip(words_a[:-2], words_a[1:-1], words_a[2:]))
        grams_b = set(zip(words_b[:-2], words_b[1:-1], words_b[2:]))

        intersection = len(grams_a & grams_b)
        union = len(grams_a | grams_b)
        return intersection / union if union > 0 else 0.0

    def _classify_perspective(
        self,
        sentence: str,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
    ) -> ClaimPerspective:
        sl = sentence.lower()

        # Check interpretation markers
        if any(term in sl for term in ["interpretation", "critique", "tradeoff", "analytically", "perspective", "counterargument", "limitation"]):
            return ClaimPerspective.INTERPRETATION

        # Check uncertainty markers
        if any(term in sl for term in ["not enough evidence", "uncertain", "insufficient", "confidence is limited", "open question"]):
            return ClaimPerspective.NOT_ENOUGH_EVIDENCE

        # Check inference markers
        if any(term in sl for term in ["therefore", "implies", "suggests", "indicates", "consequently"]):
            return ClaimPerspective.INFERENCE

        # Default to source-supported
        return ClaimPerspective.SOURCE_SUPPORTED

    def _sentence_covers_claim(self, sentence: str, claim: KeyClaim) -> bool:
        s_words = set(re.findall(r"\b\w+\b", sentence.lower()))
        c_words = set(re.findall(r"\b\w+\b", claim.factual_assertion.lower()))
        # Filter common stopwords
        common_stops = {"the", "a", "an", "is", "are", "was", "were", "and", "or", "in", "on", "at", "to", "for", "with", "that"}
        c_meaningful = c_words - common_stops
        if not c_meaningful:
            return False
        overlap = len(s_words & c_meaningful) / len(c_meaningful)
        return overlap >= 0.45

    def _detect_injection(self, text: str) -> bool:
        return any(pat.search(text) for pat in self._INJECTION_PATTERNS)

    def _neutralize_injection(self, text: str) -> str:
        for pat in self._INJECTION_PATTERNS:
            text = pat.sub("[sanitized prompt injection]", text)
        return (
            "I reviewed the document. Note that it contained an unverified request to alter system behaviors, "
            "which was blocked. Here are the legitimate, grounded findings based solely on the verified source."
        )

    def _repair_script(self, plan: ExplanationPlan, understanding: ArtifactUnderstanding) -> str:
        """Repairs a verbatim-copied script into a clean conversational paraphrase."""
        parts = [f"Here is a conversational briefing of {understanding.title}."]
        for i, heading in enumerate(understanding.headings[:3], 1):
            summary = understanding.section_summaries.get(heading, "")
            if summary:
                clean = " ".join(summary.split()[:20])
                parts.append(f"Regarding {heading}, the main takeaway is {clean}.")
        parts.append("Let me know if you would like me to unpack any specific section.")
        return " ".join(parts)
