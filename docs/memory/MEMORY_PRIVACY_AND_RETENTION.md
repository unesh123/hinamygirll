# HINAA OS — Phase 10 Memory Privacy & Retention Policy

## 1. Multi-Tenant Isolation
- **Tenant Enforcement**: Every memory record, knowledge node, edge, and ingestion candidate is tagged with an immutable `tenant_id`.
- **Query Scoping**: Database queries and REST endpoints explicitly enforce `tenant_id = ?` matching. Cross-tenant queries are rejected with an authorization error (`PermissionError` / HTTP 403).
- **Default Tenant**: When not specified in request headers (`X-Tenant-ID`), requests default safely to `default`.

---

## 2. Secret Canary & Credential Scrubbing
To prevent inadvertent persistence of sensitive user or developer credentials, `MemoryPrivacyGuard.scrub_secrets()` automatically scans all stored text:
- **Provider API Keys**: `sk-...` (OpenAI, Anthropic) -> `[REDACTED_SECRET]`
- **GitHub Tokens**: `ghp_...`, `gho_...` -> `[REDACTED_SECRET]`
- **Bearer Tokens**: `Bearer <token>` -> `[REDACTED_SECRET]`
- **Private Keys**: RSA / SSH private key PEM blocks -> `[REDACTED_SECRET]`
- **Passwords**: Key-value password assignments -> `[REDACTED_SECRET]`

---

## 3. Prompt Injection Neutralization
To prevent malicious external text (from web pages or untrusted user inputs) from hijacking future system prompts through memory recall:
- **Jailbreak Sequences**: Phrases like `"Ignore all previous instructions"` are replaced with `[DEFANGED_INJECTION: IGNORE_INSTRUCTIONS]`.
- **System Tags**: Enclosing tags like `<system>` and `</system>` are converted to `[DEFANGED_TAG]`.
- **Role Overrides**: Delimiters like `\nSystem:` or `\nAssistant:` are converted to `[DEFANGED_ROLE]`.

---

## 4. Retention & Deletion Cascades
- **Right to Erasure (GDPR / Right to be Forgotten)**: Calling `DELETE /api/memory/items/{id}` triggers an immediate hard delete from `memories`, removes full-text indices in `memory_fts`, and cascades to all derived `knowledge_edges` referencing that memory as evidence.
- **TTL Expiration**: Records with an explicit `expires_at` timestamp are automatically deactivated during scheduled sweeps (`run_ttl_purge()`).
- **Data Portability**: Users can export their memories in structured JSON or tabular CSV formats at any time (`POST /api/memory/export`).
