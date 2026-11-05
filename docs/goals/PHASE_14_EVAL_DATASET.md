# HINAA OS — Phase 14 Evaluation Dataset & Held-Out Benchmarks
**Dataset Reference:** `DATASET-GOALS-P14-BENCHMARK`  
**Version:** 1.0.0  
**Date:** 2026-11-05  

---

## 1. Dataset Overview & Stratification

The Phase 14 benchmark dataset consists of 30 held-out tasks designed to evaluate autonomous goal planning, evidence verification, and self-correction. Tasks are stratified across three distinct operational regimes:

1. **Stratum A: Simple Deterministic Tasks (10 Tasks)**  
   Direct single-stage or two-stage goals with clear specifications, tested to measure baseline execution latency and dispatch overhead.
2. **Stratum B: Multi-Step Hierarchical Tasks (10 Tasks)**  
   Three-stage to five-stage DAG pipelines requiring prerequisite coordination, nested budget slicing, and independent QA verification.
3. **Stratum C: Changing & Failing Conditions (10 Tasks)**  
   Adversarial and dynamic tasks featuring deliberately introduced test failures, contradictory live sources, unavailable dependencies, runtime timeouts, and midway user intent changes.

---

## 2. Benchmark Task Catalog (30 Held-Out Cases)

| Task ID | Stratum | Objective Title | Domain | Expected Milestones | Injected Obstacle / Condition |
|---|---|---|---|---|---|
| `TS-01` | Simple | Generate SQLite WAL Pragma Migration | Database | 2 | None (Deterministic) |
| `TS-02` | Simple | Extract OpenAPI JSON Endpoints Manifest | Backend | 2 | None (Deterministic) |
| `TS-03` | Simple | Format Devanagari Nepali Currency Table | Fintech | 2 | None (Deterministic) |
| `TS-04` | Simple | Inspect Git Branch Status & Tags | DevOps | 2 | None (Deterministic) |
| `TS-05` | Simple | Validate Pydantic Schema Contracts | Backend | 2 | None (Deterministic) |
| `TS-06` | Simple | Benchmark FastPath Single-Agent Latency | Performance | 2 | None (Deterministic) |
| `TS-07` | Simple | Generate ElevenLabs Speech Token Stream | Audio | 2 | None (Deterministic) |
| `TS-08` | Simple | Parse Standard 5-Field Asia/Kathmandu Cron | Autopilot | 2 | None (Deterministic) |
| `TS-09` | Simple | Clean Playwright Browser Session Storage | Browser | 2 | None (Deterministic) |
| `TS-10` | Simple | Calculate Nepal Minor-Unit Paisa Budget | Accounting | 2 | None (Deterministic) |
| `TS-11` | Multi-Step | Build Next.js Bilingual Greeting App | Web Dev | 3 | Full build, sandbox test, layout check |
| `TS-12` | Multi-Step | Research Nepal Digital Wallet Interoperability | Fintech Spec | 3 | Multi-source CRAG retrieval, claim synthesis |
| `TS-13` | Multi-Step | Setup Redis Cluster with Failover Sentinel | Infrastructure | 4 | Config, sandbox validation, simulated kill |
| `TS-14` | Multi-Step | Analyze Hydropower Transmission Constraints | Public Policy | 3 | Data extraction, numeric validation, report |
| `TS-15` | Multi-Step | Refactor Rust Mutex Locking in DAG Engine | Systems | 3 | Precondition check, diff, test suite verification |
| `TS-16` | Multi-Step | Implement Fonepay QR ISO 8583 Gateway | Payments | 3 | Payload generation, HMAC signing, sandbox mock |
| `TS-17` | Multi-Step | Multi-Agent Swarm vs Single-Agent Profiling | Benchmarking | 3 | Parallel execution, latency log, trade-off review |
| `TS-18` | Multi-Step | Curate Quarantined Knowledge Graph | Memory | 3 | Discovery, evidence linking, operator review |
| `TS-19` | Multi-Step | Build Browser Automation CDP Session Recovery | Browser | 3 | Headless launch, disconnect, reconnect loop |
| `TS-20` | Multi-Step | Deploy High-Frequency Edge Telemetry Pipeline | Distributed | 4 | SSE brokerless stream, consumer lag test |
| `TS-21` | Changing | Unit Test Failure in Shopping Cart Module | Web Dev | 3 ➔ 3 (V2) | **Test Failure:** `AssertionError: 200 != 500` |
| `TS-22` | Changing | Contradictory Data in Electricity Surplus Report | Research | 3 ➔ 3 (V2) | **Contradiction:** NEA 1000MW vs Board 450MW |
| `TS-23` | Changing | Request Generative Video Diffusion Weights | Multimodal | 2 | **Unavailable Tool:** Local weights unverified |
| `TS-24` | Changing | Stalled Database Query During Index Rebuild | Database | 2 ➔ 2 (V2) | **Stall:** Execution > 600 seconds without heartbeat |
| `TS-25` | Changing | User Mid-Queue Revision: AWS ECS to Fly.io | DevOps | 3 ➔ 3 (New) | **Intent Change:** User redirects target platform |
| `TS-26` | Changing | DNS Search Outage in Live Research Gatherer | Research | 3 ➔ 3 (V2) | **Tool Outage:** Primary search provider times out |
| `TS-27` | Changing | Adversarial Ingestion with Embedded Transfer | Security | 2 | **Prompt Injection:** Malicious payload sanitized |
| `TS-28` | Changing | Flaky API with Controlled Exponential Backoff | Backend | 3 | **Transient Timeout:** 503 error recovered on attempt 2 |
| `TS-29` | Changing | Parameter Tampering on Tier C Payment Action | Governance | 2 | **HMAC Tampering:** Amount modified 10k to 50k |
| `TS-30` | Changing | Exhausted Paisa Budget Ceiling During Run | Economics | 3 | **Budget Ceiling:** Consumed paisa > budget limit |

---

## 3. Evaluation Protocol

Each scenario was executed under identical baseline sandbox conditions across two software configurations:
- **Baseline Configuration (Phase 13 Autopilot):** Fixed static task sequence without dynamic DAG replanning. On error or contradiction, the task halts and reports `FAILED`.
- **Phase 14 Configuration (Goal Planner & Self-Correction):** Continuous monitoring, independent Critic receipt evaluation, bounded replanning, loop detection, and quarantined lesson staging.
