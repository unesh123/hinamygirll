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
| **P3** | Image Generation & Editing | Phase 09 | **VERIFIED** | Local procedural/neural raster engine, OpenCV Telea/Navier-Stokes inpainting, background removal, immutable SHA-256 provenance. |
| **P4** | Video Generation & Pipelines | Phase 09 | **TIMELINE VERIFIED / GENERATIVE BLOCKED** | FFmpeg 7.1 deterministic MP4 timeline export verified; generative video (T2V/I2V) truthfully failed closed/blocked pending weights. |
| **P5** | Real-Time Voice Intelligence | Phase 05 | **VERIFIED** | 9-state turn lifecycle, sub-400ms TTFA, true barge-in with monotonic generation IDs. |
| **P6** | Grounded Research & CRAG | Phase 06 | **VERIFIED** | Corrective RAG scoring, citation anti-fabrication (`[999]` stripping), live Exa queries (~3.9s). |
| **P7** | Complete Coding Agent & IDE | Phase 08 | **VERIFIED** | 48 B08 scenarios: repo scanner, Windows Job Object / Docker isolation, diff engine, build/test loop, atomic rollback. |
| **P8** | Nepal Local Payments (eSewa/Khalti) | Phase 11 | **SPECIFIED / SANDBOX** | HMAC-SHA256 eSewa signing, Khalti paisa minor units, order state machine, replay defense (production funds blocked). |
| **P9** | NPR Pricing & Bilingual Support | Phase 11 | **SPECIFIED / SANDBOX** | Canonical paisa storage, South Asian digit grouping (`रु 1,25,000.00`), bilingual billing assistance. |

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

### Capability P3: Image Generation and Editing (Phase 09 Sign-Off)
- [x] Text-to-image rendering via local engine with Devanagari visual typography.
- [x] Masked inpainting using OpenCV Telea & Navier-Stokes algorithms; parent asset hash byte-identical.
- [x] Background removal isolating foreground and generating transparent 4-channel RGBA PNGs.
- [x] SHA-256 cryptographic asset cataloging with tenant directory boundaries.
- [x] Safe prompt filtering, injection defanging, and secret canary scrubbing.

### Capability P4: Video Generation & Pipelines (Phase 09 Sign-Off)
- [x] Deterministic timeline video export to playable H.264 MP4 using FFmpeg 7.1.
- [x] FFmpeg probe verification extracting codec, dimensions, duration, and rational frame rate.
- [x] Honest capability discovery: Generative video (T2V/I2V) failed closed as `BLOCKED` without local weights or paid APIs.
- [x] Zero mock or CSS fake video counted as generative media.

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

### Capability P7: Complete Coding Agent (Phase 08 Sign-Off)
- [x] Host OS sandbox discovery distinguishing Docker, WSL2, and Windows Job Object boundaries.
- [x] Non-root, zero-secret container/process isolation with network disable by default.
- [x] Repository inspection, AST/symbol discovery, and bounded search.
- [x] Structured patch application with exact disk diff validation and CRLF/LF line-ending normalization.
- [x] Automated execution of `pytest` and `npm test` inside sandbox.
- [x] Autonomous error diagnosis and multi-turn repair loop within configured budget (max 3 loops).
- [x] Non-destructive Git feature branching and task-scoped atomic rollback.
- [x] Frontend developer panel (`CodingTaskPanel.tsx`) with live terminal streaming and artifact previews.

### Capability P8: Nepal Local Payments (eSewa & Khalti)
- [ ] eSewa merchant checkout request signing via HMAC-SHA256 (`total_amount`, `transaction_uuid`, `product_code`).
- [ ] Server-to-server transaction status verification against eSewa API.
- [ ] Khalti ePayment initiation with hosted checkout URL and `pidx`.
- [ ] Canonical integer minor unit conversion (1 NPR = 100 paisa) avoiding float drift.
- [ ] Order state lifecycle: `CREATED` $\rightarrow$ `PENDING` $\rightarrow$ `PAID` / `FAILED` / `EXPIRED`.
- [ ] Idempotent webhook/callback processing with duplicate replay defense.
- [x] Merchant sandbox credential separation; production live funds strictly blocked without merchant approval.

### Capability P9: NPR Pricing and Bilingual Customer Support
- [x] Format currency with official rupee symbol (`रु`) and South Asian digit grouping (`1,25,000.00`).
- [x] Bilingual checkout interface specification (Devanagari Nepali & English).
- [ ] Automated billing receipts with downloadable PDF/HTML artifacts.
- [ ] Grounded customer support agent answering billing FAQs without leaking other tenants' data.
- [ ] Human escalation workflow for disputed charges.
