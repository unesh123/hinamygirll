# HINAA OS — Phase 16 Experiment, Promotion & Rollback Policy

**Document ID:** `HINAA-POLICY-PROMOTION-V1`  
**Governing Standard:** OWASP Agentic Applications 2026, ASVS 5.0  
**Authority:** HINAA Release Verification & Governance Engine  

---

## 1. Experimentation Gates & Promotion Criteria

No autonomous agent modification may enter production routing without satisfying pre-registered empirical gates across both validation and sealed holdout splits:

### Gate 1: Statistical Significance & Non-Regression
- **Net Delta**: Candidate must demonstrate $\Delta_{\text{pass\_rate}} \ge 0.0$ on `VAL_POOL` and $\Delta_{\text{pass\_rate}} > 0.0$ on `SEALED_HOLDOUT`.
- **Significance Threshold**: The primary metric improvement must be statistically significant at $p < 0.05$ over a minimum of 20 evaluation cases.
- **Zero Critical Regressions**: Security compliance, PDP enforcement, and privacy containment must register **zero regressions** ($\Delta_{\text{security}} = 0$). Any security regression triggers an automatic veto (`REJECTED_SECURITY_VETO`).

### Gate 2: Authorization Hierarchy by Impact Tier

| Proposal Scope / Target | Blast Radius | Required Governance Tier | Approver Role | Token Requirement |
|---|---|---|---|---|
| **Spoken Brevity / Formatting** | Low ($\le 0.05$) | **Tier A (Automated)** | Eval Runner / System | Auto-generated system ticket |
| **RAG Chunking / Top-K** | Medium ($\le 0.10$) | **Tier B (Operator)** | Operator / Developer | Operator confirmation token |
| **Routing / Failover Rules** | High ($> 0.10$) | **Tier C (Supervisor)** | Engineering Lead | Signed Tier C authorization token |
| **Security Policies / Schemas** | Critical | **Tier C (Supervisor)** | Security Officer / Human | Signed Tier C authorization token |

Attempts to promote Tier C proposals without a valid cryptographic token (`approval_token_id`) are rejected with `REJECTED_GATE_FAILURE`.

---

## 2. Canary Deployment Stages & Telemetry Health Checks

Candidates that clear Gate 1 and Gate 2 enter phased canary rollout:

$$\text{Stage 1: 1\%} \xrightarrow{\text{Health Check}} \text{Stage 2: 5\%} \xrightarrow{\text{Health Check}} \text{Stage 3: 25\%} \xrightarrow{\text{Health Check}} \text{Stage 4: 100\% (Full Promotion)}$$

### Telemetry Health Check Requirements
Before advancing to the next traffic tier, the candidate must maintain clean telemetry over the observation window (minimum 100 live requests or 5 minutes):
1. **Error Rate**: $\text{ErrorRate} \le 1.0\%$ (Target), $< 2.0\%$ (Abort ceiling).
2. **Latency Degradation**: Candidate p95 latency must not exceed baseline p95 by $> 20\%$.
3. **Token / Cost Spikes**: Average cost per completed task must not increase by $> 25\%$ unless explicitly authorized.

---

## 3. Circuit Breaker Triggers & Automated Rollback SLA

If canary telemetry indicates instability, the automated circuit breaker fires immediately.

### Circuit Breaker Abort Conditions

| Anomaly Indicator | Threshold Trigger | Action Taken |
|---|---|---|
| **HTTP 5xx / Unhandled Exceptions** | $> 2.0\%$ of requests | **Instant Automated Rollback** |
| **Latency p95 Degradation** | $> 20.0\%$ over baseline | **Instant Automated Rollback** |
| **Security PDP Policy Fault** | $\ge 1$ violation | **Instant Automated Rollback + Tier C Lock** |
| **Memory Leak / VRAM OOM** | Threshold warning | **Pause Traffic + Drain** |

### Rollback Mechanics & SLA
1. **Target SLA**: Rollback must execute in **$< 500\text{ ms}$**. Empirical tests demonstrate execution in **$< 100\text{ ms}$**.
2. **Configuration State Restoration**: The candidate's `config_hash_before` is atomically restored to active memory, replacing `config_hash_after`.
3. **Traffic Invalidation**: Canary routing tables are cleared; 100% of traffic reverts to the verified baseline snapshot immediately.
4. **Audit Receipt**: The controller generates an immutable `RollbackReceipt` containing `rollback_id`, `candidate_id`, `trigger_reason`, `restored_config_hash`, and `restored_at`.

```python
receipt = self.promotion_ctrl.execute_rollback(
    candidate_id=candidate.candidate_id,
    reason=f"Canary error rate {error_rate:.1%} exceeded 2.0% safety threshold.",
    restored_by="canary_circuit_breaker",
)
```

---

## 4. Memory Quarantine Export Protocol

When a candidate fails evaluation or is rolled back from canary, the failure root cause must not be lost:
1. The `PromotionController` exports a structured lesson record (`lsn-<uuid>`) containing `candidate_id`, target layer, failure cluster, and root cause rationale.
2. The record is written to the **Phase 10 Temporal Memory Quarantine Ledger** with status `quarantine_status="evaluated_safe"`.
3. During subsequent proposal generation, `DiagnosticProposalEngine` checks active quarantine patterns:
   $$\text{If } \text{PatternMatch}(\text{Proposal}, \text{QuarantineLedger}) \implies \text{Block Duplicate Generation}$$
   This guarantees that HINAA OS never repeatedly attempts previously disproven optimizations.
