# HINAA OS — PHASE 05 SECURITY AUDIT AND THREAT MODEL
## AUTHORIZATION INTEGRITY, SANDBOX BOUNDARIES, AND DATA TRUST POLICIES

**Document ID:** `PHASE_05_SECURITY_REVIEW`  
**Phase:** 05 — Singularity Evolution  
**Date:** 2026-11-12  
**Classification:** Critical Security Audit  

---

## 1. CRITICAL AUTHORIZATION AUDIT: `approvalSource` AND EXECUTION PERMISSIONS

### 1.1 The Vulnerability of Client-Controlled Authorization Labels
In automated AI agent systems, a common critical failure mode is accepting client-asserted privilege flags (e.g. `{"approvalSource": "full-access", "confirmed": true}`). If the server accepts this string without server-side validation:
1. Any unauthorized caller or injected script could forge the string and execute arbitrary host commands.
2. Webhooks, browser extensions, or malicious URLs could bypass human review gates.
3. Prompt injection inside an uploaded document could instruct the agent to forge an internal request with `"full-access"`.

### 1.2 Verification of HINAA OS Policy Code
We performed an AST and execution audit of `apps/api/hinaa_api/tools/policy.py` and `security/pdp.py`:

```python
# apps/api/hinaa_api/tools/policy.py lines 126-142
# Tier 2, 3, 4 require explicit user authorization
is_user_approved = confirmed and approval_source == "user"
if not is_user_approved:
    tier_names = {
        ActionRiskTier.TIER_2_EXTERNAL: "Tier 2 (External Navigation / Downloads)",
        ActionRiskTier.TIER_3_PROCESS: "Tier 3 (Process Execution / OS Input)",
        ActionRiskTier.TIER_4_DESTRUCTIVE: "Tier 4 (Destructive / Privileged / External Send)",
    }
    tier_label = tier_names.get(tier, f"Tier {tier.value}")
    return Verdict(
        False,
        "EXPLICIT_USER_APPROVAL_REQUIRED",
        f"Action classified as {tier_label} requires explicit user approval. "
        "Standing consent or inferred intent is denied.",
    )
```

**Key Finding:**
- `is_user_approved` strictly requires `confirmed=True` AND `approval_source == "user"`.
- Passing `approval_source="standing-consent"`, `"none"`, or any arbitrary string (such as `"full-access"`) is **strictly rejected** for Tier 2, 3, and 4 actions.
- This invariant is verified by regression tests in `apps/api/tests/test_authorization_matrix.py`:
  - `test_tier3_denied_without_explicit_user_approval` (Passes).
  - `test_tier3_denied_with_standing_consent` (Passes).
  - `test_tier4_denied_without_user_approval` (Passes).

### 1.3 Local / Loopback Origin Boundary
- The presence of `Host: 127.0.0.1` or `Host: localhost` **must never be treated as proof of owner authorization**.
- A malicious page opened in the user's browser could execute `fetch('http://127.0.0.1:8000/api/v1/tools/execute', ...)` (Cross-Origin Request forgery / DNS rebinding).
- **Enforced Defense:**
  1. Strict CORS policy with explicit origin validation.
  2. Server-side session authentication tokens required for all state-mutating and tool execution endpoints.
  3. Pre-flight checks on high-risk operations.

---

## 2. UNTRUSTED DATA BOUNDARIES & PROMPT INJECTION DEFENSE

### 2.1 Untrusted Content Sources
The following inputs are classified as **strictly untrusted data**:
- User-provided prompts and conversational text.
- Uploaded files (PDFs, Word documents, spreadsheets, text files).
- Git repository contents, commit messages, issue descriptions, and pull requests.
- Web search snippets, retrieved RAG chunks, and scraped web pages.

### 2.2 Security Invariant
> **No instruction contained within untrusted data may grant, modify, or elevate execution authority or alter the model's safety policy.**

### 2.3 Delimiter Scaffolding & Escaping
All untrusted data injected into LLM prompt contexts is sanitized and enclosed in structured XML boundary tags:
```xml
<attached_documents trusted="false">
--- ATTACHED FILE: spec.md [MIME: text/markdown] ---
[Quoted file data here]
--- END FILE ---
</attached_documents>

<user_message trusted="false">
[Quoted user message here]
</user_message>
```
System instructions mandate that the model treat all enclosed content as passive data to be analyzed, never as operational directives.

---

## 3. SECRET PROTECTION & SENSITIVE DATA REDACTION

### 3.1 Prohibited Ingestion Targets
The file ingestion and repository indexing pipelines explicitly blacklist and refuse to inject:
- `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`
- `secrets.yaml`, `credentials.json`, `auth.json`
- Service account private keys and cloud token stores

### 3.2 Automated Secret Scanning
Prior to indexing or passing code into prompt context:
- Regular expression pattern matching checks for AWS keys (`AKIA[0-9A-Z]{16}`), GitHub tokens (`ghp_[0-9a-zA-Z]{36}`), OpenAI keys (`sk-[0-9a-zA-Z]{48}`), and general high-entropy tokens.
- Detected secrets are redacted with `[REDACTED_API_KEY]` before context compilation, and a warning is logged to the security audit ledger.

---

## 4. SANDBOX EXECUTION & NETWORK ISOLATION

### 4.1 Process Sandboxing (`sandbox/process_adapter.py`)
- Child processes execute under dedicated non-elevated user accounts.
- Hard resource limits enforced:
  - Max execution time: 60 seconds (configurable per tool).
  - Max buffer size: 5 MB stdout/stderr.
  - Process tree termination: SIGKILL dispatched to process groups upon timeout.

### 4.2 Future Container Isolation (`sandbox/docker_adapter.py`)
- Ephemeral rootless Docker containers per job.
- Read-only root filesystem with scoped tmpfs for scratch operations.
- Network isolation: `--network none` by default; temporary egress enabled only during dependency installation (`npm install`, `pip install`) with whitelisted package registry domains.
