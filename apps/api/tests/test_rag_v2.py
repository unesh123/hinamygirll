from __future__ import annotations

import pytest

from hinaa_api.rag import (
    BM25Index,
    CitationSpan,
    EntityGraphMatcher,
    HybridRetriever,
    ProvenanceEngine,
    Reranker,
    StructuredChunker,
    VectorIndex,
)


def test_structured_chunker_sections_tables_and_code():
    chunker = StructuredChunker(target_chunk_tokens=60, overlap_tokens=10)

    sample_doc = """# Architectural Overview

HINAA is a high performance frontier AI operating system. It coordinates reasoning, tools, and digital avatar rendering.

## Memory Architecture

The memory engine divides into 5 distinct partitions: working, episodic, semantic, procedural, and project.

```python
def remember(fact: str) -> None:
    store.add(fact)
```

| Partition | Scope | Lifespan |
|---|---|---|
| Working | Current dialogue | Ephemeral |
| Semantic | Long-term facts | Persistent |
| Episodic | Event timeline | Append-only |

### Procedural Rules

Procedural memory stores operational rules and verified workflows for code generation and task orchestration.
"""

    chunks = chunker.chunk(
        sample_doc,
        document_id="doc_hinaa_spec",
        source="HINAA Architecture Spec",
        page=1,
        visibility="internal",
        version="2.0",
    )

    assert len(chunks) >= 3

    # Verify section hierarchies
    section_paths = [c.metadata.section_path for c in chunks]
    assert any("Architectural Overview" in p for p in section_paths)
    assert any("Memory Architecture" in p for p in section_paths)

    # Verify code block was identified
    code_chunks = [c for c in chunks if c.metadata.is_code]
    assert len(code_chunks) >= 1
    assert code_chunks[0].metadata.code_language == "python"
    assert "def remember" in code_chunks[0].text

    # Verify table was preserved intact
    table_chunks = [c for c in chunks if c.metadata.is_table]
    assert len(table_chunks) >= 1
    assert "| Partition | Scope | Lifespan |" in table_chunks[0].text
    assert "| Semantic | Long-term facts |" in table_chunks[0].text

    # Verify metadata
    first = chunks[0]
    assert first.metadata.document_id == "doc_hinaa_spec"
    assert first.metadata.source == "HINAA Architecture Spec"
    assert first.metadata.visibility == "internal"
    assert first.metadata.token_count > 0
    assert len(first.metadata.content_hash) == 64


def test_bm25_and_vector_retrieval():
    chunker = StructuredChunker(target_chunk_tokens=50)
    docs = [
        "Quantum computing relies on qubits and superposition to solve combinatorial problems.",
        "Photosynthesis in plants converts solar radiation and carbon dioxide into glucose.",
        "High-performance databases use log-structured merge trees and Write-Ahead Logging for durability.",
    ]
    chunks = []
    for idx, text in enumerate(docs):
        chunks.extend(chunker.chunk(text, document_id=f"doc_{idx}", source=f"Doc {idx}"))

    # Test BM25
    bm25 = BM25Index()
    bm25.index(chunks)
    res_bm25 = bm25.search("qubits superposition", top_k=2)
    assert len(res_bm25) > 0
    assert "Quantum computing" in res_bm25[0][0].text

    # Test Vector
    vec = VectorIndex()
    vec.index(chunks)
    res_vec = vec.search("solar energy and plants", top_k=2)
    assert len(res_vec) > 0
    assert "Photosynthesis" in res_vec[0][0].text


def test_hybrid_retriever_with_entity_graph():
    chunker = StructuredChunker(target_chunk_tokens=50)
    c1 = chunker.chunk("Alice is the Principal Architect leading Project Titan.", document_id="d1", source="Team")[0]
    c2 = chunker.chunk("Bob is the SecOps Engineer responsible for network audits.", document_id="d2", source="Team")[0]
    c3 = chunker.chunk("Charlie handles documentation and technical writing.", document_id="d3", source="Team")[0]

    retriever = HybridRetriever()
    entities = [
        {"name": "Alice", "aliases": ["Architect Alice", "Titan Lead"]},
        {"name": "Project Titan", "aliases": ["Titan"]},
    ]
    retriever.index([c1, c2, c3], entities=entities)

    results = retriever.retrieve("Who is leading Project Titan?", top_k=2)
    assert len(results) >= 1
    assert results[0].chunk.chunk_id == c1.chunk_id
    assert results[0].entity_score > 0


def test_reranker_with_mmr_diversity():
    chunker = StructuredChunker(target_chunk_tokens=50)
    # Create two nearly identical chunks and one diverse chunk
    c1 = chunker.chunk("PostgreSQL replication using streaming WAL records guarantees high availability.", document_id="p1", source="official_spec")[0]
    c2 = chunker.chunk("PostgreSQL replication with streaming WAL logs ensures reliable high availability.", document_id="p2", source="user_note")[0]
    c3 = chunker.chunk("PostgreSQL query planner utilizes genetic algorithms for complex multi-table joins.", document_id="p3", source="docs")[0]

    retriever = HybridRetriever()
    retriever.index([c1, c2, c3])
    candidates = retriever.retrieve("PostgreSQL replication and high availability", top_k=3)

    reranker = Reranker(diversity_lambda=0.60)
    reranked = reranker.rerank("how to configure PostgreSQL replication", candidates, top_k=3)

    assert len(reranked) == 3
    # Top chunk should be the official spec
    assert reranked[0].authority_score >= reranked[1].authority_score
    # MMR should penalize the duplicate snippet
    assert reranked[0].diversity_penalty == 0.0
    assert reranked[1].diversity_penalty > 0.0 or reranked[2].diversity_penalty > 0.0


def test_provenance_engine_and_citation_generation():
    chunker = StructuredChunker()
    c1 = chunker.chunk(
        "HINAA uses WebAudioSpeechTimingSource to guarantee frame-perfect lip sync derived from AudioContext clock.",
        document_id="doc_speech",
        source="Voice Architecture",
    )[0]
    c2 = chunker.chunk(
        "The ResponseIntelligenceController strips verbatim input echos and deduplicates consecutive blocks.",
        document_id="doc_resp",
        source="Response Intelligence Spec",
    )[0]

    engine = ProvenanceEngine(min_confidence=0.3)
    answer = (
        "HINAA uses WebAudioSpeechTimingSource for frame-perfect lip sync from the AudioContext clock. "
        "Additionally, the ResponseIntelligenceController strips verbatim input echos."
    )

    citations = engine.extract_citations(answer, [c1, c2])
    assert len(citations) >= 2
    assert citations[0].document_name == "Voice Architecture"
    assert citations[1].document_name == "Response Intelligence Spec"

    # Test bibliography generation
    formatted = engine.format_markdown_with_citations(answer, citations)
    assert "### References & Citations" in formatted
    assert "[^1] **Voice Architecture**" in formatted
    assert "[^2] **Response Intelligence Spec**" in formatted

    # Test claim verification
    verified, score, msg = engine.verify_claim(
        "WebAudioSpeechTimingSource provides frame-perfect lip sync", c1
    )
    assert verified is True
    assert score > 0.5
