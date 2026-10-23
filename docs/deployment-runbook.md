# Production Deployment & Operational Runbook

## 1. Production Topology & Intended Architecture

The production architecture decouples edge static asset serving from containerized backend compute:
- **Frontend Distribution**: Vercel Edge Network (`apps/web`). Serves Vite SPA assets with HTTP rewrites routing `/api/*`, `/v1/*`, and health probes directly to the backend.
- **Backend Service**: Render Web Service (`apps/api`) running containerized FastAPI on Docker (`render.yaml`).
  - Configured Service Name: `hinaa-api`
  - Upstream Production Destination: `https://hinaa-api.onrender.com`
- **Database**: Managed PostgreSQL (Supabase, Neon, or Render PostgreSQL).
- **Authentication**: Clerk OAuth / JWT authentication.

> [!WARNING]
> **Configuration vs. Live Provisioning Notice**: Setting `https://hinaa-api.onrender.com` in `vercel.json` and `render.yaml` establishes the intended upstream target. It does **not** imply that the external service is provisioned, funded, or running. Live cloud deployment remains `NOT_EXECUTED`.

---

## 2. Environment Configuration & Minimum Required Credentials

To transition from local/mock verification to a live production deployment, the following exact credentials must be provisioned in the hosting environments:

### Smallest Exact List of Required Credentials
1. **`GEMINI_API_KEY`**: Google AI Studio / Vertex AI API key enabling live `gemini-2.5-flash` model inference.
2. **`CLERK_SECRET_KEY`** (Backend) & **`VITE_CLERK_PUBLISHABLE_KEY`** (Frontend): Enables live JWT token authentication and user identity management.
3. **`HINAA_DATABASE_URL`**: PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/hinaa_prod`) for durable multi-tenant persistence.

*Optional Advanced Extensions*: `ANTHROPIC_API_KEY` (Claude), `GROQ_API_KEY` (Llama 3.3), `ELEVENLABS_API_KEY` (Voice).

---

## 3. Database Migrations & Specific Recovery Runbook

### 3.1 Migration Architecture
Schema migrations are tracked internally via the `schema_migrations` table (`apps/api/hinaa_api/persistence/migrations.py`):
- `0001`: `initial_schema` (users, conversations, messages, explicit_memories, session_states)
- `0002`: `explicit_memories_expires_at`
- `0003`: `agent_runtime_tables` (agent_runs, agent_steps, agent_plans)
- `0004`: `message_attachments_and_provider_usage`
- `0005`: `conversation_intelligence_tables` (summaries, dialogue_states)
- `0006`: `training_candidate_table`
- `0007`: `durable_task_tables` (durable_tasks, steps, checkpoints, outbox)
- `0008`: `user_continuity_state`
- `0009`: `conversation_turn_states`
- `0010`: `conversation_turn_state_active_goal`
- `0011`: `task_runtime_hardening`
- `0012`: `selected_asset_state`
- `0013`: `conversation_episodes`
- `0014`: `reminders`

### 3.2 Specific Rollback & Data Loss Assessment
- **Stateless Application Rollback**: Reverting frontend bundles on Vercel or container images on Render is **safe and instantaneous**, incurring zero data loss.
- **Database Downgrade Risks**:
  - Reversing migrations (e.g. dropping tables in `0004`, `0007`, or `0014`) will **permanently destroy** stored attachments, durable task execution logs, and scheduled user reminders.
  - A generic database downgrade must **NEVER** be treated as a routine fix.
- **When a Forward Fix is Safer**:
  - If a bug involves column types or query logic on additive columns (e.g., `active_goal` in `0010` or `expires_at` in `0002`), an additive forward migration (`ALTER TABLE ...` or updating the ORM mapping) is far safer than rolling back the schema.
- **Backup Prerequisites**:
  - Before applying any schema upgrade, execute a point-in-time snapshot:
    ```bash
    pg_dump -Fc --no-acl --no-owner -h $DB_HOST -U $DB_USER $DB_NAME > backup_pre_migration.dump
    ```
- **Restore Verification Procedure**:
  - Restore backup to a staging database:
    ```bash
    pg_restore --clean --if-exists -d $STAGING_DB_URL backup_pre_migration.dump
    ```
  - Verify record counts on critical tables (`SELECT count(*) FROM conversations;`, `SELECT count(*) FROM messages;`).

---

## 4. Operational Health & Readiness Probes

The backend container exposes standardized health probes for orchestration platforms:
- **`GET /health`**: General application liveness. Returns `{ "status": "ok", "timestamp": "..." }`.
- **`GET /healthz`**: Infrastructure container liveness.
- **`GET /readyz`**: Dependency readiness (verifies PostgreSQL connection and configuration health).

---

## 5. Deployment Verification Status

| Component | Target Platform | Local Code Verification | Cloud Deployment Status |
| :--- | :--- | :--- | :--- |
| **Frontend Web App** | Vercel Edge Network | Clean production build (`tsc -b && vite build`) | `NOT_EXECUTED` (Awaiting user authorization) |
| **Backend API Service** | Render Web Service | 1,803 unit & lifecycle tests passing | `NOT_EXECUTED` (Awaiting live credentials & authorization) |
| **Database Schema** | PostgreSQL | Migrations 0001-0014 verified via test engine | `NOT_EXECUTED` |
