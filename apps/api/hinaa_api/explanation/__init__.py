"""
HINAA OS — Reflective Voice & Metacognitive Explanation Module
"""

from .contracts import (
    ArtifactUnderstanding,
    ClaimPerspective,
    DeliveryMode,
    ExplanationPlan,
    KeyClaim,
    SpokenSegment,
    SpokenTopicRecord,
    TurnState,
    compute_segment_idempotency_key,
)
from .router import IntentDeliveryRouter, RouteResult
from .analyzer import ArtifactAnalyzer
from .planner import BoundedSelfModel, MetacognitiveExplanationPlanner
from .composer import SpokenScriptComposer
from .verifier import ExplanationVerifier, VerificationResult
from .coordinator import SpeechTurnCoordinator, SegmentTelemetry, TurnSession
from .ledger import SpokenTopicLedger
from .service import ExplanationService

__all__ = [
    "ArtifactUnderstanding",
    "ClaimPerspective",
    "DeliveryMode",
    "ExplanationPlan",
    "KeyClaim",
    "SpokenSegment",
    "SpokenTopicRecord",
    "TurnState",
    "compute_segment_idempotency_key",
    "IntentDeliveryRouter",
    "RouteResult",
    "ArtifactAnalyzer",
    "BoundedSelfModel",
    "MetacognitiveExplanationPlanner",
    "SpokenScriptComposer",
    "ExplanationVerifier",
    "VerificationResult",
    "SpeechTurnCoordinator",
    "SegmentTelemetry",
    "TurnSession",
    "SpokenTopicLedger",
    "ExplanationService",
]
