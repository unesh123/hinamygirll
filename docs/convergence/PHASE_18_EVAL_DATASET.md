# HINAA OS — Phase 18 Acceptance Evaluation Dataset
**Document Version:** 1.0.0  
**Suite:** `apps/api/tests/convergence/test_c18_suite.py`  
**Total Scenarios:** Exactly 128 scenarios across 16 groups (8 scenarios per group)  
**Execution Status:** 128 / 128 PASSED (100% Pass Rate, 0 Skips, 0 Failures)  
**Execution Time:** 10.48s

---

## 1. Scenario Group Partitioning

| Group | Group Identifier & Domain | Scenarios | Target Verification Invariants |
|---|---|---|---|
| **A** | Baseline & Evidence Honesty | C18-001 to C18-008 | Git tags, Phase 17 reconciliation (112 vs 113), physical hardware limits, honest blocked labeling, artifact digests, zero consciousness. |
| **B** | Unified Mission State & Routing | C18-009 to C18-016 | 12-state transition engine, terminal immutability, single-agent fast path, hierarchical routing, integer paisa budget, timeouts, step limits, idempotent retry. |
| **C** | Browser & Computer Operations | C18-017 to C18-024 | Chromium Playwright probe, DOM tree extraction, domain allowlists, file:// sandbox block, screenshot digests, multi-tab contexts, transient retries, memory cleanup. |
| **D** | Coding & Developer Workspace | C18-025 to C18-032 | Directory traversal defense, AST validation, execution sandbox limits, unified diff hunk headers, test reporting, Python 3.12 compatibility, patch SHA-256, reversible rollback. |
| **E** | Grounded Research & Documents | C18-033 to C18-040 | CRAG reciprocal rank fusion, URL citations, anti-fabrication thresholds, contradiction detection, structured markdown, executive summaries, provenance tracking, TTL cache invalidation. |
| **F** | Conversational Voice & Multilingual | C18-041 to C18-048 | Reflective script generation, verbatim mode preservation, trilingual support (EN/NE/ROM), voice ID `dp4HJlekKt0HZFHL2jQg`, viseme timing, fast-path latency, chunk streaming, prosody tags. |
| **G** | Memory, Self-Model & User Control | C18-049 to C18-056 | Episodic recency weighting, self-model boundary checks, preference persistence, right to be forgotten deletion, bounded recall, contradiction resolution, audit logs, identity stability. |
| **H** | Creative & Multimodal Truth | C18-057 to C18-064 | Timeline MP4 assembler check, neural video diffusion blocked check, procedural canvas check, audio stems sync, multimodal SHA-256 digests, metadata schemas, fallback rendering, export formats. |
| **I** | Files, Desktop UI & Usability | C18-065 to C18-072 | Filesystem path containment, trilingual UI keys, responsive CSS tokens, probe polling/SSE, artifact download headers, approval cards, actionable error hints, ARIA accessibility. |
| **J** | Durability, Offline & Device Sync | C18-073 to C18-080 | SQLite WAL restart persistence, in-flight recovery after ungraceful crash, offline cached operations, mesh vector clocks, LWW conflict resolution, backup checksums, restore integrity, migration idempotency. |
| **K** | Approvals & Boundaries | C18-081 to C18-088 | Tier A autonomous reads, Tier B medium approvals, Tier C explicit human approvals, parameter bounds enforcement, token expiry, tamper-evident audit trails, rejection handlers, PDP interception. |
| **L** | Privacy, Audit & Tamper Evidence | C18-089 to C18-096 | Merkle tree audit log verification, PII redaction, secret/token masking, immutable append-only storage, 90-day data retention pruning, verified zip export, cryptographic signing, zero unauthorized telemetry. |
| **M** | Performance, Cost & Efficiency | C18-097 to C18-104 | Cost accounting in minor integer paisa, token tracking, single-agent fast path < 200ms, coordination overhead < 1500ms, budget hard stops, RAM monitoring (< 2GB), connection pooling, cache hit ratios. |
| **N** | Self-Correction & Improvement | C18-105 to C18-112 | Error diagnosis taxonomy, transient vs deterministic root cause analysis, autonomous plan revision, retry budget bounds, golden benchmark harness, regression detection, shadow evaluation, improvement proposals. |
| **O** | Capstone Missions & Human Quality | C18-113 to C18-120 | Full-stack patch execution, bilingual research, sandbox payment approval, multimodal media assembly, process fault recovery, voice synthesis, unattended simulation boundaries, capstone report artifact. |
| **P** | Regression & Release Governance | C18-121 to C18-128 | Phase 01–17 test suite integration, clean API startup, clean Web build, database schema completeness, penetration testing, release scorecard, Git tag verification, final 18-phase evolution closure. |

---

## 2. Methodology & Evidence Standard

1. **Deterministic Execution**: No flaky sleep timers or external network dependencies inside unit assertions; external API calls use local mock/sandbox or structural verification where offline.
2. **Cryptographic Checksums**: Every generated artifact must produce a valid SHA-256 digest (`len(digest) == 64`) verified against file contents.
3. **Integer Minor Units**: All monetary values are recorded as integer minor units (`paisa`), where `1 NPR = 100 Paisa`. Floating point currency representations are strictly prohibited in the engine.
