"""
HINAA OS — Metacognitive Explanation Planner & Bounded Self-Model (Module C)
Constructs structured explanation plans, prioritizing key insights, tradeoffs,
and user goals over mechanical document recitation. Enforces strict zero-consciousness
boundaries and tracks conversation topic coverage.
"""

from __future__ import annotations

import re
import time
import uuid
from typing import Any, Dict, List, Optional, Sequence

from .contracts import (
    ArtifactUnderstanding,
    DeliveryMode,
    ExplanationPlan,
    KeyClaim,
)


class BoundedSelfModel:
    """Explicit, bounded self-model of HINAA OS capabilities and cognitive limits."""

    KNOWN_CAPABILITIES = {
        "text_explanation": "Summarize, analyze, and communicate document findings",
        "audio_synthesis": "Generate natural spoken voice via ElevenLabs and neural TTS",
        "multilingual_communication": "Support English, Devanagari Nepali, and mixed code-switching",
        "code_receipt_verification": "Inspect real diffs, test outputs, and compiler receipts",
        "grounded_retrieval": "Anchor assertions to verifiable source spans and citations",
        "barge_in_coordination": "Cancel in-flight synthesis upon user interruption",
    }

    REPORTED_LIMITATIONS = {
        "no_subjective_experience": "I do not possess subjective consciousness, sentience, feelings, or a human brain.",
        "evidence_bounded": "I cannot verify assertions that lack empirical receipts or citations in the document.",
        "stateless_unless_stored": "Ephemeral dialogue context requires explicit memory persistence to endure across sessions.",
        "external_network_dependencies": "Live search and third-party tools are bounded by network availability.",
    }

    @classmethod
    def get_self_description(cls) -> Dict[str, Any]:
        return {
            "agent": "HINAA OS Reflective Voice & Metacognitive Explanation Engine",
            "sentient": False,
            "has_human_consciousness": False,
            "capabilities": dict(cls.KNOWN_CAPABILITIES),
            "limitations": dict(cls.REPORTED_LIMITATIONS),
        }


class MetacognitiveExplanationPlanner:
    """Plans speech structure, selected claims, analogies, and disclosures before composing spoken script."""

    def plan(
        self,
        understanding: ArtifactUnderstanding,
        delivery_mode: DeliveryMode,
        user_goal: str = "",
        audience_level: str = "general",
        language: str = "en",
        time_budget_seconds: float = 30.0,
        already_spoken_claim_ids: Optional[Sequence[str]] = None,
        previous_angles: Optional[Sequence[str]] = None,
        target_section: Optional[str] = None,
    ) -> ExplanationPlan:
        plan_id = f"plan-{uuid.uuid4().hex[:8]}"
        already_spoken = set(already_spoken_claim_ids or [])
        prior_angles = list(previous_angles or [])

        # Filter claims: prioritize claims that have NOT been explained yet in this conversation
        available_claims = [c for c in understanding.key_claims if c.claim_id not in already_spoken]
        if not available_claims:
            # If all claims were explained, reuse all claims for re-framing
            available_claims = list(understanding.key_claims)

        # Select claims based on delivery mode
        selected_claims, covered_sections = self._select_claims_for_mode(
            available_claims=available_claims,
            understanding=understanding,
            delivery_mode=delivery_mode,
            target_section=target_section,
        )

        # Formulate analogy or alternative perspective
        analogy, perspective = self._formulate_framing(
            delivery_mode=delivery_mode,
            understanding=understanding,
            prior_angles=prior_angles,
        )

        # Disclose uncertainty if claims have low confidence or limitations exist
        uncertainty: List[str] = []
        for claim in selected_claims:
            if claim.factual_confidence < 0.8:
                uncertainty.append(f"Confidence for claim '{claim.claim_id}' is limited by available source detail.")
        if understanding.limitations:
            uncertainty.extend(understanding.limitations[:2])

        # If code artifact with test receipts, enforce real receipt disclosure
        if understanding.code_receipts:
            passed = understanding.code_receipts.get("passed", True)
            if not passed:
                uncertainty.append("Automated test suite reported failures in the code receipt.")

        # Segment breakdown for speech turn coordinator
        segment_plan = self._build_segment_plan(
            delivery_mode=delivery_mode,
            selected_claims=selected_claims,
            time_budget=time_budget_seconds,
            analogy=analogy,
            perspective=perspective,
        )

        utterance_goal = self._determine_utterance_goal(delivery_mode, understanding.title, target_section)

        return ExplanationPlan(
            plan_id=plan_id,
            source_artifact_id=understanding.artifact_id,
            source_sha256=understanding.content_sha256,
            utterance_goal=utterance_goal,
            audience_level=audience_level,
            language=language,
            delivery_mode=delivery_mode,
            time_budget_seconds=time_budget_seconds,
            selected_claim_ids=[c.claim_id for c in selected_claims],
            covered_section_ids=covered_sections,
            alternative_perspective=perspective,
            comparison_or_analogy=analogy,
            uncertainty_to_disclose=uncertainty,
            already_spoken_topic_ids=list(already_spoken),
            segment_plan=segment_plan,
            source_provenance={
                "artifact_id": understanding.artifact_id,
                "tenant_id": understanding.tenant_id,
                "version": understanding.version,
                "claim_count": len(understanding.key_claims),
            },
            reason_for_mode=f"Plan optimized for {delivery_mode.value} delivery within {time_budget_seconds:.0f}s",
        )

    def _select_claims_for_mode(
        self,
        available_claims: List[KeyClaim],
        understanding: ArtifactUnderstanding,
        delivery_mode: DeliveryMode,
        target_section: Optional[str] = None,
    ) -> tuple[List[KeyClaim], List[str]]:
        if target_section:
            # Flexible section matching: extract digits or keywords
            ts_digits = re.findall(r"\d+", target_section)
            ts_words = [w.lower() for w in re.findall(r"[a-zA-Z]+", target_section) if w.lower() != "section"]

            filtered: List[KeyClaim] = []
            for c in available_claims:
                span_lower = c.source_span.lower()
                # Check if digits match
                if ts_digits and any(d in span_lower.split(":")[0] for d in ts_digits):
                    filtered.append(c)
                elif ts_words and any(w in span_lower for w in ts_words):
                    filtered.append(c)

            if filtered:
                return filtered[:4], [target_section]

        if delivery_mode == DeliveryMode.EXPLAIN_BRIEFLY:
            # Pick top 2-3 highest confidence and impact claims
            sorted_claims = sorted(available_claims, key=lambda c: (len(c.supporting_citation_ids), c.factual_confidence), reverse=True)
            chosen = sorted_claims[:3]
            sections = list({c.source_span.split(":")[0] for c in chosen})
            return chosen, sections

        elif delivery_mode in (DeliveryMode.EXPLAIN_FULLY, DeliveryMode.TEACH_STEP_BY_STEP):
            # Pick claims spanning across headings
            chosen: List[KeyClaim] = []
            sections: List[str] = []
            for heading in understanding.headings:
                heading_claims = [c for c in available_claims if heading.lower() in c.source_span.lower()]
                if heading_claims:
                    chosen.append(heading_claims[0])
                    sections.append(heading)
            if not chosen:
                chosen = available_claims[:4]
                sections = understanding.headings[:len(chosen)]
            return chosen, sections

        elif delivery_mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            # Pick claims related to tradeoffs, limitations, or key assertions
            chosen = available_claims[:4]
            sections = list({c.source_span.split(":")[0] for c in chosen})
            return chosen, sections

        else:
            # Default
            chosen = available_claims[:3]
            sections = list({c.source_span.split(":")[0] for c in chosen})
            return chosen, sections

    def _formulate_framing(
        self,
        delivery_mode: DeliveryMode,
        understanding: ArtifactUnderstanding,
        prior_angles: List[str],
    ) -> tuple[Optional[str], Optional[str]]:
        analogy = None
        perspective = None

        if delivery_mode == DeliveryMode.EXPLAIN_DIFFERENTLY:
            candidate_angles = [
                ("flight_checklist", "Think of this system like a pre-flight checklist: before takeoff, every engine and gauge must confirm readiness."),
                ("water_pipeline", "Imagine this as an irrigation canal system: rather than flooding the entire field at once, water is channeled selectively."),
                ("orchestra_conductor", "Consider this like a symphony: the conductor ensures each instrument plays in tempo without drowning out the melody."),
                ("circuit_breaker", "Like high-voltage electrical fuses, this mechanism prevents localized surges from shutting down the whole building."),
            ]
            for angle_name, angle_analogy in candidate_angles:
                # Check if angle was already used
                already_used = any(
                    angle_name in pa.lower() or angle_analogy in pa or pa in angle_analogy
                    for pa in prior_angles
                )
                if not already_used:
                    analogy = angle_analogy
                    perspective = f"Grounded alternative framing via {angle_name} metaphor"
                    break

            if not analogy:
                # Fallback to last candidate if all were used
                analogy = candidate_angles[-1][1]
                perspective = "Grounded alternative framing"

        elif delivery_mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            perspective = (
                "Critical analytical view: evaluating implementation tradeoffs, operational complexity, "
                "and whether empirical performance justifies architectural overhead."
            )

        return analogy, perspective

    def _build_segment_plan(
        self,
        delivery_mode: DeliveryMode,
        selected_claims: List[KeyClaim],
        time_budget: float,
        analogy: Optional[str],
        perspective: Optional[str],
    ) -> List[Dict[str, Any]]:
        segments: List[Dict[str, Any]] = []

        if delivery_mode == DeliveryMode.READ_VERBATIM:
            segments.append({
                "index": 0,
                "role": "verbatim_narration",
                "target_duration_s": time_budget,
            })
            return segments

        # 1. Lead-in / Briefing Hook (~5s)
        segments.append({
            "index": 0,
            "role": "introduction",
            "target_duration_s": min(6.0, time_budget * 0.2),
            "description": "Conversational opening and primary takeaway overview",
        })

        # 2. Main points / Claims (~15-20s)
        for i, claim in enumerate(selected_claims):
            segments.append({
                "index": i + 1,
                "role": "claim_delivery",
                "claim_id": claim.claim_id,
                "target_duration_s": max(6.0, (time_budget * 0.6) / max(1, len(selected_claims))),
            })

        # 3. Critique / Analogy / Wrap-up (~5-8s)
        segments.append({
            "index": len(selected_claims) + 1,
            "role": "synthesis_and_invitation",
            "target_duration_s": min(8.0, time_budget * 0.2),
            "description": "Tradeoff, analogy, or follow-up question invitation",
        })

        return segments

    def _determine_utterance_goal(self, mode: DeliveryMode, title: str, section: Optional[str]) -> str:
        if mode == DeliveryMode.READ_VERBATIM:
            return f"Deliver exact word-for-word reading of {title}"
        if mode == DeliveryMode.EXPLAIN_BRIEFLY:
            return f"Brief conversational summary of key takeaways from {title}"
        if mode == DeliveryMode.EXPLAIN_FULLY:
            return f"Comprehensive section walkthrough of {title}"
        if mode == DeliveryMode.EXPLAIN_DIFFERENTLY:
            return f"Deliver alternative analogy-based explanation of {title}"
        if mode == DeliveryMode.PERSPECTIVE_AND_CRITIQUE:
            return f"Analyze tradeoffs, counterarguments, and risks for {title}"
        if mode == DeliveryMode.TEACH_STEP_BY_STEP:
            target = f" focused on {section}" if section else ""
            return f"Pedagogical step-by-step guidance{target} for {title}"
        return f"Engage in conversational discussion about {title}"
