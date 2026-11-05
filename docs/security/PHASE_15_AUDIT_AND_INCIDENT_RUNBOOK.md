# HINAA OS — Phase 15 Audit & Incident Response Runbook
**Document Version:** 1.0  
**Date:** 2026-11-06  
**Auditor:** Anti-Gravity Principal Engineering Verification Agent  

---

## 1. Append-Only Tamper-Evident Audit Trail

Every policy decision (both `ALLOW` and `DENY`), human approval ceremony, and privilege change is appended to the `audit_events` SQLite table in WAL mode.

### Hash-Chaining Protocol:
1. **Genesis Block:** Record #1 has `prev_hash = "0000000000000000000000000000000000000000000000000000000000000000"` (64 zeros).
2. **Subsequent Records:** For record $i \ge 2$, `prev_hash` equals the exact `event_hash` of record $i - 1$.
3. **Canonical Payload:**
   ```json
   {
     "action": "<scrubbed_action>",
     "decision": "<allow|deny|require_approval>",
     "event_id": "<evt_uuid>",
     "prev_hash": "<prev_hash_hex>",
     "reason_code": "<reason_code>",
     "resource": "<scrubbed_resource>",
     "sequence_id": <monotonic_int>,
     "subject_id": "<user_or_agent>",
     "tenant_id": "<tenant>",
     "timestamp": <round(epoch, 4)>
   }
   ```
4. **Digest & Signature:**
   $$\text{event\_hash} = \text{SHA256}(\text{canonical\_bytes})$$
   $$\text{signature} = \text{HMAC-SHA256}_{K}(\text{event\_hash})$$

---

## 2. On-Demand Integrity Verification Procedure

The audit trail can be cryptographically verified at any time via:
`POST /api/security/audit/verify` (requires `OWNER` or `TENANT_ADMIN` role).

### Verification Steps Executed by `verify_chain()`:
1. **Monotonicity:** Scans all records from sequence $1$ to $N$. Asserts that sequence IDs are contiguous with zero skipped or duplicate integers.
2. **Chain Continuity:** Asserts that each record's `prev_hash` matches the preceding record's `event_hash`.
3. **Digest Recomputation:** Recomputes the canonical SHA256 digest of the record's payload and verifies equality with `event_hash`.
4. **Signature Validation:** Recalculates HMAC signature using current audit key and confirms authenticity.

### Tamper Detection Output:
If a row is modified in SQLite directly:
```json
{
  "is_valid": false,
  "total_records": 10,
  "last_sequence_id": 10,
  "errors": [
    "Content integrity failure at sequence 3: stored event_hash ... does not match recomputed ...",
    "Hash link broken at sequence 4: record prev_hash ... does not match expected ..."
  ]
}
```

---

## 3. Incident Response Playbook

### Scenario A: Suspected Subagent Compromise / Rogue Tool Invocations
1. **Immediate Emergency Stop:**
   - Click "Trigger Emergency Stop" in the Security Control Center, or execute:
     ```bash
     curl -X POST http://127.0.0.1:8000/api/security/emergency-stop \
          -H "Authorization: Bearer <owner_token>" \
          -d '{"tenant_id": "*", "reason": "Suspected agent compromise"}'
     ```
   - **Result:** PDP immediately returns `DENY` with reason `EMERGENCY_STOP_ACTIVE` for all active agents and tool runners.
2. **Agent Revocation:**
   - Submit agent ID to `revocation_ledger`:
     ```bash
     curl -X POST http://127.0.0.1:8000/api/security/revocations \
          -H "Authorization: Bearer <owner_token>" \
          -d '{"target_type": "agent", "target_id": "agent_untrusted", "reason": "Containment"}'
     ```
3. **Lift Emergency Stop:**
   - Once isolated, the owner lifts the emergency stop via `POST /api/security/emergency-stop/lift`.

### Scenario B: Audit Chain Integrity Failure Flagged
1. Identify the sequence ID reported in `verify_chain()["errors"]`.
2. Inspect SQLite WAL log and backup journal for unauthorized writes.
3. Export verified chain snapshot prior to the tampered sequence ID.
4. Notify system administrator and rotate `audit_chain_key`.
