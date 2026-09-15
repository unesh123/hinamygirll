# HINAA Release Environments Specification

**Version**: RC1 Release Candidate  
**Date**: September 15, 2026  
**Status**: Canonical Environment Standard  

---

## 1. Environment Matrix Overview

| Attribute | LOCAL | TEST | PREVIEW | PRODUCTION |
|---|---|---|---|---|
| **Primary Goal** | Fast developer inner loop & desktop hardware binding | Deterministic regression & CI test execution | Stakeholder & browser verification over real network | Highly-available, multi-user, fault-tolerant operation |
| **Hosting Target** | Developer Workstation (Windows/macOS/Linux) | GitHub Actions / Local Runner | Public Preview Host / Secure Tunnel / Staging Container | Cloud Run / Kubernetes / AWS ECS |
| **API Endpoint** | `http://127.0.0.1:8000` | Ephemeral localhost port | `https://preview.hinaa.app` (or tunnel) | `https://api.hinaa.app` |
| **Web Endpoint** | `http://localhost:5173` | Headless Playwright runner | `https://preview-app.hinaa.app` | `https://app.hinaa.app` |
| **Database Engine** | SQLite (`hinaa.db`) | In-Memory SQLite (`:memory:`) | Managed PostgreSQL or Volume SQLite | Managed Cloud SQL PostgreSQL (PgBouncer) |
| **Object / Media Storage**| Local disk (`~/.hinaa/workspace/`) | Temp test fixtures | S3 / GCS bucket or persistent PVC | Durable Cloud Storage (GCS / AWS S3) |
| **Auth Mode** | `dev` (automatic user context) | `dev` / synthetic mock tokens | `clerk` (staging) or token-based | `clerk` (production tenant isolation) |
| **Desktop Bridges** | Direct loopback (:8188, :11434, UDP 39539) | Mocked / bypassed | `LOCAL_ONLY` (Desktop Bridge required) | `LOCAL_ONLY` (Remote server never probes) |
| **Streaming / SSE** | Direct HTTP connection | Buffered fixture streams | Proxy buffering disabled (`X-Accel-Buffering: no`) | Edge-optimized CDN with SSE keepalive (15s) |

---

## 2. Detailed Configuration Profiles

### A. LOCAL Environment (`LOCAL`)
- **Use Case**: Developing features, editing VRM shaders, running local LLMs, testing VSeeFace face tracking.
- **Environment Variables**:
  ```bash
  ENVIRONMENT=development
  HINAA_PROVIDER_MODE=claude # or mock, local, openai
  HINAA_AUTH_MODE=dev
  HINAA_DATABASE_URL=sqlite+pysqlite:///$HOME/.hinaa/workspace/hinaa.db
  HINAA_PERSISTENCE_ENABLED=true
  HINAA_ALLOWED_ORIGINS=["http://localhost:5173","http://127.0.0.1:5173"]
  ```
- **Desktop Bridges**:
  - ComfyUI: Direct loopback `http://127.0.0.1:8188`
  - Ollama: Direct loopback `http://127.0.0.1:11434`
  - VSeeFace: Direct UDP port `39539`

### B. TEST Environment (`TEST`)
- **Use Case**: Automated testing (`pytest`, `vitest`, `playwright`), CI pipelines.
- **Environment Variables**:
  ```bash
  ENVIRONMENT=test
  HINAA_PROVIDER_MODE=mock
  HINAA_AUTH_MODE=dev
  HINAA_DATABASE_URL=sqlite+pysqlite:///:memory:
  HINAA_PERSISTENCE_ENABLED=true
  HINAA_AGENT_RUNTIME_ENABLED=true
  ```
- **Guarantees**:
  - Zero external HTTP requests made during standard unit suites.
  - Test isolation: each test suite runs with freshly initialized migrations and tables.

### C. PREVIEW Environment (`PREVIEW`)
- **Use Case**: Cross-device browser acceptance, mobile testing (Pixel 5, iPhone 14), team dogfooding, network streaming stress tests.
- **Environment Variables**:
  ```bash
  ENVIRONMENT=preview
  HINAA_PROVIDER_MODE=claude # or agent-router, cx-gateway
  HINAA_AUTH_MODE=clerk # or token
  HINAA_DATABASE_URL=postgresql+psycopg://preview_user:secret@postgres-host:5432/hinaa_preview
  HINAA_PERSISTENCE_ENABLED=true
  HINAA_ALLOWED_ORIGINS=["https://preview.hinaa.app","https://*.ngrok-free.app"]
  ```
- **Crucial Infrastructure Rules**:
  - **Reverse Proxy**: Must pass `X-Accel-Buffering: no` and disable response buffering for `/api/v1/conversations/turns:stream` and `/api/v1/agent/events`.
  - **Desktop Bridge Handling**: Settings UI flags ComfyUI, Ollama, and VMC as `DESKTOP_BRIDGE (LOCAL_ONLY)`. The preview backend server **never** attempts to connect to `127.0.0.1` for user desktop services.

### D. PRODUCTION Environment (`PRODUCTION`)
- **Use Case**: Live end-user traffic, durable cross-session memory, enterprise task execution.
- **Environment Variables**:
  ```bash
  ENVIRONMENT=production
  HINAA_PROVIDER_MODE=claude # or agent-router, cx-gateway
  HINAA_AUTH_MODE=clerk
  HINAA_DATABASE_URL=postgresql+psycopg://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:5432/${DB_NAME}?sslmode=require
  HINAA_PERSISTENCE_ENABLED=true
  HINAA_STORAGE_BACKEND=gcs # or s3
  HINAA_ALLOWED_ORIGINS=["https://app.hinaa.app"]
  ```
- **Reliability & Telemetry**:
  - Uvicorn multi-worker process manager (`--workers 4`).
  - Liveness probe: `GET /health/live` (fast 200 process check).
  - Readiness probe: `GET /health/ready` (verifies DB migration version and provider readiness).
  - Metrics & Logging: Structured JSON logs with correlation IDs (`X-Correlation-ID`).
