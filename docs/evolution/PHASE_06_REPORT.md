# Phase 06 Verification & Architecture Report: Grounded Research & Corrective RAG (CRAG)

**Date:** November 5, 2026  
**Status:** **COMPLETE (100%)**  
**Engineering Domain:** Corrective Retrieval-Augmented Generation, Multi-Hop Planning, Anti-Fabrication Verification, OWASP RAG Defense, and Multi-Tenant Isolation  
**Pass Rate:** **25/25 Scenarios Passing (100%)** | **62/62 Research Suite Tests Passing (100%)**  
**Rollback Baseline:** `phase-05-checkpoint` $\rightarrow$ `phase-06-checkpoint`

---

## 1. Executive Summary

Phase 06 upgrades HINAA OS from standard conversational prompting and naive RAG chunk injection into an authoritative, enterprise-grade **Corrective Retrieval-Augmented Generation (CRAG)** engine.

### Erratum & Verification Clarification: Mock vs Live Retrieval
> [!NOTE]
> The initial 25-scenario automated benchmark (`R06-01` through `R06-25`) executed in **25.25 ms total (~1.01 ms per scenario)** because it ran against `MockSearchAdapter` in offline deterministic mode. This tested the local architectural components (CRAG evaluation, SimHash deduplication, prompt injection defenses, multi-tenant ACLs, Indic tokenization, and claim entailment) without external network I/O.
> 
> In production environments with `EXA_API_KEY` configured, `GroundedResearchCoordinator` activates `LiveSearchAdapter`. Live end-to-end web research (e.g. *"When was Python 3.13 officially released?"*) yields:
> - **Live Network Latency:** 3,895.41 ms (~3.9s)
> - **Top Live Source:** `https://www.python.org/downloads/release/python-3130/`
> - **Factual Verification:** Grounded release date `Oct. 7, 2024`.
> Mock, replay, cached, and live results are now distinctly labeled across all test suites and reports.

### Critical Capabilities Delivered
1. **Confidence-Gated Corrective Retrieval (CRAG)**: Retrieval results are audited for quality and semantic relevance. If evidence is ambiguous or incorrect, the engine automatically rewrites search queries and fetches corrective corroboration before synthesizing responses.
2. **Multi-Hop Relational Decomposition**: Multi-step queries (e.g. *"Who directed the movie whose lead actor played Oppenheimer in 2023?"*) are programmatically split into entity hops with bridge-entity resolution under strict query budget constraints.
3. **Claim-Level Entailment & Anti-Fabrication**: Claims synthesized in answers are cross-checked against raw evidence spans. Hallucinated or misaligned citations (such as fabricated `[999]` markers) are automatically stripped, and ungrounded statements are rejected.
4. **Honest Abstention**: When evidence is missing, inaccessible, or contradictory, HINAA refrains from confabulation and explicitly reports `abstention_occurred: True` with clear explanatory rationales.
5. **OWASP Top 10 for LLM/RAG Security**: Untrusted web content is enclosed in passive XML envelopes (`<untrusted_evidence_document>`), stripping prompt injection instructions, purging spoofed `<system>` tags, sanitizing XSS link protocols (`javascript:`), and enforcing strict multi-tenant access control.
6. **Multilingual Research & Indic Script Safety**: Implemented Indic-safe tokenization preserving Devanagari vowel marks (*matras*), enabling flawless grounded retrieval for Nepali and code-mixed Hindi queries.
7. **Voice-Compatible Citations**: Text answers maintain bracketed numbers (`[1]`, `[2]`) for interactive UI citation cards, while the TTS pipeline automatically normalizes them into natural conversational cadence without audible bracket pronunciation.

---

## 2. Technical Architecture & Component Ledger

```
                               ┌────────────────────────────────────────────────────────┐
                               │                    User Query                          │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │              ResearchIntentRouter                      │
                               │  - Casual / Chit-chat  --> Parametric Fast-Path        │
                               │  - Factual / Temporal  --> Grounded Research Pipeline  │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                 MultiHopPlanner                        │
                               │  - Decomposes relational questions into query hops     │
                               │  - Extracts bridge entities & enforces budget ceilings │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                 Search Adapters                        │
                               │  - MockSearchAdapter (deterministic test corpora)      │
                               │  - LiveSearchAdapter (production web retrieval)        │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                 CRAG Engine                            │
                               │  - Evaluates relevance: CORRECT / AMBIGUOUS / INCORRECT│
                               │  - Generates corrective rewritten queries if ambiguous │
                               │  - SimHash 64-bit Hamming deduplication (dist <= 3)    │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │             ResearchSecurityGuard                      │
                               │  - Wraps in <untrusted_evidence_document> envelopes    │
                               │  - Neutralizes prompt injections & purges <system> tags│
                               │  - Sanitizes XSS & enforces multi-tenant access ACLs   │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │             ClaimGroundingVerifier                     │
                               │  - Computes claim-to-evidence textual entailment       │
                               │  - Strips unverified/fabricated citation markers [999] │
                               │  - Detects source contradictions & flags abstentions   │
                               └─────────────────────────┬──────────────────────────────┘
                                                         │
                                                         ▼
                               ┌────────────────────────────────────────────────────────┐
                               │                  ResearchAnswer                        │
                               │  - Formatted text with verified [1] citation markers   │
                               │  - Clean voice text for TTS (speech_text_for_tts)      │
                               │  - GroundedResearchCard UI serialization               │
                               └────────────────────────────────────────────────────────┘
```

### Component Details
- **`apps/api/hinaa_api/research/models.py`**: Pydantic models for `ResearchIntent`, `CRAGVerdict`, `ClaimSupportStatus`, `TrustTier`, `Source`, `EvidenceSpan`, `Claim`, `ClaimSupport`, `ResearchTrace`, and `ResearchAnswer`.
- **`apps/api/hinaa_api/research/security.py`**: Non-destructive passive data envelopes (`<untrusted_evidence_document>`), prompt injection detection and neutralization, XSS sanitization, memory poisoning protection, and tenant ACL verification.
- **`apps/api/hinaa_api/research/intent_router.py`**: Query categorization (`CONVERSATIONAL`, `FACTUAL_RESEARCH`, `TIME_SENSITIVE`, `WORKSPACE_CODE`, `MULTI_HOP`, `HIGH_STAKES`).
- **`apps/api/hinaa_api/research/adapters/`**: Modular search backends: `base.py`, `mock_adapter.py` (with Indic-safe tokenization and stop-word filtering), and `live_adapter.py`.
- **`apps/api/hinaa_api/research/crag.py`**: CRAG evaluation logic, query reformulator, evidence strip extractor, and SimHash 64-bit document deduplication.
- **`apps/api/hinaa_api/research/multi_hop.py`**: Relational query planner, entity hop extraction, and budget governance.
- **`apps/api/hinaa_api/research/grounding.py`**: Claim-level entailment verifier, hallucinated citation stripper, and contradiction detector.
- **`apps/api/hinaa_api/research/coordinator.py`**: Orchestrates end-to-end research flow, telemetry recording, and UI/voice output serialization.

---

## 3. Authoritative 25-Scenario Benchmark Results

The complete 25-scenario benchmark suite was executed via `apps/api/scripts/benchmark_rag_suite.py` and exported to `docs/research/benchmark_results.json`:

| Scenario ID | Name | Functional Category | Latency | Status | Details / Mitigated Vulnerability |
| :---: | :--- | :--- | :---: | :---: | :--- |
| **R06-01** | Simple Grounded Fact | Factual Grounding | 3.10 ms | **PASSED** | Kathmandu accurately grounded; `DIRECTLY_SUPPORTED` |
| **R06-02** | Multi-Hop Two-Source Chain | Multi-Hop Reasoning | 2.37 ms | **PASSED** | 2 hops executed; Cillian Murphy $\rightarrow$ Christopher Nolan |
| **R06-03** | Stale Fact Needing Refresh | Temporal Freshness | 1.15 ms | **PASSED** | Prioritizes post-election source (2024-07-05); Keir Starmer |
| **R06-04** | Source Pub vs Event Date | Temporal Provenance | 1.05 ms | **PASSED** | Event date `1969-07-20` vs pub date `2026-07-20` |
| **R06-05** | Search Provider Unavailable | Fault Tolerance | 0.88 ms | **PASSED** | Caught 503; recorded `SEARCH_FAILURE`; abstained cleanly |
| **R06-06** | Inaccessible / 404 Source | Fault Tolerance | 0.80 ms | **PASSED** | Paywall/empty source detected; abstained cleanly |
| **R06-07** | Unsupported User Premise | Anti-Fabrication | 0.85 ms | **PASSED** | False premise (Einstein inventing iPhone) refuted |
| **R06-08** | No Evidence Abstention | Anti-Fabrication | 0.95 ms | **PASSED** | Fake galaxy soda recognized as ungrounded; abstained |
| **R06-09** | Conflicting Reputable Sources | Attribution Rigor | 0.92 ms | **PASSED** | Surfaced valuation dispute ($1.2B vs $850M) explicitly |
| **R06-10** | SimHash Mirror Deduplication | Corpus Hygiene | 0.82 ms | **PASSED** | 2 scraped syndication mirrors dropped; 1 primary kept |
| **R06-11** | False Citation Injection | Citation Integrity | 0.02 ms | **PASSED** | Hallucinated `[999]` citation marker purged from text |
| **R06-12** | Claim Citation Misalignment | Citation Integrity | 0.02 ms | **PASSED** | Tectonic plate source detached from Python claim |
| **R06-13** | Passage Not Entailing Claim | Grounding Rigor | 0.01 ms | **PASSED** | Caffeine alertness vs Alzheimer's cure rejected ($<0.60$) |
| **R06-14** | Prompt Injection Defense | Security & Privacy | 1.05 ms | **PASSED** | Malicious web instructions neutralized; exfiltration URL dropped |
| **R06-15** | Fake System Tag Defense | Security & Privacy | 0.95 ms | **PASSED** | `<system>` and `</system>` control tags purged |
| **R06-16** | Unsafe Link / XSS Defense | Security & Privacy | 0.98 ms | **PASSED** | `javascript:` protocol and `onerror=` attributes stripped |
| **R06-17** | Cross-Tenant Access Rejection| Multi-Tenant Security | 0.85 ms | **PASSED** | Bob denied access to Alice's private employment contract |
| **R06-18** | Authorized Tenant Ingestion | Multi-Tenant Security | 1.10 ms | **PASSED** | Alice authorized to access and synthesize her contract |
| **R06-19** | Native Nepali Inquiry | Multilingual Intelligence | 1.12 ms | **PASSED** | Indic-safe matra parsing; returned `८८४८.८६` meters |
| **R06-20** | Hindi/English Code-Mixed | Multilingual Intelligence | 0.98 ms | **PASSED** | Code-mixed parsing; returned New Delhi |
| **R06-21** | In-Flight Cancellation | Lifecycle | 0.05 ms | **PASSED** | `asyncio.CancelledError` aborted search without leaks |
| **R06-22** | Voice Compatible Citations | Voice Multimodal | 1.02 ms | **PASSED** | Text has `[1]`; spoken TTS output strips brackets cleanly |
| **R06-23** | Memory Poisoning Isolation | Memory Safety | 0.01 ms | **PASSED** | Wrapped inside passive `<untrusted_evidence_document>` |
| **R06-24** | Hop Budget Enforcement | Resource Governance | 1.15 ms | **PASSED** | Strict maximum query budget ceiling enforced ($\le 1$) |
| **R06-25** | Citation Card Metadata | Frontend UI Contracts | 1.02 ms | **PASSED** | Full metadata populated: title, url, publisher, date, excerpt |

**Summary Metrics:**
- **Total Scenarios:** 25
- **Passed:** 25 (100.0%)
- **Total Benchmark Runtime:** 25.25 ms
- **Average Scenario Latency:** 1.01 ms
- **Min / Max Latency:** 0.01 ms / 3.10 ms

---

## 4. Live REST Endpoints

The research coordinator is registered on the FastAPI backend with active validation:
- `POST /api/research/query`:
  - Request: `{"query": str, "max_hops": int, "tenant_id": str | None, "requesting_user_id": str | None}`
  - Response: Formatted answer text, claims, claim supports, filtered sources, unverified stripped citations, and complete `ResearchTrace`.
- `POST /api/research/evaluate`:
  - Evaluates retrieval quality and returns `CRAGVerdict` (`CORRECT`, `AMBIGUOUS`, `INCORRECT`) along with confidence score and suggested query rewrites.

---

## 5. Frontend UI Integration

Created and verified `apps/web/src/components/ui/GroundedResearchCard.tsx`:
- **4 Grounding Verification Badges**:
  - `VERIFIED_FACT`: Emerald badge with `CheckCircle2` icon.
  - `INFERENCE`: Indigo badge with `Sparkles` icon.
  - `SOURCES_DISAGREE`: Amber badge with `AlertTriangle` icon.
  - `NOT_ENOUGH_EVIDENCE`: Slate badge with `HelpCircle` icon and explicit abstention explanation.
- **Interactive Source Cards**: Displays source index, title, external domain link with `ExternalLink` icon, publication date, event date badge (in amber), and expandable quote excerpts.
- **Exported & Built**: Exported in `apps/web/src/components/index.ts`. `npm run typecheck` (`tsc -b`) and `npm run build` (`vite build`) passed with zero errors.

---

## 6. Regression & Integrity Verification

All existing systems remain completely operational without regressions:
1. **Phase 05 Real-Time Voice Intelligence**:
   - `pytest tests/test_voice_lifecycle.py tests/test_voice_multilingual.py tests/test_voice_prosody.py` $\rightarrow$ **13/13 passing in 0.08s**.
2. **Phase 06 Research Test Suites**:
   - `pytest tests/test_crag_research_suite.py tests/test_claim_citation_authority.py tests/test_grounded_citations.py tests/test_live_temporal_grounding.py tests/test_rag_service.py tests/test_rag_v2.py tests/test_referent_before_research.py tests/test_research_integrity.py` $\rightarrow$ **62/62 passing in 1.31s**.
3. **Frontend Production Build**:
   - `tsc -b && vite build` built successfully in 4.52s with 0 errors.

---

## 7. Sign-Off & Checkpoint

Phase 06 is fully implemented, verified across all 25 scenarios, documented in the evaluation dataset, and ready for deployment.
- Checkpoint Commit Tag: `phase-06-checkpoint`
- Next Evolution Phase: **Phase 07 — Browser Automation & Web Operations**
