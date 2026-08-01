# 30 — Phase 5 memory architecture

## Implemented offline

- SQLAlchemy 2 ORM models: users, conversations, messages, conversation_summaries, explicit_memories, memory_consents, audit_events
- `MemoryService` consent-controlled CRUD
- Dev auth via `X-HINAA-Dev-User` when `HINAA_AUTH_MODE=dev`
- OIDC mode scaffold (rejects real JWTs until issuer + validator configured)
- Privacy HTTP API under `/v1/privacy/*`
- Default DB: SQLite in-memory for tests; configurable `HINAA_DATABASE_URL` for PostgreSQL
- Alembic listed as dependency; schema bootstrap via `Base.metadata.create_all` for offline/dev
- pgvector: **deferred** (not required for basic memory)

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/privacy/status` | Memory toggle + retention explanation |
| PATCH | `/v1/privacy/memory` | Enable/disable memory |
| GET/POST | `/v1/privacy/memories` | List / remember |
| DELETE | `/v1/privacy/memories/{id}` | Forget |
| DELETE | `/v1/privacy/conversations/{id}` | Clear conversation |
| GET | `/v1/privacy/export` | Export JSON |
| DELETE | `/v1/privacy/account` | Delete-all |

## Guarantees

- Sensitive credential-like content blocked
- Cross-user forget fails closed
- Deleted memories excluded from list/retrieval
- Memory never becomes system policy text without delimiting (approved blocks are application-tagged)
- Raw audio not stored

## Not complete for production

- Full OIDC JWT validation
- PostgreSQL RLS policies in-database
- Managed DB restore drill
- Privacy dashboard UI polish (API exists; frontend panel may be minimal)
- Automatic prompt injection of approved memories into every live turn (service helper exists: `approved_memory_blocks`)
