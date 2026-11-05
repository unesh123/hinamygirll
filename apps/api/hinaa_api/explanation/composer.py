"""
HINAA OS — Independent Spoken Script Composer (Module D)
Generates natural conversational speech tailored for audio playback. Strips raw markdown
syntax, tables, URLs, and bracketed citation numbers. Distinguishes source facts from
interpretations, supports Nepali / English / code-mixing, and handles verbatim reading.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .contracts import (
    ArtifactUnderstanding,
    ClaimPerspective,
    DeliveryMode,
    ExplanationPlan,
    KeyClaim,
)


class SpokenScriptComposer:
    """Composes spoken scripts that are natural to hear aloud and strictly grounded."""

    # Cleaning patterns for spoken text
    _URL_RE = re.compile(r"https?://\S+|www\.\S+")
    _MARKDOWN_TABLE_RE = re.compile(r"\|[^\n]+\|(\r?\n\|[^\n]+\|)+")
    _BRACKETED_CITATION_RE = re.compile(r"\[([0-9]+|[A-Za-z]+[-_0-9]+|arXiv:[0-9.]+[^\]]*)\]")
    _CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_-]*\n[\s\S]*?```")
    _INLINE_CODE_RE = re.compile(r"`([^`]+)`")
    _MARKDOWN_HEADER_RE = re.compile(r"^#{1,6}\s*", re.MULTILINE)
    _MARKDOWN_BOLD_ITALIC_RE = re.compile(r"(\*\*|\*|__|_)(.*?)\1")

    def compose(
        self,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
    ) -> str:
        """Composes a natural spoken script honoring the plan and delivery mode."""

        # 1. READ_VERBATIM: preserve exact document body without paraphrase or novelty changes
        if plan.delivery_mode == DeliveryMode.READ_VERBATIM:
            return self._clean_verbatim_text(understanding.raw_content)

        # 2. Retrieve selected KeyClaims
        claim_map: Dict[str, KeyClaim] = {c.claim_id: c for c in understanding.key_claims}
        selected_claims = [claim_map[cid] for cid in plan.selected_claim_ids if cid in claim_map]

        # If no claims exist in understanding, provide honest fallback
        if not selected_claims and not understanding.raw_content.strip():
            return self._compose_empty_fallback(plan.language)

        # 3. Handle by language
        if plan.language == "ne":
            return self._compose_nepali(plan, understanding, selected_claims)
        elif plan.language == "mixed":
            return self._compose_mixed(plan, understanding, selected_claims)
        else:
            return self._compose_english(plan, understanding, selected_claims)

    def _compose_english(
        self,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
        claims: List[KeyClaim],
    ) -> str:
        parts: List[str] = []

        # Code artifact receipts handling
        code_receipt = understanding.code_receipts
        if code_receipt:
            passed = code_receipt.get("passed", True)
            total = code_receipt.get("total_tests", code_receipt.get("total", 0))
            passed_count = code_receipt.get("passed_tests", code_receipt.get("passed_count", total if passed else 0))
            duration = code_receipt.get("duration_seconds", code_receipt.get("duration", 0.0))
            if passed:
                parts.append(f"I inspected the code receipts: all {total} automated tests passed cleanly in {duration:.2f} seconds.")
            else:
                parts.append(f"I checked the execution receipt: {passed_count} of {total} tests passed, but there are reported test failures.")

        # Mode-specific opening & composition
        if plan.delivery_mode == DeliveryMode.EXPLAIN_BRIEFLY:
            parts.append(f"Here are the key takeaways from {understanding.title}.")
            for i, claim in enumerate(claims[:3], 1):
                clean_claim = self._sanitize_for_speech(claim.factual_assertion)
                parts.append(f"Point {i}: {clean_claim}")
            if understanding.conclusions:
                clean_conclusion = self._sanitize_for_speech(understanding.conclusions[0])
                parts.append(f"In conclusion: {clean_conclusion}")
            parts.append("I can walk through any specific section in detail whenever you'd like.")

        elif plan.delivery_mode == DeliveryMode.EXPLAIN_FULLY:
            parts.append(f"Let's do a complete walkthrough of {understanding.title}.")
            if claims:
                for i, claim in enumerate(claims, 1):
                    clean_claim = self._sanitize_for_speech(claim.factual_assertion)
                    parts.append(f"Section {i}: {clean_claim}")
            else:
                for heading in understanding.headings:
                    summary = understanding.section_summaries.get(heading, "")
                    if summary:
                        clean_sum = self._sanitize_for_speech(summary)
                        parts.append(f"Regarding {heading}: {clean_sum}")
            if understanding.conclusions:
                parts.append(f"Looking at the results: {self._sanitize_for_speech(understanding.conclusions[0])}")

        elif plan.delivery_mode == DeliveryMode.EXPLAIN_DIFFERENTLY:
            if plan.comparison_or_analogy:
                parts.append(plan.comparison_or_analogy)
            else:
                parts.append("Let's look at this from another angle.")
            for claim in claims[:3]:
                parts.append(f"In practical terms: {self._sanitize_for_speech(claim.factual_assertion)}")

        elif plan.delivery_mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            parts.append(f"Evaluating {understanding.title} from an analytical perspective.")
            for claim in claims[:2]:
                parts.append(f"Source-supported finding: {self._sanitize_for_speech(claim.factual_assertion)}")
            if plan.alternative_perspective:
                parts.append(f"Interpretation and critique: {plan.alternative_perspective}")
            if understanding.limitations:
                parts.append(f"A notable tradeoff or limitation is: {self._sanitize_for_speech(understanding.limitations[0])}")

        elif plan.delivery_mode == DeliveryMode.TEACH_STEP_BY_STEP:
            parts.append(f"Let's learn {understanding.title} step by step.")
            for step_idx, claim in enumerate(claims[:4], 1):
                parts.append(f"Step {step_idx}: {self._sanitize_for_speech(claim.factual_assertion)}")
            parts.append("Does this step make sense, or would you like me to clarify before we move on?")

        elif plan.delivery_mode == DeliveryMode.DISCUSS:
            parts.append(f"Regarding {understanding.title}:")
            if claims:
                parts.append(f"The central finding is that {self._sanitize_for_speech(claims[0].factual_assertion)}.")
            parts.append("What are your thoughts on this direction?")

        else:
            # VOICE_CHAT or generic
            for claim in claims[:2]:
                parts.append(self._sanitize_for_speech(claim.factual_assertion))

        # Disclose uncertainty if required
        if plan.uncertainty_to_disclose:
            parts.append(f"Keep in mind: {plan.uncertainty_to_disclose[0]}")

        return " ".join(parts)

    def _compose_nepali(
        self,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
        claims: List[KeyClaim],
    ) -> str:
        parts: List[str] = []

        if plan.delivery_mode == DeliveryMode.EXPLAIN_BRIEFLY:
            parts.append(f"मैले {understanding.title} को मुख्य सार तयार पारेको छु।")
            for i, claim in enumerate(claims[:3], 1):
                clean_claim = self._sanitize_for_speech(claim.factual_assertion)
                parts.append(f"बुँदा {i}: {clean_claim}")
            parts.append("तपाईंलाई थप विस्तृतमा बुझ्न मन भए म अर्को बुँदा पनि व्याख्या गर्न सक्छु।")

        elif plan.delivery_mode == DeliveryMode.EXPLAIN_DIFFERENTLY:
            parts.append("यसलाई अर्को फरक दृष्टिकोण र उदाहरणबाट हेरौँ।")
            if plan.comparison_or_analogy:
                parts.append(plan.comparison_or_analogy)
            for claim in claims[:2]:
                parts.append(f"व्यावहारिक रूपमा: {self._sanitize_for_speech(claim.factual_assertion)}")

        elif plan.delivery_mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            parts.append(f"{understanding.title} का फाइदा र बेफाइदाहरूलाई केलाएर हेर्दा:")
            for claim in claims[:2]:
                parts.append(f"तथ्यगत प्रमाण: {self._sanitize_for_speech(claim.factual_assertion)}")
            parts.append("विश्लेषणात्मक दृष्टिकोणबाट हेर्दा केही महत्वपूर्ण जोखिम र सीमितताहरू पनि छन्।")

        else:
            parts.append(f"{understanding.title} को विस्तृत जानकारी यस प्रकार छ।")
            for claim in claims[:3]:
                parts.append(self._sanitize_for_speech(claim.factual_assertion))

        return " ".join(parts)

    def _compose_mixed(
        self,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
        claims: List[KeyClaim],
    ) -> str:
        parts: List[str] = []

        if plan.delivery_mode == DeliveryMode.EXPLAIN_BRIEFLY:
            parts.append(f"Maile {understanding.title} ko key takeaways prepare gareko chhu.")
            for i, claim in enumerate(claims[:3], 1):
                clean_claim = self._sanitize_for_speech(claim.factual_assertion)
                parts.append(f"Point {i}: {clean_claim}")
            parts.append("Hajur lai kunai particular section detail ma bujhnu chha bhane bhannuhos.")

        elif plan.delivery_mode == DeliveryMode.EXPLAIN_DIFFERENTLY:
            parts.append("Aru tarika le bujhnu parda:")
            if plan.comparison_or_analogy:
                parts.append(plan.comparison_or_analogy)
            for claim in claims[:2]:
                parts.append(f"Practical terms ma: {self._sanitize_for_speech(claim.factual_assertion)}")

        elif plan.delivery_mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            parts.append(f"{understanding.title} ko tradeoff ra critique herda:")
            for claim in claims[:2]:
                parts.append(f"Report ko fact: {self._sanitize_for_speech(claim.factual_assertion)}")
            parts.append("Critical perspective bata herda implementation risk pani dhyaan dina parne dekhinchha.")

        else:
            parts.append(f"{understanding.title} ko barema:")
            for claim in claims[:3]:
                parts.append(self._sanitize_for_speech(claim.factual_assertion))

        return " ".join(parts)

    def _compose_empty_fallback(self, language: str) -> str:
        if language == "ne":
            return "यस विषयमा पर्याप्त तथ्यगत जानकारी उपलब्ध छैन, त्यसैले म अनुमानित कुराहरू भन्न सक्दिन।"
        elif language == "mixed":
            return "Yo report ma enough verified evidence chaina, so maile estimate garera bolna mildaina."
        return "There is insufficient verified evidence in the artifact to form a reliable explanation."

    def _clean_verbatim_text(self, text: str) -> str:
        """Cleans formatting syntax while strictly preserving all original words for READ_VERBATIM."""
        # Strip code fences but keep code lines
        text = re.sub(r"```[a-zA-Z0-9_-]*\n", "", text)
        text = text.replace("```", "")
        # Strip markdown headers '# '
        text = self._MARKDOWN_HEADER_RE.sub("", text)
        # Strip bold/italic markers
        text = self._MARKDOWN_BOLD_ITALIC_RE.sub(r"\2", text)
        # Normalize whitespace
        return " ".join(text.strip().split())

    def _sanitize_for_speech(self, text: str) -> str:
        """Strips out visual markdown, raw URLs, code blocks, and bracketed citations."""
        t = self._URL_RE.sub("", text)
        t = self._MARKDOWN_TABLE_RE.sub(" ", t)
        t = self._CODE_BLOCK_RE.sub(" ", t)
        t = self._INLINE_CODE_RE.sub(r"\1", t)
        t = self._BRACKETED_CITATION_RE.sub("", t)
        t = self._MARKDOWN_HEADER_RE.sub("", t)
        t = self._MARKDOWN_BOLD_ITALIC_RE.sub(r"\2", t)
        t = t.replace("\n", " ")
        # Clean double spaces
        return " ".join(t.split())
