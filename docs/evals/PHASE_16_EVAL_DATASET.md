# HINAA OS — Phase 16 Canonical Evaluation Dataset Catalog

**Dataset ID:** `hinaa-canonical-eval-v1`  
**Total Items:** 240  
**Version:** 1.0.0  
**License Metadata:** `consented:true,custody:hinaa_os_sealed`  
**Dataset SHA-256 Hash:** `77f65fcf607e84d4ad1d07e65111548684e30f05acafa7292a916ae58341805e`  

---

## 1. Dataset Partition Summary

| Partition | Total Cases | Share (%) | Purpose | Access Permission |
|---|---|---|---|---|
| **DEV_POOL** | 144 | 60.0% | Diagnostic clustering, prompt engineering, agent exploration | Agents, Developers, Verifiers |
| **VAL_POOL** | 48 | 20.0% | Candidate tuning, hyperparameter search, matched A/B comparison | Agents (Eval mode), Developers, Verifiers |
| **SEALED_HOLDOUT** | 48 | 20.0% | Final promotion gate, anti-leakage audit | Release Verifiers & Auditors ONLY |
| **TOTAL** | **240** | **100.0%** | **Consented Multi-Domain Benchmark** | **Strictly Governed** |

---

## 2. Domain Distribution & Case Mapping

Every domain contains exactly 30 cases partitioned into 18 DEV (60%), 6 VAL (20%), and 6 SEALED_HOLDOUT (20%):

| Domain Name | Prefix | Dev Cases | Val Cases | Holdout Cases | Scorer Assigned | Focus Scope |
|---|---|---|---|---|---|---|
| **Reasoning** | `CASE-RSN` | 001–018 | 019–024 | 025–030 | `DETERMINISTIC_ARTIFACT` | Multi-step logic, distributed consensus, math |
| **Research** | `CASE-RSR` | 001–018 | 019–024 | 025–030 | `CITATION_GROUNDEDNESS` | Fact retrieval, context citations, anti-hallucination |
| **Coding** | `CASE-COD` | 001–018 | 019–024 | 025–030 | `DETERMINISTIC_ARTIFACT` | Python algorithms, regex, error handling |
| **Bilingual** | `CASE-BIL` | 001–018 | 019–024 | 025–030 | `BLINDED_PAIRWISE_JUDGE` | Nepali honorifics, Dev/Rom translation, idioms |
| **Reflective Voice** | `CASE-VOI` | 001–018 | 019–024 | 025–030 | `REFLECTIVE_SPEECH_METRICS` | Spoken brevity ($\le 45$ words), fact recall, SSML |
| **Temporal Memory** | `CASE-MEM` | 001–018 | 019–024 | 025–030 | `DETERMINISTIC_ARTIFACT` | Entity recall, contradiction handling, session state |
| **Tools & Agents** | `CASE-TLG` | 001–018 | 019–024 | 025–030 | `DETERMINISTIC_ARTIFACT` | Multi-agent leases, DAG ordering, tool receipts |
| **Commerce** | `CASE-COM` | 001–018 | 019–024 | 025–030 | `BLINDED_PAIRWISE_JUDGE` | Nepal VAT (13%), integer paisa calculations |

---

## 3. Representative Case Catalog (Samples Across Domains)

### 3.1 Reasoning (`CASE-RSN`)
- **`CASE-RSN-001` (DEV_POOL)**:
  - *Prompt*: "Given three servers in a Raft cluster where leader node 1 crashes, describe which node becomes leader if node 2 has term 4 and node 3 has term 3."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `node 2|server 2|term 4`)
- **`CASE-RSN-027` (SEALED_HOLDOUT)**:
  - *Prompt*: "In a synchronous network with $f$ Byzantine faulty nodes, what is the minimum total number of nodes $N$ required for consensus?"
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Ground Truth: `3f + 1`)

### 3.2 Research (`CASE-RSR`)
- **`CASE-RSR-001` (DEV_POOL)**:
  - *Prompt*: "Based on context [1], summarize the population of Pokhara metropolitan city."
  - *Scorer*: `CITATION_GROUNDEDNESS` (Requires `[1]`, forbids fabricated citations like `[999]`)
- **`CASE-RSR-025` (SEALED_HOLDOUT)**:
  - *Prompt*: "According to source [Source-Hydro], what is the installed capacity of the Upper Tamakoshi Hydroelectric Project in Nepal?"
  - *Scorer*: `CITATION_GROUNDEDNESS` (Ground Truth: `456 MW`)

### 3.3 Coding (`CASE-COD`)
- **`CASE-COD-001` (DEV_POOL)**:
  - *Prompt*: "Write a Python function `def is_palindrome(s: str) -> bool:` that handles alphanumeric strings case-insensitively."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Regex: `def is_palindrome\(`)
- **`CASE-COD-028` (SEALED_HOLDOUT)**:
  - *Prompt*: "Implement an exponential backoff retry decorator with jitter in Python with type annotations."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Regex: `def retry\(|backoff`)

### 3.4 Bilingual (`CASE-BIL`)
- **`CASE-BIL-001` (DEV_POOL)**:
  - *Prompt*: "Translate 'Could you please confirm if the payment was processed?' into formal Nepali using respectful honorifics."
  - *Scorer*: `BLINDED_PAIRWISE_JUDGE` (Expected Devanagari: कृपया भुक्तानी सम्पन्न भयो कि भएन पुष्टि गरिदिनुहुन्छ कि?)
- **`CASE-BIL-026` (SEALED_HOLDOUT)**:
  - *Prompt*: "Explain the difference between 'तपाईं' and 'हजुर' in formal customer service communication in Nepal."
  - *Scorer*: `BLINDED_PAIRWISE_JUDGE`

### 3.5 Reflective Voice (`CASE-VOI`)
- **`CASE-VOI-001` (DEV_POOL)**:
  - *Prompt*: "Provide a spoken explanation of the database migration status in under 45 words using SSML."
  - *Scorer*: `REFLECTIVE_SPEECH_METRICS` (Max Words: 45, Valid `<speak>` wrapper)
- **`CASE-VOI-029` (SEALED_HOLDOUT)**:
  - *Prompt*: "Summarize the 10-page quarterly financial report for spoken audio briefing in 30 words."
  - *Scorer*: `REFLECTIVE_SPEECH_METRICS` (Max Words: 30)

### 3.6 Temporal Memory (`CASE-MEM`)
- **`CASE-MEM-001` (DEV_POOL)**:
  - *Prompt*: "User changed their shipping address from Lalitpur to Kathmandu yesterday. Where should order #491 be sent?"
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `Kathmandu`)
- **`CASE-MEM-025` (SEALED_HOLDOUT)**:
  - *Prompt*: "Recall the supervisor authorization token issued for task DAG-8812."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `AUTH-TIER-C`)

### 3.7 Tools & Agents (`CASE-TLG`)
- **`CASE-TLG-001` (DEV_POOL)**:
  - *Prompt*: "Execute multi-agent lease acquisition on task `eval-run-99` and return worker fencing token."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `fence_token: 1`)
- **`CASE-TLG-028` (SEALED_HOLDOUT)**:
  - *Prompt*: "Detect circular dependency in worker task DAG with nodes A->B->C->A and abort execution."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `circular dependency detected|cycle detected`)

### 3.8 Multimodal Commerce (`CASE-COM`)
- **`CASE-COM-001` (DEV_POOL)**:
  - *Prompt*: "Calculate the exact 13% Nepal VAT on an invoice subtotal of Rs 1,450.50 in integer paisa."
  - *Scorer*: `BLINDED_PAIRWISE_JUDGE` / `DETERMINISTIC_ARTIFACT` (Ground Truth: `18856 paisa` / `Rs 188.56`)
- **`CASE-COM-030` (SEALED_HOLDOUT)**:
  - *Prompt*: "Reconcile daily card batch of 48 transactions totaling Rs 248,912.40 with bank gateway settlement fee of 1.75%."
  - *Scorer*: `DETERMINISTIC_ARTIFACT` (Pattern: `435597 paisa|Rs 4355.97`)
