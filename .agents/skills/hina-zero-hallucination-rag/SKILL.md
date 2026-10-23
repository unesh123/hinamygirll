---
name: hina-zero-hallucination-rag
description: Zero-Hallucination Corrective RAG (CRAG) rules, Reciprocal Rank Fusion, source attribution, and anti-fabrication verification gates
---

# Zero-Hallucination Corrective RAG (CRAG) Specification

## 1. Grounding Principles
- **Strict Verification Gate**: No factual claim may be presented without an attributed document chunk or verified citation.
- **Confidence Threshold (0.72)**: If the maximum RRF retrieval score is `< 0.72`, HINA must automatically trigger live search fallback rather than hallucinating or speculating.

## 2. Reciprocal Rank Fusion (RRF)
Hybrid retrieval fuses sparse BM25 scores and dense cosine similarity:
$$\text{RRF}(d) = \sum_{m \in \{\text{dense}, \text{sparse}\}} \frac{1}{60 + \text{rank}_m(d)}$$

## 3. Inline Citation Standard
- Every factual proposition must end with an inline citation tag: `[cite: doc_id]`.
- Example:
  `The ElevenLabs Flash v2.5 model has an inference latency of 75ms [cite: elevenlabs_docs].`

## 4. Self-Correction & Web Fallback Protocol
If internal vector knowledge is outdated, contradictory, or below confidence:
1. Issue query to web search fallback.
2. Cross-reference search results against trusted domain allowlist.
3. Strip unsupported conjectures from the final synthesized output.
