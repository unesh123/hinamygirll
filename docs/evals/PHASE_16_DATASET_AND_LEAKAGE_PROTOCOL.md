# HINAA OS — Phase 16 Dataset & Leakage Protocol

**Document ID:** `HINAA-EVAL-LEAKAGE-V1`  
**Dataset ID:** `hinaa-canonical-eval-v1`  
**Dataset SHA-256 Hash:** `77f65fcf607e84d4ad1d07e65111548684e30f05acafa7292a916ae58341805e`  
**License Metadata:** `consented:true,custody:hinaa_os_sealed`  
**Canonical Freeze Timestamp:** `1762387200.0` (2025-11-06T00:00:00Z)  

---

## 1. Dataset Composition & Domain Stratification

The HINAA OS canonical evaluation dataset contains exactly **240 curated, consented benchmark cases** spanning all eight operational domains. To prevent overfitting, prompt hacking, and distribution collapse, the dataset is stratified into three immutable partitions:

- **DEV_POOL (60% / 144 items)**: Accessible to engineers and autonomous agents for failure diagnosis, prompt experimentation, and iterative proposal tuning.
- **VAL_POOL (20% / 48 items)**: Accessible for candidate validation, hyperparameter tuning, and matched A/B comparison prior to promotion.
- **SEALED_HOLDOUT (20% / 48 items)**: Strictly isolated and cryptographic sealed. Accessible solely to authorized release verifiers during the final promotion ceremony.

### Domain Stratification Matrix

| Domain Code | Domain Name | Total Cases | DEV_POOL (60%) | VAL_POOL (20%) | SEALED_HOLDOUT (20%) | Primary Scorer Type |
|---|---|---|---|---|---|---|
| `RSN` | **Reasoning** | 30 | 18 | 6 | 6 | `DETERMINISTIC_ARTIFACT` |
| `RSR` | **Research** | 30 | 18 | 6 | 6 | `CITATION_GROUNDEDNESS` |
| `COD` | **Coding** | 30 | 18 | 6 | 6 | `DETERMINISTIC_ARTIFACT` |
| `BIL` | **Bilingual** (En/Ne) | 30 | 18 | 6 | 6 | `BLINDED_PAIRWISE_JUDGE` |
| `VOI` | **Reflective Voice** | 30 | 18 | 6 | 6 | `REFLECTIVE_SPEECH_METRICS` |
| `MEM` | **Temporal Memory** | 30 | 18 | 6 | 6 | `DETERMINISTIC_ARTIFACT` |
| `TLG` | **Tools & Agents** | 30 | 18 | 6 | 6 | `DETERMINISTIC_ARTIFACT` |
| `COM` | **Multimodal Commerce** | 30 | 18 | 6 | 6 | `BLINDED_PAIRWISE_JUDGE` |
| **TOTAL** | **All 8 Domains** | **240** | **144** | **48** | **48** | **Balanced Oracles** |

---

## 2. Cryptographic Manifest Integrity

Every evaluation case $C_i$ is serialized into canonical sorted JSON without ephemeral execution markers. The overall dataset manifest hash $H_{\text{dataset}}$ is computed over the lexicographically sorted case array:

$$H_{\text{dataset}} = \text{SHA-256}\left(\bigoplus_{i=1}^{240} \text{CanonicalJSON}(C_i)\right)$$

Any modification—such as adding a trailing space, altering an expected assertion, or tampering with a tag—immediately changes $H_{\text{dataset}}$. The `DatasetManager` verifies this hash at runtime during initialization. If a tamper attempt is detected, initialization aborts with a validation error.

---

## 3. Strict Holdout Isolation Protocol

### Access Control Matrix

| System Subject / Role | Read DEV_POOL | Read VAL_POOL | Read SEALED_HOLDOUT | Run Matched Eval | Promote Candidate |
|---|---|---|---|---|---|
| **Autonomous Agent** | ALLOW | ALLOW | **DENY (403)** | ALLOW (on Val) | DENY |
| **Proposal Engine** | ALLOW | ALLOW | **DENY (403)** | ALLOW (on Val) | DENY |
| **Developer / Engineer** | ALLOW | ALLOW | **DENY (403)** | ALLOW (on Val) | DENY |
| **Eval Runner (Automated)** | ALLOW | ALLOW | ALLOW (Execution only) | ALLOW | DENY |
| **Release Verifier** | ALLOW | ALLOW | ALLOW (Auditing) | ALLOW | ALLOW (with Token) |
| **Security Auditor** | ALLOW | ALLOW | ALLOW (Read-only) | ALLOW | VETO ONLY |

### Implementation Enforcement
Holdout isolation is enforced at the data manager layer (`apps/api/hinaa_api/evals/dataset.py`) and guarded by zero-trust PDP:
```python
def get_case(self, case_id: str, caller_role: str = "agent") -> EvalCase:
    case = self._case_index.get(case_id)
    if not case:
        raise KeyError(f"Eval case not found: {case_id}")
    if case.partition == DatasetPartition.SEALED_HOLDOUT and caller_role not in self.ALLOWED_HOLDOUT_ROLES:
        raise PermissionError(
            f"Access Denied: Role '{caller_role}' is not authorized to read SEALED_HOLDOUT case {case_id}."
        )
    return case
```

Any attempt by `agent`, `proposal_engine`, or unauthorized callers to list or inspect holdout items raises `PermissionError`, which translates to HTTP 403 Forbidden in the API.

---

## 4. Contamination & Paraphrase Leakage Detection

To prevent synthetic prompt generation or fine-tuning from surreptitiously memorizing holdout items, the harness provides an active contamination detector (`check_contamination`):

### Detection Mechanics
1. **8-Gram Sliding Window Search**:
   Given candidate text $T$, the detector extracts all consecutive 8-token sequences:
   $$N_8(T) = \{(t_k, t_{k+1}, \dots, t_{k+7}) \mid 1 \le k \le |T| - 7\}$$
   If any $n \in N_8(T)$ matches an 8-gram from any sealed holdout prompt or ground truth, the text is flagged as an exact contamination leak.

2. **Jaccard Token Overlap Filtering**:
   For paraphrase detection, the detector computes token set Jaccard similarity:
   $$J(T_A, T_B) = \frac{|T_A \cap T_B|}{|T_A \cup T_B|}$$
   If $J(T, P_{\text{holdout}}) \ge 0.65$, the candidate is flagged for manual review and blocked from automated canary rollout.

### Empirical Leakage Test Results

| Probe Description | Probe Content Summary | Detected? | Matched Case | Max Jaccard | Result |
|---|---|---|---|---|---|
| **Adversarial Leak Probe** | "In a synchronous network with f Byzantine faulty nodes..." | **YES** | `CASE-RSN-027` | 0.94 | **BLOCKED (Contaminated)** |
| **Paraphrase Probe** | "What is the minimum nodes N for Byzantine consensus..." | **YES** | `CASE-RSN-027` | 0.72 | **BLOCKED (Contaminated)** |
| **Benign Novel Task** | "Deploying an optimized FastAPI microservice in Pokhara..." | **NO** | `None` | 0.08 | **PASSED (Clean)** |
| **Benign Nepali Greeting** | "नमस्ते हिना! आजको मौसम कस्तो छ?" | **NO** | `None` | 0.04 | **PASSED (Clean)** |

---

## 5. Dataset Evolution & Quarantine Rules

1. **Immutable Freeze**: The dataset version `1.0.0` is frozen. No test case may be modified, replaced, or deleted in place.
2. **Expansion Protocol**: Introducing new cases requires incrementing the minor version (`1.1.0`), maintaining the strict 60/20/20 balance across all 8 domains (multiples of 30 items per domain), and re-computing the SHA-256 manifest hash.
3. **Quarantine Memory Ingestion**: Failing candidate patterns are deposited in the Phase 10 temporal memory quarantine ledger. Subsequent proposal runs consult this quarantine to prevent repeating previously discarded hypotheses.
