# HINAA OS — Feature Acceptance Matrix (V3 Specification)

**Status**: Canonical Acceptance Matrix  
**Scope**: Mandatory Capabilities across 18 Phases  
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
| **P10** | Long-Term Memory & Knowledge Graph | Phase 10 | **VERIFIED** | 64 M10 scenarios: SQLite WAL ACID persistence, FTS5 BM25, temporal knowledge graph (max 3 hops), non-destructive supersession, quarantine staging, 11 REST endpoints. |
| **P11** | Autonomous Tooling & Multi-Agent Swarms | Phase 11 | **VERIFIED** | 80 A11 scenarios: 10 canonical specialist roles, acyclic DAG planning, cryptographic ToolReceipts, independent verification oracle, Tier C HMAC approvals, CAS leases, restart recovery, SSE event journal, React 19 UI workspace. |
| **P12** | Hierarchical Team Orchestration & Long-Horizon Execution | Phase 12 | **VERIFIED** | 80 H12 scenarios: 3-way adaptive routing, 4 canonical team templates, typed delegation packets & outcomes, context isolation & secret scrubbing, nested budget slicing with auto-refunds, complete ancestry HMAC approvals, independent QA overrides, workflows W1–W6 verified, 3-mode comparative benchmark. |

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

### Capability P10: Long-Term Memory & Continuous Knowledge Graph (Phase 10 Sign-Off)
- [x] Durable SQLite transactional persistence with WAL mode (PRAGMA journal_mode=WAL), foreign keys, and idempotent schema migrations (v1_phase10_init).
- [x] Full-text search via SQLite FTS5 with automatic insert/update/delete synchronization triggers and Devanagari Unicode support.
- [x] Temporal knowledge graph with typed directed edges, alias resolution (English, Romanized, Devanagari), cycle detection, and bounds (max depth 3, max nodes 50).
- [x] Hybrid multi-modal retrieval blending lexical FTS5 (0.45), dense vector cosine similarity (0.40), and graph proximity (0.15) with token budgeting and source provenance.
- [x] Non-destructive contradiction detection and supersession lineage (is_contradicted=True, superseded_by_id, SUPERSEDES edge) preserving complete audit history.
- [x] Multi-tenant privacy boundaries, automatic secret canary scrubbing (sk-..., tokens, private keys), and prompt injection defanging.
- [x] Continuous knowledge acquisition quarantine staging pipeline (IngestionCandidate) with operator review workflow (approve/reject).
- [x] Scoped JSON/CSV data export and hard delete cascade invalidating memory rows, FTS entries, and derived graph edges.
- [x] Frontend developer & operations panel (MemoryKnowledgePanel.tsx) with hybrid search, graph visualization, candidate queue, and telemetry badges.
- [x] 11 authenticated REST endpoints under /api/memory/... and /v1/memory/... in main.py.

### Capability P11: Autonomous Tooling & Multi-Agent Swarms (Phase 11 Sign-Off)
- [x] Zero "swarm theater": 10 isolated specialist roles with explicit `CapabilityGrant`, tool whitelists, and model routing.
- [x] Directed Acyclic Graph (DAG) task planning, topological sorting, and cycle rejection with `DAGCycleError`.
- [x] Decision gate: single-agent fast path (<50ms) for direct queries vs multi-agent DAG for complex missions.
- [x] Context minimization handoffs scrubbing API keys and credentials, with bounded delegation depth ($\le 4$).
- [x] Universal tool execution receipts (`ToolReceipt`) with cryptographic SHA-256 input/output digests and exit codes.
- [x] Independent postcondition verification oracle; resolves conflicting claims strictly in favor of QA evidence.
- [x] Tier C human-in-the-loop governance: HMAC-SHA256 signature verification over action, arguments digest, nonce, TTL, and integer paisa monetary amounts.
- [x] Crash recovery and atomic worker leases: SQLite WAL persistence (`hinaa_agent_tasks.db`), Compare-and-Swap (CAS) claiming, and automatic restart recovery.
- [x] Real-time SSE event journal with monotonic sequence numbers (`hinaa_agent_events.db`).
- [x] Frontend multi-agent workspace (`AgentOrchestrationPanel.tsx`, `AgentTaskGraph.tsx`, `AgentApprovalPanel.tsx`) typechecked with React 19 (`tsc -b` clean).
- [x] 9 authenticated REST endpoints in `main.py` verified on live daemon serving 548 total routes.
- [x] Authoritative 80-scenario acceptance benchmark passed (80/80, 100.0%) in 11.48s.


### Capability P12: Hierarchical Team Orchestration & Long-Horizon Execution (Phase 12 Sign-Off)
- [x] **3-Way Adaptive Execution Mode:** Automated classification dynamically routing requests to Single-Agent Fast Path (< 100ms), Flat Multi-Agent Swarm (Phase 11), or Hierarchical Teams (Phase 12).
- [x] **4 Canonical Team Templates:** EngineeringTeam, ResearchTeam, CreativeTeam, and OperationsTeam registered with strict least-privilege capability grants and subagent budgets.
- [x] **Typed Delegation & Outcomes:** Bounded DelegationRequest envelopes and cryptographically signed TeamResult packets with SHA-256 digests and postcondition checks.
- [x] **Context Isolation & Secret Scrubbing:** Credentials, bearer tokens, and API keys scrubbed in-flight by ContextScrubber during team delegation.
- [x] **Nested Budget Slicing:** Child budgets bounded by parent capacity with automated return/refund of unconsumed allocations.
- [x] **HMAC-SHA256 Ancestry Binding:** Complete execution ancestry (	ask > team > node) bound in Tier C human authorization tokens preventing replay across nodes/teams.
- [x] **Independent QA Verification Overrides:** Developer claims strictly subordinated to test exit codes (0 vs non-zero) and artifact SHA-256 verification.
- [x] **Workflows W1–W6:** Bilingual app build, research to code, conflict rejection, worker crash recovery, safe Nepali commerce, and creative limitation honesty verified.
- [x] **Acceptance Suite:** 80/80 H12 scenarios passed (100.0%) in 3.43s; 80/80 Phase 11 regression passed (100.0%) in 11.87s.
- [x] **Comparative Benchmark:** 30 frozen tasks evaluated across Mode A, Mode B, and Mode C logged in docs/agents/benchmark_results_phase12.json.
- [x] **Frontend & API Routes:** AgentOrchestrationPanel.tsx, AgentTaskGraph.tsx, and AgentApprovalPanel.tsx updated and built cleanly (pnpm --filter web build 3.63s, 0 errors). Live daemon serving 550 total routes.
