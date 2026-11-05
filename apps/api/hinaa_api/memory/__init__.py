"""
HINAA OS — Phase 10 Long-Term Memory, Continuous Knowledge Graph & Verified Learning
Package root exporting durable transactional memory, temporal knowledge graph,
hybrid retrieval engine, and legacy session memory compatibility wrappers.
"""

from __future__ import annotations

# Legacy SessionMemory backwards compatibility
from .session_memory import (
    SessionMemory,
    _NAME_PATTERNS,
    _LIKE_PATTERNS,
    _DISLIKE_PATTERNS,
    _TOPIC_PATTERNS,
    _EXPLICIT_PATTERNS,
    _MAX_LEARNED_MEMORIES,
    _MAX_MEMORY_CHARS,
    _clean_fact,
)

# Phase 10 Core Engine & Models
from .schemas import (
    MemoryScope,
    MemoryType,
    TrustTier,
    CandidateStatus,
    MemoryRecord,
    KnowledgeNode,
    KnowledgeEdge,
    IngestionCandidate,
    MemoryEvent,
    HybridSearchResult,
    MemoryStats,
    CreateMemoryRequest,
    UpdateMemoryRequest,
    MemorySearchRequest,
    MemorySearchResponse,
    MemoryExportRequest,
    ReviewCandidateRequest,
    GraphQueryRequest,
    GraphResponse,
)

from .privacy import MemoryPrivacyGuard
from .repository import MemoryRepository
from .graph import KnowledgeGraphManager
from .retrieval import HybridRetrievalEngine
from .contradictions import ContradictionDetector
from .ingestion import KnowledgeIngestionPipeline
from .lifecycle import MemoryLifecycleCoordinator
from .service import MemoryService

__all__ = [
    # Legacy
    "SessionMemory",
    "_NAME_PATTERNS",
    "_LIKE_PATTERNS",
    "_DISLIKE_PATTERNS",
    "_TOPIC_PATTERNS",
    "_EXPLICIT_PATTERNS",
    "_MAX_LEARNED_MEMORIES",
    "_MAX_MEMORY_CHARS",
    "_clean_fact",
    # Schemas
    "MemoryScope",
    "MemoryType",
    "TrustTier",
    "CandidateStatus",
    "MemoryRecord",
    "KnowledgeNode",
    "KnowledgeEdge",
    "IngestionCandidate",
    "MemoryEvent",
    "HybridSearchResult",
    "MemoryStats",
    "CreateMemoryRequest",
    "UpdateMemoryRequest",
    "MemorySearchRequest",
    "MemorySearchResponse",
    "MemoryExportRequest",
    "ReviewCandidateRequest",
    "GraphQueryRequest",
    "GraphResponse",
    # Modules & Facade
    "MemoryPrivacyGuard",
    "MemoryRepository",
    "KnowledgeGraphManager",
    "HybridRetrievalEngine",
    "ContradictionDetector",
    "KnowledgeIngestionPipeline",
    "MemoryLifecycleCoordinator",
    "MemoryService",
]
