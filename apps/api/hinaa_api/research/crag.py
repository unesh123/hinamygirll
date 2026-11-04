"""Corrective Retrieval-Augmented Generation (CRAG) Engine for HINAA OS.

Implements the CRAG architecture (Yan et al., 2024; arXiv:2401.15884):
1. Retrieval Evaluation: Grades retrieved documents as CORRECT, INCORRECT, or AMBIGUOUS.
2. Knowledge Strip Decomposition: Dissects retrieved documents into fine-grained evidence strips, filtering out noise.
3. Corrective Query Rewriting: When retrieval is noisy, stale or insufficient, triggers transformed queries.
4. Source Deduplication & Independence: Detects scraped mirrors via SimHash so duplicates are never counted as independent corroboration.
"""

from __future__ import annotations

import logging
import re
from typing import Sequence
from .models import CRAGVerdict, Source, EvidenceSpan
from .security import ResearchSecurityGuard

logger = logging.getLogger("hinaa.research.crag")


def _hamming_distance(h1: int, h2: int) -> int:
    """Computes bitwise Hamming distance between two 64-bit SimHashes."""
    x = (h1 ^ h2) & 0xFFFFFFFFFFFFFFFF
    return bin(x).count("1")


class CRAGEngine:
    """Corrective RAG Evaluator, Document Decomposer, and Deduplication Manager."""

    def __init__(
        self,
        high_threshold: float = 0.65,
        low_threshold: float = 0.30,
        max_mirror_hamming_distance: int = 3,
    ) -> None:
        self.high_threshold = high_threshold
        self.low_threshold = low_threshold
        self.max_mirror_hamming_distance = max_mirror_hamming_distance

    def deduplicate_sources(self, sources: list[Source]) -> tuple[list[Source], int]:
        """Identifies and filters near-duplicate/mirrored articles based on content hash & SimHash."""
        unique_sources: list[Source] = []
        seen_hashes: set[str] = set()
        seen_simhashes: list[int] = []
        filtered_count = 0

        for src in sources:
            # 1. Exact hash check
            if src.content_hash and src.content_hash in seen_hashes:
                filtered_count += 1
                continue

            # 2. Near-duplicate SimHash check
            is_mirror = False
            if src.simhash is not None:
                for existing_sh in seen_simhashes:
                    if _hamming_distance(src.simhash, existing_sh) <= self.max_mirror_hamming_distance:
                        is_mirror = True
                        break

            if is_mirror:
                filtered_count += 1
                logger.debug("CRAG: Filtered mirror source %s (%s)", src.source_id, src.title)
                continue

            if src.content_hash:
                seen_hashes.add(src.content_hash)
            if src.simhash is not None:
                seen_simhashes.append(src.simhash)
            unique_sources.append(src)

        return unique_sources, filtered_count

    def evaluate_retrieval(self, query: str, sources: list[Source]) -> tuple[CRAGVerdict, float]:
        """Evaluates overall confidence and relevance of retrieved sources for answering the query."""
        if not sources:
            return CRAGVerdict.INCORRECT, 0.0

        query_tokens = set(re.findall(r"\w+", query.lower()))
        if not query_tokens:
            return CRAGVerdict.INCORRECT, 0.0

        scores: list[float] = []
        for src in sources:
            src_text = f"{src.title} {src.excerpt}".lower()
            tokens_in_src = sum(1 for tok in query_tokens if tok in src_text)
            coverage = tokens_in_src / len(query_tokens)

            # Bonus for high trust tier
            trust_multiplier = 1.0
            if src.trust_tier.value == "verified_primary":
                trust_multiplier = 1.2
            elif src.trust_tier.value == "untrusted":
                trust_multiplier = 0.5

            score = min(1.0, coverage * trust_multiplier)
            scores.append(score)

        avg_score = sum(scores) / len(scores) if scores else 0.0
        max_score = max(scores) if scores else 0.0
        blended = (avg_score * 0.4) + (max_score * 0.6)

        if blended >= self.high_threshold:
            verdict = CRAGVerdict.CORRECT
        elif blended < self.low_threshold:
            verdict = CRAGVerdict.INCORRECT
        else:
            verdict = CRAGVerdict.AMBIGUOUS

        logger.info("CRAG Evaluation: verdict=%s (blended_score=%.3f, sources=%d)", verdict.value, blended, len(sources))
        return verdict, round(blended, 3)

    def decompose_knowledge_strips(self, query: str, sources: list[Source]) -> list[EvidenceSpan]:
        """Splits retrieved sources into fine-grained sentences/strips and retains relevant spans."""
        query_tokens = set(re.findall(r"\w+", query.lower()))
        evidence_spans: list[EvidenceSpan] = []

        span_counter = 0
        for src in sources:
            sentences = re.split(r"(?<=[.!?।])\s+", src.excerpt)
            char_offset = 0

            for sent in sentences:
                sent_clean = sent.strip()
                if not sent_clean:
                    continue

                sent_lower = sent_clean.lower()
                matching_tokens = sum(1 for tok in query_tokens if tok in sent_lower)
                relevance = matching_tokens / len(query_tokens) if query_tokens else 0.0

                # Only keep strips with baseline relevance (filters out noise / ads)
                if relevance > 0.1 or len(sentences) == 1:
                    span_counter += 1
                    span = EvidenceSpan(
                        span_id=f"span-{src.source_id}-{span_counter}",
                        source_id=src.source_id,
                        text=sent_clean,
                        start_char=char_offset,
                        end_char=char_offset + len(sent_clean),
                        confidence=round(relevance, 2),
                    )
                    evidence_spans.append(span)

                char_offset += len(sent) + 1

        return evidence_spans

    def generate_corrective_query(self, query: str, previous_queries: list[str]) -> str:
        """Transforms query when retrieval is ambiguous or incorrect."""
        cleaned = query.strip()
        # Remove common conversational prefixes
        rewritten = re.sub(
            r"(?i)^(?:can\s+you\s+)?(?:tell\s+me|explain|what\s+is|who\s+is|why\s+did|how\s+does)\s+",
            "",
            cleaned,
        ).strip(" ?.!")

        # If rewritten is identical to a previous query, append specific search terms
        if rewritten in previous_queries or not rewritten:
            rewritten = f"{cleaned} official facts"

        return rewritten
