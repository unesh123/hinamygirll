# HINAA OS — Phase 10 Evaluation Dataset & Benchmark Manifest

## 1. Evaluation Methodology

Phase 10 evaluation is conducted against **64 reproducible scenarios** covering durability, graph traversal bounds, hybrid ranking fidelity, contradiction resolution, multi-tenant isolation, cascade deletions, and REST endpoints.

| Group | Range | Scenario Category | Target Metric |
| :--- | :--- | :--- | :--- |
| **G1** | `M10-01` – `M10-08` | Architecture Baseline & Durability | 100% Pass, ACID rollback integrity |
| **G2** | `M10-09` – `M10-16` | Temporal Knowledge Graph | Max depth 3, max nodes 50, cycle termination |
| **G3** | `M10-17` – `M10-24` | Hybrid Retrieval Engine | FTS5 BM25 match, Devanagari Unicode support |
| **G4** | `M10-25` – `M10-32` | Contradiction Resolution | Zero data loss, supersession pointers preserved |
| **G5** | `M10-33` – `M10-40` | Privacy & Secret Scrubbing | 100% tenant isolation, all secret canaries redacted |
| **G6** | `M10-41` – `M10-48` | Lifecycle Governance & Cascades | Derived edge cleanup, TTL sweep, valid JSON/CSV |
| **G7** | `M10-49` – `M10-56` | Continuous Ingestion Quarantine | Zero unverified contamination, promotion verified |
| **G8** | `M10-57` – `M10-64` | REST Endpoints & Telemetry | 200/201 HTTP status, 404 on missing, live stats |

---

## 2. Test Execution & Evidence Log

- **Benchmark Runner**: `apps/api/scripts/run_m10_benchmark.py`
- **Pytest Suite**: `apps/api/tests/memory/test_m10_suite.py`
- **Output Digest**: `docs/memory/benchmark_results.json`
- **Total Scenarios**: 64
- **Passed**: 64 (100.0%)
- **Failed**: 0
- **Duration**: 10.55s total runtime (4.16s test execution)
