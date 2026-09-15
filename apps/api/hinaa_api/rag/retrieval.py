from __future__ import annotations

import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Sequence

from .ingestion import StructuredChunk


def _tokenize(text: str) -> list[str]:
    return [w.lower() for w in re.findall(r"\b\w+\b", text)]


def _deterministic_embedding(text: str, dim: int = 128) -> list[float]:
    """Lightweight deterministic feature-hashing embedding.

    Provides stable cosine-similar dense vector space without requiring an external API key.
    """
    vec = [0.0] * dim
    words = _tokenize(text)
    if not words:
        return vec

    # Unigrams + Bigrams hashing
    tokens = list(words)
    for i in range(len(words) - 1):
        tokens.append(f"{words[i]}_{words[i+1]}")

    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest()[:8], 16)
        idx = abs(h) % dim
        sign = 1.0 if (h & 1) == 0 else -1.0
        vec[idx] += sign

    # L2 normalize
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 1e-9:
        vec = [x / norm for x in vec]
    return vec


def _cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    return max(0.0, min(1.0, dot))


class BM25Index:
    """Okapi BM25 index with Robertson-Spärck Jones IDF."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[StructuredChunk] = []
        self.doc_tokens: list[list[str]] = []
        self.doc_lens: list[int] = []
        self.avg_dl: float = 0.0
        self.df: Counter[str] = Counter()
        self.idf: dict[str, float] = {}

    def index(self, chunks: Sequence[StructuredChunk]) -> None:
        self.chunks = list(chunks)
        self.doc_tokens = []
        self.doc_lens = []
        self.df.clear()
        self.idf.clear()

        n = len(self.chunks)
        if n == 0:
            self.avg_dl = 0.0
            return

        total_len = 0
        for chunk in self.chunks:
            tokens = _tokenize(chunk.text)
            self.doc_tokens.append(tokens)
            dl = len(tokens)
            self.doc_lens.append(dl)
            total_len += dl
            unique_terms = set(tokens)
            for term in unique_terms:
                self.df[term] += 1

        self.avg_dl = total_len / n if n > 0 else 0.0

        for term, freq in self.df.items():
            # BM25 IDF formulation
            self.idf[term] = math.log(1.0 + (n - freq + 0.5) / (freq + 0.5))

    def search(self, query: str, top_k: int = 10) -> list[tuple[StructuredChunk, float]]:
        q_tokens = _tokenize(query)
        if not q_tokens or not self.chunks:
            return []

        scores: list[tuple[StructuredChunk, float]] = []
        for idx, chunk in enumerate(self.chunks):
            doc_terms = Counter(self.doc_tokens[idx])
            dl = self.doc_lens[idx]
            score = 0.0

            for q_term in q_tokens:
                if q_term not in doc_terms:
                    continue
                tf = doc_terms[q_term]
                idf = self.idf.get(q_term, 0.0)
                denom = tf + self.k1 * (1.0 - self.b + self.b * (dl / (self.avg_dl or 1.0)))
                score += idf * (tf * (self.k1 + 1.0)) / (denom if denom > 0 else 1.0)

            if score > 0:
                scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class VectorIndex:
    """Vector index for dense semantic retrieval."""

    def __init__(self, dim: int = 128) -> None:
        self.dim = dim
        self.chunks: list[StructuredChunk] = []
        self.vectors: list[list[float]] = []

    def index(
        self,
        chunks: Sequence[StructuredChunk],
        embeddings: Sequence[list[float]] | None = None,
    ) -> None:
        self.chunks = list(chunks)
        if embeddings is not None and len(embeddings) == len(chunks):
            self.vectors = [list(e) for e in embeddings]
        else:
            self.vectors = [_deterministic_embedding(chunk.text, self.dim) for chunk in chunks]

    def search(self, query: str, top_k: int = 10, query_vector: list[float] | None = None) -> list[tuple[StructuredChunk, float]]:
        if not self.chunks:
            return []
        q_vec = query_vector or _deterministic_embedding(query, self.dim)

        scores: list[tuple[StructuredChunk, float]] = []
        for chunk, v in zip(self.chunks, self.vectors):
            sim = _cosine_similarity(q_vec, v)
            if sim > 0.01:
                scores.append((chunk, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


class EntityGraphMatcher:
    """Entity graph matching across query and document chunks."""

    def __init__(self, entities: Sequence[dict[str, Any]] | None = None) -> None:
        # Each entity can have: {"name": str, "type": str, "aliases": list[str]}
        self.entities: list[dict[str, Any]] = list(entities or [])

    def set_entities(self, entities: Sequence[dict[str, Any]]) -> None:
        self.entities = list(entities)

    def match_entities_in_text(self, text: str) -> set[str]:
        lower_text = text.lower()
        matched: set[str] = set()
        for ent in self.entities:
            name = ent.get("name", "").lower()
            if name and name in lower_text:
                matched.add(name)
            for alias in ent.get("aliases") or []:
                al = str(alias).lower()
                if al and al in lower_text:
                    matched.add(name)
        return matched

    def score_chunk(self, query_entities: set[str], chunk_text: str) -> float:
        if not query_entities:
            return 0.0
        chunk_entities = self.match_entities_in_text(chunk_text)
        overlap = query_entities & chunk_entities
        return len(overlap) / max(1, len(query_entities))


@dataclass
class RetrievalResult:
    chunk: StructuredChunk
    hybrid_score: float
    bm25_score: float
    vector_score: float
    entity_score: float
    rank: int = 0


class HybridRetriever:
    """Hybrid Retriever combining BM25 keyword matching, vector dense similarity,

    and entity graph lookup using weighted Reciprocal Rank Fusion (RRF) and linear scaling.
    """

    def __init__(
        self,
        bm25_weight: float = 0.45,
        vector_weight: float = 0.40,
        entity_weight: float = 0.15,
        rrf_k: int = 60,
    ) -> None:
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.entity_weight = entity_weight
        self.rrf_k = rrf_k
        self.bm25_index = BM25Index()
        self.vector_index = VectorIndex()
        self.entity_matcher = EntityGraphMatcher()
        self._chunks: list[StructuredChunk] = []

    def index(
        self,
        chunks: Sequence[StructuredChunk],
        embeddings: Sequence[list[float]] | None = None,
        entities: Sequence[dict[str, Any]] | None = None,
    ) -> None:
        self._chunks = list(chunks)
        self.bm25_index.index(self._chunks)
        self.vector_index.index(self._chunks, embeddings)
        if entities is not None:
            self.entity_matcher.set_entities(entities)

    def retrieve(
        self,
        query: str,
        *,
        top_k: int = 8,
        filter_visibility: str | None = None,
        query_vector: list[float] | None = None,
    ) -> list[RetrievalResult]:
        if not self._chunks:
            return []

        # 1. BM25 Search
        bm25_results = self.bm25_index.search(query, top_k=len(self._chunks))
        bm25_map: dict[str, tuple[int, float]] = {}
        max_bm25 = max([s for _, s in bm25_results], default=1.0) or 1.0
        for rank, (c, score) in enumerate(bm25_results, 1):
            bm25_map[c.chunk_id] = (rank, score / max_bm25)

        # 2. Vector Search
        vector_results = self.vector_index.search(query, top_k=len(self._chunks), query_vector=query_vector)
        vector_map: dict[str, tuple[int, float]] = {}
        for rank, (c, score) in enumerate(vector_results, 1):
            vector_map[c.chunk_id] = (rank, score)

        # 3. Entity graph matches
        q_entities = self.entity_matcher.match_entities_in_text(query)

        # 4. Hybrid combination
        results: list[RetrievalResult] = []
        for c in self._chunks:
            if filter_visibility and c.metadata.visibility != filter_visibility:
                continue

            bm25_rank, norm_bm25 = bm25_map.get(c.chunk_id, (9999, 0.0))
            vec_rank, vec_score = vector_map.get(c.chunk_id, (9999, 0.0))
            ent_score = self.entity_matcher.score_chunk(q_entities, c.text)

            # RRF component
            rrf_score = 0.0
            if bm25_rank < 9999:
                rrf_score += self.bm25_weight * (1.0 / (self.rrf_k + bm25_rank))
            if vec_rank < 9999:
                rrf_score += self.vector_weight * (1.0 / (self.rrf_k + vec_rank))

            # Linear hybrid score
            hybrid = (
                self.bm25_weight * norm_bm25
                + self.vector_weight * vec_score
                + self.entity_weight * ent_score
            )

            # Combine linear with RRF boost
            final_score = hybrid + 10.0 * rrf_score

            results.append(
                RetrievalResult(
                    chunk=c,
                    hybrid_score=final_score,
                    bm25_score=norm_bm25,
                    vector_score=vec_score,
                    entity_score=ent_score,
                )
            )

        results.sort(key=lambda x: x.hybrid_score, reverse=True)
        for rank, res in enumerate(results[:top_k], 1):
            res.rank = rank
        return results[:top_k]
