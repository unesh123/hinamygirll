"""
HINAA OS — Phase 10 Continuous Knowledge Acquisition Pipeline
Stages candidate facts from CRAG, browser runs, and coding actions into a quarantined queue.
Prevents unverified memory pollution and provides a verified promotion workflow.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Optional

from .privacy import MemoryPrivacyGuard
from .repository import MemoryRepository
from .schemas import (
    CandidateStatus,
    IngestionCandidate,
    MemoryRecord,
    MemoryScope,
    MemoryType,
    TrustTier,
    _now_iso,
)

logger = logging.getLogger("hinaa.memory.ingestion")


class KnowledgeIngestionPipeline:
    """Quarantine staging area for automated knowledge acquisition."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repo = repository

    def stage_candidate(
        self,
        candidate_fact: str,
        source_url: Optional[str] = None,
        source_tool: Optional[str] = None,
        raw_evidence: str = "",
        tenant_id: str = "default",
        trust_tier: TrustTier = TrustTier.STAGED,
    ) -> IngestionCandidate:
        """Sanitize and stage a discovered fact for human or agent review."""
        clean_fact = MemoryPrivacyGuard.sanitize_content(candidate_fact.strip())

        # Simple entity extraction heuristic (capitalized sequences)
        entities: list[dict[str, str]] = []
        found_names = re.findall(r"\b[A-Z][a-zA-Z0-9_\-]{2,}\b", clean_fact)
        for name in set(found_names):
            entities.append({"name": name, "type": "Entity"})

        candidate = IngestionCandidate(
            tenant_id=tenant_id,
            candidate_fact=clean_fact,
            source_url=source_url,
            source_tool=source_tool,
            raw_evidence=raw_evidence,
            extracted_entities=entities,
            trust_tier=trust_tier,
            status=CandidateStatus.PENDING,
        )

        return self.repo.save_candidate(candidate)

    def review_candidate(
        self,
        candidate_id: str,
        decision: str,  # "approve" or "reject"
        tenant_id: str = "default",
        review_notes: Optional[str] = None,
        promoted_scope: MemoryScope = MemoryScope.USER,
        promoted_type: MemoryType = MemoryType.FACT,
    ) -> tuple[Optional[IngestionCandidate], Optional[MemoryRecord]]:
        """Approve or reject a staged candidate. Approved items are promoted to active memories."""
        candidate = self.repo.get_candidate(candidate_id, tenant_id=tenant_id)
        if not candidate:
            return (None, None)

        if decision.lower() == "approve":
            updated_candidate = self.repo.update_candidate_status(
                candidate_id=candidate_id,
                status=CandidateStatus.APPROVED,
                review_notes=review_notes or "Approved by operator",
                tenant_id=tenant_id,
            )

            # Promote to permanent memory record
            promoted_memory = MemoryRecord(
                tenant_id=tenant_id,
                scope=promoted_scope,
                memory_type=promoted_type,
                content=candidate.candidate_fact,
                trust_tier=TrustTier.VERIFIED,
                confidence=0.95,
                source_url=candidate.source_url,
                source_tool=candidate.source_tool,
                evidence_text=candidate.raw_evidence,
            )
            saved_memory = self.repo.save_memory(promoted_memory)
            return (updated_candidate, saved_memory)

        else:
            updated_candidate = self.repo.update_candidate_status(
                candidate_id=candidate_id,
                status=CandidateStatus.REJECTED,
                review_notes=review_notes or "Rejected during verification",
                tenant_id=tenant_id,
            )
            return (updated_candidate, None)

    def list_pending(self, tenant_id: str = "default", limit: int = 50) -> list[IngestionCandidate]:
        """List candidates awaiting review."""
        return self.repo.list_candidates(tenant_id=tenant_id, status=CandidateStatus.PENDING, limit=limit)
