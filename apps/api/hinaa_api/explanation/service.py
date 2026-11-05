"""
HINAA OS — Reflective Voice & Metacognitive Explanation Service
Unified service orchestrating Router, Analyzer, Planner, Composer, Verifier,
Speech Coordinator, and Topic Ledger into a cohesive, evidence-grounded pipeline.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .analyzer import ArtifactAnalyzer
from .composer import SpokenScriptComposer
from .contracts import (
    ArtifactUnderstanding,
    DeliveryMode,
    ExplanationPlan,
    SpokenSegment,
)
from .coordinator import SpeechTurnCoordinator
from .ledger import SpokenTopicLedger
from .planner import BoundedSelfModel, MetacognitiveExplanationPlanner
from .router import IntentDeliveryRouter, RouteResult
from .verifier import ExplanationVerifier, VerificationResult

logger = logging.getLogger("hinaa.explanation.service")


class ExplanationService:
    """Master service for reflective explanations, conversation working memory, and verified voice delivery."""

    def __init__(
        self,
        router: Optional[IntentDeliveryRouter] = None,
        analyzer: Optional[ArtifactAnalyzer] = None,
        planner: Optional[MetacognitiveExplanationPlanner] = None,
        composer: Optional[SpokenScriptComposer] = None,
        verifier: Optional[ExplanationVerifier] = None,
        coordinator: Optional[SpeechTurnCoordinator] = None,
        ledger: Optional[SpokenTopicLedger] = None,
    ) -> None:
        self.router = router or IntentDeliveryRouter()
        self.analyzer = analyzer or ArtifactAnalyzer()
        self.planner = planner or MetacognitiveExplanationPlanner()
        self.composer = composer or SpokenScriptComposer()
        self.verifier = verifier or ExplanationVerifier()
        self.coordinator = coordinator or SpeechTurnCoordinator()
        self.ledger = ledger or SpokenTopicLedger()

    def route_request(
        self,
        user_text: str,
        artifact_present: bool = False,
        default_mode: DeliveryMode = DeliveryMode.EXPLAIN_BRIEFLY,
    ) -> RouteResult:
        return self.router.route(user_text, artifact_present=artifact_present, default_mode=default_mode)

    def understand_artifact(
        self,
        artifact_id: str,
        content: str,
        content_type: str = "research_report",
        title: str = "",
        tenant_id: str = "default",
        access_scope: str = "tenant",
        version: int = 1,
        code_receipts: Optional[Dict[str, Any]] = None,
        media_receipts: Optional[Dict[str, Any]] = None,
    ) -> ArtifactUnderstanding:
        return self.analyzer.analyze(
            artifact_id=artifact_id,
            content=content,
            content_type=content_type,
            title=title,
            tenant_id=tenant_id,
            access_scope=access_scope,
            version=version,
            code_receipts=code_receipts,
            media_receipts=media_receipts,
        )

    def plan_explanation(
        self,
        understanding: ArtifactUnderstanding,
        delivery_mode: DeliveryMode,
        conversation_id: str,
        user_goal: str = "",
        audience_level: str = "general",
        language: str = "en",
        time_budget_seconds: float = 30.0,
        target_section: Optional[str] = None,
    ) -> ExplanationPlan:
        # Check topic ledger for already explained claims and prior angles
        already_spoken = self.ledger.get_explained_claim_ids(
            conversation_id=conversation_id,
            artifact_id=understanding.artifact_id,
            tenant_id=understanding.tenant_id,
        )
        prior_angles = self.ledger.get_prior_angles(
            conversation_id=conversation_id,
            artifact_id=understanding.artifact_id,
            tenant_id=understanding.tenant_id,
        )

        return self.planner.plan(
            understanding=understanding,
            delivery_mode=delivery_mode,
            user_goal=user_goal,
            audience_level=audience_level,
            language=language,
            time_budget_seconds=time_budget_seconds,
            already_spoken_claim_ids=already_spoken,
            previous_angles=prior_angles,
            target_section=target_section,
        )

    def compose_and_verify(
        self,
        plan: ExplanationPlan,
        understanding: ArtifactUnderstanding,
    ) -> tuple[str, VerificationResult]:
        initial_script = self.composer.compose(plan, understanding)
        verification = self.verifier.verify(initial_script, plan, understanding)
        final_script = verification.repaired_script or initial_script
        return final_script, verification

    def coordinate_speech(
        self,
        conversation_id: str,
        response_id: str,
        script: str,
        delivery_mode: DeliveryMode,
    ) -> List[SpokenSegment]:
        segments = self.coordinator.plan_segments(
            conversation_id=conversation_id,
            response_id=response_id,
            script=script,
            delivery_mode=delivery_mode,
        )
        for seg in segments:
            self.coordinator.enqueue_segment(conversation_id, seg)
        return segments

    def record_completed_explanation(
        self,
        conversation_id: str,
        artifact_id: str,
        plan: ExplanationPlan,
        speech_turn: int = 1,
        user_feedback: Optional[str] = None,
        tenant_id: str = "default",
    ) -> None:
        narrative_angle = plan.comparison_or_analogy or plan.reason_for_mode
        self.ledger.record_turn(
            conversation_id=conversation_id,
            artifact_id=artifact_id,
            claim_ids=plan.selected_claim_ids,
            narrative_angle=narrative_angle,
            examples_used=[plan.comparison_or_analogy] if plan.comparison_or_analogy else [],
            speech_turn=speech_turn,
            user_feedback=user_feedback,
            tenant_id=tenant_id,
        )

    def handle_barge_in(self, conversation_id: str, reason: str = "user_interruption") -> int:
        return self.coordinator.barge_in(conversation_id, reason=reason)

    def invalidate_artifact(self, artifact_id: str, tenant_id: str = "default") -> None:
        self.analyzer.invalidate(artifact_id, tenant_id)
        self.ledger.invalidate_artifact(artifact_id, tenant_id)

    def get_self_model(self) -> Dict[str, Any]:
        return BoundedSelfModel.get_self_description()
