"""Grounded Research & Corrective RAG (CRAG) Package for HINAA OS."""

from .models import (
    Claim,
    ClaimSupport,
    ClaimSupportStatus,
    CRAGVerdict,
    EvidenceSpan,
    ResearchAnswer,
    ResearchIntent,
    ResearchTrace,
    Source,
    TrustTier,
)
from .intent_router import ResearchIntentRouter, IntentRoutingDecision
from .adapters import BaseSearchAdapter, MockSearchAdapter, LiveSearchAdapter, MOCK_CORPUS
from .crag import CRAGEngine
from .multi_hop import MultiHopPlanner
from .grounding import ClaimGroundingVerifier
from .security import ResearchSecurityGuard
from .coordinator import GroundedResearchCoordinator

__all__ = [
    "Claim",
    "ClaimSupport",
    "ClaimSupportStatus",
    "CRAGVerdict",
    "EvidenceSpan",
    "ResearchAnswer",
    "ResearchIntent",
    "ResearchTrace",
    "Source",
    "TrustTier",
    "ResearchIntentRouter",
    "IntentRoutingDecision",
    "BaseSearchAdapter",
    "MockSearchAdapter",
    "LiveSearchAdapter",
    "MOCK_CORPUS",
    "CRAGEngine",
    "MultiHopPlanner",
    "ClaimGroundingVerifier",
    "ResearchSecurityGuard",
    "GroundedResearchCoordinator",
]
