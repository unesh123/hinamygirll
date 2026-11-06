# HINAA OS — Phase 17 Route Audit & API Surface Diff

**Phase:** Phase 17 — Production Hardening, Edge Distribution & High Availability  
**Starting Route Count:** 572 routes (Phase 16 baseline)  
**New Endpoints Mounted:** 16 endpoints (4 Probes, 12 Platform Management)  
**Total Endpoint Count:** 588 routes  
**Status:** ALL MOUNTED & VERIFIED  

---

## 1. Probes & Health Checks (`health_router`)

| Route | Method | Access Level | Description |
|---|---|---|---|
| `/health/live` | `GET` | Public / Low Overhead | Fast liveness probe (<5ms). Validates process is alive and responding. |
| `/health/ready` | `GET` | Public | Readiness probe. Validates SQLite WAL, queue, and returns 503 during degraded mode. |
| `/health/startup` | `GET` | Public | Startup probe. Returns 503 STARTING during bootstrapping and 200 HEALTHY once initialized. |
| `/health/dependencies` | `GET` | Authenticated (Operator/Admin) | Deep dependency diagnostic (SQLite, Redis, GPU VRAM, queue). Denies unauthenticated calls with 401/403. |

---

## 2. Platform Management & Edge Sync (`platform_router`)

### Deployment Profile & Telemetry
| Route | Method | Access Level | Description |
|---|---|---|---|
| `/api/platform/profile` | `GET` | Public / Client | Returns active deployment profile, honest verification status, and backend type. |
| `/api/platform/slo` | `GET` | Operator / Client | Computes p50/p95/p99 latency quantiles, audible TTFA sink time, and paisa cost accounting. |

### Durable Queue & DLQ Operations
| Route | Method | Access Level | Description |
|---|---|---|---|
| `/api/platform/queue/status` | `GET` | Operator / Client | Backlog depth, pending count, and backend status (SQLite vs Redis Streams). |
| `/api/platform/queue/dlq` | `GET` | Operator | Inspects dead-lettered entries with preserved root cause error messages. |
| `/api/platform/queue/replay` | `POST` | Operator | Requeues a dead-lettered message for re-execution with a fresh message ID. |

### Hot Backups & Restores
| Route | Method | Access Level | Description |
|---|---|---|---|
| `/api/platform/backup/create` | `POST` | Operator / Admin | Triggers non-locking online `sqlite3.backup` with pre-WAL checkpoint and SHA-256 verification. |
| `/api/platform/backup/restore` | `POST` | Operator / Admin | Performs deterministic restore rehearsal measuring RTO (<5s) and RPO (<60s). |

### Edge Sync & Device Pairing
| Route | Method | Access Level | Description |
|---|---|---|---|
| `/api/platform/sync/devices` | `GET` | Authenticated | Lists paired edge devices with public key fingerprints and sync watermarks. |
| `/api/platform/sync/pair` | `POST` | Authenticated | Pairs a new edge device (e.g. mobile phone/tablet) with cryptographic validation. |
| `/api/platform/sync/revoke` | `POST` | Admin / Operator | Instant revocation kill-switch. Blocks subsequent sync requests from the device. |
| `/api/platform/sync/conflicts` | `GET` | Operator / User | Lists unreviewed sync conflicts between local and remote devices. |
| `/api/platform/sync/resolve` | `POST` | Operator / User | Resolves conflict via `LOCAL_WINS`, `REMOTE_WINS`, or `MANUAL_MERGE`. |

---

## 3. Preserved Capabilities
All existing routes from Phases 01–16 remain intact:
- Goal planner routes (`/api/goals/*`)
- Security & PDP routes (`/api/security/*`)
- Continuous evaluation routes (`/api/evals/*`)
- Reflective speech & explanation routes (`/api/explanation/*`)
- Realtime WebSocket routes (`/ws`)
