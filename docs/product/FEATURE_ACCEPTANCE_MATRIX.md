# HINAA OS — Feature Acceptance Matrix (V3 Specification)

**Status**: Canonical Acceptance Matrix  
**Scope**: 9 Mandatory Capabilities across 18 Phases  
**Rule**: No feature is marked complete without deterministic automated tests and verifiable end-to-end evidence.

---

## 1. Acceptance Matrix Overview

| Cap ID | Capability Name | Target Phase | Implementation Status | Evidence Standard Required |
| :---: | :--- | :---: | :---: | :--- |
| **P1** | Advanced Reasoning & Planning | Phase 03–04 | **VERIFIED** | Algorithmic turn complexity, 7-mood continuous vector, held-out logic benchmarks. |
| **P2** | Bilingual Nepali & English | Phase 04–05 | **VERIFIED** | Indic-safe tokenization, Devanagari vowel preservation, Romanized disambiguation. |
| **P3** | Image Generation & Editing | Phase 09 | **QUEUED** | Text-to-image, inpainting, background removal, ComfyUI/Diffusers, asset provenance. |
| **P4** | Video Generation & Pipelines | Phase 10 | **QUEUED** | Text/image-to-video, queue management, cancellation, downloadable MP4, VRAM guard. |
| **P5** | Real-Time Voice Intelligence | Phase 05 | **VERIFIED** | 9-state turn lifecycle, sub-400ms TTFA, true barge-in with monotonic generation IDs. |
| **P6** | Grounded Research & CRAG | Phase 06 | **VERIFIED** | Corrective RAG scoring, citation anti-fabrication (`[999]` stripping), live Exa queries (~3.9s). |
| **P7** | Complete Coding Agent & IDE | **Phase 08** | **ACTIVE EXECUTION** | 48 B08 scenarios: repo scanner, sandbox isolation, diff engine, build/test loop, rollback. |
| **P8** | Nepal Local Payments (eSewa/Khalti) | Phase 11 | **SPECIFIED / SANDBOX** | HMAC-SHA256 eSewa signing, Khalti paisa minor units, order state machine, replay defense. |
| **P9** | NPR Pricing & Bilingual Support | Phase 11 | **SPECIFIED / SANDBOX** | Canonical paisa storage, South Asian digit grouping (`रु 1,00,000`), support ticket CRM. |

---

## 2. Detailed Capability Acceptance Gates

### Capability P1: Advanced Reasoning
- [x] Adaptive model routing across 5 distinct provider tiers based on normalized turn complexity.
- [x] Auto-healing circuit breaker with exponential backoff and half-open probes.
- [x] Structured tool pre/postconditions preventing hallucinated action outcomes.
- [x] Honest uncertainty detection and abstention when evidence is insufficient.

### Capability P2: Bilingual Nepali and English Conversations
- [x] Devanagari Unicode preservation without forced phonetic distortion.
- [x] Romanized Nepali recognition (*"Kasto chha timilai?", "K cha khabar?"*).
- [x] Real-time code-switching handling in conversational turns.
- [x] Domain glossary mapping Nepali administrative, geographic, and tech terminology.

### Capability P3: Image Generation and Editing (Queued for Phase 09)
- [ ] Text-to-image rendering via local GPU or remote API.
- [ ] Masked inpainting and background removal.
- [ ] SHA-256 asset cataloging and persistent metadata inventory.
- [ ] Safe prompt filtering and content labeling.

### Capability P4: Video Generation (Queued for Phase 10)
- [ ] Text-to-video / image-to-video pipeline execution.
- [ ] Hardware capability detection (RTX 4060 8GB VRAM boundaries).
- [ ] Job status polling, cancellation, and download receipt generation.
- [ ] Graceful fallback when local GPU capacity is constrained.

### Capability P5: Real-Time Voice Conversation
- [x] 9-state formal lifecycle (`IDLE` $\rightarrow$ `SPEAKING` $\rightarrow$ `INTERRUPTING`).
- [x] Microsecond-accurate latency measurements for TTFT, TTFA, and barge-in.
- [x] Immediate streaming cancellation and audio queue purge on user speech.
- [x] 4D emotional prosody modulation across 7 discrete mood states.

### Capability P6: Research with Verified Sources
- [x] Confidence-gated Corrective RAG (CRAG) with SimHash deduplication.
- [x] Multi-hop entity graph decomposition and iterative query formulation.
- [x] Anti-fabrication citation gate stripping ungrounded bracket markers (`[999]`).
- [x] Live search integration with Exa API verified with real internet queries.

### Capability P7: Complete Coding Agent (Phase 08 Active Implementation)
- [ ] Host OS sandbox discovery distinguishing Docker, WSL2, and Windows Job Object boundaries.
- [ ] Non-root, zero-secret container/process isolation with network disable by default.
- [ ] Repository inspection, AST/symbol discovery, and bounded search.
- [ ] Structured patch application with exact disk diff validation.
- [ ] Automated execution of `pytest` and `npm test` inside sandbox.
- [ ] Autonomous error diagnosis and multi-turn repair loop within configured budget.
- [ ] Non-destructive Git feature branching and one-click rollback.
- [ ] Frontend developer panel with live terminal streaming and artifact previews.

### Capability P8: Nepal Local Payments (eSewa & Khalti)
- [ ] eSewa merchant checkout request signing via HMAC-SHA256 (`total_amount`, `transaction_uuid`, `product_code`).
- [ ] Server-to-server transaction status verification against eSewa API.
- [ ] Khalti ePayment initiation with hosted checkout URL and `pidx`.
- [ ] Canonical integer minor unit conversion (1 NPR = 100 paisa) avoiding float drift.
- [ ] Order state lifecycle: `CREATED` $\rightarrow$ `PENDING` $\rightarrow$ `PAID` / `FAILED` / `EXPIRED`.
- [ ] Idempotent webhook/callback processing with duplicate replay defense.
- [ ] Merchant sandbox credential separation; production live funds strictly blocked without merchant approval.

### Capability P9: NPR Pricing and Bilingual Customer Support
- [ ] Format currency with official rupee symbol (`रु`) and South Asian digit grouping (`1,25,000.00`).
- [ ] Bilingual checkout interface (Devanagari Nepali & English).
- [ ] Automated billing receipts with downloadable PDF/HTML artifacts.
- [ ] Grounded customer support agent answering billing FAQs without leaking other tenants' data.
- [ ] Human escalation workflow for disputed charges.
