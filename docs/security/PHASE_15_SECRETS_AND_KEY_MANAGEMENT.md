# HINAA OS — Phase 15 Secrets & Key Management Architecture
**Document Version:** 1.0  
**Date:** 2026-11-06  
**Auditor:** Anti-Gravity Principal Engineering Verification Agent  
**Standard:** NIST SP 800-57, NIST SP 800-63B  

---

## 1. Keystore Platform Reality & Honest Probing

HINAA OS strictly avoids security theater and false claims. While earlier prototypes reported "HARDWARE_TPM_AVAILABLE", Phase 15 introduces real-time platform probing:

```python
# Live probe result measured on Windows host
KeystoreProbeResult(
    keystore_type=KeystoreType.SOFTWARE_DPAPI,
    is_hardware_backed=False,
    provider_name="Windows DPAPI (CryptProtectData / crypt32.dll)",
    capabilities=["os_user_bound_encryption", "dpapi_data_protection", "memory_isolated", "log_scrubbing"],
    status_details="Windows DPAPI OS-level user-bound credential protection active. "
                   "Honest posture: is_hardware_backed=False (software DPAPI master key, not TPM non-exportable)."
)
```

### Why `is_hardware_backed = False`?
- On personal Windows workstations, Data Protection API (DPAPI) encrypts credentials using keys tied to the logged-in Windows user account.
- While DPAPI protects against offline disk theft and unprivileged processes, it does not guarantee hardware non-exportability unless a TPM 2.0 CNG Key Storage Provider with an export-restricted certificate is physically enrolled.
- **Honest Posture:** HINAA OS explicitly labels the keystore as `SOFTWARE_DPAPI` with `is_hardware_backed: false`.

---

## 2. Universal Zero-Leak Secret Scrubber

Credentials must NEVER leak into LLM prompts, agent traces, error messages, WebSocket events, or audit logs.

### Monitored Patterns:
1. **Bearer Tokens:** `Bearer [REDACTED_BEARER_TOKEN]` (`Bearer [A-Za-z0-9_\-\.]{24,}`)
2. **JSON Web Tokens:** `[REDACTED_JWT_TOKEN]` (`eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}`)
3. **OpenAI / Model API Keys:** `[REDACTED_API_KEY_SK]` (`sk-[A-Za-z0-9_-]{20,}`)
4. **ElevenLabs Keys:** `[REDACTED_ELEVENLABS_KEY]` (`xi-[a-zA-Z0-9]{20,}`)
5. **GitHub Tokens:** `[REDACTED_GITHUB_TOKEN]` (`gh[pousr]_[A-Za-z0-9_]{30,}`)
6. **Payment Credentials:** `[REDACTED_PAYMENT_SECRET]` (`(?:live|test)_secret_key_[a-f0-9]{24,}`)
7. **PEM Private Keys:** `[REDACTED_PRIVATE_KEY]` (`-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----`)

All registered system secrets (from `.env.local` and runtime keystore) are injected dynamically into the scrubber dictionary and redacted from any outgoing string.

---

## 3. Cryptographic Key Lifecycle & Rotation

| Key Name | Algorithm | Usage | Rotation Strategy |
|---|---|---|---|
| `audit_chain_key` | HMAC-SHA256 | Signs hash-chained audit events | Key ID indexing (`kid`); re-signing on rotation |
| `approval_ceremony_key` | HMAC-SHA256 | Parameter-bound single-use challenge tokens | Short TTL (300s); instant invalidation on rotate |
| `identity_signing_key` | HMAC-SHA256 | Session JWT generation & verification | Daily rotation; active sessions expire in 3600s |

### Rotation Playbook:
1. `OWNER` invokes `POST /api/security/revocations` or triggers key rotation via `KeystoreManager.rotate_signing_key(key_id)`.
2. A new cryptographically secure 256-bit key (`secrets.token_bytes(32)`) is generated.
3. Existing active tokens continue until expiration; new tokens strictly require the new key.
