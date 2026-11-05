# HINAA OS — Phase 13 Recovery & Operations Runbook
## Operator Guide for Persistent Autopilot & Autonomous Tasks

---

### 1. Architecture & Persistence Baseline

- **Database Path:** `apps/api/data/hinaa_autopilot.db`
- **Journal Mode:** `WAL` (Write-Ahead Logging)
- **Synchronous Flag:** `NORMAL`
- **Default Port:** `8000`
- **Health Endpoint:** `GET /api/autopilot/health`

---

### 2. Operational Procedures & Runbooks

#### Runbook 1: Unscheduled Worker Crash & Orphan Lease Recovery

**Symptom:** Worker process dies abruptly while jobs are in `RUNNING` status.  
**Mechanism:** Every lease has an `expires_at_utc` timestamp (default: 30 seconds). The `AutopilotScheduler` loop automatically invokes `store.recover_orphaned_jobs(now)` on each evaluation cycle.  
**Manual Recovery Command:**
```bash
curl -X POST http://127.0.0.1:8000/api/autopilot/jobs/recover-orphans \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "default"}'
```
**Expected Outcome:**
- All expired jobs are reverted to `READY`.
- Fencing tokens are incremented.
- If the crashed worker restarts and tries to commit its previous execution, it is rejected with `StaleFencingTokenError` (HTTP 409).

---

#### Runbook 2: Global Emergency Stop & Kill Switch

**Symptom:** Rogue loop, anomalous token consumption, or unintended autonomous action detected.  
**Action:** Activate Emergency Stop immediately.  
**Endpoint Call:**
```bash
curl -X POST http://127.0.0.1:8000/api/autopilot/emergency-stop \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "default", "reason": "Operator initiated emergency shutdown"}'
```
**Effects:**
1. All active schedules for the tenant are immediately paused (`is_paused = True`).
2. All in-flight `READY` and `RUNNING` jobs are transitioned to `CANCELLED`.
3. An audit notification with `CRITICAL` severity is written to the persistent notifications table.

---

#### Runbook 3: Tier C High-Impact Human Authorization

**Symptom:** Job status is `WAITING_APPROVAL` with `Action requires signed Tier C human authorization`.  
**Eligible Actions:**
- `simulate_nepali_payment`
- `execute_payment`
- `publish_post`
- `delete_database`
- `deploy_production`

**Resolution:**
1. Inspect the job payload and ancestry HMAC signature.
2. Operator submits cryptographic approval:
```bash
curl -X POST http://127.0.0.1:8000/api/autopilot/jobs/{job_id}/approve \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "default",
    "approver_id": "admin_user",
    "approved": true,
    "signature": "<HMAC_SHA256_OVER_ANCESTRY>"
  }'
```
**Outcome:** Job transitions from `WAITING_APPROVAL` to `READY` and is scheduled for immediate execution by the worker pool.

---

#### Runbook 4: Zero Swarm Theater Audit & Truthful Status Verification

**Rule:** Generative neural video (T2V / I2V) must NEVER be reported as available without physical local model weights.  
**Inspection Command:**
```bash
curl -s http://127.0.0.1:8000/api/autopilot/health | jq .
```
**Expected Verification Response:**
```json
{
  "status": "HEALTHY",
  "services": {
    "creative_studio_neural_video": {
      "status": "BLOCKED_UNAVAILABLE",
      "reason": "Generative video diffusion weights not present locally"
    }
  }
}
```
