# HINAA OS — Phase 14 Security & Recovery Runbook
**Version:** 1.0.0  
**Date:** 2026-11-05  
**Checkpoint:** `phase-14-checkpoint`  

---

## 1. Threat Modeling & Defense Vectors

| Threat Vector | Attack Mechanism | Phase 14 Mitigation & Enforcement | Test Scenario |
|---|---|---|---|
| **Goal Hijacking via Injection** | Adversarial text embedded in web pages or documents instructing the agent to overwrite its original goal | Input sanitization; strict immutable goal scoping. Injected text in descriptions cannot expand `authorized_scope`. | `G14-52` |
| **Privilege Escalation** | Delegated child tasks or replanned milestones attempting to grant themselves administrative or deploy tools | Subgoal mathematical intersection. A child node cannot inherit permissions outside the parent's explicit scope. | `G14-51` |
| **Tier C Parameter Tampering** | Attacker intercepts an approved HMAC token and alters the payment amount or recipient address | Cryptographic parameter binding. HMAC-SHA256 signature includes `action:resource:amount:recipient:nonce:expires`. Any byte modification invalidates the digest. | `G14-50` |
| **Approval Token Replay** | Re-submitting a captured approval token to execute duplicate financial transactions | Atomic CAS consumption. When an approval token is executed, `is_consumed` is updated to 1 within a SQLite transaction. Replay attempts are rejected. | `G14-58` |
| **Adversarial Memory Poisoning** | Malicious text attempting to inject persistent backdoor rules into agent memory | Regex & semantic injection scanner in `ReflectionManager`. Malicious reflections are dropped before reaching quarantine. | `G14-45` |
| **Cross-Tenant Data Leakage** | Tenant A attempting to read, modify, or execute goals belonging to Tenant B | Multi-tenant compound primary keys and database query scoping (`WHERE tenant_id = ?`). Cross-tenant requests return 404/403. | `G14-12`, `G14-53` |
| **Infinite Cost Loops** | Flaky task repeatedly retrying failing actions under disguised names | Semantic loop detector (Jaccard >= 0.80 check) and hard replan cap (`max_replans = 3`). | `G14-35`, `G14-36` |

---

## 2. Crash Recovery & Disaster Resilience

### 2.1 SQLite WAL Atomic Recovery
The authoritative state engine runs in SQLite WAL mode (`PRAGMA journal_mode=WAL`).
- All milestone state transitions, evidence receipts, and plan versions are committed atomically.
- In-flight worker leases use monotonically increasing fencing tokens to reject late mutations from crashed processes.

### 2.2 Cold Boot Re-hydration Protocol
Upon system startup:
1. `AutopilotStore` and `GoalStore` connect to `hinaa_autopilot.db`.
2. Active goals with status `RUNNING` or `WAITING_APPROVAL` are loaded without data mutation.
3. Completed milestones retain their `VERIFIED` receipts; unexecuted milestones remain in `PENDING` state.
4. Active approvals remain in `WAITING_APPROVAL` without automatic granting.

---

## 3. Operational Runbook & Emergency Rollback

### 3.1 Invoking Emergency Stop
If an anomaly or security alert occurs, an operator can invoke an immediate tenant-wide emergency stop via the REST API or UI:
```bash
curl -X POST http://127.0.0.1:8000/api/goals/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "default_tenant", "reason": "Operator manual abort"}'
```
This atomically cancels all `RUNNING`, `ACCEPTED`, `PAUSED`, and `WAITING_APPROVAL` goals within the tenant.

### 3.2 Rollback Procedure
If Phase 14 needs to be rolled back to Phase 13 / Reflective Voice baseline:
```bash
# 1. Stop API server
# 2. Reset git HEAD to prior checkpoint
git checkout reflective-voice-realworld-checkpoint

# 3. Clean temporary caches
rm -rf apps/api/.pytest_cache apps/web/dist

# 4. Restart services
pnpm --filter web build
cd apps/api && python -m uvicorn hinaa_api.main:app --port 8000
```
Prior database records in `hinaa_autopilot.db` remain fully backward-compatible as Phase 14 tables operate without mutating core Phase 13 schemas.
