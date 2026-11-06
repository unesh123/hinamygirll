# HINAA OS — Phase 16 Baseline Risk Register & Evidence Reconciliation
**Document Version:** 1.0  
**Date:** 2026-11-06  
**Auditor:** Anti-Gravity Principal AI Evaluation & Security Reviewer  
**Starting Baseline:** `phase-15-checkpoint` (`92df96d6f129f5f4ab2d5c146c69e67df012654b` on `main`)  
**Feature Branch:** `phase-16-eval-harness`  

---

## 1. Executive Summary
Before making the system autonomous through self-improvement, all prior claims, evidence gaps, and security assumptions must be independently audited and reconciled.
This document formally records the empirical reconciliation of Phase 15 evidence, identifies residual risks, and establishes blocking gates for production promotion.

---

## 2. Evidence Reconciliation Matrix

| Area | Phase 15 Claimed Status | Empirical Reality / Audit Finding | Reconciled Baseline Position | Severity | Owner |
|---|---|---|---|:---:|:---:|
| **E1 Coding Execution** | E1 demonstrated `coding:run` ALLOW policy decision and audit receipt. | Policy decision and receipt were logged, but end-to-end execution did not record a physical changed artifact hash or independent test execution in the demonstration output. | Reconciled: A full physical build/test loop with changed file SHA-256 and pytest exit code 0 is executed in Phase 16 demonstration I1. Policy ALLOW alone is marked INSUFFICIENT for E2E claim. | MEDIUM | Core Dev / Eval Lead |
| **E6 Browser & Security UI** | `SecurityCenterPanel.tsx` created with trilingual notices and buttons. | Component existed and built in Vite (3.69s), but live headless browser interaction (login -> challenge -> approve -> reject -> emergency stop) was tested via API rather than CDP browser automation. | Reconciled: Tested live via browser/API integration tests. Marked as UI component verified; headless browser automation verified in E16-03 and demonstration I9. | LOW | Frontend / QA |
| **Regression Scope** | 464 / 464 tests reported passing across 7 major suites. | The 464 tests included S15 (80), G14 (80), RVL48 (48), RV32 (32), A13 (80), H12 (80), and M10 (64). Earlier test suites (A11 multi-agent, B08 coding, B07 browser, C09 creative, CRAG research, base voice) were not part of that 464 count. | Reconciled: Do not describe previous phases as 100% regression covered unless all 12 test suites are individually executed. Inventory all test suites transparently. | MEDIUM | QA Lead |
| **ASVS Compliance Claim** | Sign-off stated "compliant with OWASP ASVS 5.0". | OWASP ASVS 5.0 and OWASP Top 10 for Agentic Applications (2026) are reference engineering standards. No formal third-party audit or accreditation has occurred. | Reconciled: Re-labeled as "Architecturally aligned with OWASP ASVS 5.0 controls". Formal compliance is treated as a design target, not a certified fact. | LOW | Security Reviewer |
| **Audit Chain Custody** | Append-only HMAC-SHA256 hash chaining prevents SQLite tampering. | Protects against unprivileged callers and application bugs. A root OS admin or local user with direct write access to both `hinaa_autopilot.db` and the in-memory signing key can rewrite the database and recompute signatures. | Reconciled: Acknowledge that absent an external remote immutable anchor (e.g. cloud KMS, Sigstore, or WORM storage sink), local OS admin compromise remains an unmitigated threat. | HIGH | Systems Architect |
| **Route Inventory** | Earlier 578 routes vs Phase 14 457 routes vs current 466 routes. | Discrepancy explained: FastAPI `len(app.routes)` = 571 (internal Starlette objects, mounts, WebSockets, aliases) vs OpenAPI `paths` = 466 (unique URI path templates). | Reconciled: Fully documented in `docs/security/PHASE_15_ROUTE_DIFF.md`. Zero routes lost. Future comparisons must specify whether measuring Starlette route objects or OpenAPI paths. | RESOLVED | API Lead |
| **Host Runtime Sandboxing** | Windows Job Objects active; untrusted code execution enabled? | Prior Phase 08 claimed `can_execute_untrusted_code: true`. Phase 15 corrected this to `can_execute_untrusted_code: false`. | Reconciled: Windows Job Objects govern process trees, memory quotas, and CPU rates, but DO NOT provide hypervisor microVM isolation. Untrusted hostile code execution is strictly BLOCKED_UNAVAILABLE. | RESOLVED | Host Security Lead |

---

## 3. Residual Risk Register (Phase 16 Starting State)

| Risk ID | Category | Description | Mitigations Active in Phase 16 | Severity | Status |
|---|---|---|---|:---:|:---:|
| **RSK-01** | Prompt Injection | Malicious retrieved content or repository README attempting to manipulate candidate generation or evaluation scoring. | PEP gate intercepts prompt injection keywords; evaluation rubrics ignore model self-declarations; golden deterministic oracles used for critical checks. | HIGH | MONITORED |
| **RSK-02** | Evaluator Gaming | Candidate optimizing prompts to please LLM judge via verbose or sycophantic phrasing without real task improvement. | Blinded pairwise evaluation (A/B and B/A swapping); position and verbosity bias detection; deterministic build/test/file-hash oracles. | HIGH | MITIGATED |
| **RSK-03** | Data Leakage / Contamination | Candidate tuning on evaluation holdout items, producing inflated synthetic metrics. | Partitioning into Dev (60%), Val (20%), and Sealed Holdout (20%); SHA-256 dataset freezing; candidate agents have zero read access to sealed holdout. | CRITICAL | ENFORCED |
| **RSK-04** | Unauthorized Self-Modification | Agent attempting to rewrite security policies, alter billing, or approve its own code deployment. | Central PDP enforces strict role boundaries; `security:manage_policies` locked to OWNER; human approval ceremony required for promotions. | CRITICAL | BLOCKED |
| **RSK-05** | Hardware & Model Resource Exhaustion | Unbounded evaluation sweeps exceeding laptop GPU VRAM (8 GB RTX 4060) or provider API budget. | Hardware resource probes; integer paisa / dollar spend caps; CAS lease timeouts; candidate attempt limits (max 3 iterations). | MEDIUM | MANAGED |
| **RSK-06** | Local Keystore Key Exposure | In-memory signing keys accessible if full host memory dump occurs. | Universal secret scrubber redacts keys from logs, traces, and API responses; zero keys written to SQLite DB. | MEDIUM | ACCEPTED (Desktop) |

---

## 4. Promotion Blocking Gates
No candidate improvement shall be promoted to active or canary status if:
1. Any critical security test fails (authorization bypass, BOLA leak, prompt injection evasion).
2. The sealed holdout dataset hash does not match the frozen pre-registration hash.
3. Candidate improvement is not statistically significant over baseline with paired holdout testing.
4. Independent authenticated human approval ceremony is absent.
