"""
HINAA OS — Phase 10 Hybrid Retrieval Engine
Combines FTS5 lexical ranking, dense vector semantic similarity,
and knowledge graph traversal with strict token budgeting and provenance attribution.
"""

from __future__ import annotations

import math
import re
from typing import Any, Optional

from .graph import KnowledgeGraphManager
from .repository import MemoryRepository
from .schemas import (
    HybridSearchResult,
    MemoryRecord,
    MemoryScope,
    MemoryType,
)


def _compute_cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return max(0.0, min(1.0, dot / (norm_a * norm_b)))


def _compute_embedding(text: str, dim: int = 128) -> list[float]:
    """Generate normalized deterministic dense vector embedding for text."""
    try:
        from ..rag.retrieval import _deterministic_embedding
        vec = _deterministic_embedding(text, dim=dim)
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec
    except Exception:
        # Fallback character n-gram hashing
        vec = [0.0] * dim
        clean = text.lower().strip()
        for i in range(len(clean) - 2):
            trigram = clean[i : i + 3]
            idx = hash(trigram) % dim
            vec[idx] += 1.0
        norm = math.sqrt(sum(v * v for v in vec))
        return [v / norm for v in vec] if norm > 0 else vec


class HybridRetrievalEngine:
    """Executes multi-modal search combining FTS5, embeddings, and graph traversal."""

    def __init__(self, repository: MemoryRepository, graph_manager: KnowledgeGraphManager) -> None:
        self.repo = repository
        self.graph = graph_manager

    def search(
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
        """
        Execute hybrid search and return (results, tokens_used, was_truncated).
        Blends:
          - Lexical score (FTS5 BM25 match)
          - Semantic score (Dense cosine similarity)
          - Graph score (Neighborhood entity proximity)
        """
        # 1. Candidate retrieval from FTS5
        fts_hits = self.repo.fts_search(query, tenant_id=tenant_id, limit=limit * 2)
        fts_score_map: dict[str, float] = {}
        if fts_hits:
            max_rank = max(s for _, s in fts_hits) or 1.0
            for mem_id, rank in fts_hits:
                fts_score_map[mem_id] = min(1.0, rank / max_rank)

        # 2. General candidates from metadata filter
        all_candidates = self.repo.query_memories(
            tenant_id=tenant_id,
            user_id=user_id,
            project_id=project_id,
            scope=scope,
            memory_type=memory_type,
            include_contradicted=include_contradicted,
            limit=50,
        )

        candidate_map: dict[str, MemoryRecord] = {m.id: m for m in all_candidates}

        # Include FTS hits if not already present
        for mem_id in fts_score_map:
            if mem_id not in candidate_map:
                rec = self.repo.get_memory(mem_id, tenant_id=tenant_id)
                if rec and (include_contradicted or (rec.is_active and not rec.is_contradicted)):
                    candidate_map[mem_id] = rec

        if not candidate_map:
            return ([], 0, False)

        # 3. Dense Embedding similarity
        query_embedding = _compute_embedding(query)
        semantic_score_map: dict[str, float] = {}
        for mem_id, rec in candidate_map.items():
            if rec.embedding is None:
                rec_embedding = _compute_embedding(rec.content)
            else:
                rec_embedding = rec.embedding
            semantic_score_map[mem_id] = _compute_cosine_similarity(query_embedding, rec_embedding)

        # 4. Knowledge Graph Expansion
        graph_boost_map: dict[str, float] = {}
        query_words = re.findall(r"\w+", query)
        for word in query_words:
            matched_node = self.repo.find_node_by_name(word, tenant_id=tenant_id)
            if matched_node:
                # Traverse 1 hop
                _, edges = self.graph.traverse_subgraph(matched_node.id, tenant_id=tenant_id, max_depth=1, max_nodes=10)
                for edge in edges:
                    if edge.evidence_id and edge.evidence_id in candidate_map:
                        graph_boost_map[edge.evidence_id] = max(graph_boost_map.get(edge.evidence_id, 0.0), 1.0)

        # 5. Hybrid Fusion
        scored_results: list[HybridSearchResult] = []
        for mem_id, rec in candidate_map.items():
            lex = fts_score_map.get(mem_id, 0.0)
            sem = semantic_score_map.get(mem_id, 0.0)
            graph = graph_boost_map.get(mem_id, 0.0)

            # Combined weighted score
            final_score = (0.45 * lex) + (0.40 * sem) + (0.15 * graph)

            # Recency & Confidence modifiers
            final_score = final_score * rec.confidence

            # Extract matching terms
            matched_terms = [w for w in query_words if w.lower() in rec.content.lower()]

            provenance = {
                "source_url": rec.source_url,
                "source_tool": rec.source_tool,
                "evidence_text": rec.evidence_text,
                "created_at": rec.created_at,
                "trust_tier": rec.trust_tier.value,
                "confidence": rec.confidence,
            }

            scored_results.append(
                HybridSearchResult(
                    record=rec,
                    score=round(final_score, 4),
                    lexical_score=round(lex, 4),
                    semantic_score=round(sem, 4),
                    graph_score=round(graph, 4),
                    matched_terms=matched_terms,
                    provenance=provenance,
                )
            )

        # Sort descending by score
        scored_results.sort(key=lambda r: r.score, reverse=True)

        # 6. Token Budgeting
        token_limit = token_budget if token_budget is not None else 2048
        current_tokens = 0
        budgeted_results: list[HybridSearchResult] = []
        truncated = False

        for res in scored_results:
            # Estimate tokens ~ 4 characters per token
            item_tokens = max(1, len(res.record.content) // 4)
            if current_tokens + item_tokens <= token_limit:
                budgeted_results.append(res)
                current_tokens += item_tokens
                if len(budgeted_results) >= limit:
                    break
            else:
                truncated = True
                break

        return (budgeted_results, current_tokens, truncated)
