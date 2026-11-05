# HINAA OS — Phase 15 Policy & Authorization Architecture
**Document Version:** 1.0  
**Date:** 2026-11-06  
**Auditor:** Anti-Gravity Principal Engineering Verification Agent  
**Standard:** OWASP ASVS 5.0 (Server-Side Access Control)  

---

## 1. Unified Authorization Model: RBAC + ABAC + Capability Intersection

HINAA OS implements a centralized **Policy Decision Point (PDP)** (`hinaa_api.security.pdp.PolicyDecisionPoint`) with lightweight **Policy Enforcement Points (PEP)** (`hinaa_api.security.pep.PolicyEnforcementGate`).

```
           +--------------------------------------------+
           |           Incoming Request / Tool          |
           +---------------------+----------------------+
                                 |
                                 v
           +--------------------------------------------+
           |       Verified Identity Context            |
           | - Verified Subject ID & Tenant ID          |
           | - Role: OWNER, OPERATOR, MEMBER, VIEWER    |
           | - Delegation Ancestry: [supervisor, coder] |
           +---------------------+----------------------+
                                 |
                                 v
           +--------------------------------------------+
           |       Central Policy Decision Point        |
           | 1. Emergency Stop Check (Global / Tenant)  |
           | 2. Dynamic Revocation Check (User/Session) |
           | 3. Multi-Tenant BOLA Isolation Check       |
           | 4. Tier C Human Approval Ceremony Check    |
           | 5. RBAC Permission & Scopes Check          |
           | 6. Delegation Capability Intersection      |
           | 7. Default DENY for Unknown Actions        |
           +---------------------+----------------------+
                                 |
                     +-----------+-----------+
                     |                       |
                     v                       v
               [ALLOW (200)]           [DENY (403)]
```

---

## 2. Role-to-Permission Matrix

| Permission | `OWNER` | `TENANT_ADMIN` | `OPERATOR` | `MEMBER` | `VIEWER` | `SERVICE_WORKER` |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| `read` (general telemetry, posture) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `write` (mutations within scope) | ✓ | ✓ | ✓ | ✓ | ✗ | ✓ (scoped) |
| `tool:execute` (general agent tools) | ✓ | ✓ | ✓ | ✗ | ✗ | ✓ (scoped) |
| `code:execute` (workspace scripts) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `browser:navigate` (browser actions) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `memory:read` (retrieve private memories) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ |
| `memory:write` (store learned facts) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `memory:export` (bulk export memories) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `memory:delete` (purge memory records) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `audit:read` (inspect audit trail) | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `audit:export` (export raw audit log) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `approval:tier_c` (approve high-impact) | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ |
| `security:emergency_stop` | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| `security:manage_policies` | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |
| `commerce:charge` (Nepal payment sandbox)| ✓ (Ceremony) | ✓ (Ceremony)| ✗ | ✗ | ✗ | ✗ |
| `secrets:manage` (rotate signing keys) | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ |

---

## 3. Delegation Capability Intersection Formalism

When a parent agent (e.g., `supervisor`) delegates a sub-task to a child agent (e.g., `coder`), the child's effective capability set $C_{\text{effective}}$ is governed by:

$$C_{\text{effective}} = P(\text{parent\_role}) \cap P(\text{child\_role}) \cap G_{\text{task}} \setminus R_{\text{revoked}}$$

Where:
- $P(\text{role})$ is the maximum capability set assigned to that role.
- $G_{\text{task}}$ is the task-scoped grant defined in the delegation request.
- $R_{\text{revoked}}$ is the active set of dynamic revocations in `revocation_ledger`.

### Key Properties:
1. **Zero Escalation:** A child agent can NEVER possess permissions not held by its parent, even if the child's configured role profile allows it.
2. **Ancestry Revocation:** If any node in the `delegation_chain` ($A_1 \to A_2 \to \dots \to A_k$) is marked as revoked, $C_{\text{effective}} = \emptyset$.
3. **No Prompt Self-Promotion:** An agent generating output text such as `"role: owner"` is ignored by the PDP; role claims are derived exclusively from server-signed identity contexts.

---

## 4. Cryptographic Human Approval Ceremonies (Tier C)

Certain actions are classified as **Tier C High-Impact Operations**:
1. `commerce:charge`: Financial sandbox transactions (eSewa / Khalti sandbox).
2. `deploy:production`: Releasing code or pushing commits to production branches.
3. `terminal:rm_rf_root`: Destructive filesystem operations.
4. `security:manage_policies`: Modifying authorization rules or roles.

### Execution Protocol:
1. **Challenge Generation:** When a Tier C action is proposed without a token, PDP creates an `ApprovalCeremonyToken`:
   $$\text{digest} = \text{SHA256}(\text{canonical\_json}(\text{parameters}))$$
   $$\text{signature} = \text{HMAC-SHA256}_{K}(\text{token\_id} \mathbin{\Vert} \text{tenant\_id} \mathbin{\Vert} \text{action} \mathbin{\Vert} \text{digest} \mathbin{\Vert} \text{nonce} \mathbin{\Vert} \text{amount} \mathbin{\Vert} \text{exp})$$
2. **Human Inspection:** The token and parameters are presented in the **Security Control Center** (`apps/web/src/components/security/SecurityCenterPanel.tsx`) with a trilingual risk notice (English, Nepali, Romanized).
3. **Sign-off:** The human `OWNER` clicks "Authorize Ceremony", which marks the token `status = 'APPROVED'` and binds the approver ID.
4. **Execution & Atomic Consumption:** The action is invoked with header `X-Approval-Token: <token_id>`. The ceremony manager recomputes the parameter digest (detecting tampering), validates the signature, and atomically updates `status = 'CONSUMED'`. Any replay attempt immediately fails.
