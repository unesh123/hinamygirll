"""
HINAA OS — Phase 10 Unified Memory Service Facade
Single entry point integrating persistence, temporal knowledge graph,
hybrid search, contradiction resolution, privacy guard, and continuous ingestion.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from .contradictions import ContradictionDetector
from .graph import KnowledgeGraphManager
from .ingestion import KnowledgeIngestionPipeline
from .lifecycle import MemoryLifecycleCoordinator
from .privacy import MemoryPrivacyGuard
from .repository import MemoryRepository
from .retrieval import HybridRetrievalEngine
from .schemas import (
    CandidateStatus,
    CreateMemoryRequest,
    HybridSearchResult,
    IngestionCandidate,
    KnowledgeEdge,
    KnowledgeNode,
    MemoryRecord,
    MemoryScope,
    MemoryStats,
    MemoryType,
    TrustTier,
    UpdateMemoryRequest,
)

logger = logging.getLogger("hinaa.memory.service")


class MemoryService:
    """Enterprise-grade long-term memory and knowledge graph facade."""

    def __init__(self, db_path: Optional[str | Path] = None) -> None:
        self.repo = MemoryRepository(db_path=db_path)
        self.graph = KnowledgeGraphManager(self.repo)
        self.retrieval = HybridRetrievalEngine(self.repo, self.graph)
        self.contradictions = ContradictionDetector(self.repo, self.graph)
        self.ingestion = KnowledgeIngestionPipeline(self.repo)
        self.lifecycle = MemoryLifecycleCoordinator(self.repo)

    # -----------------------------------------------------------------------
    # Core Memory Operations
    # -----------------------------------------------------------------------

    def create_memory(self, req: CreateMemoryRequest) -> MemoryRecord:
        """Create a new memory record, check for contradictions, and link relations."""
        # 1. Tenant validation
        MemoryPrivacyGuard.assert_tenant_access(req.tenant_id, req.tenant_id)

        # 2. Check for contradictions against active records
        conflicting = self.contradictions.find_contradictions(
            new_content=req.content,
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            project_id=req.project_id,
            memory_type=req.memory_type,
        )

        record = MemoryRecord(
            tenant_id=req.tenant_id,
            user_id=req.user_id,
            project_id=req.project_id,
            scope=req.scope,
            memory_type=req.memory_type,
            content=req.content,
            structured_data=req.structured_data,
            trust_tier=req.trust_tier,
            confidence=req.confidence,
            source_url=req.source_url,
            source_tool=req.source_tool,
            evidence_text=req.evidence_text,
            expires_at=req.expires_at,
        )

        saved = self.repo.save_memory(record)

        # 3. Resolve supersession if conflicts exist
        if conflicting:
            self.contradictions.resolve_supersession(saved, conflicting)

        # 4. Create or link entity in knowledge graph if applicable
        if req.memory_type in (MemoryType.PREFERENCE, MemoryType.FACT, MemoryType.ENTITY):
            entity_name = req.structured_data.get("entity") or (req.user_id if req.user_id else "User")
            node = self.graph.get_or_create_node(
                name=entity_name,
                entity_type="Concept",
                tenant_id=req.tenant_id,
                scope=req.scope,
            )
            self.graph.add_relation(
                source_name=node.canonical_name,
                target_name=saved.content[:30],
                relation_type="ASSERTS",
                tenant_id=req.tenant_id,
                evidence_id=saved.id,
                confidence=saved.confidence,
            )

        return saved

    def get_memory(self, memory_id: str, tenant_id: str = "default") -> Optional[MemoryRecord]:
        return self.repo.get_memory(memory_id, tenant_id=tenant_id)

    def update_memory(self, memory_id: str, req: UpdateMemoryRequest, tenant_id: str = "default") -> Optional[MemoryRecord]:
        updates = req.model_dump(exclude_unset=True)
        reason = updates.pop("reason", None)
        return self.repo.update_memory(memory_id, updates, tenant_id=tenant_id, reason=reason)

    def delete_memory(self, memory_id: str, tenant_id: str = "default") -> bool:
        return self.lifecycle.delete_with_cascade(memory_id, tenant_id=tenant_id)

    def list_memories(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: Optional[MemoryScope] = None,
        memory_type: Optional[MemoryType] = None,
        include_contradicted: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MemoryRecord]:
        return self.repo.query_memories(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            memory_type=memory_type,
            include_contradicted=include_contradicted,
            limit=limit,
            offset=offset,
        )

    def search_memories(
        self,
        query: str,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: Optional[MemoryScope] = None,
        memory_type: Optional[MemoryType] = None,
        include_contradicted: bool = False,
        limit: int = 10,
        token_budget: Optional[int] = 2048,
    ) -> tuple[list[HybridSearchResult], int, bool]:
        return self.retrieval.search(
            query=query,
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            memory_type=memory_type,
            include_contradicted=include_contradicted,
            limit=limit,
            token_budget=token_budget,
        )

    # -----------------------------------------------------------------------
    # Knowledge Graph Operations
    # -----------------------------------------------------------------------

    def get_knowledge_graph(
        self,
        tenant_id: str = "default",
        entity_name: Optional[str] = None,
        entity_type: Optional[str] = None,
        max_depth: int = 2,
        max_nodes: int = 30,
        as_of_date: Optional[str] = None,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """Return graph nodes and edges matching query or starting from entity."""
        if entity_name:
            node = self.repo.find_node_by_name(entity_name, tenant_id=tenant_id)
            if node:
                return self.graph.traverse_subgraph(
                    start_node_id=node.id,
                    tenant_id=tenant_id,
                    max_depth=max_depth,
                    max_nodes=max_nodes,
                    as_of_date=as_of_date,
                )

        nodes = self.repo.query_nodes(tenant_id=tenant_id, entity_type=entity_type, limit=max_nodes)
        node_ids = {n.id for n in nodes}
        edges = self.repo.query_edges(tenant_id=tenant_id, as_of_date=as_of_date, limit=max_nodes * 2)
        filtered_edges = [e for e in edges if e.source_id in node_ids or e.target_id in node_ids]
        return (nodes, filtered_edges)

    # -----------------------------------------------------------------------
    # Continuous Ingestion Pipeline
    # -----------------------------------------------------------------------

    def stage_candidate(
        self,
        candidate_fact: str,
        source_url: Optional[str] = None,
        source_tool: Optional[str] = None,
        raw_evidence: str = "",
        tenant_id: str = "default",
        trust_tier: TrustTier = TrustTier.STAGED,
    ) -> IngestionCandidate:
        return self.ingestion.stage_candidate(
            candidate_fact=candidate_fact,
            source_url=source_url,
            source_tool=source_tool,
            raw_evidence=raw_evidence,
            tenant_id=tenant_id,
            trust_tier=trust_tier,
        )

    def review_candidate(
        self,
        candidate_id: str,
        decision: str,
        tenant_id: str = "default",
        review_notes: Optional[str] = None,
        promoted_scope: MemoryScope = MemoryScope.USER,
        promoted_type: MemoryType = MemoryType.FACT,
    ) -> tuple[Optional[IngestionCandidate], Optional[MemoryRecord]]:
        return self.ingestion.review_candidate(
            candidate_id=candidate_id,
            decision=decision,
            tenant_id=tenant_id,
            review_notes=review_notes,
            promoted_scope=promoted_scope,
            promoted_type=promoted_type,
        )

    def list_candidates(
        self,
        tenant_id: str = "default",
        status: Optional[CandidateStatus] = None,
        limit: int = 50,
    ) -> list[IngestionCandidate]:
        return self.repo.list_candidates(tenant_id=tenant_id, status=status, limit=limit)

    # -----------------------------------------------------------------------
    # Lifecycle & System Ops
    # -----------------------------------------------------------------------

    def export_memories(
        self,
        tenant_id: str = "default",
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        scope: Optional[MemoryScope] = None,
        format_type: str = "json",
    ) -> str:
        return self.lifecycle.export_data(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            format_type=format_type,
        )

    def get_stats(self, tenant_id: str = "default") -> MemoryStats:
        return self.repo.get_stats(tenant_id=tenant_id)

    def run_ttl_purge(self, current_time: Optional[str] = None) -> int:
        return self.lifecycle.run_ttl_maintenance(current_time=current_time)

    # -----------------------------------------------------------------------
    # Integration Helpers (Chat / Prompt Assembly)
    # -----------------------------------------------------------------------

    def recall_for_context(
        self,
        query: str,
        user_id: Optional[str] = None,
        project_id: Optional[str] = None,
        tenant_id: str = "default",
        token_budget: int = 1024,
    ) -> list[str]:
        """Format retrieved durable memories into clean context strings for LLM prompts."""
        results, _, _ = self.search_memories(
            query=query,
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            limit=8,
            token_budget=token_budget,
        )
        return [f"[{r.record.memory_type.value.upper()}]: {r.record.content}" for r in results]
