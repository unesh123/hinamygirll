"""RAG Knowledge Service for HINAA.

Coordinates document chunking, hybrid retrieval (BM25 + Dense Vector + Entity Graph),
multi-criteria reranking (MMR), and automated prompt context compilation.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any, List, Optional

from .ingestion import ChunkMetadata, StructuredChunk, StructuredChunker
from .provenance import CitationSpan, ProvenanceEngine
from .rerank import RerankedResult, Reranker
from .retrieval import HybridRetriever, RetrievalResult

logger = logging.getLogger("hinaa.rag.service")

# Common patterns indicating user is seeking knowledge from docs/code/specs
KNOWLEDGE_SEEKING_PATTERNS = [
    re.compile(r"\b(?:architecture|spec|specifications?|harness|sandbox|policy|security|threat model)\b", re.IGNORECASE),
    re.compile(r"\b(?:convention|code standards?|quality|invariants?|cve-2025|ghsa|mitigation)\b", re.IGNORECASE),
    re.compile(r"\b(?:repository|active-plan|decisions?|rag|retrieval|pipeline|how does .* work)\b", re.IGNORECASE),
    re.compile(r"\b(?:explain the structure|explain the codebase|what are the rules|system design)\b", re.IGNORECASE),
    re.compile(r"^(?:@doc|@rag|@knowledge)\b", re.IGNORECASE),
]


class RAGKnowledgeService:
    """Enterprise RAG Coordinator connecting document repositories to LLM turn planning."""

    def __init__(
        self,
        workspace_root: Optional[str] = None,
        target_chunk_tokens: int = 120,
        overlap_tokens: int = 20,
        bm25_weight: float = 0.45,
        vector_weight: float = 0.40,
        entity_weight: float = 0.15,
    ) -> None:
        self.workspace_root = Path(workspace_root or os.getcwd()).resolve()
        self.chunker = StructuredChunker(
            target_chunk_tokens=target_chunk_tokens,
            overlap_tokens=overlap_tokens,
        )
        self.retriever = HybridRetriever(
            bm25_weight=bm25_weight,
            vector_weight=vector_weight,
            entity_weight=entity_weight,
        )
        self.reranker = Reranker(
            relevance_weight=0.55,
            authority_weight=0.25,
            recency_weight=0.20,
            diversity_lambda=0.75,
        )
        self.provenance = ProvenanceEngine()
        self._all_chunks: List[StructuredChunk] = []
        self._indexed_doc_ids: set[str] = set()

    @property
    def total_chunks(self) -> int:
        return len(self._all_chunks)

    @property
    def total_documents(self) -> int:
        return len(self._indexed_doc_ids)

    def is_knowledge_seeking(self, text: str) -> bool:
        """Determines if the turn warrants automatic RAG document retrieval."""
        if not text:
            return False
        clean = text.strip()
        for pattern in KNOWLEDGE_SEEKING_PATTERNS:
            if pattern.search(clean):
                return True
        return False

    def ingest_document(
        self,
        text: str,
        document_id: str,
        source: str,
        author: str = "system",
        version: str = "1.0",
        visibility: str = "internal",
    ) -> List[StructuredChunk]:
        """Ingests, chunks, and indexes a raw document into the hybrid retriever."""
        if not text.strip():
            return []

        # Remove previous chunks of the same document if re-ingesting
        if document_id in self._indexed_doc_ids:
            self._all_chunks = [c for c in self._all_chunks if c.metadata.document_id != document_id]

        chunks = self.chunker.chunk(
            text,
            document_id=document_id,
            source=source,
            version=version,
            visibility=visibility,
        )

        self._all_chunks.extend(chunks)
        self._indexed_doc_ids.add(document_id)
        self.retriever.index(self._all_chunks)
        logger.info(
            "Ingested document '%s' (%s): %d chunks. Total index size: %d chunks.",
            document_id,
            source,
            len(chunks),
            len(self._all_chunks),
        )
        return chunks

    def index_repository_memory(self, workspace_root: Optional[str | Path] = None) -> int:
        """Indexes all `.hina/` specs and decisions from the workspace or repository root."""
        candidate_roots = [
            Path(workspace_root) if workspace_root else None,
            self.workspace_root,
            Path.cwd(),
            Path(__file__).resolve().parents[3],
        ]
        
        hina_dir = None
        for cand in candidate_roots:
            if cand and (cand / ".hina").exists():
                hina_dir = (cand / ".hina").resolve()
                break

        if not hina_dir or not hina_dir.exists():
            return 0

        indexed_count = 0
        for md_file in hina_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
                doc_id = f"hina_spec_{md_file.stem}"
                self.ingest_document(
                    text=content,
                    document_id=doc_id,
                    source=f".hina/{md_file.name}",
                    author="Hinaa Harness Spec",
                    version="2.0",
                    visibility="internal",
                )
                indexed_count += 1
            except Exception as exc:
                logger.warning("Failed to index repository spec %s: %s", md_file, exc)

        decisions_dir = hina_dir / "decisions"
        if decisions_dir.exists():
            for dec_file in decisions_dir.glob("*.md"):
                try:
                    content = dec_file.read_text(encoding="utf-8")
                    doc_id = f"hina_dec_{dec_file.stem}"
                    self.ingest_document(
                        text=content,
                        document_id=doc_id,
                        source=f".hina/decisions/{dec_file.name}",
                        author="Hinaa ADR",
                        version="1.0",
                        visibility="internal",
                    )
                    indexed_count += 1
                except Exception as exc:
                    logger.warning("Failed to index ADR %s: %s", dec_file, exc)

        return indexed_count

    def query(
        self,
        query_text: str,
        *,
        top_k: int = 4,
        score_threshold: float = 0.20,
    ) -> List[RerankedResult]:
        """Runs hybrid search (BM25 + Vector) and MMR reranking."""
        if not self._all_chunks or not query_text.strip():
            return []

        # Retrieve a wider pool for reranking
        candidates = self.retriever.retrieve(query_text, top_k=max(top_k * 3, 10))
        if not candidates:
            return []

        reranked = self.reranker.rerank(
            query_text,
            candidates,
            top_k=top_k,
        )

        filtered = [r for r in reranked if r.final_score >= score_threshold]
        return filtered

    def format_context_block(self, query_text: str, top_k: int = 3) -> str:
        """Formats the top grounded knowledge chunks into a structured LLM context block."""
        results = self.query(query_text, top_k=top_k)
        if not results:
            return ""

        lines = [
            f"RETRIEVED REPOSITORY & DOCUMENTATION EVIDENCE ({len(results)} chunks matched for {query_text!r}):",
            "Use the grounded technical knowledge below to answer with high factual precision:",
        ]

        for idx, res in enumerate(results, 1):
            chunk = res.result.chunk
            source = chunk.metadata.source
            section = f" > {chunk.metadata.section_path}" if chunk.metadata.section_path else ""
            lines.append(f"\n--- [RAG-{idx}] Source: {source}{section} (Relevance: {res.final_score:.2f}) ---")
            lines.append(chunk.text.strip())

        lines.extend([
            "\nRAG MANDATE:",
            "- Ground facts in the snippets above when responding to architecture, code conventions, or security policy.",
            "- Attribute specific claims to the respective documentation source (e.g. .hina/architecture.md or [RAG-1]).",
            "- Do not hallucinate capabilities or configs that contradict the retrieved specs.",
        ])

        return "\n".join(lines)

    def get_stats(self) -> dict[str, Any]:
        """Returns runtime diagnostics and index statistics."""
        sources = sorted(list({c.metadata.source for c in self._all_chunks}))
        return {
            "total_chunks": self.total_chunks,
            "total_documents": self.total_documents,
            "sources": sources,
            "bm25_weight": self.retriever.bm25_weight,
            "vector_weight": self.retriever.vector_weight,
            "entity_weight": self.retriever.entity_weight,
        }
