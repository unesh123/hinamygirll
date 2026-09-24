from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Sequence

from .retrieval import RetrievalResult, _deterministic_embedding, _tokenize


def _jaccard_similarity(text_a: str, text_b: str) -> float:
    words_a = set(_tokenize(text_a))
    words_b = set(_tokenize(text_b))
    if not words_a or not words_b:
        return 0.0
    intersection = len(words_a & words_b)
    union = len(words_a | words_b)
    return intersection / union if union > 0 else 0.0


@dataclass
class RerankedResult:
    result: RetrievalResult
    final_score: float
    relevance_score: float
    authority_score: float
    recency_score: float
    diversity_penalty: float
    rank: int = 0


class Reranker:
    """Multi-attribute lightweight reranker for RAG v2 with Maximal Marginal Relevance (MMR)."""

    def __init__(
        self,
        relevance_weight: float = 0.50,
        authority_weight: float = 0.25,
        recency_weight: float = 0.15,
        diversity_lambda: float = 0.70,
    ) -> None:
        self.relevance_weight = relevance_weight
        self.authority_weight = authority_weight
        self.recency_weight = recency_weight
        self.diversity_lambda = diversity_lambda

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalResult],
        *,
        top_k: int = 5,
        source_authority_map: dict[str, float] | None = None,
    ) -> list[RerankedResult]:
        if not candidates:
            return []

        auth_map = {
            "official_spec": 1.0,
            "architecture": 0.95,
            "docs": 0.90,
            "source_code": 0.85,
            "guide": 0.80,
            "user_note": 0.65,
            "scratchpad": 0.50,
            **(source_authority_map or {}),
        }

        q_terms = set(_tokenize(query))
        lower_q = query.lower()
        is_how_to = bool(re.search(r"\b(how to|steps|guide|implement|procedure)\b", lower_q))
        is_what_is = bool(re.search(r"\b(what is|define|definition|concept|meaning)\b", lower_q))

        scored_candidates: list[tuple[RetrievalResult, float, float, float, float]] = []

        now = datetime.now(UTC)

        for item in candidates:
            c = item.chunk
            text = c.text
            lower_text = text.lower()

            # 1. Relevance: Key-term overlap + phrase match + intent alignment
            c_terms = set(_tokenize(text))
            term_overlap = len(q_terms & c_terms) / max(1, len(q_terms))
            phrase_bonus = 0.20 if query.strip() and query.strip().lower() in lower_text else 0.0

            intent_bonus = 0.0
            if is_how_to and (c.metadata.is_code or "step" in lower_text or "1." in lower_text):
                intent_bonus = 0.15
            elif is_what_is and not c.metadata.is_code and len(text.split()) > 10:
                intent_bonus = 0.15

            rel_score = min(1.0, 0.4 * item.hybrid_score + 0.4 * term_overlap + phrase_bonus + intent_bonus)

            # 2. Authority: Look up source or section path
            authority = 0.70
            src_key = c.metadata.source.lower()
            for k, val in auth_map.items():
                if k in src_key or any(k in sec.lower() for sec in c.metadata.section_path):
                    authority = max(authority, val)
                    break
            auth_score = authority

            # 3. Recency: Parse timestamp or decay from version
            recency = 0.85
            if c.metadata.created_at:
                try:
                    dt = datetime.fromisoformat(c.metadata.created_at)
                    diff_days = max(0.0, (now - dt).total_seconds() / 86400.0)
                    recency = 1.0 / (1.0 + 0.05 * diff_days)
                except Exception:
                    recency = 0.85

            base_score = (
                self.relevance_weight * rel_score
                + self.authority_weight * auth_score
                + self.recency_weight * recency
            )
            scored_candidates.append((item, base_score, rel_score, auth_score, recency))

        # Sort initially by base score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        # 4. Maximal Marginal Relevance (MMR) Diversification
        selected: list[RerankedResult] = []
        remaining = list(scored_candidates)

        while remaining and len(selected) < top_k:
            best_idx = 0
            best_mmr_score = -1e9
            best_penalty = 0.0

            for idx, (item, base_s, r_s, a_s, rec_s) in enumerate(remaining):
                if not selected:
                    # First choice is simply the highest scored candidate
                    best_idx = idx
                    best_mmr_score = base_s
                    best_penalty = 0.0
                    break

                # Max similarity to already selected chunks
                max_sim = max(_jaccard_similarity(item.chunk.text, sel.result.chunk.text) for sel in selected)
                mmr_val = self.diversity_lambda * base_s - (1.0 - self.diversity_lambda) * max_sim

                if mmr_val > best_mmr_score:
                    best_mmr_score = mmr_val
                    best_idx = idx
                    best_penalty = (1.0 - self.diversity_lambda) * max_sim

            chosen_item, base_s, r_s, a_s, rec_s = remaining.pop(best_idx)
            final_s = max(0.0, base_s - best_penalty)
            selected.append(
                RerankedResult(
                    result=chosen_item,
                    final_score=final_s,
                    relevance_score=r_s,
                    authority_score=a_s,
                    recency_score=rec_s,
                    diversity_penalty=best_penalty,
                    rank=len(selected) + 1,
                )
            )

        return selected
