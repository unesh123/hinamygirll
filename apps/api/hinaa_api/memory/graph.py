"""
HINAA OS — Phase 10 Temporal Knowledge Graph Manager
Directed typed relationships, bilingual alias resolution (English & Devanagari Nepali),
cycle-safe bounded traversal, and point-in-time temporal queries.
"""

from __future__ import annotations

import collections
import logging
from typing import Any, Optional

from .repository import MemoryRepository
from .schemas import (
    KnowledgeEdge,
    KnowledgeNode,
    MemoryScope,
    _now_iso,
)

logger = logging.getLogger("hinaa.memory.graph")

# Built-in multilingual alias mappings (English, Romanized Nepali, Devanagari)
COMMON_ALIASES: dict[str, list[str]] = {
    "Kathmandu": ["काठमाडौं", "काठमाडौँ", "KTM", "Kantipur"],
    "Pokhara": ["पोखरा", "PKR"],
    "Lalitpur": ["ललितपुर", "Patan", "पाटन"],
    "Nepal": ["नेपाल", "NP"],
    "Python": ["python3", "py"],
    "TypeScript": ["typescript", "ts"],
    "FastAPI": ["fastapi"],
    "PostgreSQL": ["postgres", "pgsql"],
    "English": ["अंग्रेजी", "en"],
    "Nepali": ["नेपाली", "ne"],
}


class KnowledgeGraphManager:
    """Manages knowledge graph nodes, edges, cycle-safe traversals, and temporal queries."""

    def __init__(self, repository: MemoryRepository) -> None:
        self.repo = repository

    def resolve_canonical_name(self, name_or_alias: str) -> str:
        """Resolve a name or alias (including Nepali Devanagari) to canonical form."""
        query = name_or_alias.strip()
        if not query:
            return query

        # Check in-memory alias dictionary
        q_lower = query.lower()
        for canonical, aliases in COMMON_ALIASES.items():
            if canonical.lower() == q_lower:
                return canonical
            if any(a.lower() == q_lower for a in aliases):
                return canonical

        return query

    def get_or_create_node(
        self,
        name: str,
        entity_type: str = "Concept",
        tenant_id: str = "default",
        scope: MemoryScope = MemoryScope.USER,
        attributes: Optional[dict[str, Any]] = None,
    ) -> KnowledgeNode:
        """Fetch existing node by canonical name or alias, or create new."""
        canonical = self.resolve_canonical_name(name)
        existing = self.repo.find_node_by_name(canonical, tenant_id=tenant_id)
        if existing:
            return existing

        aliases: list[str] = []
        if canonical in COMMON_ALIASES:
            aliases.extend(COMMON_ALIASES[canonical])
        if name != canonical and name not in aliases:
            aliases.append(name)

        node = KnowledgeNode(
            tenant_id=tenant_id,
            scope=scope,
            entity_type=entity_type,
            canonical_name=canonical,
            aliases=aliases,
            attributes=attributes or {},
        )
        return self.repo.save_node(node)

    def add_relation(
        self,
        source_name: str,
        target_name: str,
        relation_type: str,
        tenant_id: str = "default",
        evidence_id: Optional[str] = None,
        confidence: float = 1.0,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        is_contradiction: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ) -> KnowledgeEdge:
        """Establish directed relationship between two entities."""
        src_node = self.get_or_create_node(source_name, tenant_id=tenant_id)
        tgt_node = self.get_or_create_node(target_name, tenant_id=tenant_id)

        edge = KnowledgeEdge(
            tenant_id=tenant_id,
            source_id=src_node.id,
            target_id=tgt_node.id,
            relation_type=relation_type.upper(),
            evidence_id=evidence_id,
            confidence=confidence,
            valid_from=valid_from or _now_iso(),
            valid_to=valid_to,
            is_contradiction=is_contradiction,
            metadata=metadata or {},
        )
        return self.repo.save_edge(edge)

    def traverse_subgraph(
        self,
        start_node_id: str,
        tenant_id: str = "default",
        max_depth: int = 2,
        max_nodes: int = 30,
        as_of_date: Optional[str] = None,
    ) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
        """
        Cycle-safe bounded breadth-first traversal starting from a node.
        Guarantees max_depth <= 3 and max_nodes <= 50 to prevent infinite loops.
        """
        # Hard bounds
        bounded_depth = max(1, min(max_depth, 3))
        bounded_max_nodes = max(1, min(max_nodes, 50))

        start_node = self.repo.get_node(start_node_id, tenant_id=tenant_id)
        if not start_node:
            return ([], [])

        visited_nodes: dict[str, KnowledgeNode] = {start_node.id: start_node}
        collected_edges: list[KnowledgeEdge] = []
        edge_ids: set[str] = set()

        # Queue contains (node_id, current_depth)
        queue: collections.deque[tuple[str, int]] = collections.deque([(start_node.id, 0)])

        while queue and len(visited_nodes) < bounded_max_nodes:
            curr_id, depth = queue.popleft()
            if depth >= bounded_depth:
                continue

            # Find outgoing and incoming edges for comprehensive neighborhood
            out_edges = self.repo.query_edges(
                tenant_id=tenant_id,
                source_id=curr_id,
                as_of_date=as_of_date,
                limit=bounded_max_nodes,
            )
            in_edges = self.repo.query_edges(
                tenant_id=tenant_id,
                target_id=curr_id,
                as_of_date=as_of_date,
                limit=bounded_max_nodes,
            )

            for edge in out_edges + in_edges:
                if edge.id not in edge_ids:
                    edge_ids.add(edge.id)
                    collected_edges.append(edge)

                next_id = edge.target_id if edge.source_id == curr_id else edge.source_id
                if next_id not in visited_nodes:
                    next_node = self.repo.get_node(next_id, tenant_id=tenant_id)
                    if next_node:
                        visited_nodes[next_id] = next_node
                        queue.append((next_id, depth + 1))
                        if len(visited_nodes) >= bounded_max_nodes:
                            break

        return (list(visited_nodes.values()), collected_edges)

    def find_contradictory_edges(
        self,
        source_id: str,
        target_id: str,
        relation_type: str,
        tenant_id: str = "default",
    ) -> list[KnowledgeEdge]:
        """Find active edges between source and target that conflict with a new relation."""
        edges = self.repo.query_edges(tenant_id=tenant_id, source_id=source_id, target_id=target_id)
        return [e for e in edges if e.relation_type == relation_type and not e.superseded_by]
