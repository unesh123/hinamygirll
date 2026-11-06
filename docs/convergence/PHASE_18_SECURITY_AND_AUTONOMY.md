# HINAA OS — Phase 18 Security, Permissions & Autonomy Governance
**Document Version:** 1.0.0  
**Compliance Standards:** OWASP Agentic Applications 2026, ASVS 5.0, NIST SP 800-63B  
**Status:** AUDITED & VERIFIED

---

## 1. Central Policy Decision Point (PDP) Integration

All missions and agent tool invocations pass through the Central Policy Decision Point (`hinaa_api.security.pdp`). The PDP evaluates every requested action against:
1. **Authenticated Subject**: User, Subagent, or System Daemon.
2. **Action Tier**:
   - **Tier A (Read-Only / Low-Impact)**: File reads, DOM inspection, memory lookups. Executed autonomously without user prompt.
   - **Tier B (Medium-Impact)**: Code generation, file edits, git branch switching. Logged and bounded by tenant autonomy contract.
   - **Tier C (High-Impact / Critical)**: Monetary transactions, production deployments, system deletions, process execution. **Strictly requires explicit human approval ceremony**.
3. **Resource & Domain Whitelists**: Enforces domain sandboxing (e.g. only permitted domains and localhost staging for browser automation; blocking `file://` scheme escapes).

---

## 2. Parameter-Bound Approval Ceremonies

Human approvals in HINAA OS are strictly parameter-bound:
- An approval for 500 NPR (`50,000 paisa`) **cannot** be reused or escalated to spend 501 NPR.
- Approvals carry cryptographic HMAC-SHA256 tokens tied to the specific `mission_id`, `recipient`, and `amount_paisa`.
- Tokens expire after 300 seconds. Expired tokens are rejected by the PDP.
- If an operator rejects an approval card, dependent tasks abort immediately with state `CANCELLED` or `PARTIAL`.

---

## 3. Tamper-Evident Merkle Audit Logging

1. **Immutable Log**: All state transitions, PDP decisions, and tool executions are written to an append-only SQLite WAL table (`platform_mission_artifacts` and `platform_missions`).
2. **Cryptographic Chaining**: Audit records are organized into a Merkle tree structure. The root hash is recorded in `RELEASE_SCORECARD.json` and session export bundles.
3. **Sanitization & Redaction**:
   - Phone numbers and email addresses are masked prior to telemetry serialization (`[REDACTED_PHONE]`, `[REDACTED_EMAIL]`).
   - Secret keys (`ELEVENLABS_API_KEY`, tokens) are masked with prefix/suffix preservation (`sk_test_***cdef`).
   - Zero outbound telemetry is dispatched without explicit user opt-in.

---

## 4. Tenant Autonomy Contracts & Emergency Stop

Each tenant maintains a persistent `AutonomyContract`:
- **Spending Ceiling**: Default 100 NPR (`10,000 paisa`) per day.
- **Active Hours**: Configurable operational windows (e.g., 08:00 to 22:00).
- **Emergency Stop Flag**: When `emergency_stop_active == True`, all in-flight missions immediately transition to `CANCELLED`, worker leases are revoked, and new mission creation is rejected.
