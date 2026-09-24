from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from .ingestion import StructuredChunk
from .retrieval import _tokenize


@dataclass
class CitationSpan:
    citation_index: int
    source_id: str
    document_name: str
    chunk_id: str
    section: str
    snippet: str
    claim_sentence: str
    confidence: float
    start_char: int = 0
    end_char: int = 0


class ProvenanceEngine:
    """Provenance and Citation Engine for RAG v2.

    Extracts citation spans linking claims in generated responses directly
    to verified evidence passages with quote verification.
    """

    def __init__(self, min_confidence: float = 0.35) -> None:
        self.min_confidence = min_confidence

    def extract_citations(
        self,
        answer_text: str,
        evidence_chunks: Sequence[StructuredChunk],
    ) -> list[CitationSpan]:
        if not answer_text or not evidence_chunks:
            return []

        # Split answer into sentences
        raw_sentences = re.split(r"(?<=[.!?])\s+", answer_text.strip())
        sentences: list[tuple[str, int, int]] = []
        cur_pos = 0
        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean or len(s_clean) < 15:
                continue
            idx = answer_text.find(s_clean, cur_pos)
            if idx != -1:
                sentences.append((s_clean, idx, idx + len(s_clean)))
                cur_pos = idx + len(s_clean)
            else:
                sentences.append((s_clean, 0, len(s_clean)))

        citations: list[CitationSpan] = []
        cited_chunks: set[str] = set()
        cit_idx = 1

        for s_text, start_c, end_c in sentences:
            s_words = set(_tokenize(s_text))
            if len(s_words) < 3:
                continue

            best_chunk: StructuredChunk | None = None
            best_score = 0.0
            best_snippet = ""

            for chunk in evidence_chunks:
                # Find matching snippet within chunk
                chunk_sentences = re.split(r"(?<=[.!?])\s+", chunk.text)
                for cs in chunk_sentences:
                    cs_clean = cs.strip()
                    if not cs_clean:
                        continue
                    cs_words = set(_tokenize(cs_clean))
                    if not cs_words:
                        continue
                    overlap = len(s_words & cs_words)
                    score = overlap / max(1, len(s_words))

                    # Exact phrase bonus
                    if len(s_text) > 20 and (s_text.lower() in cs_clean.lower() or cs_clean.lower() in s_text.lower()):
                        score = min(1.0, score + 0.30)

                    if score > best_score:
                        best_score = score
                        best_chunk = chunk
                        best_snippet = cs_clean

            if best_chunk and best_score >= self.min_confidence:
                citations.append(
                    CitationSpan(
                        citation_index=cit_idx,
                        source_id=best_chunk.metadata.document_id,
                        document_name=best_chunk.metadata.source,
                        chunk_id=best_chunk.chunk_id,
                        section=best_chunk.section_title,
                        snippet=best_snippet[:240],
                        claim_sentence=s_text,
                        confidence=round(best_score, 3),
                        start_char=start_c,
                        end_char=end_c,
                    )
                )
                cit_idx += 1

        return citations

    def format_markdown_with_citations(
        self,
        answer_text: str,
        citations: Sequence[CitationSpan],
    ) -> str:
        """Inject citation footnote markers and evidence bibliography."""
        if not citations:
            return answer_text

        result = answer_text
        # Append references section
        ref_lines = ["\n\n### References & Citations"]
        for cit in citations:
            ref_lines.append(
                f"- [^{cit.citation_index}] **{cit.document_name}** ({cit.section}) — "
                f"\"{cit.snippet}\" *(Confidence: {int(cit.confidence * 100)}%)*"
            )

        return result.rstrip() + "\n" + "\n".join(ref_lines)

    def verify_claim(
        self,
        claim_text: str,
        evidence_chunk: StructuredChunk,
    ) -> tuple[bool, float, str]:
        """Verify whether claim is substantiated by the given evidence chunk."""
        claim_words = set(_tokenize(claim_text))
        chunk_words = set(_tokenize(evidence_chunk.text))
        if not claim_words:
            return False, 0.0, "Empty claim"

        overlap = len(claim_words & chunk_words)
        ratio = overlap / len(claim_words)

        is_substantiated = ratio >= 0.40
        status = "Substantiated" if is_substantiated else "Unsupported"
        return is_substantiated, round(ratio, 3), f"{status} ({int(ratio * 100)}% term alignment)"
