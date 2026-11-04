"""Typed Domain Models for Grounded Research & Corrective RAG (CRAG).

Adheres to HINAA OS Phase 06 Directive:
- Typed Source, EvidenceSpan, Claim, ClaimSupport, ResearchTrace, ResearchAnswer
- Explicit claim support categorization (Directly Supported, Partially Supported, Disputed, Unsupported, Unverifiable)
- OWASP RAG trust boundaries and provenance tracking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
from typing import Any, Literal
from pydantic import BaseModel, Field


class ResearchIntent(str, Enum):
    CONVERSATIONAL = "conversational"
    FACTUAL_RESEARCH = "factual_research"
    TIME_SENSITIVE = "time_sensitive"
    WORKSPACE_CODE = "workspace_code"
    MULTI_HOP = "multi_hop"
    HIGH_STAKES = "high_stakes"


class CRAGVerdict(str, Enum):
    CORRECT = "CORRECT"        # High confidence, retrieved docs relevant and sufficient
    INCORRECT = "INCORRECT"    # Low confidence, retrieved docs irrelevant -> rewrite & web search
    AMBIGUOUS = "AMBIGUOUS"    # Mixed relevance -> decompose strips and augment with targeted search


class ClaimSupportStatus(str, Enum):
    DIRECTLY_SUPPORTED = "DIRECTLY_SUPPORTED"
    PARTIALLY_SUPPORTED = "PARTIALLY_SUPPORTED"
    DISPUTED = "DISPUTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNVERIFIABLE = "UNVERIFIABLE"


class TrustTier(str, Enum):
    VERIFIED_PRIMARY = "verified_primary"        # Official docs, peer-reviewed, government
    REPUTABLE_SECONDARY = "reputable_secondary"  # Established news, known tech portals
    COMMUNITY = "community"                      # Forums, blogs, social posts
    UNTRUSTED = "untrusted"                      # Anonymous mirrors, unvetted pages


class Source(BaseModel):
    source_id: str
    title: str
    url: str
    canonical_url: str | None = None
    publisher: str = "Unknown"
    author: str | None = None
    publication_date: str | None = None
    event_date: str | None = None
    retrieval_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    license: str | None = None
    excerpt: str = ""
    content_hash: str = ""
    query: str = ""
    trust_tier: TrustTier = TrustTier.REPUTABLE_SECONDARY
    is_private: bool = False
    tenant_id: str | None = None
    simhash: int | None = None

    def compute_hash(self, content: str) -> str:
        h = hashlib.sha256(content.encode("utf-8")).hexdigest()
        self.content_hash = h
        return h


class EvidenceSpan(BaseModel):
    span_id: str
    source_id: str
    text: str
    start_char: int = 0
    end_char: int = 0
    page_number: int | None = None
    confidence: float = 1.0


class Claim(BaseModel):
    claim_id: str
    text: str
    claim_type: Literal["fact", "inference", "opinion", "disputed"] = "fact"


class ClaimSupport(BaseModel):
    claim_id: str
    status: ClaimSupportStatus
    supporting_spans: list[EvidenceSpan] = Field(default_factory=list)
    contradicting_spans: list[EvidenceSpan] = Field(default_factory=list)
    entailment_score: float = 0.0
    rationale: str = ""


class ResearchTrace(BaseModel):
    trace_id: str
    query: str
    intent: ResearchIntent
    decomposed_queries: list[str] = Field(default_factory=list)
    hops_executed: int = 0
    total_sources_retrieved: int = 0
    unique_sources_accepted: int = 0
    duplicates_filtered: int = 0
    crag_eval_verdicts: list[CRAGVerdict] = Field(default_factory=list)
    corrective_rewrites_triggered: int = 0
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
    budget_used_queries: int = 0
    security_flags: list[str] = Field(default_factory=list)


class ResearchAnswer(BaseModel):
    answer_text: str
    claims: list[Claim] = Field(default_factory=list)
    claim_supports: list[ClaimSupport] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    unverified_citations_stripped: list[str] = Field(default_factory=list)
    abstention_occurred: bool = False
    abstention_reason: str | None = None
    trace: ResearchTrace
