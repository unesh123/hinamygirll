# Memory and database

## Purpose

Define consent-aware memory and a migration-oriented relational schema without cross-user leakage.

## Decision

Memory layers are current turn, ephemeral session, conversation summary, profile/preferences, explicit long-term memory, semantic retrieval, and permission state. Only an explicit “remember this” action or acceptance of a displayed candidate creates long-term memory. Sensitive categories (health, sexuality, religion, politics, finance, credentials, biometrics, precise location) default to blocked; a future policy may allow narrowly explicit storage after separate warning.

Candidate extraction returns untrusted proposals. Normalize whitespace/case for duplicate hash, then compare semantic similarity only within the same user. Exact duplicate updates `last_confirmed_at`; contradiction creates a pending replace/keep-both decision; it never silently overwrites. Retrieval filters `owner_user_id`, status, sensitivity, expiry and private-session flag before vector search. “Forget” soft-deletes immediately from retrieval and queues hard deletion of content/embedding/backups according to retention policy.

### Migration-oriented tables

All IDs are UUIDv7 (UUID if DB support is unavailable), timestamps are `timestamptz`, mutable rows include `created_at,updated_at`, and JSONB has schema validation at the application boundary.

| Table | Core columns / foreign keys | Indexes and controls |
|---|---|---|
| `users` | id PK, auth_subject UNIQUE, status, deleted_at | unique subject; RLS self/admin |
| `user_profiles` | user_id PK/FK, display_name, locale, response_length, timezone | RLS by user |
| `companions` | id PK, slug UNIQUE, presentation, active | public readable; admin write |
| `companion_personality_settings` | id PK, user_id FK, companion_id FK, 8 bounded settings | UNIQUE(user,companion), RLS user |
| `conversations` | id PK, user_id FK, companion_id FK, privacy_mode, title, ended_at | (user,updated_at DESC), RLS user |
| `messages` | id PK, conversation_id FK, turn_id, role, content, language, provider_ref, deleted_at | (conversation,created_at), UNIQUE(conversation,turn_id,role); content encrypted field-level if required |
| `conversation_summaries` | id PK, conversation_id FK, through_message_id FK, summary, version | (conversation,created_at DESC), RLS via conversation |
| `memories` | id PK, user_id FK, content, normalized_hash, status, sensitivity, source_message_id FK nullable, expires_at, confirmed_at, deleted_at | partial UNIQUE(user,normalized_hash) active; RLS user |
| `memory_embeddings` | memory_id PK/FK, model_config_id, embedding vector, created_at | HNSW/IVFFlat after benchmark; RLS via memory |
| `provider_connections` | id PK, user_id nullable FK, provider, ownership, status, config JSONB | UNIQUE(owner/provider/name), never secret values |
| `encrypted_credentials` | id PK, connection_id FK, ciphertext, nonce, wrapped_dek, kms_key_id, masked_suffix, revoked_at | backend-only role; no general API SELECT |
| `provider_health` | id PK, provider, capability, region, state, latency_ms, observed_at | (provider,capability,region,observed_at DESC); operational role |
| `consent_events` | id PK, user_id FK, purpose, action, policy_version, evidence JSONB | append-only, (user,created_at) |
| `tool_permissions` | id PK, user_id FK, tool, scope, expires_at, revoked_at | UNIQUE active scope; future-only |
| `tool_approval_requests` | id PK, user_id FK, conversation_id FK, preview, status, idempotency_key | UNIQUE(user,idempotency_key); future-only |
| `audit_logs` | id PK, actor_user_id nullable FK, action, resource_type/id, result, metadata_redacted, trace_id | append-only monthly partition; (actor,created_at) |
| `usage_ledger` | id PK, user_id nullable FK, provider, model_id, capability, units JSONB, estimated_cost_minor, currency, request_id | UNIQUE(provider,request_id); partition monthly |
| `subscription_plans` | id PK, code UNIQUE, limits JSONB, active | post-MVP admin-only |
| `subscriptions` | id PK, user_id FK, plan_id FK, status, period bounds | one active/user; post-MVP |
| `character_assets` | id PK, companion_id FK, object_key, sha256, vrm_version, license_status, size_bytes | UNIQUE sha256; only `approved` servable |
| `animation_assets` | id PK, cue_key, object_key, sha256, license_status, duration_ms | UNIQUE(cue_key,version); approved only |
| `emotion_events` | id PK, conversation_id FK, turn_id, emotion, intensity, source, created_at | (conversation,created_at); no inferred user diagnosis |
| `evaluation_sessions` | id PK, protocol_version, provider_config JSONB, device, started_at | research role; pseudonymous |
| `evaluation_results` | id PK, session_id FK, item_id, metric, value, metadata | (session,item_id,metric) |

Use FK `ON DELETE CASCADE` for private child data except append-only consent/audit/usage, which replace user references with a tombstone/pseudonym during deletion. Migrations are forward-only, transactional where PostgreSQL allows, and include backfill/rollback notes.

### Retention

Private-session content: memory only, deleted on session close. Raw microphone audio: never persisted by default. Partial transcripts/events: <=24 h diagnostics only when opt-in, otherwise memory-only. Conversations/messages: until user deletion; default inactivity review at 12 months. Deleted user content: purge active systems <=30 days; encrypted backups age out <=35 days. Audit/consent: 12 months for pilot, then anonymize/delete; usage ledger: 24 months or legal/accounting requirement. Evaluation consent governs research data separately.

### ERD

Canonical source: [database-erd.mmd](diagrams/database-erd.mmd). Every application query sets authenticated user context and PostgreSQL RLS; service/admin bypass roles are separate and audited. Tests attempt cross-user ID swapping on every private table.

## Alternatives considered

MongoDB simplifies flexible records but weakens relational consent/audit constraints. SQLite is accepted only for deterministic mock tests, not provider-integrated demo persistence. Separate vector DB is unnecessary at MVP scale.

## Reasoning

PostgreSQL supplies transactions, RLS and vector search in one operational unit.

## Risks

Embedding inversion, backup deletion delay, RLS misconfiguration and summary hallucination. Store minimal text, encrypt sensitive fields, test RLS with two users, label summaries as generated, and support source inspection.

## Acceptance criteria

- Zero long-term writes without consent event.
- Cross-user retrieval tests fail closed.
- Delete-all removes active content/vectors and records a non-content audit tombstone.
- Restore drill proves encrypted backup recovery and documented deletion limits.

